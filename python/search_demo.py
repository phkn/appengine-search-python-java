#!/usr/bin/python
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""A simple guest book app that demonstrates the App Engine search API."""


from cgi import parse_qs
from datetime import datetime
import os
import string
import urllib
from urlparse import urlparse

import logging
import webapp2
from webapp2_extras import jinja2

from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import ndb

# change these if you want
NDB_FETCH = 2000
NDB_OFFSET = 0

# _ENCODE_TRANS_TABLE = string.maketrans('-: .@', '_____')

# don't change these
_INDEX_NAME = 'bby_product'
_INDEX_BATCH = 200
# how many records we have (upper limit of massive bulk query)
_NDB_TOTAL_SIZE = 2000000

# nifty function to split our long array data into batches
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i + n]

# get a list of the attributes in iterator
def iterattr(iterator, attributename):
    for obj in iterator:
        yield getattr(obj, attributename)


class BestBuyProduct(ndb.Model):
    @classmethod
    def _get_kind(cls):
      return _INDEX_NAME
    name = ndb.StringProperty()
    department = ndb.StringProperty()
    regularPrice = ndb.FloatProperty()
    salePrice = ndb.FloatProperty()
    onSale = ndb.BooleanProperty()
    salesRankMediumTerm = ndb.IntegerProperty()
    bestSellingRank = ndb.IntegerProperty()
    sku = ndb.IntegerProperty()
    image = ndb.StringProperty()
    url = ndb.StringProperty()

class BaseHandler(webapp2.RequestHandler):
    """The other handlers inherit from this class.  Provides some helper methods
    for rendering a template."""

    @webapp2.cached_property
    def jinja2(self):
      return jinja2.get_jinja2(app=self.app)

    def render_template(self, filename, template_args):
      self.response.write(self.jinja2.render_template(filename, **template_args))


class MainPage(BaseHandler):
    """Handles search requests for comments."""

    def get(self):
        """Handles a get request with a query."""
        uri = urlparse(self.request.uri)
        query = ''
        results = []
        number_returned = 0
        if uri.query:
            query = parse_qs(uri.query)
            query = query['query'][0]

            # sort results by salesRankMediumTerm and bestSellingRank descending
            expr_list = [search.SortExpression(
                expression='salesRankMediumTerm', default_value='',
                direction=search.SortExpression.DESCENDING), search.SortExpression(
                expression='bestSellingRank', default_value='',
                direction=search.SortExpression.DESCENDING)]

            # construct the sort options
            sort_opts = search.SortOptions(
                 expressions=expr_list)
            query_options = search.QueryOptions(
                limit=10,
                sort_options=sort_opts)
            query_obj = search.Query(query_string=query, options=query_options)
            results = search.Index(name=_INDEX_NAME).search(query=query_obj)
            number_returned = len(results.results)

        # use magic python incantations to extract and filter on returned doc IDs
        dsids = iterattr(results,'doc_id')
        # dammit, remember that you have to int() your keys
        dskeys = [ndb.Key(BestBuyProduct, int(k)) for k in dsids]
        dsresults = ndb.get_multi(dskeys)

        template_values = {
            'results': results,
            'dsresults': dsresults,
            'number_returned': number_returned,
            'query': query,
        }
        self.render_template('index.html', template_values)


def CreateDocument(name, product_id=None):
    """Creates a search.Document from the named product."""
    nameFields = [search.TextField(name='name', value=name)]

    if product_id:
        # Specify using the product_id we want
        return search.Document(
            doc_id=product_id,
            fields=nameFields)
    else:
        # Let the search service supply the document id, for testing only
        return search.Document(fields=nameFields)


class AddIndex(BaseHandler):
    """Handles requests to index products."""

    def post(self):

        name = self.request.get('name')
        query = self.request.get('search')
        if name:
            # SAUCE: CREATE A NEW DOCUMENT AND INDEX IT
            search.Index(name=_INDEX_NAME).put(CreateDocument(name))
        if query:
            self.redirect('/?' + urllib.urlencode(
                #{'query': query}))
                {'query': query.encode('utf-8')}))
        else:
            self.redirect('/')

class BulkIndex(BaseHandler):
    """Handles a bulk update of the search index from GCDS/NDB"""

    def getNextProducts(self, fetchnum=200, offsetnum=0):
        prodquery = BestBuyProduct.query().order(BestBuyProduct.key)
        products = prodquery.fetch(fetchnum, offset=offsetnum, projection=[BestBuyProduct.name])
        return products

    def indexProductBatch(self, products):
        # split our data into batches...
        for productchunk in chunks(products, _INDEX_BATCH):
            # make some noise for the next product we'll touch
            loggedprod=productchunk[0];
            logging.warning('CHUNK! About to create %s index entries, next will be: %s: %s', len(productchunk), loggedprod.key.id(), loggedprod.name)

            # batch index our searchable data
            proddocs = []
            for product in productchunk:
                proddocs.append(CreateDocument(product.name, str(product.key.id())))
            search.Index(name=_INDEX_NAME).put(proddocs)


    def get(self):

        # query NDB for some items that we want to index and display them.
        # Using key order for "random" sampling

        logging.info('GET: fetch %s, offset %s', self.request.get('fetch'), self.request.get('offset'))

        try:
            fetch = int(self.request.get('fetch'))
        except:
            fetch = NDB_FETCH
        try:
            offset = int(self.request.get('offset'))
        except:
            offset = NDB_OFFSET

        products = self.getNextProducts(fetch, offset)
        
        template_values = {
            'products': products,
            'fetch': fetch,
            'offset': offset,
            'number_returned': len(products),
        }

        self.render_template('bulk.html', template_values)


    def post(self):
        confirm = self.request.get('confirm')
        superconfirm = self.request.get('superconfirm')

        # run the query and also GAE index the items, then return to display what we just did
        if confirm:
    
            ### REPEATABILITY-SAFE VERSION:
            ### Starts with the "weird" names that we don't care about messing up,
            ### And only does a few of them... use this when it's broken
            ####################
            # prodquery = BestBuyProduct.query(BestBuyProduct.name != None)
            # products = prodquery.fetch(20, projection=[BestBuyProduct.name])
            ####################

            logging.info('POST: fetch %s, offset %s', self.request.get('fetch'), self.request.get('offset'))

            try:
                fetch = int(self.request.get('fetch'))
            except:
                fetch = NDB_FETCH
            try:
                offset = int(self.request.get('offset'))
            except:
                offset = NDB_OFFSET

            products = self.getNextProducts(NDB_FETCH, NDB_OFFSET)            
            self.indexProductBatch(products)

        if superconfirm:
            # ridiculously large batch update
            logging.warning('SUPERCONFIRM:  All right, you asked for it...')

            for massoffset in xrange(0, _NDB_TOTAL_SIZE, NDB_FETCH):
                logging.warning('YOWZAH! Here comes another %s products, offset %s ...', NDB_FETCH, massoffset)
                products = self.getNextProducts(NDB_FETCH, massoffset)
                self.indexProductBatch(products)

            logging.warning('SUPERCONFIRM:  All done... go to bed already!')

        self.redirect('/bulkindex?'+urllib.urlencode(
            {'fetch': fetch, 'offset': offset}))
                

application = webapp2.WSGIApplication(
    [('/', MainPage),
     ('/add', AddIndex),
     ('/bulkindex' , BulkIndex)],
    debug=True)
