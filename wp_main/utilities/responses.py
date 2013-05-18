# -*- coding: utf-8 -*-

'''
      project: welborn productions utilities - responses
     @summary: provides easy access to HttpResponse/Request objects/functions.
    
      @author: Christopher Welborn <cj@welbornproductions.net>
@organization: welborn productions <welbornproductions.net>
 
   start date: Mar 27, 2013
'''

# Global settings
from django.conf import settings
# Local tools
from wp_main.utilities import htmltools
# Log
from wp_main.utilities.wp_logging import logger
_log = logger("utilities.responses").log
# Template loading, and Contexts
from django.http import HttpResponse, HttpResponseNotFound
from django.template import Context, loader
# Mark Html generated by these functions as safe to view.
from django.utils.safestring import mark_safe

def clean_template(template_, context_, force_ = False):
    """ renders a template with context and 
        applies the cleaning functions.
        
        Email addresses are hidden with hide_email(),
        then fixed on document load with wptools.js.
        
        Blank Lines, Whitespace, Comments are removed if DEBUG = True.
        if DEBUG = False then New Lines are removed also (to minify)
    """
    
    # these things have to be done in a certain order to work correctly.
    # hide_email, fix p spaces, remove_comments, remove_whitespace, remove_newlines
    clean_output = htmltools.remove_whitespace(
                        htmltools.remove_comments(
                        htmltools.hide_email(template_.render(context_))))

    if ((not settings.DEBUG) or (force_)):
        # minify (removes newlines except in certain tags [pre, script, etc.])
        # fixes <p> linebreak spaces before, making sure &nbsp; is there.
        clean_output = htmltools.remove_newlines(
                                htmltools.fix_p_spaces(clean_output))
    return clean_output


def alert_message(alert_msg, body_message="<a href='/'><span>Click here to go home</span></a>", noblock=False):
    """ Builds an alert message, and returns the HttpResponse object. 
        alert_message: What to show in the alert box.
        body_message: Body content wrapped in a wp-block div.
                      Default is "Click here to go home."
        noblock: Don't wrap in wp-block div if True.
    
    """
    
    if noblock:
        main_content = body_message
    else:
        main_content = "<div class='wp-block'>" + body_message + "</div>"
    tmp_notfound = loader.get_template('home/main.html')
    cont_notfound = Context({'main_content': mark_safe(main_content),
                             'alert_message': mark_safe(alert_msg),
                             })
    rendered = clean_template(tmp_notfound, cont_notfound, (not settings.DEBUG))
    return HttpResponse(rendered)


def basic_response(scontent='', *args, **kwargs):
    """ just a wrapper for the basic HttpResponse object. """
    return HttpResponse(scontent, *args, **kwargs)



def xml_response(template_name, context_dict):
    """ loads sitemap.xml template, renders with context_dict,
        returns HttpResponse with content_type='application/xml'.
    """
    
    try:
        tmp_ = loader.get_template(template_name)
        cont_ = Context(context_dict)
        clean_render = htmltools.remove_whitespace(
                            htmltools.remove_comments(tmp_.render(cont_)))
        response = HttpResponse(clean_render, content_type='application/xml')
    except:
        response = HttpResponseNotFound()
    
    return response

def text_response(text_content, content_type = 'text/plain'):
    """ sends basic HttpResponse with content type as text/plain """
    
    return HttpResponse(text_content, content_type = content_type)


def render_response(template_name, context_dict):
    """ same as render_to_response, 
        loads template, renders with context,
        returns HttpResponse.
    """
    
    try:
        tmp_ = loader.get_template(template_name)
        cont_ = Context(context_dict)
        rendered = tmp_.render(cont_)
    except:
        rendered = alert_message("Sorry, there was an error loading this page.")
    return HttpResponse(rendered)

def clean_response(template_name, context_dict, request_ = None):
    """ same as render_response, except does code minifying/compression 
        (compresses only if settings.DEBUG=False)
        returns cleaned HttpResponse.
    """
    
    try:
        tmp_ = loader.get_template(template_name)
    except Exception as ex:
        _log.error("could not load template: " + template_name + '<br/>\n' + \
                   str(ex))
        rendered = None
    else:
        try:
            # Add request to context if available.
            if request_ is not None:
                # some views already pass the request, we'll use the views.
                # this was an idea from earlier, this could probably be removed.
                if not context_dict.has_key('request'):
                    context_dict['request'] = request_
                context_dict['meta'] = request_.META
                
            cont_ = Context(context_dict)
        except Exception as ex:
            _log.error("could not load context: " + str(context_dict) + str(ex))
            rendered = None
        else:
            try:
                # Clean the template using clean_template() methods...
                rendered = clean_template(tmp_, cont_, (not settings.DEBUG))
            except Exception as ex:
                _log.error("could not clean_template!: " + str(ex))
                rendered = None
    if rendered is None:
        return alert_message("Sorry, there was an error loading this page.")
    else:
        return HttpResponse(rendered)


def redirect_response(redirect_to):
    """ returns redirect response.
        redirects user to redirect_to.
    """
    
    response = HttpResponse(redirect_to, status=302)
    response['Location'] = redirect_to
    return response


def get_request_arg(request, arg_names, default_value=None, min_val=0, max_val=9999):
    """ return argument from request (GET or POST),
        arg_names can be a list of alias names like: ['q', 'query', 'search']
           and this will look for any of those args.
        default value can be set.
        automatically returns int/float values instead of string where needed.
        min/max can be set for integer/float values.
    """
    
    # blank value to start with. (until we confirm it exists)
    val = ""
    if isinstance(arg_names, (list, tuple)):
        # list of arg aliases was passed, try them all.
        for arg_ in arg_names:
            if request.REQUEST.has_key(arg_):
                val = request.REQUEST[arg_]
                break
    else:
        # single arg_name was passed.    
        if request.REQUEST.has_key(arg_names):
            val = request.REQUEST[arg_names]
    
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
    
    # default value is empty string if none was passed.
    if default_value is None:
        default_value = ""    
    # final return after processing,
    # will goto default value if val is empty.
    if val == "":
        val = default_value
    return val
        

def get_request_args(request):
    """ returns a dict of all request args (for testing) """
    
    return request.REQUEST

    
def wsgi_error(request, smessage):
    """ print message to requests wsgi errors """
    
    request.META['wsgi_errors'] = smessage
   

def get_paged_args(request, total_count):
    """ retrieve request arguments for paginated post/tag lists.
        total count must be given to calculate last page.
        returns dict with arg names as keys, and values.
    """

    # get order_by
    order_by_ = get_request_arg(request, ['order_by','order'], '-posted')
        
    # get max_posts
    max_ = get_request_arg(request, ['max_items','max'], 25, min_val=1, max_val=100)
    
    # get start_id
    start_id = get_request_arg(request, ['start_id','start'], 0, min_val=0, max_val=9999)
    # calculate last page based on max_posts
    last_page = ( total_count - max_ ) if ( total_count > max_ ) else 0
    # fix starting id.
    if isinstance(start_id, (str, unicode)):
        if start_id.lower() == 'last':
            start_id = last_page
        #elif ((start_id.lower() == 'first') or # not needed. duh. (see below) 
        #      (start_id.lower() == 'start')):
        #    start_id = 0
        else:
            # this shouldn't happen, get_request_arg() returns an integer or float
            # if a good integer/float value was passed. So any unexpected string value
            # means someone is messing with the args in a way that would break the view.
            # so if the conditions above aren't met ('last' or 'first'), it defaults to a safe value (0).
            start_id = 0
        
    # fix maximum start_id (must be within the bounds)
    if start_id > (total_count - 1):
        start_id = total_count - 1
         
    # get prev page (if previous page is out of bounds, just show the first page)
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