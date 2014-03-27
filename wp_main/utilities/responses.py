# -*- coding: utf-8 -*-

'''
      project: welborn productions utilities - responses
     @summary: provides easy access to HttpResponse/Request objects/functions.
    
      @author: Christopher Welborn <cj@welbornproductions.net>
@organization: welborn productions <welbornproductions.net>
 
   start date: Mar 27, 2013
'''

# Default dict for request args.
from collections import defaultdict

# Local tools
from wp_main.utilities import htmltools
from wp_main.utilities.utilities import (
    get_browser_style, get_server, get_remote_ip
)

# Log
from wp_main.utilities.wp_logging import logger
_log = logger("utilities.responses").log
# Template loading, and Contexts
from django.contrib import messages
from django.http import HttpResponse, HttpResponseServerError, Http404
from django.template import RequestContext, Context, loader  # noqa
# Mark Html generated by these functions as safe to view.
from django.utils.safestring import mark_safe


# JSON stuff
import json


# regex (for get referrer view)
import re


def alert_message(request, alert_msg, **kwargs):
    """ Builds an alert message, and returns the HttpResponse object.
        Arguments:
            request       : The original request
            alert_msg     : What to show in the alert box.

        Keyword Arguments:
            body_message  : Body content wrapped in a wp-block div.
                            Default is "Click here to go home."
            noblock       : Don't wrap in wp-block div if True.
    
    """

    body_message = kwargs.get('body_message',
                              ('<a href=\'/\'><span>'
                               'Click here to go home'
                               '</span></a>'))
    noblock = kwargs.get('noblock', False)

    # passes the body message to the generic 'main_content'
    # block of the main template
    if noblock:
        main_content = body_message
    else:
        main_content = '<div class=\'wp-block\'>{}</div>'.format(body_message)

    # alert_message will display at the top of the page,
    # per the main templates 'alert_message' block.
    return clean_response("home/main.html",
                          {'main_content': mark_safe(main_content),
                           'alert_message': mark_safe(alert_msg),
                           'request': request,
                           })


def basic_response(scontent='', *args, **kwargs):
    """ just a wrapper for the basic HttpResponse object. """
    return HttpResponse(scontent, *args, **kwargs)


def clean_response(template_name, context_dict, **kwargs):
    """ same as render_response, except does code cleanup (no comments, etc.)
        returns cleaned HttpResponse.

        Keyword Args:
            see htmltools.render_clean()...
    """
    if context_dict is None:
        context_dict = {}
    request = kwargs.get('request', None) or context_dict.get('request', None)

    # Add request to context if available.
    if request:
        context_dict.update({'request': request})
        # Add server name, remote ip to context if not added already.
        if not context_dict.get('server_name', False):
            context_dict['server_name'] = get_server(request)
        if not context_dict.get('remote_ip', False):
            context_dict['remote_ip'] = get_remote_ip(request)

    # Add new context dict to kwargs for render_clean().
    kwargs['context_dict'] = context_dict
    
    try:
        rendered = htmltools.render_clean(template_name, **kwargs)
    except Exception as ex:
        _log.error('Unable to render template: '
                   '{}\n{}'.format(template_name, ex))
        return alert_message(request,
                             'Sorry, there was an error loading this page.')
    else:
        return HttpResponse(rendered)


def clean_response_req(template_name, context_dict, **kwargs):
    """ handles responses with RequestContext instead of Context,
        otherwise it's the same as clean_response
    """
    
    if not context_dict:
        context_dict = {}
    request = kwargs.get('request', None)
    if request:
        # Add server name, remote ip to context if not added already.
        if not context_dict.get('server_name', False):
            context_dict['server_name'] = get_server(request)
        if not context_dict.get('remote_ip', False):
            context_dict['remote_ip'] = get_remote_ip(request)
        # Turn this into a request context.
        context_dict = RequestContext(request, context_dict)
    else:
        _log.error('No request passed to clean_response_req!\n'
                   'template: {}\n'.format(template_name) +
                   'context: {}\n'.format(repr(context_dict)))

    kwargs['context_dict'] = context_dict

    try:
        rendered = htmltools.render_clean(template_name, **kwargs)
    except Exception as ex:
        _log.error('Unable to render template with request context: '
                   '{}\n{}'.format(template_name, ex))
        return alert_message(request,
                             'Sorry, there was an error loading this page.')
    else:
        return HttpResponse(rendered)
    
 
def clean_template(template_, context_=None, force_=False):
    """ renders a template with context and
        applies the cleaning functions.
        
        Email addresses are hidden with hide_email(),
        then fixed on document load with wptools.js.
        
        Blank Lines, Whitespace, Comments are removed if DEBUG = True.
        see: htmltools.render_clean() or htmltools.clean_html()
    """
    if context_ is None:
        context_ = {}
    
    if hasattr(template_, 'encode'):
        # render template and then clean.
        return htmltools.render_clean(template_, context_)
    elif hasattr(template_, 'render'):
        # already loaded template.
        return htmltools.clean_html(template_.render(context_))
    else:
        return None


def default_dict(request=None, extradict=None):
    """ Use default context contents for rendering templates, 
        This dict will return with at least:
        {
            'request': request, 
            'extra_style_link_list': utilities.get_browser_style(request),
        }
        Request must be passed to use this.
        Any extra dict items in the extradict override the defaults.
    """
    if request is None:
        defaults = {}
    else:
        # Items guaranteed to be present in the context dict.
        defaults = {
            'request': request,
            'extra_style_link_list': [get_browser_style(request)],
        }

    if extradict:
        defaults.update(extradict)

    return defaults


def error404(request, message=None):
    """ Raise a 404, but pass an optional message through the messages
        framework.
    """

    if message:
        messages.error(request, message)
        raise Http404(message)
    else:
        raise Http404()


def error500(request, msgs=None):
    """ Fake-raise a 500 error. I say fake because no exception is
        raised, but the user is directed to the 500-error page.
        If a message is passed, it is sent via the messages framework.
        Arguments:
            request  : Request object from view.
            message  : Optional message for the messages framework.
    """
    if msgs and isinstance(msgs, str):
        msgs = [msgs]

    if msgs:
        # Send messages using the message framework.
        for m in msgs:
            messages.error(request, m)

    context = {'request': request,
               'server_name': get_server(request),
               'remote_ip': get_remote_ip(request),
               }
    try:
        rendered = htmltools.render_clean('home/500.html',
                                          context_dict=context,
                                          request=request)
    except Exception as ex:
        _log.error('Unable to render template: home/500.html\n'
                   '{}'.format(ex))
        if msgs:
            # Send message manually.
            errmsgfmt = '<html><body>\n{}</body></html>'
            # Style each message.
            msgfmt = '<div style="color: darkred;">{}</div>'
            errmsgs = '\n'.join((msgfmt.format(m) for m in msgs))
            # Build final html page.
            errmsg = errmsgfmt.format(errmsgs)
        else:
            errmsg = 'There was an error while building this page.'
        return HttpResponseServerError(errmsg)

    # Successfully rendered 500.html page.
    return HttpResponse(rendered)


def get_paged_args(request, total_count):
    """ retrieve request arguments for paginated post/tag lists.
        total count must be given to calculate last page.
        returns dict with arg names as keys, and values.
    """

    # get order_by
    order_by_ = get_request_arg(request, ['order_by', 'order'], default=None)
        
    # get max_posts
    max_ = get_request_arg(request,
                           ['max_items', 'max'],
                           default=25,
                           min_val=1,
                           max_val=100)
    
    # get start_id
    start_id = get_request_arg(request,
                               ['start_id', 'start'],
                               default=0,
                               min_val=0,
                               max_val=9999)
    # calculate last page based on max_posts
    last_page = (total_count - max_) if (total_count > max_) else 0
    # fix starting id.
    if hasattr(start_id, 'lower'):
        start_id = last_page if start_id.lower() == 'last' else 0
    else:
        start_id = 0
        
    # fix maximum start_id (must be within the bounds)
    if start_id > (total_count - 1):
        start_id = total_count - 1
         
    # get prev page
    # (if previous page is out of bounds, just show the first page)
    prev_page = start_id - max_
    if prev_page < 0:
        prev_page = 0
    # get next page (if next page is out of bounds, just show the last page)
    next_page = start_id + max_
    if next_page > total_count:
        next_page = last_page
    
    return {"start_id": start_id,
            "max_items": max_,
            "prev_page": prev_page,
            "next_page": next_page,
            "order_by": order_by_}


def get_referer_view(request, default=None):
    ''' Return the referer view of the current request
        Example:
            def some_view(request):
                ...
                referer_view = get_referer_view(request)
                return HttpResponseRedirect(referer_view, '/accounts/login/')
    '''

    # if the user typed the url directly in the browser's address bar
    referer = request.META.get('HTTP_REFERER')
    if not referer:
        return default

    # remove the protocol and split the url at the slashes
    referer = re.sub('^https?:\/\/', '', referer).split('/')
    if referer[0] != request.META.get('SERVER_NAME'):
        return default

    # add the slash at the relative path's view and finished
    referer = u'/' + u'/'.join(referer[1:])
    return referer


def get_request_arg(request, arg_names, **kwargs):
    """ return argument from request (GET or POST),
        arg_names can be a list of alias names like: ['q', 'query', 'search']
           and this will look for any of those args.
        default value can be set.
        automatically returns int/float values instead of string where needed.
        min/max can be set for integer/float values.
        Arguments:
            request    : request object to get page args from
            arg_names  : argument names to accept for this arg.

        Keyword Arguments:
            default    : default value for argument if it's not found.
                         Default: None
            min_val    : minimum value for int args.
            max_val    : maximum vlaue for int args.
                         Default: 999999
    """
    
    default = kwargs.get('default', None)
    min_val = kwargs.get('min_val', 0)
    max_val = kwargs.get('max_val', 999999)
    # blank value to start with. (until we confirm it exists)
    val = ''
    if isinstance(arg_names, (list, tuple)):
        # list of arg aliases was passed, try them all.
        for arg_ in arg_names:
            if arg_ in request.REQUEST.keys():
                val = request.REQUEST[arg_]
                break
    else:
        # single arg_name was passed.
        if arg_names in request.REQUEST.keys():
            val = request.REQUEST[arg_names]
    
    # Default wasn't available, try some different types..
    if default is None:
        if val.isalnum():
            # check min/max for int values
            try:
                int_val = int(val)
                if (int_val < min_val):
                    int_val = min_val
                if (int_val > max_val):
                    int_val = max_val
                # return float instead of string
                val = int_val
            except:
                pass
        else:
            # try float, check min/max if needed.
            try:
                float_val = float(val)
                if (float_val < min_val):
                    float_val = min_val
                if (float_val > max_val):
                    float_val = max_val
                # return float instead of string
                val = float_val
            except:
                pass
    else:
        # Get desired type from defaults type.
        desiredtype = type(default)
        try:
            if val != '':
                desiredval = desiredtype(val)
                # If an error isn't trigured, we converted successfully.
                val = desiredval
        except Exception as ex:
            _log.error('Unable to determine type from: {}\n{}'.format(val, ex))

    # final return after processing,
    # will goto default value if val is empty.
    if val == "":
        val = default
    return val
        

def get_request_args(request, requesttype=None, default=None):
    """ returns a dict of all request args.
        A default dict is returned where 'default' is the default value 
        for missing keys.
        Arguments:
            request  : The request object to retrieve args from.

        Keyword Arguments:
            default      : What to return for missing keys.

            requesttype  : 'post', 'get', or None.
                           If None is given, it retrieves request.REQUEST
                           (which is both POST and GET)

        Example of missing key:
            myargs = get_request_args(request)
            print(str(myargs['keyname']))
            # prints: None

            myargs = get_request_args(request, default='mydefault')
            print(myargs['keyname'])
            # prints: 'mydefault'

    """
    
    # make default dict.
    defaultfactory = lambda: default
    defaultargs = defaultdict(defaultfactory)

    # Get original request args.
    if requesttype:
        # Try using provided request type.
        try:
            reqargs = getattr(request, requesttype.upper())
        except Exception as ex:
            _log.error('Invalid request arg type!: {}\n{}'.format(requesttype,
                                                                  ex))
            return defaultargs
    else:
        # Default request type is REQUEST (both GET and POST)
        reqargs = request.REQUEST

    # Put the request args in the default dict.
    defaultargs.update(reqargs)
    return defaultargs


def json_get(data):
    """ Retrieves a dict from json data string. """
    
    if isinstance(data, dict):
        return data
    
    datadict = json.loads(data.decode('utf-8'))
    return datadict


def json_get_request(request):
    """ retrieve JSON data from a request (uses json_get()). """
    
    if request.is_ajax():
        return json_get(request.body)
    return None


def json_response(data):
    """ Returns an HttpResponse with application/json
        data can be a json.dumps() or a dict.
        dicts will be transformed with json.dumps()
    """
    
    if isinstance(data, dict):
        data = json.dumps(data)
    
    return HttpResponse(data, content_type='application/json')


def json_response_err(ex, log=False):
    """ Respond with contents of error message using JSON. """
    if log:
        _log.error('Sent JSON error:\n{}'.format(ex))

    return json_response({'status': 'error', 'message': str(ex)})


def redirect_perm_response(redirect_to):
    """ returns a permanently moved response. """

    return redirect_response(redirect_to, status_code=301)


def redirect_response(redirect_to, status_code=302):
    """ returns redirect response.
        redirects user to redirect_to.
    """
    
    response = HttpResponse(redirect_to, status=status_code)
    response['Location'] = redirect_to
    return response


def render_response(template_name, context_dict):
    """ same as render_to_response, 
        loads template, renders with context,
        returns HttpResponse.
    """
    request = context_dict.get('request', None) if context_dict else None
    try:
        rendered = htmltools.render_clean(template_name, context_dict)
        return HttpResponse(rendered)
    except:
        return alert_message(request,
                             'Sorry, there was an error loading this page.')


def text_response(text_content, content_type='text/plain'):
    """ sends basic HttpResponse with content type as text/plain """
    
    return HttpResponse(text_content, content_type=content_type)


def wsgi_error(request, smessage):
    """ print message to requests wsgi errors """
    
    request.META['wsgi_errors'] = smessage
   

def xml_response(template_name, context_dict=None):
    """ loads sitemap.xml template, renders with context_dict,
        returns HttpResponse with content_type='application/xml'.
    """
    contextdict = context_dict or {}
    try:
        tmplate = loader.get_template(template_name)
        context = Context(contextdict)
        clean_render = htmltools.remove_whitespace(
            htmltools.remove_comments(tmplate.render(context)))
        response = HttpResponse(clean_render, content_type='application/xml')
    except Exception as ex:
        errmsg = 'Error: {}'.format(ex)
        response = HttpResponseServerError(errmsg, content_type='text/plain')
    
    return response
