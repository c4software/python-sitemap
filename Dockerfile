FROM python:3.6.1-alpine
WORKDIR /home/python-sitemap/
COPY main.py crawler.py config.py /home/python-sitemap/
ENTRYPOINT [ "python", "main.py" ]
CMD [ "--domain", "http://blog.lesite.us" ]

