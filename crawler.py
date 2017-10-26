import config
import logging
from urllib.parse import urljoin, urlunparse

import re
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.robotparser import RobotFileParser
from datetime import datetime

import mimetypes
import os

class Crawler():

	# Variables
	parserobots = False
	output 	= None
	report 	= False

	config 	= None
	domain	= ""

	exclude = []
	skipext = []
	drop    = []

	debug	= False

	tocrawl = set([])
	crawled = set([])
	excluded = set([])

	marked = {}

	not_parseable_ressources = (".epub", ".mobi", ".docx", ".doc", ".opf", ".7z", ".ibooks", ".cbr", ".avi", ".mkv", ".mp4", ".jpg", ".jpeg", ".png", ".gif" ,".pdf", ".iso", ".rar", ".tar", ".tgz", ".zip", ".dmg", ".exe")

	# TODO also search for window.location={.*?}
	linkregex = re.compile(b'<a [^>]*href=[\'|"](.*?)[\'"][^>]*?>')
	imageregex = re.compile (b'<img [^>]*src=[\'|"](.*?)[\'"].*?>')

	rp = None
	response_code={}
	nb_url=1 # Number of url.
	nb_rp=0 # Number of url blocked by the robots.txt
	nb_exclude=0 # Number of url excluded by extension or word

	output_file = None

	target_domain = ""
	scheme		  = ""

	def __init__(self, parserobots=False, output=None, report=False ,domain="",
				 exclude=[], skipext=[], drop=[], debug=False, verbose=False, images=False):
		self.parserobots = parserobots
		self.output 	= output
		self.report 	= report
		self.domain 	= domain
		self.exclude 	= exclude
		self.skipext 	= skipext
		self.drop		= drop
		self.debug		= debug
		self.verbose    = verbose
		self.images     = images

		if self.debug:
			log_level = logging.DEBUG
		elif self.verbose:
			log_level = logging.INFO
		else:
			log_level = logging.ERROR

		logging.basicConfig(level=log_level)

		self.tocrawl = set([self.clean_link(domain)])

		try:
			url_parsed = urlparse(domain)
			self.target_domain = url_parsed.netloc
			self.scheme = url_parsed.scheme
		except:
			logging.error("Invalide domain")
			raise ("Invalid domain")

		if self.output:
			try:
				self.output_file = open(self.output, 'w')
			except:
				logging.error ("Output file not available.")
				exit(255)

	def run(self):
		print(config.xml_header, file=self.output_file)

		if self.parserobots:
			self.check_robots()

		logging.info("Start the crawling process")

		while len(self.tocrawl) != 0:
			self.__crawling()

		logging.info("Crawling has reached end of all found links")

		print (config.xml_footer, file=self.output_file)


	def __crawling(self):
		crawling = self.tocrawl.pop()

		url = urlparse(crawling)
		self.crawled.add(crawling)
		logging.info("Crawling #{}: {}".format(len(self.crawled), url.geturl()))
		request = Request(crawling, headers={"User-Agent":config.crawler_user_agent})

		# Ignore ressources listed in the not_parseable_ressources
		# Its avoid dowloading file like pdf… etc
		if not url.path.endswith(self.not_parseable_ressources):
			try:
				response = urlopen(request)
			except Exception as e:
				if hasattr(e,'code'):
					if e.code in self.response_code:
						self.response_code[e.code]+=1
					else:
						self.response_code[e.code]=1

					# Gestion des urls marked pour le reporting
					if self.report:
						if e.code in self.marked:
							self.marked[e.code].append(crawling)
						else:
							self.marked[e.code] = [crawling]

				logging.debug ("{1} ==> {0}".format(e, crawling))
				return self.__continue_crawling()
		else:
			logging.debug("Ignore {0} content might be not parseable.".format(crawling))
			response = None

		# Read the response
		if response is not None:
			try:
				msg = response.read()
				if response.getcode() in self.response_code:
					self.response_code[response.getcode()]+=1
				else:
					self.response_code[response.getcode()]=1

				response.close()

				# Get the last modify date
				if 'last-modified' in response.headers:
					date = response.headers['Last-Modified']
				else:
					date = response.headers['Date']

				date = datetime.strptime(date, '%a, %d %b %Y %H:%M:%S %Z')

			except Exception as e:
				logging.debug ("{1} ===> {0}".format(e, crawling))
				return None
		else:
			# Response is None, content not downloaded, just continu and add
			# the link to the sitemap
			msg = "".encode( )
			date = None

		# Image sitemap enabled ?
		image_list = "";
		if self.images:
			# Search for images in the current page.
			images = self.imageregex.findall(msg)
			for image_link in list(set(images)):
				image_link = image_link.decode("utf-8", errors="ignore")

				# Ignore link starting with data:
				if image_link.startswith("data:"):
					continue

				# If path start with // get the current url scheme
				if image_link.startswith("//"):
					image_link = url.scheme + ":" + image_link
				# Append domain if not present
				elif not image_link.startswith(("http", "https")):
					if not image_link.startswith("/"):
						image_link = "/{0}".format(image_link)
					image_link = "{0}{1}".format(self.domain.strip("/"), image_link.replace("./", "/"))

				# Ignore image if path is in the exclude_url list
				if not self.exclude_url(image_link):
					continue

				# Ignore other domain images
				image_link_parsed = urlparse(image_link)
				if image_link_parsed.netloc != self.target_domain:
					continue


				# Test if images as been already seen and not present in the
				# robot file
				if self.can_fetch(image_link):
					logging.debug("Found image : {0}".format(image_link))
					image_list = "{0}<image:image><image:loc>{1}</image:loc></image:image>".format(image_list, self.htmlspecialchars(image_link))

		# Last mod fetched ?
		lastmod = ""
		if date:
			lastmod = "<lastmod>"+date.strftime('%Y-%m-%dT%H:%M:%S+00:00')+"</lastmod>"

		print ("<url><loc>"+self.htmlspecialchars(url.geturl())+"</loc>" + lastmod + image_list + "</url>", file=self.output_file)
		if self.output_file:
			self.output_file.flush()

		# Found links
		links = self.linkregex.findall(msg)
		for link in links:
			link = link.decode("utf-8", errors="ignore")
			link = self.clean_link(link)
			logging.debug("Found : {0}".format(link))

			if link.startswith('/'):
				link = url.scheme + '://' + url[1] + link
			elif link.startswith('#'):
				link = url.scheme + '://' + url[1] + url[2] + link
			elif link.startswith(("mailto", "tel")):
				continue
			elif not link.startswith(('http', "https")):
				link = url.scheme + '://' + url[1] + '/' + link

			# Remove the anchor part if needed
			if "#" in link:
				link = link[:link.index('#')]

			# Drop attributes if needed
			for toDrop in self.drop:
				link=re.sub(toDrop,'',link)

			# Parse the url to get domain and file extension
			parsed_link = urlparse(link)
			domain_link = parsed_link.netloc
			target_extension = os.path.splitext(parsed_link.path)[1][1:]

			if link in self.crawled:
				continue
			if link in self.tocrawl:
				continue
			if link in self.excluded:
				continue
			if domain_link != self.target_domain:
				continue
			if parsed_link.path in ["", "/"]:
				continue
			if "javascript" in link:
				continue
			if self.is_image(parsed_link.path):
				continue
			if parsed_link.path.startswith("data:"):
				continue

			# Count one more URL
			self.nb_url+=1

			# Check if the navigation is allowed by the robots.txt
			if not self.can_fetch(link):
				self.exclude_link(link)
				self.nb_rp+=1
				continue

			# Check if the current file extension is allowed or not.
			if (target_extension in self.skipext):
				self.exclude_link(link)
				self.nb_exclude+=1
				continue

			# Check if the current url doesn't contain an excluded word
			if (not self.exclude_url(link)):
				self.exclude_link(link)
				self.nb_exclude+=1
				continue

			self.tocrawl.add(link)

		return None

	def clean_link(self, link):
		l = urlparse(link)
		l_res = list(l)
		l_res[2] = l_res[2].replace("./", "/")
		l_res[2] = l_res[2].replace("//", "/")
		return urlunparse(l_res)

	def is_image(self, path):
		 mt,me = mimetypes.guess_type(path)
		 return mt is not None and mt.startswith("image/")

	def __continue_crawling(self):
		if self.tocrawl:
			self.__crawling()

	def exclude_link(self,link):
		if link not in self.excluded:
			self.excluded.add(link)

	def check_robots(self):
		robots_url = urljoin(self.domain, "robots.txt")
		self.rp = RobotFileParser()
		self.rp.set_url(robots_url)
		self.rp.read()

	def can_fetch(self, link):
		try:
			if self.parserobots:
				if self.rp.can_fetch("*", link):
					return True
				else:
					logging.debug ("Crawling of {0} disabled by robots.txt".format(link))
					return False

			if not self.parserobots:
				return True

			return True
		except:
			# On error continue!
			logging.debug ("Error during parsing robots.txt")
			return True

	def exclude_url(self, link):
		for ex in self.exclude:
			if ex in link:
				return False
		return True

	def htmlspecialchars(self, text):
		return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

	def make_report(self):
		print ("Number of found URL : {0}".format(self.nb_url))
		print ("Number of link crawled : {0}".format(len(self.crawled)))
		if self.parserobots:
			print ("Number of link block by robots.txt : {0}".format(self.nb_rp))
		if self.skipext or self.exclude:
			print ("Number of link exclude : {0}".format(self.nb_exclude))

		for code in self.response_code:
			print ("Nb Code HTTP {0} : {1}".format(code, self.response_code[code]))

		for code in self.marked:
			print ("Link with status {0}:".format(code))
			for uri in self.marked[code]:
				print ("\t- {0}".format(uri))
