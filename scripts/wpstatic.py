#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" wpstatic.py
    ...some tools to work with static files for Welborn Prod.
    -Christopher Welborn 08-30-2014
"""

from docopt import docopt
import os
import re
import sys

try:
    import django_init
    if not django_init.init_django():
        sys.exit(1)
except ImportError as eximp:
    print('Unable to import django_init.py, this won\'t work.')
    print('Error: {}'.format(eximp))
    sys.exit(1)

# Import django stuff.
from django.conf import settings

NAME = 'WpStatic'
VERSION = '0.0.1'
VERSIONSTR = '{} v. {}'.format(NAME, VERSION)
SCRIPT = os.path.split(os.path.abspath(sys.argv[0]))[1]
SCRIPTDIR = os.path.abspath(sys.path[0])

USAGESTR = """{versionstr}
    Usage:
        {script} [-h | -v]
        {script} -a | -c

    Options:
        -a,--analyze  : Analyze static files dirs but don't change anything.
        -c,--clean    : Analyze and clean the static files dir.
        -h,--help     : Show this help message.
        -v,--version  : Show version.

    * With no arguments the default action is --analyze.
""".format(script=SCRIPT, versionstr=VERSIONSTR)

IGNORECOLLECTED = [
    #'admin',
    'debug_toolbar',
    'django_extensions',
]

IGNOREDPAT = re.compile('/?(({}))'.format(')|('.join(IGNORECOLLECTED)))


def main(argd):
    """ Main entry point, expects doctopt arg dict as argd """
    if argd['--clean']:
        raise NotImplementedError('No --clean yet.')
    else:
        # Analyze the dirs.
        print('Gathering collected files...')
        collected = get_collected()

        print('Gathering development files...')
        development = get_development()

        colnodev = collected.difference(development)
        devnocol = development.difference(collected)

        if colnodev:
            print('\nCollected files not in development:')
            print('    {}'.format('\n    '.join(colnodev)))
            colnodevlen = len(colnodev)
            fileplural = 'file' if colnodevlen == 1 else 'files'
            print('\nFound {} {} not in development.'.format(
                colnodevlen,
                fileplural))
        else:
            print('\nAll collected files are from development.')

        if devnocol:
            print('\nDevelopment files not in collected:')
            print('    {}'.format('\n    '.join(devnocol)))
            devnocollen = len(devnocol)
            fileplural = 'file' if devnocollen == 1 else 'files'
            print('\nFound {} {} not in collected.'.format(
                devnocollen,
                fileplural))
        else:
            print('\nAll development files have been collected.')

    return 0


def get_collected():
    """ Gather files from the collected static dir. """
    collected = set()
    for root, dirs, files in os.walk(settings.STATIC_ROOT):
        for f in files:
            fullpath = os.path.join(root, f)
            relativeparts = fullpath.split('static')[1:]
            relpath = 'static'.join(relativeparts)
            if IGNOREDPAT.match(relpath):
                continue
            collected.add(relpath)
    return collected


def get_development():
    """ Gather files from the development static dirs. """
    development = set()
    for root, dirs, files in os.walk(settings.BASE_DIR):
        if not 'static' in root:
            continue
        for f in files:
            fullpath = os.path.join(root, f)
            relativeparts = fullpath.split('static')[1:]
            development.add('static'.join(relativeparts))
    return development


if __name__ == '__main__':
    mainret = main(docopt(USAGESTR, version=VERSIONSTR))
    sys.exit(mainret)