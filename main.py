import re
from urllib.request import urlopen, Request
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import argparse
import os

import json
import logging

def can_fetch(parserobots, rp, link, debug=False):
	try:
		if parserobots:
			if rp.can_fetch("*", link):
				return True
			else:
				if debug:
					logging.debug ("Crawling of {0} disabled by robots.txt".format(link))
				return False

		if not parserobots:
			return True

		return True
	except:
		# On error continue!
		if debug:
			logging.debug ("Error during parsing robots.txt")
		return True


def exclude_url(exclude, link):
	if exclude:
		for ex in exclude:
			if ex in link:
				return False
		return True
	else:
		return True

# Gestion des parametres
parser = argparse.ArgumentParser(version="0.1",description='Crawler pour la creation de site map')

parser.add_argument('--skipext', action="append", default=[], required=False, help="File extension to skip")
parser.add_argument('--parserobots', action="store_true", default=False, required=False, help="Ignore file defined in robots.txt")
parser.add_argument('--debug', action="store_true", default=False, help="Enable debug mode")
parser.add_argument('--output', action="store", default=None, help="Output file")
parser.add_argument('--exclude', action="append", default=[], required=False, help="Exclude Url if contain")
parser.add_argument('--drop', action="append", default=[], required=False, help="Drop a string from the url")

group = parser.add_mutually_exclusive_group()
group.add_argument('--config', action="store", default=None, help="Configuration file in json format")
group.add_argument('--domain', action="store", default="", help="Target domain (ex: http://blog.lesite.us)")

arg = parser.parse_args()
# Read the config file if needed
if arg.config is not None:
	try:
		config_data=open(arg.config,'r')
		config = json.load(config_data)
		config_data.close()
	except Exception as e:
		if arg.debug:
			logging.debug ("Bad or unavailable config file")
		config = {}
		print(e)
else:
	config = {}

# Overload config with flag parameters
dict_arg = arg.__dict__
for argument in config:
	if argument in dict_arg:
		if type(dict_arg[argument]).__name__ == 'list':
			dict_arg[argument].extend(config[argument])
		elif type(dict_arg[argument]).__name__ == 'bool':
			if dict_arg[argument]:
				dict_arg[argument] = True
			else:
				dict_arg[argument] = config[argument]
		else:
			dict_arg[argument] = config[argument]
	else:
		logging.error ("Unknown flag in JSON")
		
if arg.debug:
	logging.basicConfig(level=logging.DEBUG)
	logging.debug ("Configuration : ")
	logging.debug (arg)

output_file = None
if arg.output:
	try:
		output_file = open(arg.output, 'w')
	except:
		if not arg.debug:
			logging.debug ("Output file not available.")
			exit(255)
		else:
			logging.debug ("Continue without output file.")

tocrawl = set([arg.domain])
crawled = set([])
excluded = set([])
# TODO also search for window.location={.*?}
linkregex = re.compile(b'<a href=[\'|"](.*?)[\'"].*?>')

header = """<?xml version="1.0" encoding="UTF-8"?>
<urlset
      xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
            http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
"""
footer = "</urlset>"

try:
	target_domain = urlparse(arg.domain)[1]
except:
	logging.debug ("Invalid domain")

rp = None
if arg.parserobots:
	if arg.domain[len(arg.domain)-1] != "/":
		arg.domain += "/"
	request = Request(arg.domain+"robots.txt", headers={"User-Agent":'Sitemap crawler'})
	rp = RobotFileParser()
	rp.set_url(arg.domain+"robots.txt")
	rp.read()

responseCode={}
nbUrl=1
nbRp=0
print (header, file=output_file)
while tocrawl:
	crawling = tocrawl.pop()


	url = urlparse(crawling)
	crawled.add(crawling)
	
	try:
		request = Request(crawling, headers={"User-Agent":'Sitemap crawler'})
		# TODO : The urlopen() function has been removed in Python 3 in favor of urllib2.urlopen()
		response = urlopen(request)
	except Exception as e:
		if hasattr(e,'code'):
			if e.code in responseCode:
				responseCode[e.code]+=1
			else:
				responseCode[e.code]=1
		#else:
		#	responseCode['erreur']+=1
		if arg.debug:
			logging.debug ("{1} ==> {0}".format(e, crawling))
		response.close()
		continue

	# Read the response
	try:
		msg = response.read()
		if response.getcode() in responseCode:
			responseCode[response.getcode()]+=1
		else:
			responseCode[response.getcode()]=1
		response.close()
	except Exception as e:
		if arg.debug:
			logging.debug ("{1} ===> {0}".format(e, crawling))
		continue


	print ("<url><loc>"+url.geturl()+"</loc></url>", file=output_file)
	if output_file:
		output_file.flush()

	# Found links
	links = linkregex.findall(msg)
	for link in links:
		link = link.decode("utf-8")
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
		if arg.drop is not None:
			for toDrop in arg.drop:
				link=re.sub(toDrop,'',link)

		# Parse the url to get domain and file extension
		parsed_link = urlparse(link)
		domain_link = parsed_link.netloc
		target_extension = os.path.splitext(parsed_link.path)[1][1:]

		if (link in crawled):
			continue
		if (link in tocrawl):
			continue
		if (link in excluded):
			continue
		if (domain_link != target_domain):
			continue
		if ("javascript" in link):
			continue
		
		# Count one more URL
		nbUrl+=1

		if (can_fetch(arg.parserobots, rp, link, arg.debug) == False):
			if link not in excluded:
				excluded.add(link)
			nbRp+=1
			continue
		if (target_extension in arg.skipext):
			if link not in excluded:
				excluded.add(link)
			continue
		if (exclude_url(arg.exclude, link)==False):
			if link not in excluded:
				excluded.add(link)
			continue

		tocrawl.add(link)
print (footer, file=output_file)

if arg.debug:
	logging.debug ("Number of found URL : {0}".format(nbUrl))
	logging.debug ("Number of link crawled : {0}".format(len(crawled)))
	if arg.parserobots:
		logging.debug ("Number of link block by robots.txt : {0}".format(nbRp))

	for code in responseCode:
		logging.debug ("Nb Code HTTP {0} : {1}".format(code, responseCode[code]))

if output_file:
	output_file.close()
