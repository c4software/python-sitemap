import re
from urllib.request import urlopen, Request
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import argparse
import os

import json

def can_fetch(parserobots, rp, link, debug=False):
	try:
		if parserobots:
			if rp.can_fetch("*", link):
				return True
			else:
				if debug:
					print ("Crawling of {0} disabled by robots.txt".format(link))
				return False

		if not parserobots:
			return True

		return True
	except:
		# On error continue!
		if debug:
			print ("Error during parsing robots.txt")
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
	except:
		if arg.debug:
			print ("Bad or unavailable config file")
		config = {}
else:
	config = {}

# Overload config with flag parameters
dict_arg = arg.__dict__
for argument in arg.__dict__:
	if dict_arg[argument] is not (None or ""):
		try:
			print (type(config[argument]).__name__)
			if type(config[argument]).__name__ == 'list':
				config[argument].extend(dict_arg[argument])
			else:
				config[argument] = dict_arg[argument]
		except:
			pass
arg = config

if arg['debug']:
	print ("Configuration : ")
	print (arg)

output_file = None
if arg['output'] is not None:
	try:
		output_file = open(arg['output'], 'w')
	except:
		if not arg['debug']:
			print ("Output file not available.")
			exit(255)
		else:
			print ("Continue without output file.")

tocrawl = set([arg['domain']])
crawled = set([])
# TODO also search for window.location={.*?}
linkregex = re.compile(b'<a href=[\'|"](.*?)[\'"].*?>')

header = """
<?xml version="1.0" encoding="UTF-8"?>
<urlset
      xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
            http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">
"""
footer = "</urlset>"

try:
	target_domain = urlparse(arg['domain'])[1]
except:
	print ("Invalid domain")

rp = None
if arg['parserobots']:
	if arg['domain'][len(arg['domain'])-1] != "/":
		arg['domain'] += "/"
	request = Request(arg['domain']+"robots.txt", headers={"User-Agent":'Sitemap crawler'})
	rp = RobotFileParser()
	rp.set_url(arg['domain']+"robots.txt")
	rp.read()


print (header, file=output_file)
while tocrawl:
	crawling = tocrawl.pop()

	url = urlparse(crawling)
	try:
		request = Request(crawling, headers={"User-Agent":'Sitemap crawler'})
		response = urlopen(request)
		msg = response.read()
		response.close()
	except Exception as e:
		if arg['debug']:
			print ("{1} ==> {0}".format(e, crawling))
		continue

	
	links = linkregex.findall(msg)
	crawled.add(crawling)
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

		# Parse the url to get domain and file extension
		parsed_link = urlparse(link)
		domain_link = parsed_link.netloc
		target_extension = os.path.splitext(parsed_link.path)[1][1:]

		if (link not in crawled) and (link not in tocrawl) and (domain_link == target_domain) and can_fetch(arg['parserobots'], rp, link,arg['debug']) and ("javascript:" not in link) and (target_extension not in arg['skipext']) and (exclude_url(arg['exclude'], link)):
			print ("<url><loc>"+link+"</loc></url>", file=output_file)
			tocrawl.add(link)
print (footer, file=output_file)

if arg['debug']:
	print ("Number of link crawled : {0}".format(len(crawled)))

if output_file:
	output_file.close()