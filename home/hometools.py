#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
      project: welborn productions - home - tools
     @summary: various functions for home views
               (latest blog, featured project, news, etc.)

      @author: Christopher Welborn <cj@welbornproductions.net>
@organization: welborn productions <welbornproductions.net>

   start date: Apr 1, 2013
'''
import logging
import os
import os.path  # @UnusedImport: os is used.

# Home settings
from .models import home_config


# Blog/Projects info
from blogger.models import wp_blog
from projects.models import wp_project
from apps.models import wp_app

# Local tools
from wp_main.utilities import utilities

log = logging.getLogger('wp.home.tools')


def get_featured_app(config=None):
    """ retrieve the featured web app from home_config
        as a wp_app object.
        if the app isn't found, return None.
        A prefetched home_config can be passed to cut down on sql queries.
    """
    if config is None:
        config = home_config.objects.get()
    try:
        app = config.featured_app
        return app if app else get_latest_app()
    except Exception as ex:
        log.error('Unable to retrieve featured app:\n{}'.format(ex))
    return get_latest_app()


def get_featured_blog(config=None):
    """ retrieve the featured blog post from home_config
        as a wp_blog object.
        if the post isn't set or can't be retrieved, the latest post is used.
        returns None on ultimate failure.
        A prefetched home_config can be passed to cut down on sql queries.
    """
    if config is None:
        config = home_config.objects.get()
    try:
        post = config.featured_blog
        return post if post else get_latest_blog()
    except Exception as ex:
        log.error('Unable to retrieve featured blog post:\n{}'.format(ex))
        return get_latest_blog()


def get_featured_project(config=None):
    """ retrieve the featured project from home_config
        as a wp_project object.
        if the project isn't found, we will use the last published
        project.
        returns wp_project object.
        A prefetched home_config can be passed to cut down on sql queries.
    """
    if config is None:
        config = home_config.objects.get()
    try:
        # get featured project by alias.
        proj = config.featured_project
        return proj if proj else get_latest_project()
    except Exception as ex:
        # bad alias?
        log.error('Unable to retrieve featured project:\n{}'.format(ex))
    return get_latest_project()


def get_latest_app():
    """ retrieve the last published web app (wp_app object) """
    try:
        app = wp_app.objects.filter(disabled=False).latest('publish_date')
    except Exception as ex:
        log.error('Unable to retrieve latest app:\n{}'.format(ex))
        return None
    return app


def get_latest_blog():
    """ retrieve the last posted blog entry (wp_blog object)"""

    try:
        post = (
            wp_blog.objects.filter(disabled=False).latest('posted_datetime')
        )
    except Exception as ex:
        log.error('Unable to retrieve latest blog post:\n{}'.format(ex))
        return None
    return post


def get_latest_project():
    """ retrieve the last published project (wp_project object) """

    try:
        proj = (
            wp_project.objects.filter(disabled=False).latest('publish_date')
        )
    except Exception as ex:
        log.error('Unable to retrieve latest project:\n{}'.format(ex))
        return None
    return proj


def get_scriptkid_image():
    """ returns a random image filename from /static/images/scriptkids """

    import random
    image_dir = utilities.get_absolute_path('/static/images/scriptkids')
    goodexts = ('.jpeg', '.jpg', '.png', '.gif', '.bmp')
    try:
        images = [
            imgfile
            for imgfile in os.listdir(image_dir)
            if os.path.splitext(imgfile)[-1].lower() in goodexts
        ]
    except Exception as ex:
        log.error('Can\'t do listdir() on {!r}\n  {}'.format(
            image_dir,
            ex,
        ))
        return None
    if not images:
        log.error('Script kid images are empty!')
        return None

    randomindex = random.randint(0, len(images) - 1)
    return os.path.join(image_dir, images[randomindex])
