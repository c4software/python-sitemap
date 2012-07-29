Python-Sitemap
==============
Simple script to crawl a website and create a sitemap.xml of all public link in a website

Warning : This script is designed to works with ***Python3***

Simple usage
------------
	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml

Advanced usage
--------------

Enable debug :

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --debug

Skip url (by extension) (skip pdf AND xml url):

	>>> python main.py --domain http://blog.lesite.us --output sitemap.xml --skipext pdf --skipext xml 