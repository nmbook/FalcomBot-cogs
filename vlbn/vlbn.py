import discord
from discord.ext import commands
from redbot.core import Config
from redbot.core import checks
from redbot.core.utils.chat_formatting import escape, info, error
from datetime import datetime, timedelta
import asyncio
import concurrent.futures
import emoji
import fnmatch
import itertools
import math
import pytz
import re
import socket
import struct
import traceback

class BotNetVL:
    """Provides a chat-only bridge between Discord and Classic Battle.net (BNCS).
    
    Uses a bridge to Valhalla Legends' (vL) "BotNet" service and an adaptation of the "WebChannel" protocol from existing BNCS bots.
    
    BotNet is a service once used by a small number of users for inter-bot communication with the Classic Battle.net botting community."""

    global_conf = {
            # connection settings
            "server":           "botnet.bnetdocs.org",
            "port":             0x5555,
            "bot_name":         "BNETDocs",
            "bot_pass":         "33 9c 0f 58 fe c7 2a",
            "database_name":    "",
            "database_pass":    "",
            "account_name":     "Discord",
            "account_pass":     "",

            # hub settings
            "hub_guild":        0,
            "hub_category":     0,
            "hub_automirror":   False,
    }

    channel_conf = {
            "guild":                { "default": 0,      "user-editable": False, "type": "guild-id", },
            "channel_cb":           { "default": 0,      "user-editable": False, "type": "channel-id", },
            "feed_type":            { "default": "none", "user-editable": False, "type": "one-of:none,botnet,bncs", },
            "account_relay":        { "default": None,   "user-editable": True,  "set-causes-reset": True, "type": "str", },
            "users_pin":            { "default": 0,      "user-editable": False, "type": "message-id", },
            "chat_disabled":        { "default": False,  "user-editable": False, "type": "bool", },
            "chat_roles":           { "default": [],     "user-editable": False, "type": "list-of:role-id", },
            "do_users_pin":         { "default": True,   "user-editable": True,  "set-updates-users": True, "type": "bool", },
            "do_join_part":         { "default": True,   "user-editable": True,  "type": "bool", },
            "do_echo_self":         { "default": False,  "user-editable": True,  "type": "bool", },
            "post_format":          { "default": "`{timestamp:%H:%M:%S}` {post}", "user-editable": True, "type": "str:format", },
            "join_format":          { "default": "{prod_icon}{name} *{ping:,}ms* has joined.",
                "user-editable": True, "type": "str:format", },
            "part_format":          { "default": "{name} has left.",
                "user-editable": True, "type": "str:format", },
            "chat_format":          { "default": "<{hl}{name}{hl_end}> {text}",
                "user-editable": True, "type": "str:format", },
            "emote_format":         { "default": "<{hl}{name}{hl_end} {text}>",
                "user-editable": True, "type": "str:format", },
            "bot_alert_format":     { "default": "__**{INFO_TYPE}**__ <{hl}{name}{hl_end}> {text}",
                "user-editable": True, "type": "str:format", },
            "server_alert_format":  { "default": "__**SERVER {INFO_TYPE}**__ {text}",
                "user-editable": True, "type": "str:format", },
            "users_list_format":    { "default": "__**Users in {channel}{server_icon} ({count})**__\n\n{list}",
                "user-editable": True, "set-updates-users": True, "type": "str:format", },
            "users_item_format":    { "default": "{prod_list_icon}{hl}{name}{hl_end} *{ping:,}ms*",
                "user-editable": True, "set-updates-users": True, "type": "str:format", },
            "hl_norm_format":       { "default": "",    "user-editable": True, "set-updates-users": True, "type": "str:format", },
            "hl_self_format":       { "default": "",    "user-editable": True, "set-updates-users": True, "type": "str:format", },
            "hl_oper_format":       { "default": "**",  "user-editable": True, "set-updates-users": True, "type": "str:format", },
            "timezone":             { "default": "UTC", "user-editable": True, "set-updates-timezone": True, "set-updates-users": True, "type": "str:timezone", },
    }

    emoji_map = {
            "USEast":       "<:useast:424674002943082499>",
            "USWest":       "<:uswest:424674072404951050>",
            "Europe":       "\U0001f1ea", # EU flag
            "Asia":         "\U0001f30f", # Asia-facing globe

            "_bnet_disc":   "<:bnet_disc:424674000531226645>",
            "_oper":        "<:operator:424237309060448256>",

            "DRTL":         "<:drtl:434571869635608586>",
            "DSHR":         "<:drtl:434571869635608586>",
            "STAR":         "<:star:424237399778918421>",
            "SEXP":         "<:star:424237399778918421>",
            "JSTR":         "<:star:424237399778918421>",
            "SSHR":         "<:star:424237399778918421>",
            "D2DV":         "<:d2dv:435201709124616217>",
            "D2XP":         "<:d2xp:424237518905409536>",
            "W2BN":         "<:w2bn:424237361824661504>",
            "WAR3":         "<:war3:424237641098067968>",
            "W3XP":         "<:w3xp:424237662757715992>",

            "_":            "<:blank:424238165155512350>",
    }

    resolve_map = {
            "USEast": {"domain": "useast.battle.net",
                "addresses": ["199.108.55.54", "199.108.55.55", "199.108.55.56", "199.108.55.57",
                "199.108.55.58", "199.108.55.59", "199.108.55.60", "199.108.55.61", "199.108.55.62"]},
            "USWest": {"domain": "uswest.battle.net",
                "addresses": ["12.129.236.14", "12.129.236.15", "12.129.236.16", "12.129.236.17",
                "12.129.236.18", "12.129.236.19", "12.129.236.20", "12.129.236.21", "12.129.236.22"]},
            "Europe": {"domain": "europe.battle.net",
                "addresses": ["5.42.181.14", "5.42.181.15", "5.42.181.16", "5.42.181.17", "5.42.181.18"]},
            "Asia": {"domain": "asia.battle.net",
                "addresses": ["121.254.164.14", "121.254.164.15", "121.254.164.16", "121.254.164.17",
                "121.254.164.18", "121.254.164.19", "121.254.164.20", "121.254.164.21",
                "121.254.164.22", "121.254.164.23", "121.254.164.24", "121.254.164.25",
                "121.254.164.26", "121.254.164.27", "121.254.164.28", "121.254.164.29",
                "121.254.164.30", "121.254.164.31", "121.254.164.32", "121.254.164.33", "121.254.164.34"]}
    }


    product_map = {
            "CHAT": { "name_short": "Chat",   "name": "Chat" },
            "DRTL": { "name_short": "Diablo", "name": "Diablo" },
            "DSHR": { "name_short": "DiabloS","name": "Diablo Shareware" },
            "SSHR": { "name_short": "SCS",    "name": "StarCraft Shareware" },
            "JSTR": { "name_short": "SCJ",    "name": "StarCraft Japanese" },
            "STAR": { "name_short": "SC",     "name": "StarCraft" },
            "SEXP": { "name_short": "SC BW",  "name": "StarCraft: Brood War" },
            "W2BN": { "name_short": "W2 BNE", "name": "Warcraft II: Battle.net Edition" },
            "D2DV": { "name_short": "D2",     "name": "Diablo II" },
            "D2XP": { "name_short": "D2 LoD", "name": "Diablo II: Lord of Destruction" },
            "WAR3": { "name_short": "W3 RoC", "name": "Warcraft III: Reign of Chaos" },
            "W3XP": { "name_short": "W3 TFT", "name": "Warcraft III: The Frozen Throne" },
            ""    : { "name_short": "",       "name": "Unset" },
    }
    
    d1_stats_char_list   = ["Warrior", "Rogue", "Sorcerer"]
    d2_stats_char_list   = ["Amazon", "Sorceress", "Necromancer", "Paladin", "Barbarian", "Druid", "Assassin"]
    d2_stats_char_female = [True,     True,        False,         False,     False,       False,   True      ]
    d2_stats_title_table = {
            # diff, xp,    hc,    fem
            # diff = 0: none defeated
            (0,     False, False, False) : "",
            (0,     False, False, True ) : "",
            (0,     False, True , False) : "",
            (0,     False, True , True ) : "",
            (0,     True , False, False) : "",
            (0,     True , False, True ) : "",
            (0,     True , True , False) : "",
            (0,     True , True , True ) : "",
            # diff = 1: normal defeated
            (1,     False, False, False) : "Sir",
            (1,     False, False, True ) : "Dame",
            (1,     False, True , False) : "Count",
            (1,     False, True , True ) : "Countess",
            (1,     True , False, False) : "Slayer",
            (1,     True , False, True ) : "Slayer",
            (1,     True , True , False) : "Destroyer",
            (1,     True , True , True ) : "Destroyer",
            # diff = 2: nightmare defeated
            (2,     False, False, False) : "Lord",
            (2,     False, False, True ) : "Lady",
            (2,     False, True , False) : "Duke",
            (2,     False, True , True ) : "Duchess",
            (2,     True , False, False) : "Champion",
            (2,     True , False, True ) : "Champion",
            (2,     True , True , False) : "Conquerer",
            (2,     True , True , True ) : "Conquerer",
            # diff = 3: hell defeated
            (3,     False, False, False) : "Baron",
            (3,     False, False, True ) : "Baroness",
            (3,     False, True , False) : "King",
            (3,     False, True , True ) : "Queen",
            (3,     True , False, False) : "Patriarch",
            (3,     True , False, True ) : "Matriarch",
            (3,     True , True , False) : "Guardian",
            (3,     True , True , True ) : "Guardian",
    }

    re_discord_link = re.compile(r"\b(?:\<)?(?:http|https|steam)\\\:\/\/[^>\s]+\/?[^>\s]*>?\b")
    re_discord_emoji = re.compile(r"\\\:([A-Za-z0-9-_]{2,32})\\\:")
    re_discord_emoji_object = re.compile(r"<a?(\:[A-Za-z0-9-_]{2,32}\:)[0-9]+>")

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=0xff5269620001)
        self.config.register_global(**BotNetVL.global_conf)
        self.config.register_channel(**{k: v["default"] for k, v in BotNetVL.channel_conf.items()})

        self.state = None
        self.channel_states = {}
        self.tasks = []

        self.counter = 0
        self.counter_on_last_packet = 0

        coro = self.botnet_timer()
        self.tasks.append(self.bot.loop.create_task(coro))

        coro = self.botnet_main()
        self.tasks.append(self.bot.loop.create_task(coro))


    def __unload(self):
        for task in self.tasks:
            task.cancel()

    async def load_config(self):
        """Loads the configuration into the self.state and self.channel_states objects."""
        # reset objects
        self.state = BotNetVLState()
        self.channel_states = {}

        # store states
        try:
            for key, val in BotNetVL.global_conf.items():
                setattr(self.state, key, await self.config.get_attr(key)())

            # store channel states
            channel_conf = await self.config.all_channels()
            for channel_id, conf in channel_conf.items():
                channel_state = BotNetVLChannelState()
                for key, val in BotNetVL.channel_conf.items():
                    setattr(channel_state, key, conf[key])

                try:
                    channel_state.timezone_object = pytz.timezone(channel_state.timezone.replace(" ", "_"))
                except pytz.exceptions.UnknownTimeZoneError:
                    channel_state.timezone_object = pytz.utc

                if channel_state.feed_type != "none":
                    self.channel_states[channel_id] = channel_state
        except Exception as ex:
            print("BotNet EXCEPTION: {}".format(ex))

    async def save_channel_config(self, channel, channel_state):
        """Saves the setting-level properties of the given channel state."""
        try:
            for key, val in BotNetVL.channel_conf.items():
                await self.config.channel(channel).get_attr(key).set(getattr(channel_state, key, val["default"]))
        except Exception as ex:
            print("BotNet EXCEPTION: {}".format(ex))

    async def botnet_timer(self):
        last_snapshot = None
        try:
            while True:
                await asyncio.sleep(1)
                self.counter += 1

                if self.state.socket:
                    if self.counter_on_last_packet >= self.counter + 30:
                        # send keep alive after 30 seconds of no packets sent or received
                        #print("sending keepalive")
                        to_send = [self.send_keep_alive()]
                        await self.send_resp(to_send)
                
                for task in self.tasks:
                    if task.done():
                        #print("removed task: {}".format(task))
                        self.tasks.remove(task)

                #if (self.counter % 600) == 0:
                    #print("taking snapshot")
                    #snapshot = tracemalloc.take_snapshot()
                    #if last_snapshot:
                    #    #display_top(snapshot)
                    #    top_stats = snapshot.compare_to(last_snapshot, 'lineno')
                    #
                    #    print("[ Top 10 differences ]")
                    #    for stat in top_stats[:10]:
                    #        print(stat)
                    #last_snapshot = snapshot
                    #print("took snapshot")
        except concurrent.futures.CancelledError as ex:
            # module unload or other cancel -- no return here
            pass
        except Exception as ex:
            print("BotNet EXCEPTION: {}".format(ex))
            traceback.print_exc()

    async def botnet_main(self):
        """Initialize self.state and then connect to BotNet.

        The core logic of the BotNet feed. Sets up and awaits in a receive loop."""

        while True:
            try:
                await self.load_config()

                print("Connecting to {}...".format(self.state.server))

                if len(self.state.server) == 0:
                    print("No BotNet server set.")
                    return

                self.state.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.state.socket.setblocking(False)

                await self.bot.loop.sock_connect(self.state.socket, (self.state.server, self.state.port))

                to_send = self.botnet_on_connected()

                while True: # receive loop
                    await self.send_resp(to_send)
                    packet = await self.get_packet()
                    if packet is None:
                        break
                    to_send = self.botnet_on_packet(packet)
                if self.state.socket:
                    # connection closed
                    print("BotNet connection closed.")
                    self.state.socket.close()
                    self.state.socket = None
                    self.state.chat_ready = False
                    # wait 60 seconds and reconnect
                    await asyncio.sleep(60)
            except concurrent.futures.CancelledError as ex:
                if self.state.socket:
                    # module unload or other cancel -- no return here
                    print("BotNet module terminating.")
                    self.state.socket.close()
                    self.state.socket = None
                    self.state.chat_ready = False
                return
            except OSError as ex:
                # unspecified error
                print("BotNet connection error: {}".format(ex))
                if self.state.socket:
                    self.state.socket.close()
                    self.state.socket = None
                    self.state.chat_ready = False
                    # wait 60 seconds and reconnect
                    await asyncio.sleep(60)
            except Exception as ex:
                # main loop error (uncaught exception in packet parsing and handling...)
                print("BotNet uncaught Exception: {}".format(ex))
                traceback.print_exc()
            finally:
                if self.state.socket:
                    # main loop error
                    print("BotNet connection terminating.")
                    self.state.socket.close()
                    self.state.socket = None
                    self.state.chat_ready = False
                    # wait 60 seconds and reconnect
                    await asyncio.sleep(60)

    def botnet_on_connected(self):
        """On Connected Event

        Respond with a bot logon packet."""
        yield self.send_bot_logon()

    def botnet_on_packet(self, packet):
        """On Packet Event

        Respond with 0 or more packets depending on our state and received packet."""
        if   packet.id == 0x00: # 0x00 S>C keep alive
            pass
        elif packet.id == 0x01: # 0x01 S>C bot logon resp
            success = packet.get_uint32()
            self.state.received_logon_resp = True
            if self.state.server_version >= 0x04: # SERVER VERSION 4+
                self.state.local_address = packet.get_uint32()
                # send 0x0a
                yield self.send_client_caps()
                # send 0x10
                yield self.send_chat_opts()
            if len(self.state.account_name) > 0 and self.state.server_version >= 0x02: # SERVER VERSION 2+
                # send 0x0d if on account
                yield self.send_account_logon(0x00)
            else:
                # send 0x02
                yield self.send_self_update()
        elif packet.id == 0x02: # 0x02 S>C self update resp
            success = packet.get_uint32()
            self.state.users = {}
            yield self.send_user_info_list()
        elif packet.id == 0x06: # 0x06 S>C user info
            if len(packet) == 4: # end of initial list
                # note: this null-terminator is only received if we are "4.1"!
                # chat ready, so that future user events are events
                self.state.chat_ready = True

                # save self and put it at end of list
                self_user = self.state.users[next(iter(self.state.users))]
                self_bot_id = self_user.bot_id
                self.state.self_user = self_user

                del self.state.users[self_bot_id]
                self.state.users[self_bot_id] = self_user

                # raise event
                self.botnet_on_userlist(self.state.users)

                # deferred_chat
                if len(self.state.deferred_chat) > 0:
                    for command, action, bot_id, message in self.state.deferred_chat:
                        self.botnet_on_chat(self.state.users[bot_id], message, command, action)
                    del self.state.deferred_chat[:]
            else:
                account      = None
                database     = None
                dba          = None
                ada          = None
                bot_id       = packet.get_uint32()
                if self.state.server_version >= 0x04: # SERVER VERSION 4+
                    if self.state.client_comm_version >= 0x01: # CLIENT CAP 1+
                        # db access flags and admin caps, both ignored
                        dba  = packet.get_uint32()
                        ada  = packet.get_uint32()
                bnet_name    = packet.get_ntstring()
                bnet_channel = packet.get_ntstring()
                bnet_server  = packet.get_uint32()
                if self.state.server_version >= 0x02:
                    account  = packet.get_ntstring() 
                if self.state.server_version >= 0x03:
                    database = packet.get_ntstring()

                # this is a connect if the bot_id isn't present yet
                on_connect = (not (bot_id in self.state.users))

                # save object
                user = BotNetVLUser(bot_id, bnet_name, bnet_channel, bnet_server, account, database, database_access = dba, admin_access = ada)
                self.state.users[bot_id] = user

                # if chat ready, raise single event
                if self.state.chat_ready:
                    self.botnet_on_user(user, on_connect)
        elif packet.id == 0x07: # 0x07 S>C user disc
            bot_id = packet.get_uint32()

            # raise event
            if bot_id in self.state.users:
                user = self.state.users[bot_id]
                self.botnet_on_userdisc(user)

                # delete object
                del self.state.users[bot_id]
            else:
                print("BotNet WARNING: BotNet reported an unknown user with bot_id #{} has disconnected.".format(bot_id))
        elif packet.id == 0x08: # 0x08 S>C protocol violation
            errno = packet.get_uint32()
            pktid = packet.get_uint8()
            pktln = packet.get_uint16()
            unpln = packet.get_uint16()
            print("BotNet ERROR: Protocol violation occurred. Sent packet 0x{:02x} (len {}; unp len {}). Error code {}.".format(pktid, self.byte_size(pktln), self.byte_size(unpln), errno))
        elif packet.id == 0x0a: # 0x0a S>C version
            self.state.server_version      = packet.get_uint32()
        elif packet.id == 0x09: # 0x09 S>C client opts resp
            self.state.client_comm_version = packet.get_uint32()
            self.state.client_cap_bits     = packet.get_uint32()
        elif packet.id == 0x0b: # 0x0b S>C chat
            command = packet.get_uint32()
            action  = packet.get_uint32()
            bot_id  = packet.get_uint32()
            message = packet.get_ntstring()
            if bot_id in self.state.users:
                self.botnet_on_chat(self.state.users[bot_id], message, command, action)
            else:
                self.state.deferred_chat.append((command, action, bot_id, message))
        elif packet.id == 0x0d: # 0x0d S>C account logon resp
            subcommand = packet.get_uint32()
            success    = packet.get_uint32()

            if success:
                if   subcommand == 0x00: # account logon succeeded
                    # continue with sending status
                    yield self.send_self_update()
                elif subcommand == 0x02: # account create succeeded, logon to it
                    yield self.send_account_logon(0x00)
                else:
                    print("BotNet ERROR logging in: Account subcommand 0x{:x} is not known".format(subcommand))
                    # continue with sending status
                    yield self.send_self_update()
            else:
                if   subcommand == 0x00: # account logon failed (DNE?)
                    yield self.send_account_logon(0x02)
                elif subcommand == 0x02: # account create failed (was invalid pass)
                    print("BotNet ERROR logging in: Account could not be logged on to or created with name {}".format(self.state.account_name))
                    # continue with sending status
                    yield self.send_self_update()
                else:
                    print("BotNet ERROR logging in: Account subcommand 0x{:x} is not known".format(subcommand))
                    # continue with sending status
                    yield self.send_self_update()
        elif packet.id == 0x10: # 0x10 S>C chat opts resp
            # ignore contents; assume server set chat opts to 0,0,1,0
            pass
        else:
            print("BotNet WARNING unknown packet id: 0x{:x}".format(packet.id))

    def send_keep_alive(self): # 0x00 C>S keep alive
        packet = BotNetVLPacket(id = 0x00)
        return packet
    
    def send_bot_logon(self): # 0x01 C>S bot logon
        packet = BotNetVLPacket(id = 0x01)
        packet.append_ntstring(self.state.bot_name)
        packet.append_ntstring(self.state.bot_pass)
        return packet

    def send_self_update(self): # 0x02 C>S self update
        #channel = self.bot.get_channel(feed["discord_channel"])
        dbn     = self.state.database_name
        dbp     = self.state.database_pass

        packet = BotNetVLPacket(id = 0x02)
        packet.append_ntstring(self.bot.user.name)
        packet.append_ntstring("<Not logged on>")
        packet.append_uint32(0xffffffff)
        packet.append_ntstring("{n} {p}".format(n=dbn, p=dbp))
        packet.append_uint32(0)
        return packet

    def send_user_info_list(self): # 0x06 C>S user info list
        packet = BotNetVLPacket(id = 0x06)
        return packet

    def send_client_caps(self): # 0x0a C>S client caps
        packet = BotNetVLPacket(id = 0x0a)
        # sending 0x0a since we would send 0+0
        packet.append_uint32(0x01) # comm version 1
        packet.append_uint32(0x01) # client caps 0b1
        return packet

    def send_chat(self, content, *, emote : bool = False, broadcast : bool = False, whisper_to : int = 0): # 0x0b C>S chat
        packet = BotNetVLPacket(id = 0x0b)
        if whisper_to != 0:
            packet.append_uint32(0x02) # whisper to
        elif broadcast:
            packet.append_uint32(0x00) # broadcast
        else:
            packet.append_uint32(0x01) # current database

        if emote:
            packet.append_uint32(0x01) # emote
        else:
            packet.append_uint32(0x00) # not emote
        packet.append_uint32(whisper_to)
        packet.append_ntstring(content)
        return packet

    def send_account_logon(self, subcommand): # 0x0d C>S account logon
        packet = BotNetVLPacket(id = 0x0d)
        packet.append_uint32(subcommand)
        packet.append_ntstring(self.state.account_name)
        packet.append_ntstring(self.state.account_pass)
        return packet

    def send_chat_opts(self): # 0x10 C>S chat opts
        packet = BotNetVLPacket(id = 0x10)
        packet.append_uint8(0x00) # subcommand 0
        packet.append_uint8(0x00) # broadcast option 0 (receive)
        packet.append_uint8(0x00) # database  option 0 (receive)
        packet.append_uint8(0x00) # whisper   option 1 (receive only if account)
        packet.append_uint8(0x00) # odb whisp option 0 (receive)
        return packet

    async def send_resp(self, to_send):
        """Send Response
        
        Send generated response(s) in to_send array to the socket. Used with constructed packets."""
        if self.state.socket:
            self.counter_on_last_packet = self.counter
            for resp in to_send:
                if resp is None: # yield None pauses instead of sends
                    await asyncio.sleep(1)
                else:
                    #print("send pkt 0x{:02x} len {}\n{}".format(bytes(resp)[1], len(resp), bytes(resp)))
                    await self.bot.loop.sock_sendall(self.state.socket, bytes(resp))

    async def on_message(self, message):
        """Handle on_message to send back to BotNet."""
        if message.type == discord.MessageType.pins_add and message.author.id == self.bot.user.id:
            # delete pin notice
            await message.delete()
            return

        if message.type != discord.MessageType.default:
            # this is a system message
            return

        if message.author.id == self.bot.user.id:
            # this is ours, discard early
            return
        
        if message.author.bot:
            # this is a bot, discard early
            return

        if len(message.clean_content) == 0:
            if len(message.attachments) == 0:
                # nothing to do, exit early
                return
        else:
            for prefix in await self.bot.get_prefix(message):
                if message.clean_content.startswith(prefix):
                    # starts with prefix, ignore command here
                    return

        if self.state.chat_ready:
            channel = message.channel
            if channel.id in self.channel_states:
                channel_state = self.channel_states[channel.id]
                can_chat = not channel_state.chat_disabled
                if len(channel_state.chat_roles) > 0:
                    # must pass one check if there's restrictions
                    can_chat = False
                    if 0 in channel_state.chat_roles:
                        # 0 in the list means always allowed
                        can_chat = True
                    else:
                        for role in message.author.roles:
                            if role.id in channel_state.chat_roles:
                                can_chat = True
                                break
                if can_chat:
                    if   channel_state.feed_type == "botnet":
                        to_send = self.handle_discord_message(message, out_suffix = "")
                        await self.send_resp(to_send)
                    elif channel_state.feed_type == "bncs":
                        botnet_account = channel_state.account_relay
                        if not botnet_account is None:
                            for bot_id, user in self.state.users.items():
                                if user.is_on_account() and user.account.lower() == botnet_account.lower():
                                    to_send = self.handle_discord_message(message, \
                                            length = 220, \
                                            out_prefix = "CHAT {} ".format(message.author.id), \
                                            whisper_to = bot_id)
                                    await self.send_resp(to_send)

    async def get_packet(self):
        """Get Packet
        
        Get one packet off the socket. Used only by Connect Feed."""
        pleft = 4
        header = b""
        while pleft > 0:
            part = await self.bot.loop.sock_recv(self.state.socket, pleft)
            if not part:
                #print("part is none - buf == {}".format(header))
                return None
            pleft -= len(part)
            header += part
        (proto, pid, plen) = struct.unpack("<BBH", header)
        pleft = plen - 4
        buf = b""
        while pleft > 0:
            part = await self.bot.loop.sock_recv(self.state.socket, pleft)
            if not part:
                #print("part is none - buf == {} + {}".format(header, buf))
                return None
            pleft -= len(part)
            buf += part
        self.counter_on_last_packet = self.counter
        #print("recv pkt 0x{:02x} len {}\n{}".format(header[1], len(header + buf), bytes(header + buf)))
        return BotNetVLPacket(data = bytearray(header + buf))

    async def post_userlist(self, channel, channel_state):
        """Tries to post the userlist and pin it to current channel.
        
        If we already have a valid existant pin, then edits that in place."""
        #print("Posting userlist for {}...".format(channel_state))
        #try:
        #except concurrent.futures.CancelledError as ex:
        #    # module unload or other cancel -- no return here
        #    pass
        if self.state.chat_ready:
            if not channel_state is None:
                if channel_state.do_users_pin:
                    if channel_state.userlist_update_lock:
                        #print("Waiting to update pin.")
                        return

                    channel_state.userlist_update_lock = True

                    # find message object if stored
                    if channel_state.users_pin == 0:
                        #print("Pin not set!")
                        print("Not set reason: not in config")
                        to_create = True
                    else:
                        try:
                            post = await channel.get_message(channel_state.users_pin)
                            if post.author.id != self.bot.user.id:
                                # not ours...
                                #print("Pin not owned!")
                                print("Not set reason: not owned")
                                to_create = True

                            to_create = False
                        except discord.NotFound:
                            # message was deleted
                            #print("Pin not found!")
                            to_create = True
                            print("Not set reason: discord says NotFound")
                        except discord.Forbidden:
                            print("Pin inaccessible!")
                            to_create = False
                            channel_state.userlist_update_lock = False
                            return
                        except Exception as ex:
                            # named but not accessible or something
                            print("BotNet EXCEPTION finding a stored pin ID: {}".format(ex))
                            to_create = False
                            channel_state.userlist_update_lock = False
                            return

                    # generate text for this message to be pinned
                    if   channel_state.feed_type == "botnet":
                        text = self.handle_botnet_userlist(channel_state.users, self.state.self_user)
                    elif channel_state.feed_type == "bncs":
                        text = self.handle_webchannel_bncs_userlist(channel_state, channel_state.account_relay_object, channel_state.users)
                    else:
                        print("BotNet WARNING: Unknown feed type userlist being pinned: {}".format(channel_state.feed_type))
                        return

                    if not to_create:
                        # updating a pinned post
                        #print("UPDATING EXISTING USERLIST")
                        try:
                            #print("{} userlist len {}".format(channel_state.account_relay, len(text)))
                            if post.content != text:
                                await post.edit(content=text)

                            if not post.pinned:
                                # not pinned
                                try:
                                    print("PIN REASON: NOT CURRENTLY PINNED")
                                    await post.pin()
                                except discord.Forbidden:
                                    # pin failed
                                    print("Pinning forbidden!")
                                    pass
                                except discord.NotFound:
                                    # pin missing
                                    print("Message gone!")
                                    return
                                except Exception as ex:
                                    print("BotNet EXCEPTION pinning a userlist: {}".format(ex))
                                    return
                        except discord.NotFound:
                            # pin missing
                            print("Message gone!")
                            to_create = True
                        except discord.Forbidden:
                            # edit failed
                            print("Editing forbidden!")
                            pass
                        except Exception as ex:
                            print("BotNet EXCEPTION updating a userlist: {}".format(ex))
                        finally:
                            channel_state.userlist_update_lock = False

                    # create or update the post
                    if to_create:
                        # creating and pinning post
                        try:
                            print("POSTING USERLIST")
                            post = await channel.send(content=text)
                        except discord.Forbidden:
                            # write failed
                            print("Message write forbidden!")
                            return
                        except discord.NotFound:
                            # write failed
                            print("Message write not allowed to inaccessible channel!")
                            return
                        except Exception as ex:
                            print("BotNet EXCEPTION posting a userlist: {}".format(ex))
                            return
                        finally:
                            channel_state.userlist_update_lock = False

                        try:
                            print("PIN REASON: POST CREATION")
                            await post.pin()
                        except discord.Forbidden:
                            # pin failed
                            print("Pinning forbidden!")
                            pass
                        except discord.NotFound:
                            # pin missing
                            print("Late! Message gone!")
                            return
                        except Exception as ex:
                            print("BotNet EXCEPTION pinning a userlist: {}".format(ex))

                        try:
                            channel_state.users_pin = post.id
                            await self.save_channel_config(channel, channel_state)
                        except Exception as ex:
                            print("BotNet EXCEPTION saving a userlist: {}".format(ex))

    async def post_joinpart(self, channel, channel_state, user, action, *, time = None):
        """Posts a join/part alert to the given channel for the given user."""
        if self.state.chat_ready:
            if not channel_state is None:
                if channel_state.do_join_part:
                    dt, dt_aware = self.parse_time_value(channel_state, time)
                    if channel_state.feed_type == "botnet":
                        if user.database != self.state.self_user.database:
                            # ignore other databases
                            return
                        
                        bnet_inf = self.handle_botnet_user(user)
                        if   action == "JOIN":
                            action = "connected to"
                        elif action == "PART":
                            action = "disconnected from"
                        else:
                            # ignore user updates and lists
                            return

                        text = "#{id}: {name} {action} {database}.".format( \
                                id = user.str_bot_id(), \
                                name = bnet_inf, \
                                action = action, \
                                database = user.database)
                    elif channel_state.feed_type == "bncs":
                        args = self.get_webchannel_bncs_users_item_format_args(channel_state, user)
                        args = {**args, **self.get_webchannel_bncs_users_list_format_args(channel_state, channel_state.account_relay_object)}
                        if   action == "JOIN":
                            args["action"] = "joined"
                            text = self.safe_format(channel_state.join_format,
                                    BotNetVL.channel_conf["join_format"]["default"], **args)
                        elif action == "PART":
                            args["action"] = "left"
                            text = self.safe_format(channel_state.part_format,
                                    BotNetVL.channel_conf["part_format"]["default"], **args)
                        else:
                            # ignore user updates and lists
                            return

                    try:
                        await channel.send(content=self.safe_format(channel_state.post_format,
                                BotNetVL.channel_conf["post_format"]["default"],
                                timestamp = dt_aware,
                                timestamp_utc = dt,
                                post = text))
                    except concurrent.futures.CancelledError as ex:
                        # module unload or other cancel -- no return here
                        pass
                    except discord.Forbidden:
                        # write failed
                        #print("Message write forbidden!")
                        return
                    except discord.NotFound:
                        # write failed
                        #print("Message write not allowed to inaccessible channel!")
                        return
                    except Exception as ex:
                        print("BotNet EXCEPTION posting join/part alert: {}".format(ex))

    async def post_chat(self, channel, channel_state, user, text, *, time = None, emote = False, broadcast = False, info = False, error = False, no_user = False):
        """Posts a remote message to a feed channel."""
        if self.state.chat_ready:
            if not channel_state is None:
                dt, dt_aware = self.parse_time_value(channel_state, time)

                if not user is None:
                    s = ""
                    if user.is_self:
                        s += channel_state.hl_self_format
                    if user.is_priority():
                        s += channel_state.hl_oper_format
                    if not channel_state.hl_norm_format in s:
                        s += channel_state.hl_norm_format
                else:
                    s = ""
                args = {
                        "hl"                : s, \
                        "hl_end"            : s[::-1], \
                        "name"              : self.escape_text(str(user)), \
                        "text"              : self.rich_text(text), \
                        }
                if broadcast:
                    args["info_type"] = "broadcast"
                    args["action"] = "bot_alert"
                elif info:
                    args["info_type"] = "info"
                    args["action"] = "bot_alert"
                elif error:
                    args["info_type"] = "error"
                    args["action"] = "bot_alert"
                elif emote:
                    args["info_type"] = "emote"
                    args["action"] = "emote"
                else:
                    args["info_type"] = "chat"
                    args["action"] = "chat"
                args["INFO_TYPE"] = args["info_type"].upper()
                args["NAME"] = args["name"].upper()

                if user is None or (no_user and user.is_self) or len(str(user)) == 0:
                    # special "server alert" mode
                    if args["action"] == "bot_alert":
                        args["action"] = "server_alert"
                    else:
                        args["action"] = "raw"

                if   args["action"] == "chat":
                    text = self.safe_format(channel_state.chat_format,
                            BotNetVL.channel_conf["chat_format"]["default"], **args)
                elif args["action"] == "emote":
                    text = self.safe_format(channel_state.emote_format,
                            BotNetVL.channel_conf["emote_format"]["default"], **args)
                elif args["action"] == "bot_alert":
                    text = self.safe_format(channel_state.bot_alert_format,
                            BotNetVL.channel_conf["bot_alert_format"]["default"], **args)
                elif args["action"] == "server_alert":
                    text = self.safe_format(channel_state.server_alert_format,
                            BotNetVL.channel_conf["server_alert_format"]["default"], **args)
                elif args["action"] == "raw":
                    # raw text = text
                    pass

                try:
                    await channel.send(content=self.safe_format(channel_state.post_format,
                            BotNetVL.channel_conf["post_format"]["default"],
                            timestamp = dt_aware,
                            timestamp_utc = dt,
                            post = text))
                except concurrent.futures.CancelledError as ex:
                    # module unload or other cancel -- no return here
                    pass
                except discord.Forbidden:
                    # write failed
                    #print("Message write forbidden!")
                    return
                except discord.NotFound:
                    # write failed
                    #print("Message write not allowed to inaccessible channel!")
                    return
                except Exception as ex:
                    print("BotNet EXCEPTION posting chat: {}".format(ex))
                    traceback.print_exc()

    def botnet_on_userlist(self, users):
        """Event that occurs when userlist is received."""
        #print("BotNet USERLIST: {} users".format(len(users)))
        self.botnet_on_user_event(None, "LIST")

    def botnet_on_user(self, user, on_connect = False):
        """Event that occurs when singular user update is received."""
        #print("BotNet USER 0x{:x}: {}".format(user.bot_id, user))
        if on_connect:
            action = "JOIN"
        else:
            action = "UPDATE"
        self.botnet_on_user_event(user, action)

    def botnet_on_userdisc(self, user):
        """Event that occurs when singular user disconnects."""
        #print("BotNet DISC 0x{:x}: {}".format(user.bot_id, user))
        self.botnet_on_user_event(user, "PART")

    def botnet_on_user_event(self, user, action):
        """Called by the three other botnet_on_user* events."""
        # update all BotNet feeds
        for channel_id, channel_state in self.channel_states.items():
            if channel_state.feed_type == "botnet":
                channel = self.bot.get_channel(channel_id)
                if channel:
                    # store BotNet user list (REFERENCE) in channel_state
                    channel_state.users = self.state.users

                    # post BotNet userlist
                    coro = self.post_userlist(channel, channel_state)
                    self.tasks.append(self.bot.loop.create_task(coro))

                    if not user is None:
                        # post BotNet join/part alert
                        coro = self.post_joinpart(channel, channel_state, user, action)
                        self.tasks.append(self.bot.loop.create_task(coro))

        # update all BNCS channel feeds (for only those that have been changed)
        for channel_id, channel_state in self.channel_states.items():
            if channel_state.feed_type == "bncs":
                # only continue if JOIN/PART/UPDATE is this feed's account_relay
                # or if LIST, all BotNet users were updated and affects all feeds
                if user is None or \
                            (user.is_on_account() and \
                             channel_state.account_relay.lower() == user.account.lower()):

                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        # check if this BNCS channel state has a null account object
                        relay = self.botnet_get_relay_account(channel, channel_state, user, action)
                        if not relay is channel_state.account_relay_object:
                            channel_state.account_relay_object = relay

                            # post BNCS userlist if change
                            coro = self.post_userlist(channel, channel_state)
                            self.tasks.append(self.bot.loop.create_task(coro))

    def botnet_get_relay_account(self, channel, channel_state, user, action):
        """Gets what the account_relay_object on a channel_state should reference, from a given BotNet join/part event."""
        if user is None:
            # find this account in "LIST"
            for bot_id, user_item in self.state.users.items():
                if user_item.is_on_account() and \
                        channel_state.account_relay.lower() == user_item.account.lower():
                    user = user_item
                    break

        if user is None or action == "PART":
            # this BNCS channel state doesn't belong to an online BotNet user
            #print("BotNet WARNING: User account {} is not online for channel {}.".format(channel_state.account_relay, channel.mention))
            user = None

        # save this (REFERENCE) in channel state
        return user

    def botnet_on_chat(self, user, message, command, action):
        """Event that occurs when chat is received."""
        try:
            #print("BotNet CHAT from {}: {}".format(user, message))
            if   command == 0x00 or command == 0x01:
                # BotNet chat or broadcast
                emote = (action == 0x01)
                broadcast = (command == 0x00)

                for channel_id, channel_state in self.channel_states.items():
                    if channel_state.feed_type == "botnet":
                        channel = self.bot.get_channel(channel_id)
                        if channel and isinstance(channel, discord.TextChannel):
                            coro = self.post_chat(channel, channel_state, user, message, emote = emote, broadcast = broadcast)
                            self.tasks.append(self.bot.loop.create_task(coro))
                        else:
                            # channel does not exist
                            continue

            elif command == 0x02:
                # BotNet whisper, interpret as BNCS WebChannel command
                for action in self.botnet_parse_bncs_event(user, message):
                    if action["target"] == "global":
                        coro = self.botnet_dispatch_bncs_event(None, None, user, message, action)
                        self.tasks.append(self.bot.loop.create_task(coro))
                    elif action["target"] == "feed":
                        for channel_id, channel_state in self.channel_states.items():
                            if channel_state.feed_type == "bncs":
                                channel = self.bot.get_channel(channel_id)
                                if channel and isinstance(channel, discord.TextChannel):
                                    coro = self.botnet_dispatch_bncs_event(channel, channel_state, user, message, action)
                                    self.tasks.append(self.bot.loop.create_task(coro))
                                else:
                                    # channel does not exist
                                    continue

        except Exception as ex2:
            print("BotNet EXCEPTION parsing BotNet chat: {}".format(ex2))

    def botnet_parse_bncs_event(self, user, message):
        """Parses the given BotNet whisper as a WebChannel message."""
        try:
            cmd, sep, data = message.lstrip().partition(" ")
            cmd = cmd.upper()
            if   cmd == "CHATON":
                # enable chat back
                yield { "target": "feed", "type": "set_key", "key": "chat_disabled", "value": False }
                yield { "target": "global", "type": "request_status", "chat": True }
            elif cmd == "CHATOFF":
                # disable chat back
                yield { "target": "feed", "type": "set_key", "key": "chat_disabled", "value": True }
                yield { "target": "global", "type": "request_status", "chat": False }
            elif cmd == "TEXT":
                # special TEXT raw message
                [evtm, evtx] = data.split(" ", 1)
                try:
                    evtm = int(evtm, 16)
                except ValueError:
                    # not a valid timestamp
                    return
                yield { "target": "feed", "type": "post_chat", "args": { "user": None, "text": evtx, "time": evtm } }
            elif cmd == "EVENT":
                # event parsing
                [evid, evfl, evpi, evtm, evus, evtx] = data.split(" ", 5)
                try:
                    evid = int(evid, 16)
                    evfl = int(evfl, 16)
                    evpi = int(evpi, 16)
                    evtm = int(evtm, 16)
                except ValueError:
                    # not a valid id, flags, ping, or timestamp
                    return

                # make ping signed 32-bit integer
                if evpi & 0x80000000:
                    evpi = -0x100000000 + evpi

                # if "[Server Broadcast] " EID_ERROR
                if evid == 0x13 and evtx.lower().startswith("[server broadcast] "):
                    # fake EID_BROADCAST
                    evtx = evtx[19:]
                    evid = 0x06

                # if username starts with "w#", strip it now
                if evus.lower().startswith("w#"):
                    evus = evus[2:]

                # store ev object
                ev = { "id": evid, "flags": evfl, "ping": evpi, "time": evtm, "name": evus, "text": evtx }
                if evid == 0x00 or evid == 0x05 or evid == 0x06 or evid == 0x12 or evid == 0x13 or evid == 0x17:
                    # chat events (self, talk, server broadcast, server info, server error, emote)
                    yield { "target": "feed", "type": "event_chat", "event": ev }
                elif evid == 0x04 or evid == 0x0A:
                    # whisper events
                    # skip
                    pass
                elif evid == 0x01 or evid == 0x02 or evid == 0x03 or evid == 0x09:
                    # join/part/update
                    yield { "target": "feed", "type": "event_joinpart", "event": ev }
                elif evid == 0x07:
                    # enter channel
                    yield { "target": "feed", "type": "event_channel", "event": ev }
            elif cmd == "URL":
                # URL info for WebChannel
                # information is unnecessary
                pass
            else:
                # unknown
                print("BotNet WARNING BotNet WebChannel received unknown command: {} {}".format(cmd, data))
        except Exception as ex:
            print("BotNet EXCEPTION parsing BotNet WebChannel command: {}".format(ex))

    async def botnet_dispatch_bncs_event(self, channel, channel_state, botnet_user, botnet_message, action):
        """Handles the given BNCS feed event."""
        try:
            if channel_state is None:
                if action["type"] == "request_status":
                    status = [ "ERROR", "0", ""]
                    try:
                        # tell BotNet user about status
                        if not botnet_user.is_on_account():
                            status[1] = "2"
                            status[2] = "You must be on a BotNet account."
                        else:
                            # find this account's "first" feed and store it
                            first_feed = None
                            first_channel_id = 0
                            for channel_id, channel_state in self.channel_states.items():
                                if channel_state.feed_type == "bncs":
                                    if not channel_state.account_relay_object is None:
                                        if channel_state.account_relay_object.account.lower() == botnet_user.account.lower():
                                            first_feed = channel_state
                                            first_channel_id = channel_id
                                            break

                            if first_feed is None:
                                # error: no feeds are setup for that account
                                status[1] = "1"
                                status[2] = "There are no feeds expecting that account."
                            else:
                                channel = self.bot.get_channel(first_channel_id)
                                if   not channel:
                                    # error: inaccessible Discord channel
                                    status[1] = "3"
                                    status[2] = "Discord channel inaccessible."
                                elif not isinstance(channel, discord.TextChannel):
                                    # error: Discord channel is of wrong type
                                    status[1] = "4"
                                    status[2] = "Discord channel not a TextChannel."
                                else:
                                    # successfully gathered status
                                    if first_feed.chat_disabled:
                                        status[0] = "CHATOFF"
                                    else:
                                        status[0] = "CHATON"
                                    status[1] = "#{}".format(channel.name)
                                    status[2] = channel.guild.name
                    except Exception as ex:
                        status[0] = "ERROR"
                        status[1] = "0"
                        status[2] = "An exception occured."

                    # send compiled status
                    status.insert(0, "STATUS")
                    status_str = " ".join(status)
                    print("{} -> {}".format(botnet_user.account, status_str))
                    to_send = [self.send_chat(status_str, whisper_to = botnet_user.bot_id)]
                    await self.send_resp(to_send)

            else:
                if channel_state.account_relay_object is None or \
                        channel_state.account_relay_object.account.lower() != botnet_user.account.lower():
                    # this event does not belong to this BotNet user, channel_state pair
                    return

                if   action["type"] == "set_key":
                    setattr(channel_state, action["key"], action["value"])

                elif action["type"] == "post_chat":
                    await self.post_chat(channel, channel_state, **action["args"])

                elif action["type"] == "event_chat":
                    if action["event"]["id"] == 0x00 and not channel_state.do_echo_self:
                        return

                    # find user in user list
                    user_obj = None
                    for user in channel_state.users:
                        if user.name == action["event"]["name"] and user.ping == action["event"]["ping"]:
                            # this is this user
                            user_obj = user
                            break
                    if user_obj is None:
                        # make dummy
                        user_obj = BotNetVLWebChannelUser(action["event"]["name"], \
                                action["event"]["flags"], action["event"]["ping"], \
                                "", 0,
                                is_self = channel_state.account_relay_object.bnet_name == action["event"]["name"])

                    emote = (action["event"]["id"] == 0x17)
                    broadcast = (action["event"]["id"] == 0x06)
                    info = (action["event"]["id"] == 0x12)
                    error = (action["event"]["id"] == 0x13)
                    no_user = (broadcast or info or error)

                    await self.post_chat(channel, channel_state, user_obj, action["event"]["text"], \
                            time = action["event"]["time"], \
                            emote = emote, broadcast = broadcast, \
                            info = info, error = error, no_user = no_user)

                elif action["type"] == "event_joinpart":
                    # user update events
                    user_obj = None
                    for user in channel_state.users:
                        if user.name == action["event"]["name"] and user.ping == action["event"]["ping"]:
                            # this is this user
                            user_obj = user
                            break
                    
                    is_self = (channel_state.account_relay_object.bnet_name == action["event"]["name"])

                    # decide how to handle event to update data
                    if   action["event"]["id"] == 0x03: # leave
                        if not user_obj is None:
                            channel_state.users.remove(user_obj)

                    elif action["event"]["id"] == 0x02 or user_obj is None: # join/new user
                        channel_state.join_counter += 1
                        user_obj = BotNetVLWebChannelUser(action["event"]["name"], \
                                action["event"]["flags"], action["event"]["ping"], \
                                action["event"]["text"], channel_state.join_counter,
                                is_self = is_self, time = action["event"]["time"])
                        user_obj.do_parse_text()
                        channel_state.users.append(user_obj)

                    elif not user_obj is None: # update/existing user
                        user_obj.flags = action["event"]["flags"]
                        user_obj.ping = action["event"]["ping"]
                        if len(action["event"]["text"]) > 0 and user_obj.text != action["event"]["text"]:
                            user_obj.text = action["event"]["text"]
                            user_obj.do_parse_text()

                    if not user_obj is None:
                        if action["event"]["id"] == 0x02:
                            uaction = "JOIN"
                        elif action["event"]["id"] == 0x03:
                            uaction = "PART"
                        else:
                            uaction = "UPDATE"
                        # post BotNet join/part alert
                        await self.post_joinpart(channel, channel_state, user_obj, uaction, time = action["event"]["time"])

                    # decide how to dispatch
                    if action["event"]["id"] == 0x02 or \
                       action["event"]["id"] == 0x03 or \
                       action["event"]["id"] == 0x09 or \
                       is_self:
                        # reasons to update:
                        # - event is join, leave, or flagupdate
                        # - showuser is for WebChannel relay on BotNet's Battle.net name
                        await self.post_userlist(channel, channel_state)
                        channel_state.userlist_dirty = False
                    else:
                        channel_state.userlist_dirty = True
                        return

                elif action["type"] == "event_channel":
                    # clear our wc user list
                    # let the BotNet update change pin
                    del channel_state.users[:]
                    channel_state.join_counter = 0
                    channel_state.userlist_dirty = False

                # if we got here, we processed a line and our userlist is still dirty, update it
                if channel_state.userlist_dirty:
                    channel_state.userlist_dirty = False
                    await self.post_userlist(channel, channel_state)
        except concurrent.futures.CancelledError as ex:
            # module unload or other cancel -- no return here
            pass
        except Exception as ex:
            print("BotNet EXCEPTION handling BotNet WebChannel command: {}".format(ex))

    def escape_text(self, text):
        """Escapes text to be passed to discord."""
        text = text.replace("\\", "\\\\")
        text = text.replace("*", "\\*")
        text = text.replace("~", "\\~")
        text = text.replace("_", "\\_")
        text = text.replace("<", "\\<")
        text = text.replace(":", "\\:")
        text = text.replace("`", "\\`")
        text = text.replace("@", "\\@")
        return escape(text, mass_mentions=True)

    def rich_text(self, text):
        """Prepares rich text (user chat) to be passed from BotNet/Battle.net to discord."""
        text = self.escape_text(text)
        repl = []
        for link_match in BotNetVL.re_discord_link.finditer(text):
            l_text = link_match.group(0)
            l_text = l_text.replace("\\:", ":")
            l_text = l_text.replace("\\<", "<")
            l_text = l_text.replace("\\_", "_")
            l_text = l_text.replace("\\~", "~")
            l_text = l_text.replace("\\@", "@")
            l_before = link_match.group(0)
            if "%28" in l_text or "(" in l_text:
                #print("len {} endpos {}".format(len(text), link_match.end(0)))
                endpos = link_match.end(0)
                if len(text) >= endpos + 1:
                    if   text[endpos] == ")":
                        l_before += ")"
                        l_text += ")"
                    elif text[endpos:endpos + 2] == "%29":
                        l_before += "%29"
                        l_text += "%29"
            if not l_text.startswith("<") and not l_text.endswith(">"):
                l_text = "<{}>".format(l_text)
            #print(" _{}_ -> _{}_ ".format(l_before, l_text))
            repl.append((l_before, l_text))

        for em_match in BotNetVL.re_discord_emoji.finditer(text):
            em_text = em_match.group(0)
            em_name = em_match.group(1)
            for em_obj in self.bot.emojis:
                if em_obj.name == em_name:
                    repl.append((em_text, str(em_obj)))
                    break

        for (find, sub) in repl:
            text = text.replace(find, sub)

        return text

    def safe_format(self, format_str, default_format_str, **args):
        """Runs a format attempt and if it fails due to an unknown parameter, run the default format instead."""
        try:
            return format_str.format(**args)
        except KeyError:
            try:
                return default_format_str.format(**args)
            except KeyError:
                return "*Safe format failed.*"

    def parse_time_value(self, channel_state, time_value):
        """Takes a timezone object and localizes the given time_value. If time_value is None, assumed to be "now"."""
        if time_value:
            dt = datetime.utcnow()
            dt = datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)
            dt += timedelta(seconds=time_value)
        else:
            dt = datetime.utcnow()
        if channel_state:
            dt_aware = channel_state.timezone_object.localize(dt)
            dt_aware += channel_state.timezone_object.utcoffset(dt)
        else:
            dt_aware = dt
        return dt, dt_aware

    def handle_discord_message(self, message, *, length = 496, in_prefix = "", out_prefix = "", out_suffix = "", whisper_to = 0):
        """Takes a Discord message object and parses the content to be sent to BotNet."""
        if len(in_prefix) > 0:
            if message.clean_content.startswith(in_prefix):
                clean_content = message.clean_content[len(in_prefix):]
            else:
                return []
        else:
            clean_content = message.clean_content

        # convert default emoji
        clean_content = emoji.demojize(clean_content)

        # convert custom emoji
        repl = []
        for em_match in BotNetVL.re_discord_emoji_object.finditer(clean_content):
            repl.append((em_match.group(0), em_match.group(1)))
        for (find, sub) in repl:
            clean_content = clean_content.replace(find, sub)

        # convert text to array of strings
        messages      = self.handle_discord_text(clean_content, self.handle_discord_author(message.author), length)
        # convert attachments to array of strings
        messages     += self.handle_discord_attachments(message.attachments)
        if len(messages) == 0:
            # no usable content
            return []
        to_send = []
        for content in messages:
            if len(content.strip()) > 0:
                emote = False
                if len(content) > 1 and \
                  ((content.startswith("*") and content.endswith("*") and not content.endswith("**")) or \
                  (content.startswith("_") and content.endswith("_") and not content.endswith("__"))):
                    content = content[1:-1]
                    emote = True
                text = "{out_pref}{author}{out_suf} {content}".format( \
                        out_pref = out_prefix, \
                        out_suf = out_suffix, \
                        author = self.handle_discord_author(message.author), \
                        content = content)
                to_send.append(self.send_chat(text, whisper_to = whisper_to, emote = emote))
        return to_send

    def handle_discord_author(self, author):
        """Returns the Discord user's name or nick."""
        if author.nick and len(author.nick):
            text = author.nick
        else:
            text = author.name
        return "{name}#{discr}".format( \
                name = text.replace("\\", "\\\\").replace("_", "\\_").replace(" ", "_"), \
                discr = author.discriminator)

    def handle_discord_text(self, clean_content, prefix, length):
        """Splits long text to be passed from discord to BotNet.
        
        Assumes UTF-8 and maximum string length provided, and the given prefix string."""
        prefix_len = len(prefix.encode("utf-8")) + 2
        messages = clean_content.replace("\r\n", "\n").split("\n")
        index = 0
        while index < len(messages):
            # loops through the messages in array
            char = 0
            count = prefix_len
            last_space = 0
            message = messages[index]
            while char < len(message):
                # loops through the characters
                if message[char].isspace():
                    last_space = char
                count += len(message[char].encode("utf-8"))
                if count >= length:
                    # reached a message that's too long on its own
                    if last_space < length - 32:
                        # too long an ending word, let's break it
                        left = message[:length - 1] + '-'
                        right = message[length - 1:]
                    else:
                        # break at last space
                        left = message[:last_space]
                        right = message[last_space + 1:]
                    # set this index to left-half
                    messages[index] = left
                    # insert right-half after this
                    messages.insert(index + 1, right)
                    # set indices to continue looking as if right-half is current index
                    index += 1
                    char = -1
                    count = prefix_len - len(message[0].encode("utf-8"))
                    last_space = 0
                    message = messages[index]
                char += 1
            index += 1
        return messages

    def handle_discord_attachments(self, attachments):
        """Gets the text-only version of a list of attachments to be seen on BotNet as links."""
        messages = []
        for attach in attachments:
            if hasattr(attach, "width") and hasattr(attach, "height"):
                wxh = "; {w} x {h}".format(w = attach.width, h = attach.height)
            else:
                wxh = ""
            messages.append("Attachment: {link} (size: {fsize}{dsize})".format( \
                    link = attach.url, \
                    fsize = self.byte_size(attach.size), \
                    dsize = wxh))
        return messages

    def byte_size(self, bytelen):
        """Returns human-friendly file size from a given number of bytes."""
        units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB']
        ind = int(math.log2(bytelen) / 10.0)
        if ind >= len(units):
            ind = len(units) - 1
        if ind > 0:
            val = round(bytelen / (1 << (10 * ind)), 2)
        else:
            val = int(bytelen)
        return "{} {}".format(val, units[ind])

    def handle_webchannel_bncs_userlist(self, channel_state, user, wc_users):
        """Creates a textual list of users on BotNet WebChannel (on Battle.net) for use on discord."""
        userlist_fmt = ""

        if user is None or not user.is_on_bnet():
            return "*Battle.net feed is currently unavailable.*"

        userlist = sorted([x for x in wc_users if x]) # sorts by priority

        list_args = self.get_webchannel_bncs_users_list_format_args(channel_state, user)
        list_args["count"]  = len(wc_users)
        list_args["list"]   = ""
        channel_wrapper = self.safe_format(channel_state.users_list_format,
                BotNetVL.channel_conf["users_list_format"]["default"], **list_args)

        n = len(userlist)
        for wc_user in userlist:
            and_n_more = "*...and {count} more.*".format(count = n)
            user_args = self.get_webchannel_bncs_users_item_format_args(channel_state, wc_user)
            bnet_inf = self.safe_format(channel_state.users_item_format,
                    BotNetVL.channel_conf["users_item_format"]["default"], **user_args)
            if len(channel_wrapper) + len(userlist_fmt) + len(and_n_more) + len(bnet_inf) + 1 > 2000:
                # too long, step out now!
                userlist_fmt += and_n_more
                break
            else:
                # continue adding this item
                userlist_fmt += "{}\n".format(bnet_inf)
                n = n - 1

        if len(wc_users) == 0:
            userlist_fmt = "*No users.*"

        list_args["list"] = userlist_fmt
        return self.safe_format(channel_state.users_list_format,
                BotNetVL.channel_conf["users_list_format"]["default"], **list_args)

    def get_webchannel_bncs_users_item_format_args(self, channel_state, wc_user):
        """Converts a BotNet WebChannel (on Battle.net) user item to a set of args to pass to format(channel_state.users_item_format)."""
        s = ""
        prod = wc_user.product
        prod_oper = prod
        if wc_user.is_self:
            s += channel_state.hl_self_format
        if wc_user.is_priority():
            prod_oper = "_oper"
            s += channel_state.hl_oper_format
        if not channel_state.hl_norm_format in s:
            s += channel_state.hl_norm_format
        return {
                "hl"                : s,
                "hl_end"            : s[::-1],
                "name"              : self.escape_text(wc_user.name),
                "flags"             : wc_user.flags,
                "ping"              : wc_user.ping,
                "oper"              : wc_user.is_priority(),
                "is_self"           : wc_user.is_self,
                "prod"              : prod,
                "prod_icon"         : self.emoji_name(prod),
                "prod_list"         : prod_oper,
                "prod_list_icon"    : self.emoji_name(prod_oper),
                "text"              : wc_user.text,
                "prod_name"         : wc_user.product_name,
                "prod_name_short"   : wc_user.product_name_short,
                "text_parsed_1"     : wc_user.text_parsed_1,
                "text_parsed_2"     : wc_user.text_parsed_2,
                "text_parsed_3"     : wc_user.text_parsed_3,
                "tag"               : wc_user.get_value("tag", ""),
                "Clan_tag"          : wc_user.get_value("Clan_tag", ""),
                "clan_tag"          : wc_user.get_value("clan_tag", ""),
                "level"             : wc_user.get_value("level", 0),
                "level_or_empty"    : str(wc_user.get_value("level", "")),
                "wins"              : wc_user.get_value("wins", 0),
                "wins_or_empty"     : str(wc_user.get_value("wins", "")),
                "char_name"         : wc_user.get_value("char_name", ""),
                }

    def get_webchannel_bncs_users_list_format_args(self, channel_state, user):
        """Converts a BotNet WebChannel (on Battle.net) user list to a set of args to pass to format(channel_state.users_list_format)."""
        return {
                "channel"           : self.escape_text(user.bnet_channel),
                "server_address"    : user.bnet_server,
                "server"            : self.address_friendlyname(user.bnet_server),
                "server_icon"       : self.emoji_name(self.address_friendlyname(user.bnet_server)),
                }

    def handle_botnet_userlist(self, users, self_user):
        """Creates a textual list of users on BotNet for use on discord.
        
        Groups by database."""
        try:
            userlist_fmt = ""
            userlist_fmt_my_db = ""
            db_count = 0

            def db(user):
                return user.database

            userlist = sorted(users.values(), key=db)
            for k, g in itertools.groupby(userlist, key=db):
                db_count += 1
                and_n_more_db = "*...and {count} other databases.*".format(count = db_count - 1)
                if not k is None and len(k) > 0:
                    text = "__{}__\n".format(k)
                else:
                    text = "__*Public*__\n"
                if k == self_user.database:
                    userlist_fmt_my_db += text
                else:
                    userlist_fmt += text
                for user in g:
                    bnet_inf = self.handle_botnet_user(user)
                    text = "#{}: {}\n".format(user.str_bot_id(), bnet_inf)
                    if k == self_user.database:
                        userlist_fmt_my_db += text
                    else:
                        userlist_fmt += text
                if k == self_user.database:
                    userlist_fmt_my_db += "\n"
                else:
                    userlist_fmt += "\n"

            #for user in users.values():
            #    bnet_inf = self.handle_botnet_user(user)
            #    userlist_fmt += "#{}: {}\n".format(user.str_bot_id(),  bnet_inf)

            if len(userlist_fmt) == 0 and len(userlist_fmt_my_db) == 0:
                userlist_fmt = "*No users.*"

            wrapper = "__**Users on BotNet ({count})**__\n\n{my_db_list}{list}".format( \
                    count = len(users), \
                    my_db_list = "", list = "")

            if len(wrapper) + len(userlist_fmt) + len(userlist_fmt_my_db) > 2000:
                userlist_fmt = and_n_more_db

            return "__**Users on BotNet ({count})**__\n\n{my_db_list}{list}".format( \
                    count = len(users), \
                    my_db_list = userlist_fmt_my_db, \
                    list = userlist_fmt)
        except Exception as ex:
            print("BotNet EXCEPTION creating BotNet userlist: {}".format(ex))

    def handle_botnet_user(self, user):
        """Converts a user object to text form to be displayed on discord.

        Used in both userlist and connect/disconnect alerts.
        
        Parts: account name, Battle.net name, Battle.net channel, Battle.net server."""
        # account name, bold
        if user.is_on_account():
            account = "**{}**".format(self.escape_text(user.account))
        else:
            account = ""

        # Battle.net name part
        bnet_name = self.escape_text(user.bnet_name)
        if bnet_name != user.account:
            if len(user.account) > 0:
                # user.account non-empty
                bnet_name = ", {}".format(bnet_name)
        else:
            # duplication of user.account
            bnet_name = ""

        # server location
        if user.is_on_bnet():
            # get server
            server_name = self.emoji_name(self.address_friendlyname(user.bnet_server))
            # for online: account, BNCS name @ BNCS chan[BNCS server]
            bnet_inf = "{account}{name} @ {channel}{server}".format( \
                    account = account, \
                    name = bnet_name, \
                    channel = self.escape_text(user.bnet_channel), \
                    server = server_name)
        else:
            # for offline: account, BNCS name[offline]
            bnet_inf = "{account}{name}{disc}".format( \
                    account = account, \
                    name = bnet_name, \
                    disc = self.emoji_name("_bnet_disc"))

        # disabled: user db access and admin access
        #if user.database_access and user.database_access > 0:
        #    bnet_inf += "+DB[{}]".format(user.database_access)
        #if user.admin_access and user.admin_access > 0:
        #    bnet_inf += "+A[{}]".format(user.admin_access_flags())

        return bnet_inf

    def emoji_name(self, text, *, fallback = True):
        """Return the emoji name in the emoji text."""
        if text in BotNetVL.emoji_map:
            return BotNetVL.emoji_map[text]
        else:
            if fallback:
                return BotNetVL.emoji_map["_"]
            else:
                return text

    def address_friendlyname(self, intval):
        """Uses the cached self.resolve_map object to find a friendly name for a Battle.net server."""
        if intval == 0xffffffff or intval == 0:
            return ""

        dotted = socket.inet_ntoa(struct.pack("<I", intval))
        for friendly, domain in self.resolve_map.items():
            if dotted in domain["addresses"]:
                # cached
                return friendly

        return dotted

    def address_friendlyname_ignorethis(self, dotted):
        """address_friendlyname() removed code that would do blocking DNS reverse requests... it doesn't seem this would work. We must manually list server IPs in self.resolve_map for now."""
        # warning: blocking??
        try:
            hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(dotted)
            #print("resolved {} as {}".format(hostname, ipaddrlist))
        except OSError:
            return dotted
        for friendly, domain in self.resolve_map.items():
            if hostname == domain["domain"]:
                # one of the default four
                domain["addresses"] += ipaddrlist
                return friendly

        # not cached
        friendly = hostname.split(".")[0].title()
        self.resolve_map[friendly] = {"domain": hostname, "addresses": ipaddrlist}
        return friendly

    def print_conf_data(self, ctx, data):
        mkl = 0
        for k, v in data.items():
            if len(k) + 4 > mkl:
                mkl = len(k) + 4
        s = ""
        for k, v in data.items():
            if k.endswith("pass") and len(str(res)) > 0 and not ctx.guild is None:
                res = "****"
            else:
                res = repr(v)
            s += "{k}{v}\n".format(k = k.ljust(mkl), v = res)
        return "```\n{}```".format(s)

    def escape_code_text(self, text):
        return text.replace("`", "\\`").replace("\n", "\\n")

    def parse_conf_value(self, ctx, val, typ):
        if   typ == "str" or typ.startswith("str:"):
            if val.startswith("\"") and val.endswith("\""):
                val = val[1:-1]
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            val = val.replace("\\n", "\n")
            val = val.replace("\\r", "")
            val = val.replace("\\t", "\t")
            val = val.replace("\\\"", "\"")
            val = val.replace("\\'", "'")
            val = val.replace("\\\\", "\\")
            if typ == "str:timezone":
                val = val.replace(" ", "_")
                found = False
                if not found:
                    # check for exact match
                    for timezone in pytz.common_timezones:
                        if val.lower() == timezone.lower():
                            val = timezone
                            found = True
                            break
                if not found:
                    # check for partial match
                    for timezone in pytz.common_timezones:
                        if timezone.lower().startswith(val.lower()):
                            if found:
                                raise ValueError("Multiple timezones match that name.")
                            val = timezone
                            found = True
                if not found:
                    raise ValueError("No timezones match that name.")
                val = val.replace("_", " ")
            return val
        if   typ == "guild-id":
            typ = "int"
        if   typ == "channel-id":
            if len(ctx.message.channel_mentions) > 1:
                return ctx.message.channel_mentions[1]
            typ = "int"
        if   typ == "user-id" or typ == "member-id":
            if len(ctx.message.mentions) > 0:
                return ctx.message.mentions[0]
            typ = "int"
        if   typ == "role-id" or typ == "role-id":
            if len(ctx.message.mentions) > 0:
                return ctx.message.mentions[0]
            typ = "int"
        if   typ == "int":
            try:
                return int(val)
            except ValueError:
                raise
        if   typ == "bool":
            if   val.lower() in ["true", "t", "yes", "y", "on"]:
                return True
            elif val.lower() in ["false", "f", "no", "n", "off"]:
                return False
            else:
                return None
        
        return val

    @commands.command(aliases=["bnreconnect", "bnrc"])
    @checks.is_owner()
    async def botnetreconnect(self, ctx):
        """Cancels all pending tasks and reconnects to BotNet."""
        for task in self.tasks:
            task.cancel()
        del self.tasks[:]
        coro = self.botnet_main()
        self.tasks.append(self.bot.loop.create_task(coro))

    @commands.command(aliases=["bnfeed"])
    @checks.is_owner()
    async def botnetfeed(self, ctx, channel : discord.TextChannel):
        """Creates a feed between the Discord channel and the BotNet server."""
        if channel.id in self.channel_states:
            await ctx.send(content=error("A channel feed is already present in that channel."))
            return

        # set values
        channel_state = BotNetVLChannelState()
        channel_state.guild         = channel.guild.id
        channel_state.feed_type     = "botnet"
        # save channel config
        await self.save_channel_config(channel, channel_state)
        # save channel state to self
        self.channel_states[channel.id] = channel_state

        try:
            if self.state.hub_automirror:
                hub_guild = self.bot.get_guild(self.state.hub_guild)
                hub_cat = self.bot.get_channel(self.state.hub_category)
                if hub_guild:
                    if hub_cat:
                        mirror_channel = await hub_guild.create_text_channel(channel.name, category=hub_cat, reason="Mirror #{} on {}".format(channel.name, channel.guild.name))
                    else:
                        mirror_channel = await hub_guild.create_text_channel(channel.name, reason="Mirror of #{} on {}".format(channel.name, channel.guild.name))

                    # set values
                    channel_state = BotNetVLChannelState()
                    channel_state.guild         = mirror_channel.guild.id
                    channel_state.channel_cb    = channel.id
                    channel_state.feed_type     = "botnet"
                    # save channel config
                    await self.save_channel_config(mirror_channel, channel_state)
                    # save channel state to self
                    self.channel_states[mirror_channel.id] = channel_state
        except Exception as ex:
            print("BotNet EXCEPTION creating mirror channel: {}".format(ex))

        await ctx.send(content=info("Created a channel feed to the BotNet server in {}.".format(channel.mention)))

        # reconnect BotNet to make use...
        for task in self.tasks:
            task.cancel()
        del self.tasks[:]
        coro = self.botnet_main()
        self.tasks.append(self.bot.loop.create_task(coro))

    @commands.command()
    @checks.guildowner_or_permissions(manage_guild=True)
    async def bncsfeed(self, ctx, channel : discord.TextChannel, account_name : str):
        """Creates a feed between the Discord channel and a Classic Battle.net channel."""
        if channel.guild is None or ctx.guild is None or channel.guild.id != ctx.guild.id:
            await ctx.send(content=error("That channel is not known. You must be an administrator or server owner and execute this command on the server."))
            return

        if channel.id in self.channel_states:
            await ctx.send(content=error("A channel feed is already present in that channel."))
            return

        # set values
        channel_state = BotNetVLChannelState()
        channel_state.guild         = channel.guild.id
        channel_state.feed_type     = "bncs"
        channel_state.account_relay = account_name
        # save channel config
        await self.save_channel_config(channel, channel_state)
        # save channel state to self
        self.channel_states[channel.id] = channel_state

        try:
            if self.state.hub_automirror:
                hub_guild = self.bot.get_guild(self.state.hub_guild)
                hub_cat = self.bot.get_channel(self.state.hub_category)
                if hub_guild:
                    if hub_cat:
                        mirror_channel = await hub_guild.create_text_channel(channel.name, category=hub_cat, reason="Mirror #{} on {}".format(channel.name, channel.guild.name))
                    else:
                        mirror_channel = await hub_guild.create_text_channel(channel.name, reason="Mirror of #{} on {}".format(channel.name, channel.guild.name))

                    # set values
                    hub_channel_state = BotNetVLChannelState()
                    hub_channel_state.guild         = mirror_channel.guild.id
                    hub_channel_state.channel_cb    = channel.id
                    hub_channel_state.feed_type     = "bncs"
                    hub_channel_state.account_relay = account_name
                    # save channel config
                    await self.save_channel_config(mirror_channel, hub_channel_state)
                    # save channel state to self
                    self.channel_states[mirror_channel.id] = hub_channel_state
        except Exception as ex:
            print("BotNet EXCEPTION creating mirror channel: {}".format(ex))

        # send RESET to this account, if online and account_relay_object is incorrect
        relay = self.botnet_get_relay_account(channel, channel_state, None, "RESET")
        if not relay is channel_state.account_relay_object:
            channel_state.account_relay_object = relay
            if relay:
                reset_str = "RESET"
                print("{} -> {}".format(relay.account, reset_str))
                to_send = [self.send_chat(reset_str, whisper_to = relay.bot_id)]
                await self.send_resp(to_send)
            else:
                # post userlist immediately since feed not online
                await self.post_userlist(channel, channel_state)
                channel_state.userlist_dirty = False
        else:
            # post userlist immediately since feed not online
            await self.post_userlist(channel, channel_state)
            channel_state.userlist_dirty = False

        await ctx.send(content=info("Created a Classic Battle.net channel feed from BotNet account {} to {}.".format(self.escape_text(account_name), channel.mention)))

    @commands.command(aliases=["bnset", "botnetget", "bnget"])
    @checks.is_owner()
    async def botnetset(self, ctx, key : str = "", *, val : str = ""):
        """Gets or sets settings for the BotNet connection."""
        try:
            if len(key) == 0:
                is_changing = False
                key = "*"
                header = "Current BotNet settings:"
            elif len(val) == 0:
                is_changing = False
                header = "Current BotNet settings (matching `{}`)".format(self.escape_code_text(key))
            else:
                is_changing = True
                header = "BotNet setting was set:"

            if not key.lower() in BotNetVL.global_conf:
                if not "*" in key and not "?" in key and not "[" in key and not "]" in key:
                    key = key + "*"
                key_matches = fnmatch.filter(BotNetVL.global_conf.keys(), key)
                if len(key_matches) == 0:
                    await ctx.send(content="There is no BotNet setting called `{}`.".format(self.escape_code_text(key)))
                    return
                elif len(key_matches) > 1 and is_changing:
                    await ctx.send(content="Multiple BotNet settings match `{}`.".format(self.escape_code_text(key)))
                    return
            else:
                key_matches = [key.lower()]
        
            if is_changing:
                key = key_matches[0]
                val = self.parse_conf_value(ctx, val, "str")
                data = {key: str(val)}
                await self.config.get_attr(key).set(val)
                setattr(self.state, key, val)
            else:
                data = {}
                for key in key_matches:
                    data[key] = await self.config.get_attr(key)()
            await ctx.send(content="{}\n{}".format(header, self.print_conf_data(ctx, data)))
        except Exception as ex:
            print("BotNet EXCEPTION getting/setting global setting: {}".format(ex))

    @commands.command(aliases=["bncsget"])
    @checks.guildowner_or_permissions(manage_guild=True)
    async def bncsset(self, ctx, channel : discord.TextChannel, key : str = "", *, val : str = ""):
        """Gets or sets settings for the Classic Battle.net feed."""
        if channel.guild is None or ctx.guild is None or channel.guild.id != ctx.guild.id:
            await ctx.send(content=error("That channel is not known or does not have a feed. Use the !bncsfeed command to create a feed."))
            return

        if not channel.id in self.channel_states:
            await ctx.send(content=error("That channel is not known or does not have a feed. Use the !bncsfeed command to create a feed."))
            return

        try:
            if len(key) == 0:
                is_changing = False
                key = "*"
                header = "Current {} settings:".format(channel.mention)
            elif len(val) == 0:
                is_changing = False
                header = "Current {} settings (matching `{}`)".format(channel.mention, self.escape_code_text(key))
            else:
                is_changing = True
                header = "{} setting was set:".format(channel.mention)

            if not key.lower() in BotNetVL.channel_conf:
                if not "*" in key and not "?" in key and not "[" in key and not "]" in key:
                    key = key + "*"
                key_matches = fnmatch.filter(BotNetVL.channel_conf.keys(), key)
                if len(key_matches) == 0:
                    await ctx.send(content="There is no {} setting called `{}`.".format(channel.mention, self.escape_code_text(key)))
                    return
                elif len(key_matches) > 1 and is_changing:
                    await ctx.send(content="Multiple {} settings match `{}`.".format(channel.mention, self.escape_code_text(key)))
                    return
            else:
                key_matches = [key.lower()]
        
            if is_changing:
                key = key_matches[0]
                conf_set = BotNetVL.channel_conf[key]
                if not conf_set["user-editable"]:
                    await ctx.send(content="You may not set the feed setting called {}.".format(self.escape_text(key)))
                    return
                try:
                    val = self.parse_conf_value(ctx, val, conf_set["type"])
                except ValueError as vex:
                    await ctx.send(content="Value is not valid for setting called {}: `{}`".format(self.escape_text(key), self.escape_code_text(str(vex))))
                    return
                data = {key: str(val)}
                await self.config.channel(channel).get_attr(key).set(val)
                channel_state = self.channel_states[channel.id]
                setattr(channel_state, key, val)
                if "set-causes-reset" in conf_set and conf_set["set-causes-reset"]:
                    # send RESET to this account, if online and account_relay_object is incorrect
                    relay = self.botnet_get_relay_account(channel, channel_state, None, "RESET")
                    if not relay is channel_state.account_relay_object:
                        channel_state.account_relay_object = relay
                        if relay:
                            reset_str = "RESET"
                            print("{} -> {}".format(relay.account, reset_str))
                            to_send = [self.send_chat(reset_str, whisper_to = relay.bot_id)]
                            await self.send_resp(to_send)
                        else:
                            # post userlist immediately since feed not online
                            await self.post_userlist(channel, channel_state)
                            channel_state.userlist_dirty = False
                    else:
                        # post userlist immediately since feed not online
                        await self.post_userlist(channel, channel_state)
                        channel_state.userlist_dirty = False
                if "set-updates-timezone" in conf_set and conf_set["set-updates-timezone"]:
                    try:
                        channel_state.timezone_object = pytz.timezone(channel_state.timezone.replace(" ", "_"))
                    except pytz.exceptions.UnknownTimeZoneError:
                        channel_state.timezone_object = pytz.utc
                if "set-updates-users" in conf_set and conf_set["set-updates-users"]:
                    await self.post_userlist(channel, channel_state)
                    channel_state.userlist_dirty = False
            else:
                data = {}
                for key in key_matches:
                    data[key] = await self.config.channel(channel).get_attr(key)()
            await ctx.send(content="{}\n{}".format(header, self.print_conf_data(ctx, data)))
        except Exception as ex:
            print("BotNet EXCEPTION getting/setting channel setting: {}".format(ex))

    @commands.command()
    @checks.guildowner_or_permissions(manage_guild=True)
    async def bncsstatus(self, ctx, account_name):
        """Returns the Battle.net feed(s) that are relaying from the provided BotNet account."""
        restricted = not self.bot.is_owner(ctx.author)

        if restricted and ctx.guild is None:
            await ctx.send(error("You cannot get a feed status outside of a server."))
            return

        feeds = []
        for channel_id, channel_state in self.channel_states.items():
            if channel_state.feed_type == "bncs":
                if channel_state.account_relay.lower() == account_name.lower():
                    if restricted and ctx.guild.id != channel_state.guild:
                        # not for thine eyes
                        continue

                    feed = { "botnet_online": False }

                    for bot_id, botnet_user in self.state.users.items():
                        if botnet_user.is_on_account() and botnet_user.account.lower() == account_name.lower():
                            feed["botnet_online"] = True
                            feed["botnet_bot_id"] = botnet_user.bot_id
                            feed["botnet_bot_account"] = botnet_user.account
                            break

                    channel = self.bot.get_channel(channel_id)
                    if   not channel:
                        feed["error_code"] = 3
                        feed["error"] = "Discord channel inaccessible."
                    elif not isinstance(channel, discord.TextChannel):
                        feed["channel_id"] = channel.id
                        feed["channel"] = "#{}".format(channel.name)
                        feed["guild_id"] = channel.guild.id
                        feed["guild"] = channel.guild.name
                        feed["error_code"] = 4
                        feed["error"] = "Discord channel not a TextChannel."
                    else:
                        feed["channel_id"] = channel.id
                        feed["channel"] = "#{}".format(channel.name)
                        feed["guild_id"] = channel.guild.id
                        feed["guild"] = channel.guild.name

                    feeds.append(feed)

        if len(feeds) == 0:
            await ctx.send(error("There are no feeds expecting that account."))
        else:
            res = ""
            n = 0
            for feed in feeds:
                res += "Feed result #{}:\n{}\n".format(n + 1, self.print_conf_data(ctx, feed))
                n += 1
            await ctx.send(content="{}\n\n{}".format(info("{} results.".format(n)), res))

class BotNetVLState():
    """Current state object."""
    def __init__(self):
        # config mirror
        for key, val in BotNetVL.global_conf.items():
            setattr(self, key, val)

        # connection state
        self.socket                 = None
        self.chat_ready             = False
        self.received_logon_resp    = False
        self.using_account          = False
        self.server_version         = 0x00
        self.client_comm_version    = 0x00
        self.client_cap_bits        = 0x00

        # users state
        self.users                  = {}
        self.self_user              = None
        self.deferred_chat          = []

    def __repl__(self):
        return "<BotNet state object connected as {}>".format(self.self_user)

    def __str__(self):
        return "<BotNet state object connected as {}>".format(self.self_user)

class BotNetVLChannelState():
    def __init__(self):
        # config mirror
        for key, val in BotNetVL.channel_conf.items():
            setattr(self, key, val["default"])

        # BNCS channel state
        self.account_relay_object   = None
        self.users                  = []
        self.join_counter           = 0
        self.userlist_dirty         = False
        self.userlist_update_lock   = False
        self.timezone_object        = pytz.utc

    def __repl__(self):
        return "<{} feed relaying {} to {}>".format(self.feed_type, self.account_relay, self.guild)

    def __str__(self):
        return "<{} feed relaying {} to {}>".format(self.feed_type, self.account_relay, self.guild)

class BotNetVLUser:
    """Represents a user currently on the BotNet."""
    def __init__(self, bot_id : int,
            bnet_name : str, bnet_channel : str, bnet_server : int,
            account : str, database : str,
            database_access : int = 0, admin_access : int = 0):
        self.bot_id = bot_id
        self.bnet_name = bnet_name
        self.bnet_channel = bnet_channel
        self.bnet_server = bnet_server
        self.account = account
        self.database = database
        self.database_access = database_access
        self.admin_access = admin_access
        self.is_self = False

    def __str__(self):
        if self.is_on_account():
            return self.account
        else:
            return "*{}#{}".format(self.bnet_name, self.bot_id)

    def is_on_account(self):
        return self.account and len(self.account) and self.account != "No Account"

    def is_on_bnet(self):
        return self.bnet_channel.lower() != "<not logged on>" and \
               self.bnet_server != 0 and self.bnet_server != -1

    def is_priority(self):
        return True

    def str_bot_id(self):
        if self.bot_id >= 0x40000:
            return "·{}".format(self.bot_id - 0x40000)
        else:
            return str(self.bot_id)

    def admin_access_flags(self):
        flags = ""
        for index in range(32):
            if (self.admin_access & (1 << index)) != 0:
                flags += chr(ord("A") + index)
        return flags

class BotNetVLWebChannelUser:
    """Represents a user on Classic Battle.net, seen through BotNet WebChannel events."""
    def __init__(self, name, flags, ping, text, index, *, time = None, is_self = False):
        self.name = name
        self.flags = flags
        self.ping = ping
        self.text = text
        self.index = index
        self.is_self = is_self
        self.join_time = time

    def __str__(self):
        return self.name

    def priority(self):
        if self.has_flag(0x01): # Blizzard Representative
            return 1
        if self.has_flag(0x08): # Battle.net Administrator
            return 2
        if self.has_flag(0x02): # Channel Operator
            return 3
        if self.has_flag(0x04): # Channel Speaker
            return 4
        if self.has_flag(0x40): # Special Guest
            return 5
        if True:                # everyone else
            return 8

    def is_priority(self):
        return self.priority() < 8

    def has_flag(self, flag):
        return (self.flags & flag) == flag

    def weight(self):
        prio = self.priority()
        if prio < 8:
            flip = -1
        else:
            flip = 1
        return (prio << 0x10000) + (flip * self.index)

    def get_value(self, key, default):
        if key in self.__dict__ and not getattr(self, key) is None:
            return getattr(self, key)
        else:
            return default

    def do_parse_text(self):
        try:
            self.product = self.text[3::-1]
            try:
                self.product_name = BotNetVL.product_map[self.product]["name"]
                self.product_name_short = BotNetVL.product_map[self.product]["name_short"]
            except KeyError:
                self.product_name = "Unknown ({})".format(self.product)
                self.product_name_short = self.product
            self.icon_id = self.product
            self.tag = None
            self.level = None
            self.wins = None
            self.text_parsed_1 = "Unavailable"
            self.text_parsed_2 = self.text_parsed_1
            self.text_parsed_3 = self.text_parsed_2
            if self.product == "DRTL" or self.product == "DSHR":
                # Diablo-style
                parts    = self.text[5:].split(" ")

                # LTRD #level #class #diff #str #mag #dex #vit #gold #spawn
                parts2 = [0] * 9
                index = 0
                for part in parts:
                    if index >= len(parts2):
                        break
                    if part.isnumeric():
                        parts2[index] = int(part)
                    index += 1
                parts = parts2
                [self.level, self.char_class_id, self.char_diff_id,
                 self.char_str, self.char_mag, self.char_dex, self.char_vit,
                 self.char_gold, self.spawned] = parts

                try:
                    self.char_class = BotNetVL.d1_stats_char_list[self.char_class_id]
                except IndexError:
                    self.char_class = str(self.char_class_id)

                if self.char_diff_id == 0:
                    self.char_diff = "Normal"
                elif self.char_diff_id == 1:
                    self.char_diff = "Nightmare"
                elif self.char_diff_id == 2:
                    self.char_diff = "Hell"
                else:
                    self.char_diff = "Endgame"

                self.custom_text = self.text[4:]

                self.text_parsed_1 = "Level {level} {char_class}".format(level = self.level, char_class = self.char_class)
                self.text_parsed_2 = "{p1}, {str} STR, {mag} MAG, {dex} DEX, {vit} VIT, {gold} gold".format(
                        p1 = self.text_parsed_1, str = self.char_str, mag = self.char_mag,
                        dex = self.char_dex, vit = self.char_vit, gold = self.char_gold)
                self.text_parsed_3 = "{p2}, in {char_diff}".format(
                        p2 = self.text_parsed_2, char_diff = self.char_diff)

            elif self.product == "STAR" or self.product == "SEXP" or self.product == "W2BN" or self.product == "SSHR" or self.product == "JSTR":
                # StarCraft style
                parts    = self.text[5:].split(" ")
                # check this field exists and has content before numeric thing
                if len(parts) >= 9 and len(parts[8]) > 0:
                    # 9th field exists and non-empty
                    self.icon_id = parts[8][::-1]

                # SEXP #rating #rank #wins #spawned #league #hrating #irating #irank ICON
                parts2 = [0] * 8
                index = 0
                for part in parts:
                    if index >= len(parts2):
                        break
                    if part.isnumeric():
                        parts2[index] = int(part)
                    index += 1
                parts = parts2
                [self.rating, self.rank, self.wins, self.spawned, self.league,
                 self.rating_high, self.rating_im, self.rank_im] = parts

                self.text_parsed_1 = ""
                if self.wins > 0:
                    self.text_parsed_1 += "{wins} wins".format(wins = self.wins)
                self.text_parsed_2 = self.text_parsed_1
                self.text_parsed_3 = self.text_parsed_2

            elif self.product == "D2DV" or self.product == "D2XP":
                # Diablo style
                if len(self.text) == 4:
                    self.is_open = True

                    self.text_parsed_1 = "Open"
                    self.text_parsed_2 = self.text_parsed_1
                    self.text_parsed_3 = self.text_parsed_2
                else:
                    self.is_open = False
                    parts    = self.text[4:].split(",", 2)
                    parts[:] = parts + ([""] * (3 - len(parts)))

                    # VD2DRealm,CharName,CHARDATAETC[33]
                    [self.char_realm, self.char_name, self.char_data] = parts
                    if len(self.char_data) >= 33:
                        self.char_data_bytes = self.char_data.encode("cp1252", "replace")

                        self.char_class_id = self.char_data_bytes[13]
                        self.level = self.char_data_bytes[25]
                        self.char_listing_flags = self.char_data_bytes[26]
                        self.char_act_id = (self.char_data_bytes[27] & 0b00011110) >> 1
                        self.char_ladder_id = self.char_data_bytes[30]

                        self.char_is_hardcore = bool(self.char_listing_flags & 0x04)
                        self.char_is_dead = bool(self.char_listing_flags & 0x08)
                        self.char_is_expansion = bool(self.char_listing_flags & 0x20)
                        self.char_is_ladder = bool(self.char_ladder_id != 0xff)
                        if self.char_is_expansion:
                            self.char_act = (self.char_act_id % 5) + 1
                            self.char_diff_id = self.char_act_id // 5
                        else:
                            self.char_act = (self.char_act_id % 4) + 1
                            self.char_diff_id = self.char_act_id // 4

                        try:
                            self.char_class     = BotNetVL.d2_stats_char_list  [self.char_class_id - 1]
                            self.char_is_female = BotNetVL.d2_stats_char_female[self.char_class_id - 1]
                        except IndexError as ex:
                            print("BotNet ERROR Finding character class from D2 statstring char_class_id IndexError {}".format(ex))
                            self.char_class     = str(self.char_class_id)
                            self.char_is_female = False
                        try:
                            self.char_title     = BotNetVL.d2_stats_title_table[(self.char_diff_id, self.char_is_expansion, self.char_is_hardcore, self.char_is_female)]
                        except KeyError as ex:
                            print("BotNet ERROR Finding title from D2 statstring (diff_id, is_exp, is_hc, is_f) KeyError {}".format(ex))
                            self.char_title     = ""

                        #print("char {} title {} val = {:#02x} -> act_id = {}, diff_id = {}".format(self.char_name, self.char_title, self.char_data_bytes[27], self.char_act_id, self.char_diff_id))
                        self.listing_flags_str = ""
                        if self.char_is_expansion:
                            self.listing_flags_str += "expansion, "
                        else:
                            self.listing_flags_str += "classic, "
                        if self.char_is_ladder:
                            self.listing_flags_str += "ladder, "
                        else:
                            self.listing_flags_str += "non-ladder, "
                        if self.char_is_hardcore:
                            self.listing_flags_str += "hardcore"
                        else:
                            self.listing_flags_str += "softcore"

                        if self.char_diff_id == 0:
                            self.char_diff = "Normal"
                        elif self.char_diff_id == 1:
                            self.char_diff = "Nightmare"
                        elif self.char_diff_id == 2:
                            self.char_diff = "Hell"
                        else:
                            self.char_diff = "Endgame"

                        self.text_parsed_1 = ""
                        if len(self.char_title) > 0:
                            self.text_parsed_1 += "{char_title} {char_name}".format(
                                    char_title = self.char_title, char_name = self.char_name)
                        else:
                            self.text_parsed_1 += "{char_name}".format(
                                    char_title = self.char_title, char_name = self.char_name)
                        self.text_parsed_2 = "Level {level} {char_class}, {p1}".format(
                                p1 = self.text_parsed_1, level = self.level, char_class = self.char_class)
                        self.text_parsed_3 = "{p2} in {listing_flags} {char_diff} on {char_realm}".format(
                                p2 = self.text_parsed_2, listing_flags = self.listing_flags_str,
                                char_diff = self.char_diff, char_realm = self.char_realm)
                    else:
                        self.text_parsed_1 = "Unrecognized"
                        self.text_parsed_2 = self.text_parsed_1
                        self.text_parsed_3 = self.text_parsed_2

            elif self.product == "WAR3" or self.product == "W3XP":
                # WarCraft III style
                parts    = self.text[5:].split(" ")
                self.level = 0
                self.tag = ""
                if len(parts) == 1:
                    # 3RAW 0
                    if parts[0].isnumeric():
                        self.level = int(parts[0])
                    else:
                        self.icon_id = parts[0][::-1]
                else:
                    if len(parts) >= 2:
                        # 3RAW 1R3W 5
                        self.icon_id = parts[0][::-1]
                        if parts[1].isnumeric():
                            self.level = int(parts[1])
                        else:
                            self.level = 0
                    if len(parts) >= 3:
                        # 3RAW 2R3W 4 ToB
                        self.tag = parts[2][::-1]
                        self.Clan_tag = "Clan {tag}".format(tag = self.tag)
                        self.clan_tag = "clan {tag}".format(tag = self.tag)

                if self.level > 0:
                    self.text_parsed_1 = "Level {level}".format(level = self.level)
                    if len(self.tag) > 0:
                        self.text_parsed_2 = "{p1} in Clan {tag}".format(
                                p1 = self.text_parsed_1, tag = self.tag)
                else:
                    self.text_parsed_1 = ""
                    if len(self.tag) > 0:
                        self.text_parsed_2 = "In Clan {tag}".format(
                                p1 = self.text_parsed_1, tag = self.tag)
                self.text_parsed_3 = self.text_parsed_2
        except Exception as ex:
            print("BotNet EXCEPTION parsing user stats:")
            traceback.print_exc()

    def __lt__(self, other): # self < other
        if other is None:
            return False
        return self.weight() < other.weight()
    def __le__(self, other): # self <= other
        if other is None:
            return False
        return self.weight() <= other.weight()
    def __eq__(self, other): # self == other
        if other is None:
            return False
        return self.weight() == other.weight()
    def __ne__(self, other): # self != other
        if other is None:
            return True
        return self.weight() != other.weight()
    def __gt__(self, other): # self > other
        if other is None:
            return False
        return self.weight() > other.weight()
    def __ge__(self, other): # self >= other
        if other is None:
            return False
        return self.weight() >= other.weight()

class BotNetVLPacket:
    """Represents the contents of a packet being constructed or parsed for BotNet."""
    def __init__(self, *, data : bytearray = bytearray([1, 0, 4, 0]), id : int = -1):
        self.data = data.copy()
        self.proto = self.data[0]
        if id < 0:
            self.id = self.data[1]
        else:
            self.id = id
            self.data[1] = id
        self.pos = 4

    def __bytes__(self):
        return bytes(self.data)

    def __len__(self):
        return len(self.data)

    def update_plen(self):
        plen = len(self)
        struct.pack_into("<H", self.data, 2, plen)

    def append_uint8(self, b):
        self.data.append(b)
        self.pos += 1
        self.update_plen()

    def append_uint16(self, h):
        self.data += struct.pack("<H", h)
        self.pos += 2
        self.update_plen()

    def append_uint32(self, i):
        self.data += struct.pack("<I", i)
        self.pos += 4
        self.update_plen()

    def append_ntstring(self, s):
        b = s.encode("utf_8")
        self.data += b
        self.data += b"\x00"
        self.pos += len(b) + 1
        self.update_plen()

    def get_uint8(self):
        if self.pos > len(self):
            return None
        b = self.data[self.pos]
        self.pos += 1
        return b

    def get_uint16(self):
        if self.pos + 1 > len(self):
            return None
        (h,) = struct.unpack_from("<H", self.data, self.pos)
        self.pos += 2
        return h

    def get_uint32(self):
        if self.pos + 3 > len(self):
            return None
        (i,) = struct.unpack_from("<I", self.data, self.pos)
        self.pos += 4
        return i

    def get_ntstring(self):
        nt = self.data.find(0, self.pos)
        if nt < 0:
            return None
        b = self.data[self.pos:nt]
        try:
            s = b.decode("utf_8", "strict")
        except UnicodeDecodeError:
            s = b.decode("cp1252", "replace")
        self.pos += len(b) + 1
        return s
