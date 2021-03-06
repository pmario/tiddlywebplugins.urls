"""
the main entry point for all urls
"""
from tiddlywebplugins.urls.validator import (InvalidDestinationURL, is_redirect,
    figure_destination, replace_url_patterns)

from tiddlyweb.filters import parse_for_filters
from tiddlyweb.control import get_tiddlers_from_bag
from tiddlyweb.model.bag import Bag
from tiddlyweb.web.handler.recipe import get_tiddlers as recipe_tiddlers
from tiddlyweb.web.handler.bag import get_tiddlers as bag_tiddlers
from tiddlyweb.web.handler.tiddler import get as tiddler_get

import re
from urllib import quote


class NoURLFoundError(Exception):
    """
    This shouldn't ever be raised in practise, as if we get 
    into this module, the url has already matched so should 
    match again. If you get this, there is a bug in the code 
    somewhere
    """
    pass

def get_handler(environ, start_response):
    """
    selector comes to this function when a url is found. 
    
    retrieve the recipe/serialization details and pass to 
    tiddlyweb.web.handler.recipe.get_tiddlers
    """
    selector_variables = extract_variables(environ['wsgiorg.routing_args'][1])
    #add the username to be more compliant with recipe variables
    selector_variables['user'] = environ['tiddlyweb.usersign']['name']
    
    potential_matches = get_urls(environ['tiddlyweb.config']['url_bag'], \
        environ['tiddlyweb.store'])
    match = match_url(environ['tiddlyweb.config']['selector'], \
        environ['selector.matches'][0], potential_matches, \
        environ['tiddlyweb.store'])
    
    destination_url = replace_url_patterns(selector_variables, match.text)
    
    if is_redirect(match):
        if destination_url.startswith('www.'):
            destination_url = 'http://' + destination_url
        #redirect to the url and return
        start_response('301 Moved Permanently', [
            ('Location', str(destination_url))
            ])
        return_link = '''<html>
<head>
<title>URL Redirect</title>
</head>
<body>
Please see <a href="%s">%s</a>
</body>
</html>''' % (destination_url, destination_url)
        return return_link
    
    try:
        url_part, custom_filters = destination_url.split('?', 1)
    except ValueError:
        url_part = destination_url
        custom_filters = None
    
    mime_type = 'default'
    destination_parts = figure_destination(url_part)
    for part, value in destination_parts.iteritems():
        if part == 'extension':
            environ['tiddlyweb.extension'] = str(value)
            mime_type = \
                environ['tiddlyweb.config']['extension_types'].get(value)
        else:
            try:
                environ['wsgiorg.routing_args'][1][part] = str(value)
            except UnicodeEncodeError:
                environ['wsgiorg.routing_args'][1][part] = str(value.encode('utf8'))

    for key, value in selector_variables.iteritems():
        if key not in destination_parts:
            destination_parts[key] = value

    #special handling of unicode is required here so that recipe templates will work properly
    environ['tiddlyweb.recipe_template'] = {}
    for key, value in destination_parts.iteritems():
        try:
            environ['tiddlyweb.recipe_template'][key] = value.decode('utf8')
        except UnicodeEncodeError:
            environ['tiddlyweb.recipe_template'][key] = value
            
    filters = figure_filters(environ['tiddlyweb.filters'], custom_filters)
    environ['tiddlyweb.filters'] = filters
    
    #set tiddlyweb.type to make sure we call the correct serializer
    environ['tiddlyweb.type'] = [mime_type]
    
    if 'tiddler_name' in environ['wsgiorg.routing_args'][1]:
        return tiddler_get(environ, start_response)
    elif 'recipe_name' in environ['wsgiorg.routing_args'][1]:
        return recipe_tiddlers(environ, start_response)
    elif 'bag_name' in environ['wsgiorg.routing_args'][1]:
        return bag_tiddlers(environ, start_response)
    
    raise InvalidDestinationURL('URL \'%s\' is incorrectly formatted' % \
        destination_url)

def match_url(selector, url, potential_matches, store):
    """
    match the current url with the correct url in the url_bag
    
    return a tuple of (selector_path, destination_url)
    """
    for tiddler in potential_matches:
        url_regex = selector.parser.__call__(tiddler.title)
        if re.search(url_regex, url):
            #we have found our url
            return store.get(tiddler)
    raise NoURLFoundError('URL not found in selector')

def get_urls(url_bag, store):
    """
    retrieve a list of selector/destination pairs based
    on the tiddlers in the url bag
    """
    bag = Bag(url_bag)
    bag = store.get(bag)
    tiddlers = get_tiddlers_from_bag(bag)
    return (tiddler for tiddler in tiddlers)

def figure_filters(filters, custom_filters):
    """
    figure out the filters that have been added to the query
    string and match them with filters in the destination. 
    
    Override any that match.
    
    return a list of filter functions
    """
    if custom_filters:
        custom_filters = parse_for_filters(custom_filters)[0]
        #strip duplicate filters
        user_filters = [user_filter[1][0] for user_filter in filters]
        result_filters = [custom_filter for custom_filter in custom_filters \
            if custom_filter[1][0] not in user_filters]
        if len(filters) > 0:
            result_filters.extend(filters)
        return result_filters
    return filters

def extract_variables(routing_args):
    """
    extract wsgiorg.routing_args and set as appropriate
    
    returns a dict of all variables found
    """
    variables = {}
    
    if routing_args:
        for element, value in routing_args.iteritems():
            variables[element] = value
            
    return variables

