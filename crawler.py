import config
import logging

import re
from urllib.request import urlopen, Request
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

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
	# TODO also search for window.location={.*?}
	linkregex = re.compile(b'<a href=[\'|"](.*?)[\'"].*?>')

	rp = None
	response_code={}
	nb_url=1 # Number of url.
	nb_rp=0 # Number of url blocked by the robots.txt
	nb_exclude=0 # Number of url excluded by extension or word
	
	output_file = None

	target_domain = ""

	def __init__(self, parserobots=False, output=None, report=False ,domain="", exclude=[], skipext=[], drop=[], debug=False):
		self.parserobots = parserobots
		self.output 	= output
		self.report 	= report
		self.domain 	= domain
		self.exclude 	= exclude
		self.skipext 	= skipext
		self.drop		= drop
		self.debug		= debug

		if self.debug:
			logging.basicConfig(level=logging.DEBUG)

		self.tocrawl = set([domain])

		try:
			self.target_domain = urlparse(domain)[1]
		except:
			raise ("Invalid domain")


		if self.output:
			try:
				self.output_file = open(self.output, 'w')
			except:
				logging.debug ("Output file not available.")
				exit(255)

	def run(self):
		print (config.xml_header, file=self.output_file)

		logging.debug("Start the crawling process")
		self.__crawling()
		logging.debug("Crawling as reach the end of all found link")

		print (config.xml_footer, file=self.output_file)


	def __crawling(self):
		crawling = self.tocrawl.pop()

		url = urlparse(crawling)
		self.crawled.add(crawling)
		
		try:
			request = Request(crawling, headers={"User-Agent":config.crawler_user_agent})
			response = urlopen(request)
		except Exception as e:
			if hasattr(e,'code'):
				if e.code in self.response_code:
					self.response_code[e.code]+=1
				else:
					self.response_code[e.code]=1
			logging.debug ("{1} ==> {0}".format(e, crawling))
			response.close()
			return self.__continue_crawling()

		# Read the response
		try:
			msg = response.read()
			if response.getcode() in self.response_code:
				self.response_code[response.getcode()]+=1
			else:
				self.response_code[response.getcode()]=1
			response.close()
		except Exception as e:
			logging.debug ("{1} ===> {0}".format(e, crawling))
			return self.__continue_crawling()


		print ("<url><loc>"+url.geturl()+"</loc></url>", file=self.output_file)
		if self.output_file:
			self.output_file.flush()

		# Found links
		links = self.linkregex.findall(msg)
		for link in links:
			link = link.decode("utf-8")
			#logging.debug("Found : {0}".format(link))		
			if link.startswith('/'):
				link = 'http://' + url[1] + link
			elif link.startswith('#'):
				link = 'http://' + url[1] + url[2] + link
			elif not link.startswith('http'):
				link = 'http://' + url[1] + '/' + link
			
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

			if (link in self.crawled):
				continue
			if (link in self.tocrawl):
				continue
			if (link in self.excluded):
				continue
			if (domain_link != self.target_domain):
				continue
			if ("javascript" in link):
				continue
			
			# Count one more URL
			self.nb_url+=1

			# Check if the navigation is allowed by the robots.txt
			if (not self.can_fetch(link)):
				if link not in excluded:
					self.excluded.add(link)
				self.nb_rp+=1
				continue

			# Check if the current file extension is allowed or not.
			if (target_extension in self.skipext):
				if link not in excluded:
					self.excluded.add(link)
				self.nb_exclude+=1
				continue

			# Check if the current url doesn't contain an excluded word
			if (not self.exclude_url(link)):
				if link not in self.excluded:
					self.excluded.add(link)
				self.nb_exclude+=1
				continue

			self.tocrawl.add(link)

		return self.__continue_crawling()

	def __continue_crawling(self):
		if self.tocrawl:
			self.__crawling()

	def checkRobots(self):
		if self.domain[len(self.domain)-1] != "/":
			self.domain += "/"
		request = Request(self.domain+"robots.txt", headers={"User-Agent":config.crawler_user_agent})
		self.rp = RobotFileParser()
		self.rp.set_url(self.domain+"robots.txt")
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

	def make_report(self):
		print ("Number of found URL : {0}".format(self.nb_url))
		print ("Number of link crawled : {0}".format(len(self.crawled)))
		if self.parserobots:
			print ("Number of link block by robots.txt : {0}".format(self.nb_rp))
		if self.skipext or self.exclude:
			print ("Number of link exclude : {0}".format(self.nb_exclude))

		for code in self.response_code:
			print ("Nb Code HTTP {0} : {1}".format(code, self.response_code[code]))