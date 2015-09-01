#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
          project: utilities.py
         @summary: various tools/utilities for Welborn Prod.

          @author: Christopher Welborn <cj@welbornprod.com>
    @organization: welborn productions <welbornprod.com>
"""
import logging
import os
import sys
import traceback
from datetime import datetime

from django.conf import settings
# Import modules within this project.
from django.utils.module_loading import import_module

# User-Agent helper...
from wp_user_agents.utils import get_user_agent

log = logging.getLogger('wp.utilities')


class _NoValue(object):

    """ Something other than 'None' to represent no value, or missing attr. """

    def __bool__(self):
        """ NoValue is falsey. """
        return False

    def __str__(self):
        return 'NoValue'
NoValue = _NoValue()


def append_path(*args):
    """ os.path.join fails if append_this starts with '/'.
        so I made my own. it's not as dynamic as os.path.join, but
        it will work. It doesn't short-circuit to a root dir when using
        args like 'home', '/wp'.
        ex:
            mypath = append_path('/view' , project.source_dir)
    """
    spath = '/'.join(args)
    while '//' in spath:
        spath = spath.replace('//', '/')
    return spath


def debug_allowed(request):
    """ returns True if the debug info is allowed for this ip/request.
        inspired by debug_toolbar's _show_toolbar() method.
    """

    # full test mode, no debug allowed (as if it were the live site.)
    if getattr(settings, 'TEST', False):
        return False

    # If this is local development, we allow it.
    if settings.SERVER_LOCATION.lower() == 'local':
        return True

    # If user is admin/authenticated we're okay.
    if request.user.is_authenticated() and request.user.is_staff:
        return True
    else:
        if 'test' in settings.SITE_VERSION.lower():
            return False

    # Non-authenticated users:
    # Get ip for this user
    remote_addr = get_remote_ip(request)
    if not remote_addr:
        return False

    # run address through our quick debug security check
    # (settings.INTERNAL_IPS and settings.DEBUG)
    ip_in_settings = (remote_addr in settings.INTERNAL_IPS)
    # log all invalid ips that try to access debug
    if settings.DEBUG and (not ip_in_settings):
        ipwarnmsg = '\n'.join((
            'Debug not allowed for ip: {}'.format(str(remote_addr)),
            '             ...DEBUG is: {}'.format(str(settings.DEBUG))))
        log.warn(ipwarnmsg)
    return (ip_in_settings and bool(settings.DEBUG))


def get_absolute_path(relative_file_path):
    """ return absolute path for file, if any
        returns empty string on failure.
        restricted to public STATIC_PARENT dir.
        if no_dir is True, then only file paths are returned.
    """

    if relative_file_path == "":
        return ""

    # Guard against ../ tricks.
    if '..' in relative_file_path:
        return ''

    sabsolutepath = ''
    # Remove '/static' from the file path.
    if relative_file_path.startswith(('static', '/static')):
        staticparts = relative_file_path.split('/')
        if len(staticparts) > 1:
            staticstart = 2 if relative_file_path.startswith('/') else 1
            staticpath = '/'.join(staticparts[staticstart:])
            # use new relative path (without /static)
            relative_file_path = staticpath
        else:
            # Don't allow plain '/static'
            return ''

    # Walk real static dir.
    for root, dirs, files in os.walk(settings.STATIC_ROOT):  # noqa
        spossible = os.path.join(root, relative_file_path)
        if os.path.exists(spossible):
            sabsolutepath = spossible
            break

    # Guard against files outside of the public /static dir.
    if not sabsolutepath.startswith(settings.STATIC_ROOT):
        return ''

    return sabsolutepath


def get_apps(
        exclude=None, include=None, name_filter=None,
        child=None, no_django=True):
    """ Returns a list of modules (apps) from INSTALLED_APPS.
        Arguments:
            exclude     : A function to exclude modules from being added.
                          It should return True to exclude, False to not.
                          It's signature is:
                          exclude(module) -> bool
                          Default: None
            include     : A function to include modules to be added.
                          It should return True to include, False to not.
                          It's signature is:
                          include(module) -> bool
                          Default: None
            name_filter : A function to include modules by name.
                          It should return True to include, False to not.
                          It's signature is:
                          name_filter(appname) -> bool
            child       : A str containing child modules to load instead of
                          the parent apps.
                          Example: (grab all apps with a 'search' module)
                              # Import all <app_name>.search
                              apps = get_apps(child='search')
                          Default: None
            no_django   : True/False. Whether to exclude modules
                          starting with 'django'.
                          Default: True
    """
    apps = []
    for appname in settings.INSTALLED_APPS:
        if no_django and appname.startswith('django'):
            continue
        elif name_filter and not name_filter(appname):
            continue
        if child:
            childname = '{}.{}'.format(appname, child.strip('.'))
        else:
            childname = appname
        try:
            app = import_module(childname)
            if exclude and exclude(app):
                continue
            elif include and include(app):
                apps.append(app)
        except ImportError as ex:
            log.debug('Module wasn\'t imported: {}\n  {}'.format(
                childname, ex))

    return apps


def get_attrs(o, attrs, default=NoValue):
    """ Like getattr(), but accepts dotted names to retrieve attributes of
        another attribute. Like: o.image.name
        It will first try o.image, and on success try o.image.name.
        None is an acceptable default, and will return None on failure.
        To raise AttributeError, simply don't provide any default argument.

        Example: val = get_attrs(obj, 'image.name', default=None)

        Returns default on failure if set, otherwise raises AttributeError.
    """
    if not attrs:
        raise AttributeError('You must provide attributes to retrieve.')

    def attr_return(obj, val, attr):
        """ Determine whether AttributeError should be raised,
            or the default should be returned.
        """
        if val is NoValue:
            if default is NoValue:
                errmsg = '{} has no attribute: {} from ({})'.format(
                    obj.__class__.__name__,
                    attr,
                    attrs)
                raise AttributeError(errmsg)
            return default
        return val

    def try_attr(obj, attr):
        """ Try getting an attribute, raise AttributeError if no default is
            provided, otherwise return the default.
        """
        val = getattr(obj, attr, NoValue)
        return attr_return(obj, val, attr)

    attrlst = tuple((a for a in attrs.split('.') if a))
    root = try_attr(o, attrlst[0])
    lastroot = o
    subattr = NoValue
    for subattr in attrlst[1:]:
        lastroot = root
        root = try_attr(lastroot, subattr)

    if subattr is NoValue:
        return attr_return(lastroot, root, attrlst[0])
    return attr_return(lastroot, root, subattr)


def get_browser_name(request):
    """ return the user's browser name """

    # get user agent
    user_agent = get_user_agent(request)
    return user_agent.browser.family.lower()


def get_browser_style(request):
    """ return browser-specific css file (or None if not needed) """

    browser_name = get_browser_name(request)
    # get browser css to use...
    if browser_name.startswith('ie'):
        return '/static/css/main-ie.min.css'

    return None


def get_date(date=None, shortdate=False):
    """ Return a string from a datetime object, or now() when `date` is empty.
        Arguments:
            date       : Existing datetime object to format.
                         Default: datetime.now()
            shortdate  : Return date in short format (m-d-yyyy)
                         Default: False
    """
    if date is None:
        date = datetime.now()
    if shortdate:
        return date.strftime('%m-%d-%Y')
    return date.strftime('%A %b. %d, %Y')


def get_datetime(date=None, shortdate=False):
    """ Return date/time string.
        Arguments:
            date       : Existing datetime object to format.
                         Default: datetime.now()
            shortdate  : Return date part in short format (m-d-yyyy)
                         Default: False
    """
    if date is None:
        date = datetime.now()
    if shortdate:
        return date.strftime('%m-%d-%Y %I:%M:%S %p')
    return date.strftime('%A %b. %d, %Y %I:%M:%S %p')


def get_filename(file_path):
    if not file_path:
        return file_path
    try:
        sfilename = os.path.split(file_path)[1]
    except Exception:
        log.error('Error in os.path.split({})'.format(file_path))
        sfilename = file_path
    return sfilename


def get_objects_enabled(objects_):
    """ Safely retrieves all objects where disabled == False.
        Handles 'no objects', returns [] if there are no objects.
    """

    # Model was passed instead of model.objects.
    if hasattr(objects_, 'objects'):
        objects_ = getattr(objects_, 'objects')

    try:
        allobjs = objects_.filter(disabled=False)
    except Exception as ex:
        log.error('No objects to get!: {}\n{}'.format(objects_.__name__, ex))
        allobjs = None

    return allobjs


def get_object_safe(objects, **kwargs):
    """ does a mymodel.objects.get(kwargs),
        returns None on error.
    """
    if hasattr(objects, 'objects'):
        # Main Model passed instead of Model.objects.
        objects = getattr(objects, 'objects')

    try:
        obj = objects.get(**kwargs)
    except Exception:
        # No Error is raised, just return None
        return None
    return obj

# Alias for function.
get_object = get_object_safe


def get_relative_path(spath):
    """ removes base path to make it django-relative.
        if its a '/static' related dir, just trim up to '/static'.
    """

    if not spath:
        return ''

    prepend = ''
    if settings.STATIC_ROOT in spath:
        spath = spath.replace(settings.STATIC_ROOT, '')
        prepend = '/static'
    elif settings.BASE_PARENT in spath:
        spath = spath.replace(settings.BASE_PARENT, '')
    if spath and (not spath.startswith('/')):
        spath = '/{}'.format(spath)

    if prepend:
        spath = '{}{}'.format(prepend, spath)

    return spath


def get_remote_host(request):
    """ Returns the HTTP_HOST for this user. """

    host = request.META.get('REMOTE_HOST', None)
    return host


def get_remote_ip(request):
    """ Just returns the IP for this user
        (for ip.html, debug_allowed(), etc.)
    """
    # possible ip forwarding, if available use it.
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', None)
    if x_forwarded_for:
        remote_addr = x_forwarded_for.split(',')[0].strip()
    else:
        remote_addr = request.META.get('REMOTE_ADDR', None)
    return remote_addr


def get_server(request):
    """ Return the current server/hostname for a request. """
    if not request:
        return None

    try:
        meta = request.META
    except AttributeError as exatt:
        log.error('Unable to retrieve META from request:\n'
                  '{}'.format(exatt))
        return None

    tryattrs = (
        'SERVER_NAME',
        'HTTP_X_FORWARDED_SERVER',
        'HTTP_HOST',
        'HTTP_X_FORWARDED_HOST',
    )
    for attr in tryattrs:
        server = meta.get(attr, None)
        if server is not None:
            return server

    # None of those attributes were filled out in request.META.
    return None


def get_time(time=None, shorttime=False,):
    """ Return time string.
        Arguments:
            time       : Existing datetime object to format.
                         Default: datetime.now()
            shorttime  : Return time in short format (without am/pm)
                         Default: False
    """
    if time is None:
        time = datetime.now()
    if shorttime:
        return time.strftime('%I:%M:%S')
    return time.strftime('%I:%M:%S %p')


def get_time_since(date, humanform=True, limit=False):  # noqa
    """ Parse a datetime object,
        return human-readable time-elapsed.
        Arguments:
            date       : datetime object to work with.
            humanform  : Use minutes, seconds, etc. instead of m, s, etc.
            limit      : If True, uses get_datetime() when it's been over one
                         week.
    """

    secs = (datetime.now() - date).total_seconds()
    if secs < 60:
        if humanform:
            # Right now.
            if secs < 0.1:
                return ''
            # Seconds (decimal format)
            return '{:0.1f} seconds'.format(secs)
        else:
            # Seconds only.
            return '{:0.1f}s'.format(secs)

    minutes = secs / 60
    seconds = int(secs % 60)
    minstr = 'minute' if int(minutes) == 1 else 'minutes'
    secstr = 'second' if seconds == 1 else 'seconds'
    if minutes < 60:
        # Minutes and seconds only.
        if humanform:
            if seconds == 0:
                # minutes
                return '{} {}'.format(int(minutes), minstr)
            # minutes, seconds
            fmtstr = '{} {}, {} {}'
            return fmtstr.format(int(minutes), minstr, seconds, secstr)
        else:
            # complete minutes, seconds
            fmtstr = '{}m:{}s'
            return fmtstr.format(int(minutes), seconds)

    hours = minutes / 60
    minutes = int(minutes % 60)
    hourstr = 'hour' if int(hours) == 1 else 'hours'
    minstr = 'minute' if minutes == 1 else 'minutes'
    if hours < 24:
        # Hours, minutes, and seconds only.
        if humanform:
            if minutes == 0:
                # hours
                return '{} {}'.format(int(hours), hourstr)
            # hours, minutes
            fmtstr = '{} {}, {} {}'
            return fmtstr.format(int(hours), hourstr, minutes, minstr)
        else:
            # complete hours, minutes, seconds
            fmtstr = '{}h:{}m:{}s'
            return fmtstr.format(int(hours), hourstr, minutes, seconds)

    days = int(hours / 24)
    hours = int(hours % 24)
    if limit and (days > 7):
        return get_datetime(date)

    # Days, hours
    daystr = 'day' if days == 1 else 'days'
    hourstr = 'hour' if hours == 1 else 'hours'
    if humanform:
        if hours == 0:
            # days
            return '{} {}'.format(days, daystr)
        # days, hours
        fmtstr = '{} {}, {} {}'
        return fmtstr.format(days, daystr, hours, hourstr)
    else:
        # complete days, hours, minutes, seconds
        fmtstr = '{}d:{}h:{}m:{}s'
        return fmtstr.format(days, hours, minutes, seconds)


def is_file_or_dir(spath):
    """ returns true if path is a file, or is a dir. """

    return (os.path.isfile(spath) or os.path.isdir(spath))


def is_mobile(request):
    """ Determine if the client is a mobile phone/tablet
        actually, determine if its not a pc.
    """

    if request is None:
        # happens on template errors,
        # which hopefully never make it to production.
        return False

    return (not get_user_agent(request).is_pc)


def is_textmode(request):
    """ Return True if the User Agent is a known text mode browser. """
    if request is None:
        # An error would cause this.
        return False
    ua = getattr(get_user_agent(request), 'ua_string', '').lower()
    return (
        ('curl' in ua) or
        ('textmode' in ua) or
        ('elinks' in ua) or
        ('lynx' in ua)
    )


def logtraceback(log=None, message=None):
    """ Log the latest traceback.
        Arguments:
            log      : Function that accepts a string as its first argument.
                       If None is passed, print() will be used.
                       The idea is to use myloggingobject.error.
            message  : Optional additional message to log.

        Returns a list of all lines logged.
    """
    typ, val, tb = sys.exc_info()
    tbinfo = traceback.extract_tb(tb)
    linefmt = ('Error in:\n'
               '  {fname}, {funcname}(),\n'
               '    line {num}: {txt}\n'
               '    {typ}:\n'
               '      {msg}')
    if log is None:
        log = print

    logged = []
    for filename, lineno, funcname, txt in tbinfo:
        # Build format() args from the tb info.
        fmtargs = {
            'fname': filename,
            'funcname': funcname,
            'num': lineno,
            'txt': txt,
            'typ': typ,
            'msg': val,
        }
        # Report the error.
        if message is None:
            logmsg = linefmt.format(**fmtargs)
        else:
            logmsg = '{}\n{}'.format(message, linefmt.format(**fmtargs))
        log(logmsg)
        logged.append(logmsg)
    return logged


def parse_bool(s):
    """ Parse a string as a boolean.
        Values for True: '1', 'T[rue]', 't[rue]', 'Y[es]', 'y[es]'
        Values for False: ..everything else.
    """
    if s:
        return s.lower().startswith(('1', 't', 'y'))
    return False


def remove_list_dupes(lst, max_allowed=1):
    """ removes duplicates from a list object.
        default allowed duplicates is 1, you can allow more if needed.
        minimum allowed is 1. this is not a list deleter.
    """
    if max_allowed <= 1:
        try:
            new = lst.__class__(set(lst))
        except Exception as ex:
            log.error(
                'Incompatible type passed: {}\n{}'.format(lst.__class__, ex)
            )
        else:
            return new

    # Modify a copy, the original should remain untouched (even lists)
    # Tuples have to be copied anyway.
    copy = list(lst)
    for item in lst:
        while copy.count(item) > max_allowed:
            copy.remove(item)

    return copy


def safe_arg(url):
    """ basically just trims one / from the POST args right now """
    s = url[:-1] if url.endswith('/') else url
    return s[1:] if s.startswith('/') else s


def slice_list(lst, start=0, max_items=-1):
    """ slice a list starting at: starting index.
        if max_items > 0 then only that length of items is returned.
        otherwise, all items are returned.
    """
    if not lst:
        return []
    if max_items > 0:
        return lst[start: start + max_items]
    return lst[start:]


def trim_special(source):
    """ removes all html, and other code related special chars.
        so <tag> becomes tag, and javascript.code("write");
        becomes javascriptcodewrite.
        to apply some sort of safety to functions that generate html strings.
        incase someone did this (all one line):
            welbornprod.com/blog/tag/<script type="text/javascript">
                document.write("d");
            </script>
    """
    if not source:
        return source
    special = '<>/.\'"#!;:\\&='
    return ''.join((c for c in source if c not in special))
