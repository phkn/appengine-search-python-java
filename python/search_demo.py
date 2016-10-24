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

_INDEX_NAME = 'bby_product'

# _ENCODE_TRANS_TABLE = string.maketrans('-: .@', '_____')

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
            direction=search.SortExpression.DESCENDING),]

        # construct the sort options
        sort_opts = search.SortOptions(
             expressions=expr_list)
        query_options = search.QueryOptions(
            limit=3,
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
            'url': url,
            'url_linktext': url_linktext,
        }
        self.render_template('index.html', template_values)


# def CreateDocument(sku, name, department, regularPrice, salePrice, onSale, salesRankMediumTerm, bestSellingRank, image, url):
def CreateDocument(name):
    """Creates a search.Document from the named product."""

    # Let the search service supply the document id, for testing only
    return search.Document(
        fields=[search.TextField(name='name', value=name)])
        # fields=[search.TextField(name='name', value=name),
        #         search.TextField(name='department', value=department),
        #         search.NumberField(name='sku', value=sku),
        #         search.NumberField(name='regularPrice', value=regularPrice),
        #         search.NumberField(name='salePrice', value=salePrice),
        #         search.NumberField(name='onSale', value=onSale),
        #         search.NumberField(name='salesRankMediumTerm', value=salesRankMediumTerm),
        #         search.NumberField(name='bestSellingRank', value=bestSellingRank),
        #         search.TextField(name='image', value=image),
        #         search.TextField(name='url', value=url)])

class Comment(BaseHandler):
    """Handles requests to index comments."""

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


application = webapp2.WSGIApplication(
    [('/', MainPage),
     ('/add', Comment)],
    debug=True)
