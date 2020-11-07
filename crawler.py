import asyncio
import concurrent.futures
import base64
from copy import copy
import math

import config
import logging
from urllib.parse import urljoin, urlunparse, urlsplit, urlunsplit

import re
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.robotparser import RobotFileParser
from datetime import datetime

import mimetypes
import os

class IllegalArgumentError(ValueError):
	pass

class Crawler:

	MAX_URLS_PER_SITEMAP = 50000

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
	auth = False

	urls_to_crawl = set([])
	url_strings_to_output = []
	crawled_or_crawling = set([])
	excluded = set([])

	marked = {}

	not_parseable_resources = (".epub", ".mobi", ".docx", ".doc", ".opf", ".7z", ".ibooks", ".cbr", ".avi", ".mkv", ".mp4", ".jpg", ".jpeg", ".png", ".gif" ,".pdf", ".iso", ".rar", ".tar", ".tgz", ".zip", ".dmg", ".exe")

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

	def __init__(self, num_workers=1, parserobots=False, output=None,
				 report=False ,domain="", exclude=[], skipext=[], drop=[],
				 debug=False, verbose=False, images=False, auth=False, as_index=False):
		self.num_workers = num_workers
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
		self.auth       = auth
		self.as_index   = as_index

		if self.debug:
			log_level = logging.DEBUG
		elif self.verbose:
			log_level = logging.INFO
		else:
			log_level = logging.ERROR

		logging.basicConfig(level=log_level)

		self.urls_to_crawl = {self.clean_link(domain)}
		self.url_strings_to_output = []
		self.num_crawled = 0

		if num_workers <= 0:
			raise IllegalArgumentError("Number or workers must be positive")

		try:
			url_parsed = urlparse(domain)
			self.target_domain = url_parsed.netloc
			self.scheme = url_parsed.scheme
		except:
			logging.error("Invalide domain")
			raise IllegalArgumentError("Invalid domain")

		if self.output:
			try:
				self.output_file = open(self.output, 'w')
			except:
				logging.error ("Output file not available.")
				exit(255)
		elif self.as_index:
			logging.error("When specifying an index file as an output option, you must include an output file name")
			exit(255)

	def run(self):
		if self.parserobots:
			self.check_robots()

		logging.info("Start the crawling process")

		if self.num_workers == 1:
			while len(self.urls_to_crawl) != 0:
				current_url = self.urls_to_crawl.pop()
				self.crawled_or_crawling.add(current_url)
				self.__crawl(current_url)
		else:
			event_loop = asyncio.get_event_loop()
			try:
				while len(self.urls_to_crawl) != 0:
					executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers)
					event_loop.run_until_complete(self.crawl_all_pending_urls(executor))
			finally:
				event_loop.close()

		logging.info("Crawling has reached end of all found links")

		self.write_sitemap_output()



	async def crawl_all_pending_urls(self, executor):
		event_loop = asyncio.get_event_loop()

		crawl_tasks = []
		# Since the tasks created by `run_in_executor` begin executing immediately,
		# `self.urls_to_crawl` will start to get updated, potentially before the below
		# for loop finishes.  This creates a race condition and if `self.urls_to_crawl`
		# is updated (by `self.__crawl`) before the for loop finishes, it'll raise an
		# error
		urls_to_crawl = copy(self.urls_to_crawl)
		self.urls_to_crawl.clear()
		for url in urls_to_crawl:
			self.crawled_or_crawling.add(url)
			task = event_loop.run_in_executor(executor, self.__crawl, url)
			crawl_tasks.append(task)

		logging.debug('waiting on all crawl tasks to complete')
		await asyncio.wait(crawl_tasks)
		logging.debug('all crawl tasks have completed nicely')
		return



	def __crawl(self, current_url):
		url = urlparse(current_url)
		logging.info("Crawling #{}: {}".format(self.num_crawled, url.geturl()))
		self.num_crawled += 1

		request = Request(current_url, headers={"User-Agent": config.crawler_user_agent})

		if self.auth:
			base64string = base64.b64encode(bytes(f'{config.username}:{config.password}', 'ascii'))
			request.add_header("Authorization", "Basic %s" % base64string.decode('utf-8'))

		# Ignore ressources listed in the not_parseable_resources
		# Its avoid dowloading file like pdf… etc
		if not url.path.endswith(self.not_parseable_resources):
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
							self.marked[e.code].append(current_url)
						else:
							self.marked[e.code] = [current_url]

				logging.debug ("{1} ==> {0}".format(e, current_url))
				return
		else:
			logging.debug("Ignore {0} content might be not parseable.".format(current_url))
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
				logging.debug ("{1} ===> {0}".format(e, current_url))
				return
		else:
			# Response is None, content not downloaded, just continu and add
			# the link to the sitemap
			msg = "".encode( )
			date = None

		# Image sitemap enabled ?
		image_list = ""
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
		url_string = "<url><loc>"+self.htmlspecialchars(url.geturl())+"</loc>" + lastmod + image_list + "</url>"
		self.url_strings_to_output.append(url_string)

		# Found links
		links = self.linkregex.findall(msg)
		for link in links:
			link = link.decode("utf-8", errors="ignore")
			logging.debug("Found : {0}".format(link))

			if link.startswith('/'):
				link = url.scheme + '://' + url[1] + link
			elif link.startswith('#'):
				link = url.scheme + '://' + url[1] + url[2] + link
			elif link.startswith(("mailto", "tel")):
				continue
			elif not link.startswith(('http', "https")):
				link = self.clean_link(urljoin(current_url, link))

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

			if link in self.crawled_or_crawling:
				continue
			if link in self.urls_to_crawl:
				continue
			if link in self.excluded:
				continue
			if domain_link != self.target_domain:
				continue
			if parsed_link.path in ["", "/"] and parsed_link.query == '':
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
			if target_extension in self.skipext:
				self.exclude_link(link)
				self.nb_exclude+=1
				continue

			# Check if the current url doesn't contain an excluded word
			if not self.exclude_url(link):
				self.exclude_link(link)
				self.nb_exclude+=1
				continue

			self.urls_to_crawl.add(link)

	def write_sitemap_output(self):
		are_multiple_sitemap_files_required = \
			len(self.url_strings_to_output) > self.MAX_URLS_PER_SITEMAP

		# When there are more than 50,000 URLs, the sitemap specification says we have
		# to split the sitemap into multiple files using an index file that points to the
		# location of each sitemap file.  For now, we require the caller to explicitly
		# specify they want to create an index, even if there are more than 50,000 URLs,
		# to maintain backward compatibility.
		#
		# See specification here:
		# https://support.google.com/webmasters/answer/183668?hl=en
		if are_multiple_sitemap_files_required and self.as_index:
			self.write_index_and_sitemap_files()
		else:
			self.write_single_sitemap()

	def write_single_sitemap(self):
		self.write_sitemap_file(self.output_file, self.url_strings_to_output)

	def write_index_and_sitemap_files(self):
		sitemap_index_filename, sitemap_index_extension = os.path.splitext(self.output)

		num_sitemap_files = math.ceil(len(self.url_strings_to_output) / self.MAX_URLS_PER_SITEMAP)
		sitemap_filenames = []
		for i in range(0, num_sitemap_files):
			# name the individual sitemap files based on the name of the index file
			sitemap_filename = sitemap_index_filename + '-' + str(i) + sitemap_index_extension
			sitemap_filenames.append(sitemap_filename)

		self.write_sitemap_index(sitemap_filenames)

		for i, sitemap_filename in enumerate(sitemap_filenames):
			self.write_subset_of_urls_to_sitemap(sitemap_filename, i * self.MAX_URLS_PER_SITEMAP)

	def write_sitemap_index(self, sitemap_filenames):
		sitemap_index_file = self.output_file
		print(config.sitemapindex_header, file=sitemap_index_file)
		for sitemap_filename in sitemap_filenames:
			sitemap_url = urlunsplit([self.scheme, self.target_domain, sitemap_filename, '', ''])
			print("<sitemap><loc>" + sitemap_url + "</loc>""</sitemap>", file=sitemap_index_file)
		print(config.sitemapindex_footer, file=sitemap_index_file)

	def write_subset_of_urls_to_sitemap(self, filename, index):
		# Writes a maximum of self.MAX_URLS_PER_SITEMAP urls to a sitemap file
		#
		# filename: name of the file to write the sitemap to
		# index:    zero-based index from which to start writing url strings contained in
		#           self.url_strings_to_output
		try:
			with open(filename, 'w') as sitemap_file:
				start_index = index
				end_index = (index + self.MAX_URLS_PER_SITEMAP)
				sitemap_url_strings = self.url_strings_to_output[start_index:end_index]
				self.write_sitemap_file(sitemap_file, sitemap_url_strings)
		except:
			logging.error("Could not open sitemap file that is part of index.")
			exit(255)

	@staticmethod
	def write_sitemap_file(file, url_strings):
		print(config.xml_header, file=file)

		for url_string in url_strings:
			print (url_string, file=file)

		print (config.xml_footer, file=file)

	def clean_link(self, link):
		parts = list(urlsplit(link))
		parts[2] = self.resolve_url_path(parts[2])
		return urlunsplit(parts)

	def resolve_url_path(self, path):
		# From https://stackoverflow.com/questions/4317242/python-how-to-resolve-urls-containing/40536115#40536115
		segments = path.split('/')
		segments = [segment + '/' for segment in segments[:-1]] + [segments[-1]]
		resolved = []
		for segment in segments:
			if segment in ('../', '..'):
				if resolved[1:]:
					resolved.pop()
			elif segment not in ('./', '.'):
				resolved.append(segment)
		return ''.join(resolved)

	@staticmethod
	def is_image(path):
		 mt,me = mimetypes.guess_type(path)
		 return mt is not None and mt.startswith("image/")

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

	@staticmethod
	def htmlspecialchars(text):
		return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

	def make_report(self):
		print ("Number of found URL : {0}".format(self.nb_url))
		print ("Number of links crawled : {0}".format(self.num_crawled))
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
