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

import webapp2
from webapp2_extras import jinja2

from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext import ndb

_INDEX_NAME = 'bby_product'

# _ENCODE_TRANS_TABLE = string.maketrans('-: .@', '_____')

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
        if users.get_current_user():
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'results': results,
            'number_returned': len(results.results),
            'query': query,
            'url': url,
            'url_linktext': url_linktext,
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

    def get(self):

        # query NDB for some items that we want to index and display them

        prodquery = BestBuyProduct.query(BestBuyProduct.name != None)
        products = prodquery.fetch(200, projection=[BestBuyProduct.name])

        template_values = {
            'products': products,
            'number_returned': len(products),
        }

        self.render_template('bulk.html', template_values)


    def post(self):
        confirm = self.request.get('confirm')

        # run the query and also GAE index the items, then return to display what we just did

        self.redirect('/index')

application = webapp2.WSGIApplication(
    [('/', MainPage),
     ('/add', AddIndex),
     ('/bulkindex' , BulkIndex)],
    debug=True)
