#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import crawler

parser = argparse.ArgumentParser(description='Python SiteMap Crawler')
parser.add_argument('--skipext', action="append", default=[], required=False, help="File extension to skip")
parser.add_argument('-n', '--num-workers', type=int, default=1, help="Number of workers if multithreading")
parser.add_argument('--parserobots', action="store_true", default=False, required=False, help="Ignore file defined in robots.txt")
parser.add_argument('--user-agent', action="store", default="*", help="Use the rules defined in robots.txt for a specific User-agent (i.e. Googlebot)")
parser.add_argument('--debug', action="store_true", default=False, help="Enable debug mode")
parser.add_argument('--auth', action="store_true", default=False, help="Enable basic authorisation while crawling")
parser.add_argument('-v', '--verbose', action="store_true", help="Enable verbose output")
parser.add_argument('--output', action="store", default=None, help="Output file")
parser.add_argument('--as-index', action="store_true", default=False, required=False, help="Outputs sitemap as index and multiple sitemap files if crawl results in more than 50,000 links (uses filename in --output as name of index file)")
parser.add_argument('--no-sort',  action="store_false", default=True, required=False, help="Disables sorting the output URLs alphabetically", dest='sort_alphabetically')
parser.add_argument('--exclude', action="append", default=[], required=False, help="Exclude Url if contain")
parser.add_argument('--drop', action="append", default=[], required=False, help="Drop a string from the url")
parser.add_argument('--report', action="store_true", default=False, required=False, help="Display a report")
parser.add_argument('--images', action="store_true", default=False, required=False, help="Add image to sitemap.xml (see https://support.google.com/webmasters/answer/178636?hl=en)")
parser.add_argument('--fetch-iframes', action="store_true", default=False, required=False, help="Fetch iframes' content when generating sitemap")

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
		config = {}
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
del(dict_arg['config'])

if dict_arg["domain"] == "":
	print ("You must provide a domain to use the crawler.")
	exit()

crawl = crawler.Crawler(**dict_arg)
crawl.run()

if arg.report:
	crawl.make_report()
