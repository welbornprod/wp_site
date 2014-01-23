#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""ircbot_commands.py

    Handles commands for ircbot.py, separate from the rest of the other
    irc bot functionality to prevent mess.

    -Christopher Welborn (original ircbot.py from github.com/habnabit)
"""

import json
import os
from sys import version as sysversion
from datetime import datetime
import subprocess


from pyval_exec import ExecBox, TempInput, TimedOut
from pyval_util import NAME, VERSION

ADMINFILE = '{}_admins.lst'.format(NAME.lower().replace(' ', '-'))
BANFILE = '{}_banned.lst'.format(NAME.lower().replace(' ', '-'))
HELPFILE = '{}_help.json'.format(NAME.lower().replace(' ', '-'))

# Parses common string for True/False values.
parse_true = lambda s: s.lower() in ('true', 'on', 'yes', '1')
parse_false = lambda s: s.lower() in ('false', 'off', 'no', '0')

# Location of pastebinit
# TODO: needs to check other locations as well.
PASTEBINIT_EXE = '/usr/bin/pastebinit'


def simple_command(func):
    """ Simple decorator for simple commands.
        Used for commands that have no use for args.
        Example:
            @simple_command
            def cmd_hello(self):
                return 'hello'
            # Calling cmd_hello('blah')
            # is like calling cmd_hello()
    """

    def inner(self, *args, **kwargs):
        return func(self)
    return inner


def basic_command(func):
    """ Simple decorator for basic commands that accept a 'rest' arg.
        Used for commands that have no use for the 'nick' arg.
        Example:
            @basic_command
            def cmd_hello(self, rest):
                return 'hello'
            # Calling cmd_hello('hey', nick='blah'),
            # is like calling cmd_hello('hey')
    """

    def inner(self, *args, **kwargs):
        return func(self, *args)
    return inner


def load_json_object(filename):
    """ Loads an object from a json file,
        returns {} on failure.
    """
    try:
        with open(filename, 'r') as fjson:
            rawjson = fjson.read()
    except (OSError, IOError) as exio:
        print('\nError loading json from: {}\n{}'.format(filename, exio))
        return {}

    try:
        jsonobj = json.loads(rawjson)
    except Exception as ex:
        print('\nError parsing json from: {}\n{}'.format(filename, ex))
        return {}

    return jsonobj


class AdminHandler(object):

    """ Handles admin functions like bans/admins/settings. """

    def __init__(self, nick=None, help_info=None):
        # Set startup time.
        self.starttime = datetime.now()
        # Current channels the bot is in.
        self.channels = []
        # Set command character and nick.
        self.command_char = '!'
        self.nickname = nick or 'pyval'
        # Whether or not to use PyVal.ExecBoxs blacklist.
        self.blacklist = False
        # Monitoring options. (privmsgs, all recvline, include ips)
        self.monitor = False
        self.monitordata = False
        self.monitorips = False
        # List of admins/banned
        self.admins = self.admins_load()
        self.banned = self.ban_load()
        self.banned_warned = {}
        # Time of last response sent (rate-limiting/bans)
        self.last_handle = None
        # Last nick responded to (rate-limiting/bans)
        self.last_nick = None
        # Last command handled (dupe-blocking/rate-limiting)
        self.last_command = None
        # Whether or not response rate-limiting is enabled.
        self.limit_rate = True
        # Current load, and lock required to change its value.
        self.handlingcount = 0
        self.handlinglock = None
        # Number of handled requests
        self.handled = 0
        # Help dict {'user': {'cmd': {'args': null, {'desc': 'mycommand'}}},
        #            'admin': <same as 'user' key> }
        # Tests can pass a preloaded help_info in.
        self.help_info = help_info if help_info else self.load_help()
        if self.help_info:
            if (not help_info):
                print('\nHelp info file loaded: {}'.format(HELPFILE))
        else:
            print('\nNo help commands will be available.')

    def admins_add(self, nick):
        """ Add an admin to the list and save it. """
        if nick in self.admins:
            return 'already an admin: {}'.format(nick)

        self.admins.append(nick)
        if self.admins_save():
            return 'added admin: {}'.format(nick)
        else:
            return 'unable to save admins, {} is not permanent.'.format(nick)

    def admins_list(self):
        """ List admins. """
        return 'admins: {}'.format(', '.join(self.admins))

    def admins_load(self):
        """ Load admins from list. """

        if not os.path.exists(ADMINFILE):
            print('No admins list, defaults will be used.')
            # cj is the default admin.
            return ['cjwelborn']

        # admin is cj until the admins file says otherwise.
        admins = ['cjwelborn']
        try:
            with open('pyval_admins.lst') as fread:
                admins = [l.strip('\n') for l in fread.readlines()]
        except (IOError, OSError) as ex:
            print('Unable to load admins list:\n{}'.format(ex))
            pass

        return admins

    def admins_remove(self, nick):
        """ Remove an admin from the list and save it. """
        if nick in self.admins:
            self.admins.remove(nick)
            if self.admins_save():
                return 'removed admin: {}'.format(nick)
            else:
                return ('unable to save admins, '
                        '{} will persist on restart'.format(nick))
        else:
            return 'not an admin: {}'.format(nick)

    def admins_save(self):
        """ Save current admins list. """
        try:
            with open(ADMINFILE, 'w') as fwrite:
                fwrite.write('\n'.join(self.admins))
                fwrite.write('\n')
                return True
        except (IOError, OSError) as ex:
            print('Error saving admin list:\n{}'.format(ex))
            return False

    def ban_add(self, nick, permaban=False):
        """ Add a warning to a nick, after 3 warnings ban them for good. """

        if nick in self.admins:
            # Admins wont be banned or counted.
            return False

        if permaban:
            # Straight to permaban.
            self.banned.append(nick)
            self.ban_save()
            return True

        # Auto banner.
        if nick in self.banned_warned.keys():
            # Increment the warning count.
            self.banned_warned[nick]['last'] = datetime.now()
            self.banned_warned[nick]['count'] += 1
            if self.banned_warned[nick]['count'] == 3:
                # No more warnigns, permaban.
                self.banned.append(nick)
                self.ban_save()
                return True
        else:
            # First warning.
            self.banned_warned[nick] = {'last': datetime.now(),
                                        'count': 1}
        return False

    def ban_load(self):
        """ Load banned nicks if any are available. """

        banned = []
        if os.path.isfile(BANFILE):
            try:
                with open(BANFILE) as fread:
                    banned = [l.strip('\n') for l in fread.readlines()]
            except (IOError, OSError) as exos:
                print('\nUnable to load banned file: {}\n{}'.format(BANFILE,
                                                                    exos))
        return banned

    def ban_save(self):
        """ Load perma-banned list. """
        try:
            with open(BANFILE, 'w') as fwrite:
                fwrite.write('\n'.join(self.banned))
                return True
        except (IOError, OSError) as exos:
            print('\nUnable to save banned file: {}\n{}'.format(BANFILE, exos))
        return False

    def ban_remove(self, nick):
        """ Remove a nick from the banned list. """
        while nick in self.banned:
            self.banned.remove(nick)
        if nick in self.banned_warned.keys():
            self.banned_warned[nick] = {'last': datetime.now(), 'count': 0}
        return self.ban_save()

    def get_uptime(self):
        """ Return the current uptime for this instance. """
        uptime = ((datetime.now() - self.starttime).total_seconds() / 60)
        return round(uptime, 2)

    def handling_decrease(self):
        if self.handlingcount > 0:
            self.handlinglock.acquire()
            self.handlingcount -= 1
            self.handlinglock.release()

    def handling_increase(self):
        self.handlinglock.acquire()
        self.handlingcount += 1
        self.handlinglock.release()

    def load_help(self):
        """ Load help from json file. """

        return load_json_object(HELPFILE)


class CommandHandler(object):

    """ Handles commands/messages sent from pyvalbot.py """

    def __init__(self, **kwargs):
        """ Keyword Arguments:
                ** These are required. **
                adminhandler  : Shared AdminHandler() for these functions.
                defer_        : Shared defer module.
                reactor_      : Shared reactor module.
                task_         : Shared task module.
        """
        self.admin = kwargs.get('adminhandler', None)
        self.defer = kwargs.get('defer_', None)
        self.reactor = kwargs.get('reactor_', None)
        self.task = kwargs.get('task_', None)
        self.command_char = '!'
        self.commands = CommandFuncs(defer_=self.defer,
                                     reactor_=self.reactor,
                                     task_=self.task,
                                     adminhandler=self.admin)

    def parse_command(self, msg, username=None):
        """ Parse a message, return corresponding command function if found,
            otherwise, return None.
        """
        command, sep, rest = msg.lstrip(self.command_char).partition(' ')
        # Retrieve function related to this command.
        func = getattr(self.commands, 'cmd_' + command, None)
        # Check admin command.
        if username and (username in self.admin.admins):
            adminfunc = getattr(self.commands, 'admin_' + command, None)
            if adminfunc:
                # return callable admin command.
                return adminfunc

        # Return callable function for command.
        return func
 
    def parse_data(self, user, channel, msg):
        """ Parse raw data from prvmsg()... hands off to proper functions.
            Arguments:
                user        : (str) - user from IRCClient.privmsg()
                channel     : (str) - channel from IRCClient.privmsg()
                msg         : (str) - message from IRCClient.privmsg()
        """
       
        # Monitor incoming messages?
        if self.admin.monitor:
            # Parse irc name, ip address from user.
            username, ipstr = self.parse_username(user)
            # Include ip address in print info?
            if self.admin.monitorips:
                userstr = '{} ({})'.format(username, ipstr)
            else:
                userstr = username
            print('[{}]\t{}:\t{}'.format(channel, userstr, msg))
        
        # Handle message
        return self.parse_message(msg, username=self.parse_username(user)[0])

    def parse_message(self, msg, username=None):
        """ Parse a message, return corresponding command function if found,
            otherwise return None
        """
        
        # Handle user command string.
        if msg.startswith(self.admin.command_char):
            return self.parse_command(msg, username=username)

        # Not a command.
        return None

    def parse_username(self, rawuser):
        """ Parse a raw username into (ircname, ipaddress),
            returns (rawuser, '') on failure.
        """
        if '!' in rawuser:
            splituser = rawuser.split('!')
            username = splituser[0].strip()
            rawip = splituser[1]
            if '@' in rawip:
                ipaddress = rawip.split('@')[1]
            else:
                ipaddress = rawip
        else:
            username = rawuser
            ipaddress = ''
        return (username, ipaddress)


class CommandFuncs(object):

    """ Holds only the command-handling functions themselves. """
    
    def __init__(self, **kwargs):
        """ Keyword Arguments:
                ** These are required. **
                adminhandler  : Shared AdminHandler() for these functions.
                defer_        : Shared defer module.
                reactor_      : Shared reactor module.
                task_         : Shared task module.
        """
        self.admin = kwargs.get('adminhandler', None)
        self.defer = kwargs.get('defer_', None)
        self.reactor = kwargs.get('reactor_', None)
        self.task = kwargs.get('task_', None)

    # Commands (must begin with cmd)
    @basic_command
    def admin_adminadd(self, rest):
        """ Add an admin to the list. """
        return self.admin.admins_add(rest)

    def admin_adminhelp(self, rest, nick=None):
        """ Build list of admin commands. """
        return self.get_help(role='admin', cmdname=rest, usernick=None)

    @simple_command
    def admin_adminlist(self):
        """ List current admins. """
        return self.admin.admins_list()

    @simple_command
    def admin_adminreload(self):
        """ Reloads admin list for IRCClient. """
        # Really need to reorganize things, this is getting ridiculous.
        self.admin.admins_load()
        return 'admins loaded.'

    @basic_command
    def admin_adminrem(self, rest):
        """ Alias for admin_adminremove """
        return self.admin_adminremove(rest)

    @basic_command
    def admin_adminremove(self, rest):
        """ Remove an admin from the handlers list. """
        return self.admin.admins_remove(rest)

    @basic_command
    def admin_ban(self, rest):
        """ Ban a nick. """

        if self.admin.ban_add(rest, permaban=True):
            return 'banned: {}'.format(rest)
        else:
            return 'unable to ban: {}'.format(rest)

    @simple_command
    def admin_banned(self):
        """ list banned. """
        return 'currently banned: {}'.format(', '.join(self.admin.banned))

    @basic_command
    def admin_blacklist(self, rest):
        """ Toggle the blacklist option """
        if rest == '?' or (not rest):
            # current status will be printed at the bottom of this func.
            pass
        elif rest == '-':
            # Toggle current value.
            self.admin.blacklist = False if self.admin.blacklist else True
        else:
            if parse_true(rest):
                self.admin.blacklist = True
            elif parse_false(rest):
                self.admin.blacklist = False
            else:
                return 'invalid value for blacklist option (true/false).'
        return 'blacklist enabled: {}'.format(self.admin.blacklist)

    @simple_command
    def admin_channels(self):
        """ Return a list of current channels for the bot. """
        return 'current channels: {}'.format(', '.join(self.admin.channels))

    @basic_command
    def admin_getattr(self, rest):
        """ Return value for attribute. """
        if not rest.strip():
            return 'usage: getattr <attribute>'

        parent, attrname, attrval = self.parse_attrstr(rest)
        if attrname is None:
            return 'no attribute named: {}'.format(rest)

        attrval = str(attrval)
        if len(attrval) > 250:
            attrval = '{} ...truncated'.format(attrval[:250])
        return '{} = {}'.format(rest, attrval)

    @basic_command
    def admin_identify(self, rest):
        """ Identify with nickserv, expects !identify password """

        print('Identifying with nickserv...')
        if not rest:
            return 'no password supplied.'

        self.admin.sendLine('PRIVMSG NickServ :IDENTIFY '
                            '{} {}'.format(self.admin.nickname, rest))
        return None

    @basic_command
    def admin_join(self, rest):
        """ Join a channel as pyval. """
        if ',' in rest:
            # multiple channel names.
            chans = [s.strip() for s in rest.split(',')]
        else:
            # single channel.
            chans = [rest]

        alreadyin = []
        for chan in chans:
            if not chan.startswith('#'):
                chan = '#{}'.format(chan)

            if chan in self.admin.channels:
                # already in that channel, send a msg in a moment.
                alreadyin.append(chan)
            else:
                print('Joining: {}'.format(chan))
                self.admin.sendLine('JOIN {}'.format(chan))

            if alreadyin:
                chanstr = 'channel' if len(alreadyin) == 1 else 'channels'
                return 'Already in {}: {}'.format(chanstr,
                                                  ', '.join(alreadyin))
        # Joined channels, no response is sent
        # (you can look at the log/stdout)
        return None

    @basic_command
    def admin_limitrate(self, rest):
        """ Toggle limit_rate """
        if rest == '?' or (not rest):
            # current status will be printed at the bottom of this func.
            pass
        elif rest == '-':
            # Toggle current value.
            self.admin.limit_rate = False if self.admin.limit_rate else True
        else:
            if parse_true(rest):
                self.admin.limit_rate = True
            elif parse_false(rest):
                self.admin.limit_rate = False
            else:
                return 'invalid value for limitrate option (true/false).'
        return 'limitrate enabled: {}'.format(self.admin.limit_rate)

    @basic_command
    def admin_msg(self, rest):
        """ Send a private msg, expects !msg nick/channel message """

        msgparts = rest.split()
        if len(msgparts) < 2:
            return 'need target and message.'
        target = msgparts[0]
        msgtext = ' '.join(msgparts[1:])
        self.admin.sendLine('PRIVMSG {} :{}'.format(target, msgtext))
        return None

    @basic_command
    def admin_part(self, rest):
        """ Leave a channel as pyval. """
        if ',' in rest:
            # multichannel
            chans = [s.strip() for s in rest.split(',')]
        else:
            # single channel.
            chans = [rest]

        notinchans = []
        for chan in chans:
            if not chan.startswith('#'):
                chan = '#{}'.format(chan)

            if chan in self.admin.channels:
                print('Parting from: {}'.format(chan))
                self.admin.sendLine('PART {}'.format(chan))
            else:
                # not in that channel, send a msg in a moment.
                notinchans.append(chan)

        if notinchans:
            chanstr = 'channel' if len(notinchans) == 1 else 'channel'
            return 'Not in {}: {}'.format(chanstr, ', '.join(notinchans))

        # parted channel(s) no response is sent.
        # (you can check the log/stdout)
        return None

    @simple_command
    def admin_partall(self):
        """ Part all current channels.
            The only way to re-join is to send a private msg to pyval,
            or shutdown and restart.
        """

        return self.admin_part(','.join(self.admin.channels))

    @basic_command
    def admin_say(self, rest):
        """ Send chat message back to person. """
        print('Saying: {}'.format(rest))
        return rest

    @basic_command
    def admin_sendline(self, rest):
        """ Send raw line as pyval. """
        print('Sending line: {}'.format(rest))
        self.admin.sendLine(rest)
        return None

    @basic_command
    def admin_setattr(self, rest):
        """ Set an attribute to self or children of self by string.
            Example:
                self.admin_setattr('admin.blacklist True')
            Automatically converts types from string so
            admin_setattr('attribute True')
            will set attribute to bool(True)
            ...special handling is needed for False and other values.

        """

        if not rest.strip():
            return 'usage: setattr <attribute> <val>'

        # Parse args
        cmdargs = rest.split()
        if len(cmdargs) != 2:
            return 'incorrect number of arguments for setattr.'
        attrstr, valstr = cmdargs

        # Find old value, final attrname, and parent of old value.
        parent, oldname, oldval = self.parse_attrstr(attrstr)
        if oldname is None:
            return 'no attribute named: {}'.format(attrstr)

        # convret the new string value into the old type.
        try:
            newval = self.parse_typestr(oldval, valstr)
        except Exception as ex:
            # Unable to convert new value into old type.
            return ex

        # Actually set the new value.
        try:
            setattr(parent, oldname, newval)
        except Exception as ex:
            # Unable to set the attribute.
            return ex

        # Success. Show new value.
        newval = str(newval)
        if len(newval) > 250:
            newval = '{} ...truncated'.format(newval[:250])
        return '{} = {}'.format(attrstr, newval)

    @simple_command
    def admin_shutdown(self):
        """ Shutdown the bot. """
        print('Shutting down...')
        self.admin.quit(message='shutting down...')
        return None

    @simple_command
    def admin_stats(self):
        """ Return simple stats info. """
        uptime = self.admin.get_uptime()
        return 'uptime: {}min, handled: {}'.format(uptime, self.admin.handled)

    @basic_command
    def admin_unban(self, rest):
        """ Unban a nick. """
        if self.admin.ban_remove(rest):
            return 'unbanned: {}'.format(rest)
        else:
            return 'unable to unban: {}'.format(rest)

    def cmd_help(self, rest, nick=None):
        """ Returns a short help string. """
        return self.get_help(role='user', cmdname=rest, usernick=nick)

    @basic_command
    def cmd_py(self, rest):
        """ Shortcut for cmd_python """
        return self.cmd_python(rest)

    @basic_command
    def cmd_python(self, rest):
        """ Evaluate python code and return the answer.
            Restrictions are set. No os module, no nested eval() or exec().
        """

        def pastebin_chatout(pastebinurl):
            """ Callback for deferred print_topastebin.
            Expects result from print_topastebin(content).
                Returns final chat output when finished.
            """
            # Get chat safe output (partial eval output with pastebin url)
            if pastebinurl:
                # Build chat result
                # semi-full output was pasted, but still need acceptable chat
                # msg.
                chatout = execbox.safe_output(maxlines=30, maxlength=140)
                if len(chatout) > 100:
                    chatout = chatout[:100]
                return ('{} '.format(chatout) +
                        ' full: {}'.format(pastebinurl))
            else:
                # failed to pastebin.
                chatout = execbox.safe_output(maxlines=30, maxlength=140)
                if len(chatout) > 100:
                    chatout = chatout[:100]
                return '{} (...truncated)'.format(chatout)

        if not rest.replace(' ', '').replace('\t', ''):
            # No input.
            return None

        # User wants help.
        if rest.lower().startswith('help'):
            return self.cmd_help(rest)

        # Execute using pypy-sandbox/pyval_sandbox powered ExecBox.
        execbox = ExecBox(rest)
        try:
            # Get raw output from eval, this will have to be checked
            # and possibly trimmed later before returning a result.
            results = execbox.execute(use_blacklist=self.admin.blacklist,
                                      raw_output=True)
        except TimedOut:
            return 'result: timed out.'
        except Exception as ex:
            return 'error: {}'.format(ex)

        if len(results) > 160:
            # Use pastebinit, with safe_pastebin() settings.
            pastebincontent = self.safe_pastebin(execbox.output,
                                                 maxlines=65,
                                                 maxlength=240)
            if self.admin.handlingcount > 1:
                # Delay this pastebin call based on the handling count.
                timeout = 3 * self.admin.handlingcount
                print('Delaying pastebin call for {} seconds.'.format(timeout))
                # Create a deferred that will be called at a later time.
                deferredurl = self.task.deferLater(self.reactor,
                                                   timeout,
                                                   self.print_topastebin,
                                                   pastebincontent)
                # Create a callback that takes in the url and produces
                # the final chat response.
                # IRCClient.privmsg() looks for a deferred and will add
                # the _sendMessage callback to this when it is finished.
                # (after some further checking/processing ofcourse)
                deferredurl.addCallback(pastebin_chatout)
                return deferredurl

            else:
                # paste it right away
                pastebinout = self.print_topastebin(pastebincontent)
                resultstr = pastebin_chatout(pastebinout)

        else:
            # No pastebin needed.
            resultstr = execbox.safe_output()

        return resultstr

    def cmd_pyval(self, rest, nick=None):
        """ Someone addressed 'pyval' directly. """
        if rest.replace(' ', '').replace('\t', ''):
            print('Message from {}: {}'.format(nick, rest))
            # Don't reply to this valid msg.
            return None
        else:
            return 'try !help, !py help, or !help py'

    @basic_command
    def _cmd_saylater(self, rest):
        """ Delayed response... DISABLED"""
        when, sep, msg = rest.partition(' ')
        try:
            when = int(when)
        except:
            when = 0
        
        d = self.defer.Deferred()
        # A small example of how to defer the reply from a command. callLater
        # will callback the Deferred with the reply after so many seconds.
        self.reactor.callLater(when, d.callback, msg)
        # Returning the Deferred here means that it'll be returned from
        # maybeDeferred in privmsg.
        return d
    
    @simple_command
    def cmd_time(self):
        """ Retrieve current date and time. """
        
        return str(datetime.now())

    @simple_command
    def cmd_uptime(self):
        """ Return uptime, and starttime """
        uptime = self.admin.get_uptime()
        s = 'start: {}, up: {}min'.format(self.admin.starttime, uptime)
        return s
    
    @simple_command
    def cmd_version(self):
        """ Return pyval version, and sys.version. """
        pyvalver = '{}: {}'.format(NAME, VERSION)
        pyver = 'Python: {}'.format(sysversion.split()[0])
        gccver = 'GCC: {}'.format(sysversion.split('\n')[-1])
        verstr = '{}, {}, {}'.format(pyvalver, pyver, gccver)
        return verstr

    def get_commands(self, role='user', usernick=None):
        """ Returns a list of available user commands. """
        if role == 'user':
            # Not dynamically generating list right now, maybe later when
            # commands are final and stable.
            # This is a list of 'acceptable' commands right now.
            if usernick and (usernick in self.admin.admins):
                # hint an admin user towards the adminhelp command.
                usercmds = ['adminhelp']
            else:
                usercmds = []
            usercmds.extend(['help', 'py', 'python',
                             'pyval', 'uptime', 'version'])
            return usercmds

        else:
            # Dynamically generate a list of admin commands.
            admincmds = [a for a in dir(self) if a.startswith('admin_')]
            admincmdnames = [s.split('_')[1] for s in admincmds]
            return sorted(admincmdnames)

    def get_help(self, role='user', cmdname=None, usernick=None):
        """ Retrieve help for a command. """

        if not self.admin.help_info:
            return 'help isn\'t available right now.'

       # Handle python style help (still only works for pyval cmds)
        if cmdname and '(' in cmdname:
            # Convert 'help(test)' into 'help test', or 'help()' into 'help '
            cmdname = cmdname.replace('(', ' ')
            cmdname = cmdname.strip(')')
            # Remove " and '
            if ("'" in cmdname) or ('"' in cmdname):
                cmdname = cmdname.replace('"', '').replace("'", '')
            # Convert 'help ' into 'help'
            cmdname = cmdname.strip()
            # Convert 'help ' into None so it can be interpreted as plain help.
            if cmdname == 'help':
                cmdname = None
            else:
                # Convert 'help blah' into 'blah'
                cmdname = ' '.join(cmdname.split()[1:])

        if cmdname:
            # Look for cmd name in help_info.
            cmdname = cmdname.lower()
            if cmdname in self.admin.help_info[role]:
                cmdhelp = self.admin.help_info[role][cmdname]
                if cmdhelp['args']:
                    return '{}{} {}: {}'.format(self.admin.command_char,
                                                cmdname,
                                                cmdhelp['args'],
                                                cmdhelp['desc'])
                else:
                    return '{}{}: {}'.format(self.admin.command_char,
                                             cmdname,
                                             cmdhelp['desc'])
            else:
                return 'no {} command named: {}'.format(role, cmdname)

        else:
            # All commands
            cmds = self.get_commands(role=role, usernick=usernick)
            return '{} commands: {}'.format(role, ', '.join(cmds))

    def parse_attrstr(self, attrstr):
        """ Return value and parent for attribute by string. """
        if '.' in attrstr:
            attrs = attrstr.split('.')
        else:
            attrs = [attrstr]

        # Find old value, and parent of old value.
        parent = None
        abase = self
        for aname in attrs:
            if hasattr(abase, aname):
                parent = abase
                abase = getattr(parent, aname)
            else:
                return None, None, None
        # Parent, and value.
        return parent, aname, abase

    def parse_typestr(self, oldval, newval):
        """ Returns correct type from string, 
            when given the original value.
            Example:
                mybool = True
                newval = parse_typestr(mybool, 'False')
                #   newval == bool(False)
                myint = 23
                newval = parse_typestr(myint, '46')
                #   newval == int(46)

            Handles all builtin types, not datetime (yet).
            Does not suppress any ValueError/TypeError.
        """

        def make_bool(s):
            """ Return a bool by string value. """
            if s.lower() in ('false', '0'):
                return False
            return bool(s)

        # NoneType just returns none.
        if oldval is None:
            return None

        handlers = {bool: make_bool}

        if type(oldval) in handlers.keys():
            # Special cases need custom handlers. Like bool('False')...
            converted = handlers[type(oldval)](newval)
        else:
            # Normal case, or no custom handler.
            converted = type(oldval)(newval)
        return converted

    def print_topastebin(self, s):
        """ Uses paste.pound-python.org to paste a string. """

        if not s:
            return None

        cmdargs = [PASTEBINIT_EXE,
                   '-a', 'pyval',
                   '-b', 'http://paste.pound-python.org']
        try:
            with TempInput(s) as stdinput:
                proc = subprocess.Popen(cmdargs,
                                        stdin=stdinput,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
        except Exception as ex:
            print('Error running pastebinit:\n{}'.format(ex))
            return None

        output = self.proc_output(proc)
        if output.startswith('http'):
            return output
        else:
            return None

    def proc_output(self, proc):
        """ Get process output, whether its on stdout or stderr.
            Used with _exec/timed_call.
            Arguments:
                proc  : a POpen() process to get output from.
        """

        if not proc:
            return ''

        # Get stdout
        outlines = []
        for line in iter(proc.stdout.readline, ''):
            if line:
                outlines.append(line.strip('\n'))
            else:
                break

        # Get stderr
        errlines = []
        for line in iter(proc.stderr.readline, ''):
            if line:
                errlines.append(line.strip('\n'))
            else:
                break

        # Pick stdout or stderr.
        if outlines:
            output = '\n'.join(outlines)
        elif errlines:
            output = '\n'.join(outlines)
        else:
            # no output
            output = ''

        return output.strip('\n')

    def safe_pastebin(self, s, maxlines=65, maxlength=240):
        """ Format string for safe pastebin pasting.
            maxlines is the limit of lines allowed.
            maxlength is the limit allowed for each line.
        """

        if maxlines < 1:
            maxlines = 1
        if maxlength < 1:
            maxlength = 1

        if not s:
            return s

        if '\n' in s:
            lines = s.split('\n')
        elif '\\n' in s:
            lines = s.split('\\n')
        else:
            lines = [s]

        truncatedlines = False
        # truncate by line count first.
        if len(lines) > maxlines:
            lines = lines[:maxlines]
            truncatedlines = True

        # Truncate each line if maxlength is set.
        trimmedlines = []
        for line in lines:
            if len(line) > maxlength:
                newline = ('{} ..truncated'.format(line[:maxlength]) +
                           ' ({} chars)'.format(maxlength))
                trimmedlines.append(newline)
            else:
                trimmedlines.append(line)
        lines = trimmedlines

        if truncatedlines:
            lines.append('..truncated at {} lines.'.format(maxlines))

        return '\n'.join(lines)