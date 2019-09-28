#!/usr/bin/python3
# -*- coding: utf-8 -*-

#
# Queue tasks for batch processing and parallel processing
#

# Queue handler
import time
from celery import Celery
from kombu import Queue, Exchange

# ETL connectors
from etl import ETL
from etl_delete import Delete
from etl_file import Connector_File
from etl_web import Connector_Web
from etl_rss import Connector_RSS


verbose = True
quiet = False

app = Celery('etl.tasks')

app.conf.CELERY_QUEUES = [Queue('tasks', Exchange(
    'tasks'), routing_key='tasks', queue_arguments={'x-max-priority': 10})]

app.conf.CELERYD_MAX_TASKS_PER_CHILD = 1
app.conf.CELERYD_PREFETCH_MULTIPLIER = 1
app.conf.CELERY_ACKS_LATE = True

etl_delete = Delete()
etl_web = Connector_Web()
etl_rss = Connector_RSS()


#
# Delete document with URI from index
#

@app.task(name='etl.delete')
def delete(uri):
    etl_delete.delete(uri=uri)


#
# Index a file
#

@app.task(name='etl.index_file')
def index_file(filename, additional_plugins=(), wait=0, config=None):

    if wait:
        time.sleep(wait)

    etl_file = Connector_File()

    # set alternate config options (will overwrite config options from config file)
    if config:
        for option in config:
            etl_file.config[option] = config[option]

    etl_file.index_file(filename=filename,
                        additional_plugins=additional_plugins)
    etl_file.commit()

#
# Index file directory
#


@app.task(name='etl.index_filedirectory')
def index_filedirectory(filename):

    from etl_filedirectory import Connector_Filedirectory

    connector_filedirectory = Connector_Filedirectory()

    result = connector_filedirectory.index(filename)
    connector_filedirectory.commit()

    return result


#
# Index a webpage
#
@app.task(name='etl.index_web')
def index_web(uri, wait=0, downloaded_file=False, downloaded_headers=None):

    if wait:
        time.sleep(wait)

    result = etl_web.index(uri, downloaded_file=downloaded_file,
                           downloaded_headers=downloaded_headers)

    return result


#
# Index full website
#

@app.task(name='etl.index_web_crawl')
def index_web_crawl(uri, crawler_type="PATH"):

    import etl_web_crawl

    etl_web_crawl.index(uri, crawler_type)


#
# Index webpages from sitemap
#

@app.task(name='etl.index_sitemap')
def index_sitemap(uri):

    from etl_sitemap import Connector_Sitemap

    connector_sitemap = Connector_Sitemap()

    result = connector_sitemap.index(uri)

    return result


#
# Index RSS Feed
#

@app.task(name='etl.index_rss')
def index_rss(uri):

    result = etl_rss.index(uri)

    return result


#
# Enrich with / run plugins
#

@app.task(name='etl.enrich')
def enrich(plugins, uri, wait=0):

    if wait:
        time.sleep(wait)

    etl = ETL()
    etl.read_configfile('/etc/opensemanticsearch/etl')
    etl.read_configfile('/etc/opensemanticsearch/enhancer-rdf')

    etl.config['plugins'] = plugins.split(',')

    filename = uri

    # if exist delete protocoll prefix file://
    if filename.startswith("file://"):
        filename = filename.replace("file://", '', 1)

    parameters = etl.config.copy()

    parameters['id'] = uri
    parameters['filename'] = filename

    parameters, data = etl.process(parameters=parameters, data={})

    return data


#
# Read command line arguments and start
#

# if running (not imported to use its functions), run main function
if __name__ == "__main__":

    from optparse import OptionParser

    parser = OptionParser("etl-tasks [options]")
    parser.add_option("-q", "--quiet", dest="quiet", action="store_true",
                      default=False, help="Don\'t print status (filenames) while indexing")
    parser.add_option("-v", "--verbose", dest="verbose",
                      action="store_true", default=False, help="Print debug messages")

    (options, args) = parser.parse_args()

    if options.verbose == False or options.verbose == True:
        verbose = options.verbose
        etl_delete.verbose = options.verbose
        etl_web.verbose = options.verbose
        etl_rss.verbose = options.verbose

    if options.quiet == False or options.quiet == True:
        quiet = options.quiet

    app.worker_main()
