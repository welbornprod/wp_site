#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" apttool.py
    provides a few apt-related functions based on the 'apt' module.
    -Christopher Welborn
    06-2013
"""

from datetime import datetime    # timing
import os.path                   # for file/dir
import re                        # search pattern matching
import sys                       # for args (Scriptname)
import weakref                   # for iterCache()

try:
    import apt                        # apt tools
    import apt_pkg                    # for iterCache()
    from apt_pkg import gettext as _  # for iterCache()
    import apt.progress.text          # apt tools
except ImportError as eximp:
    print('\nMissing important module or modules!\n{}'.format(eximp))
    print('\nThese must be installed:')
    print('      apt: ..uses apt.progress.text and others')
    print('  apt_pkg: ..uses apt_pkg.gettext and others.')
    print('\nTry doing: pip install <modulename>`\n')
    sys.exit(1)

try:
    from docopt import docopt        # cmdline arg parser
except ImportError as exdoc:
    print('\nDocopt must be installed, '
          'try: pip install docopt.\n\n{}'.format(exdoc))
    sys.exit(1)

_VERSION = "0.2.0"
_NAME = "AptTool"

# Get short script name.
_SCRIPTFILE = sys.argv[0]
_SCRIPTNAME = _SCRIPTFILE[2:] if _SCRIPTFILE.startswith('./') else _SCRIPTFILE
if '/' in _SCRIPTNAME:
    _SCRIPTNAME = os.path.split(_SCRIPTNAME)[1]

usage_str = """{propername} v. {version}

    Usage:
        {name} -c file [-o]
        {name} -i package
        {name} -d package | -p package
        {name} -e package | -f package
        {name} -h | -v
        {name} -u
        {name} -V package [-a]
        {name} <pkgname> [-I | -N] [-n] [-r] [-s]
        
    Options:
        -a,--all                     : When viewing package version, list all
                                       available versions.
        -c file,--containsfile file  : Search all installed packages for an
                                       installed file.
        -i pkg,--install pkg         : Install a package.
        -I,--INSTALLED               : When searching for a package, only
                                       include installed packages.
        -d pkg,--delete pkg          : Uninstall/delete/remove a package.
        -e pkg,--executables pkg     : Show installed executables for a
                                       package.
                                       It just shows files installed to
                                       /bin directories.
        -f pkg,--files pkg           : Show installed files for package.
        -h,--help                    : Show this help message and exit.
        -n,--names                   : When searching, only search names,
                                       not descriptions.
        -N,--NOTINSTALLED            : When searching for a package, only
                                       include non-installed packages.
        -o,--onlyname                : When searching with -c, don't include
                                       the path.
        -p pkg,--purge pkg           : Purge the package completely,
                                       remove all configuration.
        -s,--short                   : When searching, don't print the
                                       description. 
        -r,--reverse                 : When searching, return packages that
                                       DON'T match.
        -u,--update                  : Update the cache.
                                       ..Just like `apt-get update`
        -v,--version                 : Show version and exit.
        -V pkg,--VERSION pkg         : Show a package's installed or available
                                       versions.
        
    Notes:
        If no options are given, the default behaviour is to search for
        packages by name and description, then print results.
        
        In the search results:
            [i] = package is installed
            [u] = package is not installed
        
""".format(propername=_NAME, name=_SCRIPTNAME, version=_VERSION)

# CLASSES -----------------------------------------------


class oProgress(apt.progress.text.OpProgress):

    """ Handles progress updates for Operations """

    def __init__(self, msg=None):
        self.msg = msg if msg else 'Doing operation'
        self.current_percent = 0

    def update(self, percent=None):
        if percent:
            self.current_percent = percent

    def done(self, otherarg=None):
        self.current_percent = 0

    def set_msg(self, s):
        self.msg = s


class fProgress(apt.progress.text.TextProgress):

    """ Handles progress updates for Fetches """

    def __init__(self, msg=None):
        self.msg = msg if msg else 'Fetching'
        apt.progress.text.TextProgress.__init__(self)

    # existing pulse() function works pretty good, just leave it alone.
    def pulse(self, owner=None):
        if hasattr(apt.progress.text.TextProgress, 'pulse'):
            return apt.progress.text.TextProgress.pulse(self, owner)
        else:
            return True

    def start(self):
        print(self.msg)

    def stop(self):
        print('Finished ' + self.msg)

    def set_msg(self, s):
        self.msg = s


class iProgress(apt.progress.base.InstallProgress):

    """ Handles progress updates for Installs """

    def __init__(self, msg=None, pkgname=None):
        self.msg = msg if msg else 'Installing'
        self.pkgname = pkgname if pkgname else None

        apt.progress.base.InstallProgress.__init__(self)
        # Redirect dpkg's messages to stdout.
        self.writefd = sys.stdout

    def error(self, pkg, errormsg):
        """ Handles errors from dpkg. """

        print('\nError while installing: {}\n{}'.format(pkg.name, errormsg))

    def finish_update(self):
        """ Handles end of installation """

        if self.pkgname:
            print('\nFinished {}: {}'.format(self.msg.lower(), self.pkgname))


class iterCache(apt.Cache):

    """ Allows searching the package cache while loading. """

    def __init__(self, progress=None, rootdir=None,
                 memonly=False, do_open=True):
        self._cache = None
        self._depcache = None
        self._records = None
        self._list = None
        self._callbacks = {}
        self._weakref = weakref.WeakValueDictionary()
        self._set = set()
        self._fullnameset = set()
        self._changes_count = -1
        self._sorted_set = None

        self.connect('cache_post_open', self._inc_changes_count)
        self.connect('cache_post_change', self._inc_changes_count)
        if memonly:
            # force apt to build its caches in memory
            apt_pkg.config.set('Dir::Cache::pkgcache', '')
        if rootdir:
            if os.path.exists(rootdir + '/etc/apt/apt.conf'):
                apt_pkg.read_config_file(apt_pkg.config,
                                         rootdir + '/etc/apt/apt.conf')
            if os.path.isdir(rootdir + '/etc/apt/apt.conf.d'):
                apt_pkg.read_config_dir(apt_pkg.config,
                                        rootdir + '/etc/apt/apt.conf.d')
            apt_pkg.config.set('Dir', rootdir)
            apt_pkg.config.set('Dir::State::status',
                               rootdir + '/var/lib/dpkg/status')
            # also set dpkg to the rootdir path so that its called for the
            # --print-foreign-architectures call
            apt_pkg.config.set('Dir::bin::dpkg',
                               os.path.join(rootdir, 'usr', 'bin', 'dpkg'))
            # create required dirs/files when run with special rootdir
            # automatically
            self._check_and_create_required_dirs(rootdir)
            # Call InitSystem so the change to Dir::State::Status is actually
            # recognized (LP: #320665)
            apt_pkg.init_system()

        if do_open:
            self.open(progress)

    def _pre_iter_open(self, progress=None):
        """ Things to do before the actual iter_open,
            this allows you to get the rough size before iterating.
        """

        self._run_callbacks('cache_pre_open')

        self._cache = apt_pkg.Cache(progress)
        self._depcache = apt_pkg.DepCache(self._cache)
        self._records = apt_pkg.PackageRecords(self._cache)
        self._list = apt_pkg.SourceList()
        self._list.read_main_list()
        self._set.clear()
        self._fullnameset.clear()
        self._sorted_set = None
        self._weakref.clear()

        self._have_multi_arch = len(apt_pkg.get_architectures()) > 1
        self.rough_size = len(self._cache.packages)

    def iter_open(self, progress=None):
        """ Open the package cache, yielding packages as they are loaded
        """
        if progress is None:
            progress = apt.progress.base.OpProgress()
        self.op_progress = progress

        # Need to load the cache?
        if self._cache is None:
            self._pre_iter_open(progress=progress)

        progress.op = _('Building data structures')
        i = last = 0
        size = len(self._cache.packages)

        for pkg in self._cache.packages:
            if progress is not None and last + 100 < i:
                progress.update(i / float(size) * 100)
                last = i
            # drop stuff with no versions (cruft)
            if pkg.has_versions:
                pkgname = pkg.get_fullname(pretty=True)
                self._set.add(pkgname)
                if self._have_multi_arch:
                    self._fullnameset.add(pkg.get_fullname(pretty=False))
                # Yield this package as it is loaded...
                yield self.__getitem__(pkgname)

            i += 1

        progress.done()
        self._run_callbacks('cache_post_open')

    def iter_open_no_progress(self):
        """ same as iter_open, with no progress-related features.
            possible performance enhancement, not tested.
        """

        if self._cache is None:
            self._pre_iter_open(progress=None)

        for pkg in self._cache.packages:
            if pkg.has_versions:
                pkgname = pkg.get_fullname(pretty=True)
                self._set.add(pkgname)
                if self._have_multi_arch:
                    self._fullnameset.add(pkg.get_fullname(pretty=False))
                yield self.__getitem__(pkgname)


# Fatal Errors that when raised will end this script.
class BadSearchQuery(Exception):
    pass


class CacheNotLoaded(Exception):
    pass


# GLOBALS ------------------------------------------------
# custom progress reporters
oprogress = oProgress()

fprogress = fProgress()
# placeholder for global cache
cache_main = None


# MAIN ---------------------------------------------------
def main(dargs):
    """ Main entry point for apttool """
    global cache_main, oprogress, fprogress

    # initial return value.
    ret = 0
    # Search (iter_open the cache, not pre-load. for performance)
    if dargs['<pkgname>']:
        try:
            ret = cmdline_search(dargs['<pkgname>'],
                                 desc_search=(not dargs['--names']),
                                 print_no_desc=dargs['--short'],
                                 installed_only=dargs['--INSTALLED'],
                                 uninstalled_only=dargs['--NOTINSTALLED'])
        except KeyboardInterrupt:
            print('\nUser Cancelled, goodbye.')
            ret = 1
        # Quit after search.
        return ret

    # -----v-- Actions that may benefit from cache pre-loading --v------
    # Initialize
    print('Loading APT Cache...')
    cache_main = apt.Cache()
    if not cache_main:
        print('Failed to load apt cache!')
        return 1

    # Cache was loaded properly.
    print('Loaded {} packages.'.format(len(cache_main)))

    # Operations
    if dargs['--update']:
        # Update the cache (like: apt-get update)
        ret = update()
    elif dargs['--install']:
        # Install a package. (like: apt-get install)
        pkgname = dargs['--install']
        print('\nLooking for \'{}\'...'.format(pkgname))
        ret = install_package(pkgname)
    elif dargs['--executables']:
        # Show installed executables.
        pkgname = dargs['--executables']
        print('\nGetting installed executables for \'{}\'\n'.format(pkgname))
        ret = print_installed_files(pkgname, execs_only=True)
    elif dargs['--files']:
        # Show installed files.
        pkgname = dargs['--files']
        print('\nGetting installed files for \'{}\'\n'.format(pkgname))
        ret = print_installed_files(pkgname)
    elif dargs['--delete'] or dargs['--purge']:
        # Delete/Purge package
        pkgname = dargs['--delete'] if dargs['--delete'] else dargs['--purge']
        print('\nLooking for \'{}\'...'.format(pkgname))
        ret = remove_package(pkgname, purge=bool(dargs['--purge']))
    elif dargs['--VERSION']:
        # Show package version.
        pkgname = dargs['--VERSION']
        print('\nLooking for \'{}\'...'.format(pkgname))
        ret = print_package_version(pkgname, allversions=dargs['--all'])
    elif dargs['--containsfile']:
        # Search for installed file.
        ret = search_file(dargs['--containsfile'],
                          shortnamesonly=dargs['--onlyname'])
    # Finished.
    return ret


# FUNCTIONS -----------------------------------------------
def install_package(pkgname, doupdate=False):
    """ Install a package. """

    if doupdate:
        updateret = update()
        if updateret:
            print('\nCan\'t update cache!')

    if pkgname in cache_main.keys():
        package = cache_main[pkgname]
        if get_install_state(package):
            print('\nThis package is already installed: '
                  '{}'.format(package.name))
            return 1

        print('Installing package: {}'.format(package.name))
        # Mark for install.
        if not hasattr(package, 'mark_install'):
            print('\napt_pkg doesn\'t have \'mark_install\' attribute, '
                  'apt/apt_pkg module may be out of date.\n'
                  'Stopping.')
            return 1
        cache_main[pkgname].mark_install()
        # Install the package
        try:
            cache_main.commit(fetch_progress=fProgress(),
                              install_progress=iProgress(pkgname=pkgname))
        except apt.cache.LockFailedException as exlock:
            print('\nCan\'t install package, '
                  'make sure you have proper permissions. (are you root?)\n'
                  '\nError Message:\n{}'.format(exlock))
            return 1
        except SystemError as exsys:
            # dpkg is already being used by something else.
            print('\nCan\'t install package, '
                  'make sure all other package managers are closed.\n'
                  '\nError Message:\n{}'.format(exsys))
            return 1

    else:
        print('\nCan\'t find a package by that name: {}'.format(pkgname))
        return 1
    return 0


def is_search(dargs):
    """ check to see if any non-search options were passed,
        if no non-search-related args were passed then
        this is a search run.
    """

    no_args = []
    for opt, val in dargs.items():
        # These options are automatically valid for a search run.
        if opt in ('--update', '--names', '--short'):
            no_args.append(True)
        else:
            # test arg
            if opt.startswith('-'):
                no_args.append(not val)
    return all(no_args)


def cmdline_search(query, **kwargs):
    """ print results while searching the cache...
        Arguments:
            query             : Seach term for package name/desc.

        Keyword Arguments:
            desc_search       : If True, search descriptions.
                                Default: True
            print_no_desc     : If True, don't print descriptions of packages.
                                Default: False
            installed_only    : If True, only match installed packages.
                                Defaut: False
            uninstalled_only  : If True, only match non-installed palckages.
                                Default: False
    """

    desc_search = kwargs.get('desc_search', True)
    print_no_desc = kwargs.get('print_no_desc', False)
    installed_only = kwargs.get('installed_only', False)
    uninstalled_only = kwargs.get('uninstalled_only', False)
    if installed_only and uninstalled_only:
        print('\nMismatched args! -N and -I can\'t be used together!')
        return 1

    # try:
        # Initialize cache without doing an .open() (do iter_open() instead)
    print('Initializing Cache...')
    cache = iterCache(do_open=False)
    cache._pre_iter_open()
    print('Searching ~' + str(cache.rough_size) + ' packages for ' + query)

    result_cnt = 0
    for result in search_itercache(query,
                                   desc_search=desc_search,
                                   cache=cache,
                                   progress=None,
                                   installed_only=installed_only,
                                   uninstalled_only=uninstalled_only):
        print('\n{}'.format(format_result(result, no_desc=print_no_desc)))
        result_cnt += 1

    # except Exception as ex:
    #    print('Error while searching:\n' + str(ex))
    #    raise Exception(ex)

    result_str = ' result.' if result_cnt == 1 else ' results.'
    print('\nFinished searching, found ' + str(result_cnt) + result_str)
    return 0


def format_result(result, no_desc=False):
    """ prints a single search result to the console

        Keyword Arguments:
            no_desc : if True, only prints state and name.
    """

    # max text lengths
    total_len = 110
    desc_max = 60
    pkgname_max = (total_len - desc_max - 13)  # 13 extra chars added later

    # name formatting
    pkgname = result.name
    name_space_len = pkgname_max - len(pkgname)
    name_space = (' ' * name_space_len) if name_space_len > 0 else ' '

    # Format install state string...
    pkgstate = '[i] ' if get_install_state(result) else '[u] '
    # resulting left-hand side
    name_side = '    ' + pkgstate + result.name + name_space
    # No description needed RETURN only the name....
    if no_desc:
        return name_side

    # Get Package Description....
    pkgdesc_full = get_pkg_description(result)
    # No description to search?
    if not pkgdesc_full:
        return name_side

    name_side += ' : '

    # description slicing, remove newlines
    if '\n' in pkgdesc_full:
        pkgdesc_full = pkgdesc_full[:pkgdesc_full.index('\n')]

    if len(pkgdesc_full) <= desc_max:
        # already short description
        pkgdesc = pkgdesc_full
    else:
        # trim to 2 lines worth, or use first sentence.
        pkgdesc_full = pkgdesc_full[:(desc_max * 2)]
        if '.' in pkgdesc_full:
            # use first sentance.
            pkgline = pkgdesc_full[:pkgdesc_full.index('.') + 1]
        else:
            # use two lines of text.
            pkgline = pkgdesc_full
        padding = (' ' * len(name_side))
        pkgdesc_lines = [pkgline[:desc_max],
                         padding + pkgline[desc_max:].strip(' ')[:-4],
                         ]
        if pkgdesc_lines[1].strip(' ') == '':
            pkgdesc = pkgdesc_lines[0]
        else:
            pkgdesc = '\n'.join(pkgdesc_lines) + ' ...'

    return name_side + pkgdesc


def get_actual_package(possiblepkg):
    """ Returns the original package if this is the old apt API,
        If this is the new apt API, then further processing is done
        to retrieve the actual installed package.
    """

    if hasattr(possiblepkg, 'description'):
        return possiblepkg
    elif hasattr(possiblepkg, 'installed'):
        return possiblepkg.installed


def get_install_state(pkg):
    """ Returns True/False whether this package is installed.
        Uses old and new apt API methods.
    """

    if hasattr(pkg, 'isInstalled'):
        return pkg.isInstalled()
    elif hasattr(pkg, 'installed'):
        return (pkg.installed is not None)
    else:
        # API fell through?
        # (it has happened before, hince the need for the 2 ifs above)
        return False


def get_pkg_description(pkg):
    """ Retrieves package description using old and new apt API,
        Returns empty string on failure, or no description.
    """

    if hasattr(pkg, 'description'):
        desc = pkg.description if pkg.description else ''
    elif hasattr(pkg, 'installed'):
        installedpkg = pkg.installed
        if installedpkg:
            # Use installed version description
            desc = installedpkg.description if installedpkg.description else ''
        else:
            # Get first description found in all versions.
            desc = ''
            for ver in pkg.versions:
                if ver.description:
                    desc = ver.description
                    break

    else:
        desc = ''
    return desc


def print_installed_files(pkgname, execs_only=False):
    """ Print a list of installed files for a package. """

    if not pkgname in cache_main.keys():
        print('\nCan\'t find a package with that name: {}'.format(pkgname))
        return 1
    package = cache_main[pkgname]

    if not get_install_state(package):
        print(''.join(['\nThis package is not installed: ',
                       '{}'.format(package.name),
                       '\nCan\'t get installed files for ',
                       'uninstalled packages.']))
        return 1

    if not hasattr(package, 'installed_files'):
        print(''.join(['\nUnable to get installed files for ',
                       '{}'.format(package.name),
                       ', apt/apt_pkg module may be out of date.']))
        return 1

    files = sorted(package.installed_files)
    if execs_only:
        # Show executables only (/bin directory files.)
        files = [s for s in files if '/bin' in s]
        label = 'executables'
    else:
        # Show installed files.
        label = 'installed files'

    if files:
        print('Found {} {} for {}:'.format(len(files), label, package.name))
        print('    {}\n'.format('\n    '.join(sorted(files))))
        return 0

    # No files found (possibly after trimming to only executables)
    print('Found 0 {} for: {}'.format(label, package.name))
    return 1


def print_package_version(pkgname, allversions=False):
    """ Retrieve the current version for a package. """

    if not pkgname in cache_main.keys():
        print('\nCan\'t find a package with that name: {}'.format(pkgname))
        return 1

    package = cache_main[pkgname]

    if not hasattr(package, 'versions'):
        print(''.join(['\nUnable to retrieve versions for ',
                       '{}'.format(pkgname),
                       ', apt/apt_pkg may be out of date.']))
        return 1

    versions = [v.version for v in package.versions]
    if package.installed:
        installedver = package.installed.version
    else:
        installedver = None

    latestver = versions[0]
    latestinstalled = latestver == installedver
    versions[0] = '{} (latest)'.format(latestver)
    versions = ['{} (installed)'.format(v)
                if v.split()[0] == installedver else v for v in versions]

    if allversions:
        print('\nFound {} versions for: {}'.format(len(versions),
                                                   package.name))
        print('    {}'.format('\n    '.join(versions)))
    else:
        print('\nVersion:')
        if latestinstalled:
            fmtargs = package.name, installedver
            print('    {} {} (latest version is installed)\n'.format(*fmtargs))
        elif installedver:
            fmtargs = package.name, installedver, latestver
            fmtline = '    {} {} installed, latest version is: {}\n'
            print(fmtline.format(*fmtargs))
        else:
            fmtargs = package.name, latestver
            print('    {} {} (latest version available)\n'.format(*fmtargs))

    pkgdesc = get_pkg_description(package)
    print('Description:\n    {}\n'.format(pkgdesc.replace('\n', '\n    ')))

    return 0


def remove_package(pkgname, purge=False):
    """ Remove or Purge a package by name """

    if purge:
        opaction = 'purge'
        opstatus = 'Purging'
    else:
        opaction = 'remove'
        opstatus = 'Removing'

    if pkgname in cache_main.keys():
        package = cache_main[pkgname]
        if not get_install_state(package):
            print('\nThis package is not installed: {}'.format(package.name))
            return 1

        print('Removing package: {}'.format(package.name))
        # Mark for delete.
        if not hasattr(package, 'mark_delete'):
            print('\napt_pkg doesn\'t have \'mark_delete\' attribute, '
                  'apt/apt_pkg module may be out of date.\n'
                  'Stopping.')
            return 1
        cache_main[pkgname].mark_delete(purge=purge)
        # Remove the package
        try:
            cache_main.commit(fetch_progress=fProgress(),
                              install_progress=iProgress(pkgname=pkgname,
                                                         msg=opstatus))
        except apt.cache.LockFailedException as exlock:
            print(''.join([
                '\nCan\'t {} package, '.format(opaction),
                'make sure you have proper permissions. (are you root?)\n',
                '\nError Message:\n{}'.format(exlock),
            ]))
            return 1
        except SystemError as exsys:
            # dpkg is already being used by something else.
            print(''.join([
                'Can\'t {} package, '.format(opaction),
                'make sure all other package managers are closed.\n'
                '\nError Message:\n{}'.format(exsys),
            ]))
            return 1
    else:
        print('\nCan\'t find a package by that name: {}'.format(pkgname))
        return 1
    return 0


def search_file(name, shortnamesonly=False):
    """ Search all installed files for a filename.
        Print packages containing matches.
        Arguments:
            name            : Name or part of a name to search for

        Keyword Arguments:
            shortnamesonly  : don't include the full path in search,
                              just the short file name.
    """

    try:
        repat = re.compile(name)
    except Exception as ex:
        print('\nInvalid search term!: {}\n{}'.format(name, ex))
        return 1

    # Setup filename methods (long or short, removes an 'if' from the loop.)
    getfilenameshort = lambda s: os.path.split(s)[1]
    # Pick filename method.
    filenamefunc = getfilenameshort if shortnamesonly else (lambda s: s)

    # Iterate all packages...
    totalpkgs = 0
    totalfiles = 0
    try:
        for pkgname in cache_main.keys():
            pkg = cache_main[pkgname]
            matchingfiles = []
            if get_install_state(pkg):
                if not hasattr(pkg, 'installed_files'):
                    print(''.join(['\nUnable to retrieve installed files for ',
                                   '{}'.format(pkgname),
                                   ', apt/apt_pkg may be out of date!']))
                    return 1
                # Iterate all installed files.
                if not pkg.installed_files:
                    continue
                try:
                    for installedfile in pkg.installed_files:
                        shortname = filenamefunc(installedfile)
                        rematch = repat.search(shortname)
                        if rematch:
                            # Save match for report,
                            # (report when we're finished with this package.)
                            matchingfiles.append(installedfile)
                except KeyboardInterrupt:
                    print('\nUser cancelled.\n')
                    return 1
                # Report any matches.
                if matchingfiles:
                    totalpkgs += 1
                    totalfiles += len(matchingfiles)
                    print('\n{}'.format(pkgname))
                    print('    {}'.format('\n    '.join(matchingfiles)))
    except KeyboardInterrupt:
        print('\nUser cancelled.\n')
        return 1
        
    print('\nFound {} files in {} packages.'.format(totalfiles, totalpkgs))
    return 0


def update(load_cache=False):
    """ update the cache, 
        init or re-initialize the cache if load_cache is True
    """
    global cache_main
    if load_cache:
        cache_main = apt.Cache()

    try:
        cache_main.update(fProgress(msg='Updating...'))
        cache_main.open(progress=oProgress(msg='Opening cache...'))
        print('Loaded ' + str(len(cache_main.keys())) + ' packages.')
    except KeyboardInterrupt:
        print('\nUser cancelled.\n')
    except apt.cache.FetchFailedException as exfail:
        print('\nFailed to complete download.\n{}'.format(exfail))
    except Exception as ex:
        print('\nError during update!:\n{0}\n'.format(ex))
    return True


def search_itercache(regex, **kwargs):
    """ search while building the cache,
        Arguments:
            regex             :  regex pattern to search for

        Keyword Arguments:
            desc_search       : if True, search through descriptions also,
                                not just names.
                                Default: True
            installed_only    : if True, only search installed packages.
                                Default: False
            uninstalled_only  : if True, only search non-installed packages.
                                Default: False
            reverse           : if True, yield packages that DON'T match.
                                Default: False
            progress          : apt.OpProgress() to report to on iter_open()
                                Default: None
            cache             : initialized (not .open()ed iterCache())
                                if you need to do it yourself.
    """

    # parse args
    desc_search = kwargs.get('desc_search', True)
    progress = kwargs.get('progress', None)
    reverse = kwargs.get('reverse', False)
    installed_only = kwargs.get('installed_only', False)
    uninstalled_only = kwargs.get('uninstalled_only', False)

    # initialize Cache object without opening,
    # or use existing cache passed in with cache keyword.
    cache = kwargs.get('cache', iterCache(do_open=False))

    if cache is None:
        raise CacheNotLoaded('No apt cache to search.')

    try:
        re_pat = re.compile(regex)
    except Exception as ex:
        raise BadSearchQuery(str(ex))

    # iterate the pkgs as they are loaded.
    for pkg in cache.iter_open(progress=progress):
        if is_pkg_match(re_pat, pkg,
                        desc_search=desc_search,
                        reverse=reverse,
                        installed_only=installed_only,
                        uninstalled_only=uninstalled_only):
            yield pkg


def is_match(re_pat, pkg, reverse=False, installed_only=False):
    """ returns True/False if re_pat.search(targetstr) returns a match) """
    if hasattr(pkg, 'description'):
        targetstr = pkg.description
    else:
        return False

    # installed packages only.
    if installed_only and (not get_install_state(pkg)):
        return False
    # Search the text.
    re_match = re_pat.search(targetstr)
    if reverse:
        return (re_match is None)
    else:
        return (re_match is not None)


def is_pkg_match(re_pat, pkg, **kwargs):
    """ returns True/False if pkg matches the regex.
        Arguments:
            re_pat           : compiled regex pattern to match with.
            pkg              : Package() to match.

        Keyword Arguments:
            desc_search      : if True, try matching descriptions.
                               Default: True
            reverse          : if True, opposite of matching. return packages 
                               that don't match.
                               Default: False
            installed_only   : if True, only match installed packages.
                               Default: False
            uninstalled_only : if True, only match non-installed packages.
                               Default: False
    """

    desc_search = kwargs.get('desc_search', True)
    reverse = kwargs.get('reverse', False)
    installed_only = kwargs.get('installed_only', False)
    uninstalled_only = kwargs.get('uninstalled_only', False)

    # Trim not-installed packages if install_only is used.
    # ...the same for uninstalled_only..
    installstate = get_install_state(pkg)
    if installed_only and (not installstate):
        return False
    elif uninstalled_only and installstate:
        return False

    def matchfunc(targetstr, reversed=False):
        rematch = re_pat.search(targetstr)
        if reversed:
            return (rematch is None)
        else:
            return (rematch is not None)

    # Try matching the name. (reverse handled also.)
    if matchfunc(pkg.name, reverse):
        return True

    if desc_search:
        # Old apt API of getting description...
        if hasattr(pkg, 'description'):
         # description sometimes returns None.
            if pkg.description is None:
                return False
            pkgdesc = pkg.description
        # New apt API of getting description for installed packages...
        elif hasattr(pkg, 'installed'):
            installedpkg = pkg.installed
            # Still sometimes returns None
            if installedpkg is None:
                # Get latest versions description
                for ver in pkg.versions:
                    pkgdesc = ver.description
                    if pkgdesc:
                        break
                if not pkgdesc:
                    return False
            else:
                pkgdesc = installedpkg.description
        # Try matching description.
        if matchfunc(pkgdesc, reverse):
            return True
    return False


# START ---------------------------------------------------
if __name__ == '__main__':
    main_dargs = docopt(usage_str, version='{} v. {}'.format(_NAME, _VERSION))
    # grab start time for timing.
    start_time = datetime.now()

    ret = main(main_dargs)
    # Report how long it took
    duration = (datetime.now() - start_time).total_seconds()
    print(str(duration)[:5] + 's')

    sys.exit(ret)