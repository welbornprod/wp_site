import logging
from django.http import Http404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import cache_page

from wp_main.utilities import responses

from misc import tools as misctools

log = logging.getLogger('wp.misc')


@cache_page(15 * 60)
@csrf_protect
def view_index(request):
    """ Main index for Misc objects. """
    context = {
        'miscobjects': misctools.get_visible_objects()
    }
    return responses.clean_response(
        'misc/index.html',
        context=context,
        request=request)


@cache_page(15 * 60)
@csrf_protect
def view_misc_any(request, identifier):
    """ View a specific misc item. """

    misc = misctools.get_by_identifier(identifier)
    if not misc:
        # No misc item found by that identifier
        raise Http404()
    context = {
        'misc': misc,
    }
    return responses.clean_response(
        'misc/misc.html',
        context=context,
        request=request)
