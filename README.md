Python-Sitemap
==============
Simple script to crawl a website and create a sitemap.xml of all public link in a website

Warning : This script is designed to works with ***Python3***

Simple usage
------------
	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml

Advanced usage
--------------

Read a config file to set parameters:
***You can overide (or add for list) any parameters define in the config.json***

	>>> python main.py --config config.json

Enable debug :

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --debug

Enable report for print summary of the crawl:

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --report

Skip url (by extension) (skip pdf AND xml url):

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --skipext pdf --skipext xml 

Drop a part of an url via regexp :

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --drop "id=[0-9]{5}"

Exclude url by filter a part of it :

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --exclude "action=edit"

Read the robots.txt to ignore some url:

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --parserobots
