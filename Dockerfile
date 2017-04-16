FROM python:3.6.1-alpine
COPY main.py crawler.py config.py /home/python-sitemap/
RUN mkdir -p /home/python-sitemap/output/
ENTRYPOINT [ "python", "/home/python-sitemap/main.py" ]
CMD [ "--domain", "http://blog.lesite.us" ]

