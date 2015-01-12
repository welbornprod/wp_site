""" Welborn Productions - Stats - Tools
    Tools for gathering info about other models and their counts.
    (downloads, views, etc.)
"""

from functools import partial

from wp_main.utilities import (
    utilities,
    wp_logging
)

_log = wp_logging.logger('stats.tools').log


def get_models_info(modelinfo):
    """ Retrieve several model's info.
        Returns a list of StatsGroup on success, or [] on failure.
        Arguments:
            modelinfo  : A dict with Models as keys, and for values it has a
                         dict of options.
                         Example:
                            get_models_info({wp_blog: {'orderby': '-posted'}})
    """
    allstats = []
    for model, modelopts in modelinfo.items():
        modelgrp = get_model_info(
            model,
            orderby=modelopts.get('orderby', None))
        if modelgrp:
            allstats.append(modelgrp)
    return sorted(allstats, key=lambda sgrp: str(sgrp.name))


def get_model_info(model, orderby=None):
    """ Retrieves info about a model's objects.
        Returns a StatsGroup on success, or None on failure.
    """
    if not hasattr(model, 'objects'):
        _log.error('Model with no objects attribute!: {}'.format(model))
        return None

    # Try getting Model._meta.verbose_name_plural. Use None on failure.
    name = getattr(getattr(model, '_meta', None), 'verbose_name_plural', None)
    # Build a new StatsGroup to use.
    stats = StatsGroup(name=name)
    if orderby:
        if not validate_orderby(model, orderby):
            _log.error('Invalid orderby for {}: {}'.format(name, orderby))
            return None
        get_objects = partial(model.objects.order_by, orderby)
    else:
        get_objects = model.objects.all

    try:
        for obj in get_objects():
            statitem = get_object_info(obj)
            if statitem:
                stats.items.append(statitem)
    except Exception as ex:
        _log.error('Error getting objects from: {}\n{}'.format(name, ex))

    return stats if stats else None


def get_object_info(obj):
    """ Retrieves a single objects info.
        Returns a StatsItem (with name, download_count, view_count).
    """

    dlcount = getattr(obj, 'download_count', None)
    viewcount = getattr(obj, 'view_count', None)
    name = None
    # The order of these attributes matters. (we want shortname before name)
    for obj_id_attr in ('shortname', 'slug', 'name'):
        name = getattr(obj, obj_id_attr, None)
        if name:
            break
    else:
        _log.error('Object without a name!: {}'.format(obj))
    return StatsItem(name=name, download_count=dlcount, view_count=viewcount)


def validate_orderby(modelobj, orderby):
    """ Make sure this orderby is valid for this modelobj.
        It knows about the  '-orderby' style.
        Returns True if the orderby is good, else False.
    """

    try:
        tempobj = modelobj.objects.create()
    except Exception as ex:
        if hasattr(modelobj, '__name__'):
            mname = modelobj.__name__
        else:
            mname = 'unknown model'
        errmsg = '\nUnable to create temp object for: {}\n{}'
        _log.error(errmsg.format(mname, ex))
        return None
    if orderby.startswith('-'):
        orderby = orderby.strip('-')
    goodorderby = hasattr(tempobj, orderby)
    # Delete the object that was created to test the orderby attribute.
    tempobj.delete()
    return goodorderby


class _NoValue(object):

    """ Something other than None to mean 'No value set'.
        It can mean 'missing this attribute originally'.
    """

    def __bool__(self):
        """ NoValue is like None, bool(NoValue) is always False. """
        return False

NoValue = _NoValue()


class StatsGroup(object):

    """ Holds a collection of stats with a name (Projects, Posts, etc.)
        Each item in .items will be a StatsItem().
    """

    def __init__(self, name=None, items=None):
        self.name = name or 'Unknown'
        self.items = items or []

    def __bool__(self):
        """ Returns True if any(self.items). """
        return any(self.items)

    def __repr__(self):
        """ A short and simple str representation for this group. """
        return '{}: ({} items)'.format(self.name, len(self.items))

    def __str__(self):
        """ A formatted str for this stats group. """
        return '{}:\n    {}'.format(
            self.name,
            '\n    '.join(
                (str(i).replace('\n', '\n    ') for i in self.items)))


class StatsItem(object):

    """ A single item with a name, download_count, and view_count. """

    def __init__(self, name=None, download_count=None, view_count=None):
        self.name = name or NoValue
        if download_count is None:
            self.download_count = NoValue
        else:
            self.download_count = download_count
        if view_count is None:
            self.view_count = NoValue
        else:
            self.view_count = view_count

    def __bool__(self):
        """ Returns False if all attributes are set to NoValue. """
        return not (
            (self.name is NoValue) and
            (self.download_count is NoValue) and
            (self.view_count is NoValue))

    def __repr__(self):
        """ Basic str representation. """
        name = 'No Name' if self.name is NoValue else self.name
        return '{}: {}, {}'.format(name, self.download_count, self.view_count)

    def __str__(self):
        name = 'No Name' if self.name is NoValue else self.name
        infolines = []
        if self.download_count is not NoValue:
            infolines.append('    downloads: {}'.format(self.download_count))
        if self.view_count is not NoValue:
            infolines.append('        views: {}'.format(self.view_count))
        if infolines:
            return '{}\n{}'.format(name, '\n'.join(infolines))
        # A stats item with no info!
        return '{} (No Info!)'.format(name)