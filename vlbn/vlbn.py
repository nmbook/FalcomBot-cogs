import discord
from discord.ext import commands
from redbot.core import Config
from redbot.core import checks
from redbot.core.utils.chat_formatting import escape, info, error
from datetime import datetime
import asyncio
import concurrent
import itertools
import socket
import struct

class BotNetVL:
    """Provides a chat-only bridge to Valhalla Legends' (vL) "BotNet" service.
    
    BotNet is a service once used by a small number of users for inter-bot communication with the Classic Battle.net botting community."""

    def __init__(self, bot):
        self.bot = bot
        
        self.default_feed = {
                "discord_channel": 0,
                "discord_userlist_post": 0,
                "server": "",
                "port": 0x5555,
                "bot_name": "StealthBot",
                "bot_pass": "33 9c 0f 58 fe c7 2a",
                "database_name": "",
                "database_pass": "",
                "use_account": False,
                "account_name": "",
                "account_pass": ""
        }
        self.default_active_feed = {
                "connected": False,
                "server_address": "",
                "logon_state": 0b0000
        }

        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xff5269620001)
        self.config.register_global(
                feeds = []
        )

        self.active_feeds = []
        self.tasks = []
        self.resolve_map = { \
                "\U0001f30e\U0001f1ea": {"domain": "useast.battle.net", \
                    "addresses": ["199.108.55.54", "199.108.55.55", "199.108.55.56", "199.108.55.57", \
                    "199.108.55.58", "199.108.55.59", "199.108.55.60", "199.108.55.61", "199.108.55.62"]}, \
                "\U0001f30e\U0001f1fc": {"domain": "uswest.battle.net", \
                    "addresses": ["12.129.236.14", "12.129.236.15", "12.129.236.16", "12.129.236.17", \
                    "12.129.236.18", "12.129.236.19", "12.129.236.20", "12.129.236.21", "12.129.236.22"]}, \
                "\U0001f30d": {"domain": "europe.battle.net", \
                    "addresses": ["5.42.181.14", "5.42.181.15", "5.42.181.16", "5.42.181.17", "5.42.181.18"]}, \
                "\U0001f30f": {"domain": "asia.battle.net", \
                    "addresses": ["121.254.164.14", "121.254.164.15", "121.254.164.16", "121.254.164.17", \
                    "121.254.164.18", "121.254.164.19", "121.254.164.20", "121.254.164.21", \
                    "121.254.164.22", "121.254.164.23", "121.254.164.24", "121.254.164.25", \
                    "121.254.164.26", "121.254.164.27", "121.254.164.28", "121.254.164.29", \
                    "121.254.164.30", "121.254.164.31", "121.254.164.32", "121.254.164.33", "121.254.164.34"]} \
                }

        coro = self.init_feeds()
        self.tasks.append(self.bot.loop.create_task(coro))

    def __unload(self):
        for task in self.tasks:
            task.cancel()

    @commands.command(aliases=["bnaccount"])
    @checks.is_owner()
    async def botnetaccount(self, ctx, channel : discord.TextChannel, account_name : str, account_pass : str):
        """Sets the account name and password for the BotNet feed denoted by the provided channel."""
        cur_feed = None
        for feed in self.active_feeds:
            if feed["discord_channel"] == channel.id:
                cur_feed = feed
                break

        if not cur_feed:
            await ctx.send(error("There is no BotNet bridge set up for that channel."))
            return

        cur_feed["use_account"] = True
        cur_feed["account_name"] = account_name
        cur_feed["account_pass"] = account_pass
        await self.save_to_feed_config(cur_feed, "use_account", True)
        await self.save_to_feed_config(cur_feed, "account_name", account_name)
        await self.save_to_feed_config(cur_feed, "account_pass", account_pass)
        await ctx.send(info("Saved account credentials for the BotNet feed in {}.".format(channel.mention)))

    @commands.command(aliases=["bnsetup"])
    @checks.is_owner()
    async def botnetsetup(self, ctx, channel : discord.TextChannel, database_name : str, database_pass : str, server : str, port : int = 0x5555):
        """Sets up a new BotNet feed to the specified discord channel."""
        feeds = (await self.config.feeds()).copy()
        for feed in feeds:
            if feed["discord_channel"] == channel.id:
                await ctx.send(error("A BotNet bridge is already set up for that channel."))
                return
        
        feed = self.default_feed.copy()
        feed["discord_channel"] = channel.id
        feed["discord_userlist_post"] = 0
        feed["server"] = server
        feed["port"] = port
        feed["database_name"] = database_name
        feed["database_pass"] = database_pass
        feeds.append(feed)
        await self.config.feeds.set(feeds)

        active_feed = feed.copy()
        await ctx.send(info("BotNet feed created. BotNet chat from the `{}` database will now appear in {}. You may interact with BotNet by sending messages there.".format(database_name, channel.mention)))
        coro = self.connect_feed(active_feed)
        self.tasks.append(self.bot.loop.create_task(coro))

    async def save_to_feed_config(self, active_feed, key, value):
        """Saves a single key-value pair in the config for a feed."""
        feeds = (await self.config.feeds()).copy()
        feed = None
        for find_feed in feeds:
            if find_feed["discord_channel"] == active_feed["discord_channel"]:
                feed = find_feed
                break

        if not feed:
            # no matching feed in config
            return

        feed[key] = value
        await self.config.feeds.set(feeds)

    async def init_feeds(self):
        """Initialize Feeds

        Initialize an array of feeds stored in configuration."""
        #print("INIT FEEDS")
        feeds = (await self.config.feeds()).copy()
        for feed in feeds:
            await self.connect_feed(feed.copy())

    async def connect_feed(self, feed):
        """Connect Feed

        The core logic of the BotNet feed. Sets up and awaits in a receive loop."""

        # save feed as active
        self.active_feeds.append(feed)

        # intial vars
        feed["socket"]              = None
        feed["chat_ready"]          = False
        feed["received_logon_resp"] = False
        feed["server_version"]      = 0x00
        feed["client_comm_version"] = 0x00
        feed["client_cap_bits"]     = 0x00

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            feed["socket"] = sock
            feed["chat_ready"] = False

            await self.bot.loop.sock_connect(sock, (feed["server"], feed["port"]))

            #print("connected")

            to_send = self.botnet_on_connected(feed)

            #self.bot.loop.create_task(150, self.keep_alive, feed)

            while True: # receive loop
                await self.send_resp(feed, to_send)
                packet = await self.get_packet(feed)
                if packet is None:
                    break
                to_send = self.botnet_on_packet(feed, packet)
            if feed["socket"]:
                #print("Closing socket (eof)...")
                feed["socket"].close()
                feed["socket"] = None
            self.active_feeds.remove(feed)
        except concurrent.futures.CancelledError as ex:
            # module unload
            pass
        except IOError as ex:
            # unspecified error
            print("BotNet connection error: {}".format(ex))
        except Exception as ex:
            # unspecified error
            print("BotNet uncaught Exception: {}".format(ex))
        finally:
            if feed["socket"]:
                #print("Closing socket (error)...")
                feed["socket"].close()
                feed["socket"] = None
            self.active_feeds.remove(feed)

    async def keep_alive(self, feed):
        """Keep Alive Timer Tick

        Call send_keep_alive and then wait another 150 seconds."""
        to_send = [self.send_keep_alive(feed)]
        await self.send_resp(feed, to_send)
        self.bot.loop.call_later(150, self.keep_alive, feed)

    async def send_resp(self, feed, to_send):
        """Send Response
        
        Send generated response(s) in to_send array to the socket. Used with constructed packets."""
        for resp in to_send:
            if resp is None: # yield None pauses instead of sends
                await asyncio.sleep(1)
            else:
                #print("send pkt 0x{:02x} len {}\n{}".format(bytes(resp)[1], len(resp), bytes(resp)))
                await self.bot.loop.sock_sendall(feed["socket"], bytes(resp))

    async def on_message(self, message):
        """Handle on_message to send back to BotNet."""
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
        # disabled: unexpected side-effect: it catches typing "..." or the like...
        #else:
        #    for prefix in await self.bot.get_prefix(message):
        #        if message.clean_content.startswith(prefix):
        #            # starts with prefix, ignore command here
        #            return

        for feed in self.active_feeds:
            if message.channel.id == feed["discord_channel"]:
                if feed["chat_ready"]:
                    # convert text to array of strings
                    messages      = self.text_discord_to_botnet(message.clean_content, str(message.author))
                    # convert attachments to array of strings
                    messages     += self.attach_discord_to_botnet(message.attachments)
                    if len(messages) == 0:
                        # no usable content
                        break
                    to_send = []
                    for content in messages:
                        if len(content.strip()) > 0:
                            if len(content) > 1 and \
                              ((content.startswith("*") and content.endswith("*") and not content.endswith("**")) or \
                              (content.startswith("_") and content.endswith("_") and not content.endswith("__"))):
                                content = content[1:-1]
                                to_send.append(self.send_chat(feed, "{} {}".format(message.author, content), emote = True))
                            else:
                                to_send.append(self.send_chat(feed, "{}: {}".format(message.author, content)))

                    await self.send_resp(feed, to_send)
                break

    async def get_packet(self, feed):
        """Get Packet
        
        Get one packet off the socket. Used only by Connect Feed."""
        header = await self.bot.loop.sock_recv(feed["socket"], 4)
        if not header:
            #print("header is none")
            return None
        (proto, pid, plen) = struct.unpack("<BBH", header)
        pleft = plen - 4
        buf = b""
        while pleft > 0:
            part = await self.bot.loop.sock_recv(feed["socket"], pleft)
            if not part:
                #print("part is none - buf == {} + {}".format(header, buf))
                return None
            pleft -= len(part)
            buf += part
        #print("recv pkt 0x{:02x} len {}\n{}".format(header[1], len(header + buf), bytes(header + buf)))
        return BotNetVLPacket(data = bytearray(header + buf))

    async def post_userlist(self, feed, channel, users):
        """Tries to post the userlist and pin it to current channel.
        
        If we already have a valid existant pin, then edits that in place."""
        if feed["discord_userlist_post"] == 0:
            to_create = True
        else:
            try:
                post = await channel.get_message(feed["discord_userlist_post"])
                to_create = False
            except:
                # named but not found or accessible
                to_create = True

        if to_create:
            # creating and pinning post
            try:
                post = await channel.send(content=self.userlist_botnet_to_discord(users))
                await post.pin()
                feed["discord_userlist_post"] = post.id
                await self.save_to_feed_config(feed, "discord_userlist_post", post.id)
            except Exception as ex:
                print("BotNet exception posting userlist: {}".format(ex))
        else:
            # updating a pinned post
            try:
                await post.edit(content=self.userlist_botnet_to_discord(users))
            except Exception as ex:
                print("BotNet exception updating userlist: {}".format(ex))

    def botnet_on_userlist(self, feed, users):
        """Event that occurs when userlist is received."""
        #print("BotNet USERLIST: {} users".format(len(feed["users"])))
        channel = self.bot.get_channel(feed["discord_channel"])
        if channel:
            coro = self.post_userlist(feed, channel, users)
            self.tasks.append(self.bot.loop.create_task(coro))

    def botnet_on_user(self, feed, user, on_connect = False):
        """Event that occurs when singular user update is received."""
        #print("BotNet USER 0x{:x}: {}".format(user.bot_id, user))
        self.botnet_on_userlist(feed, feed["users"])

        try:
            channel = self.bot.get_channel(feed["discord_channel"])
            if channel and on_connect and user.database == feed["self"].database:
                timestamp = datetime.now().strftime("%I:%M:%S %p")
                bnet_inf = self.user_botnet_to_discord(user)
                message = "({}) #{}: {} connected to {}.".format(timestamp, user.str_bot_id(), bnet_inf, user.database)

                coro = channel.send(message)
                self.tasks.append(self.bot.loop.create_task(coro))
        except Exception as ex:
            print("BotNet exception posting user connect: {}".format(ex))

    def botnet_on_userdisc(self, feed, user):
        """Event that occurs when singular user disconnects."""
        #print("BotNet DISC 0x{:x}: {}".format(user.bot_id, user))
        self.botnet_on_userlist(feed, feed["users"])

        try:
            channel = self.bot.get_channel(feed["discord_channel"])
            if channel and user.database == feed["self"].database:
                timestamp = datetime.now().strftime("%I:%M:%S %p")
                bnet_inf = self.user_botnet_to_discord(user)
                message = "({}) #{}: {} disconnected from {}.".format(timestamp, user.str_bot_id(), bnet_inf, user.database)

                coro = channel.send(message)
                self.tasks.append(self.bot.loop.create_task(coro))
        except Exception as ex:
            print("BotNet exception posting user disconnect: {}".format(ex))

    def botnet_on_chat(self, feed, user, message, command, action):
        """Event that occurs when chat is received."""
        #print("BotNet CHAT from {}: {}".format(user, message))
        try:
            channel = self.bot.get_channel(feed["discord_channel"])
            if channel:
                timestamp = datetime.now().strftime("%I:%M:%S %p")
                if command == 0x00: # broadcast
                    broadcast = "__**BROADCAST**__ "
                else:
                    broadcast = ""
                if action == 0x01: # emote
                    ec1 = ""
                    ec2 = ">"
                else:
                    ec1 = ">"
                    ec2 = ""
                message = "{}({}) <**{}**{} {}{}".format(broadcast, timestamp, user, ec1, self.text_botnet_to_discord(message), ec2)

                coro = channel.send(message)
                self.tasks.append(self.bot.loop.create_task(coro))
        except Exception as ex:
            print("BotNet exception posting chat: {}".format(ex))

    def text_botnet_to_discord(self, text):
        """Escapes text to be passed from BotNet to discord."""
        text = text.replace("\\", "\\\\")
        text = text.replace("*", "\\*")
        text = text.replace("~", "\\~")
        text = text.replace("_", "\\_")
        text = text.replace("<", "\\<")
        text = text.replace(":", "\\:")
        text = text.replace("`", "\\`")
        text = text.replace("@", "\\@")
        return escape(text)

    def attach_discord_to_botnet(self, attachments):
        """Gets the text-only version of a list of attachments to be seen on BotNet as links."""
        messages = []
        for attach in attachments:
            if hasattr(attach, "width") and hasattr(attach, "height"):
                wxh = "; {} x {}".format(attach.width, attach.height)
            else:
                wxh = ""
            messages.append("Attachment: {} (size: {}{})".format(attach.url, self.byte_size(attach.size), wxh))
        return messages

    def byte_size(self, bytelen):
        """Returns human-friendly file size from a given number of bytes."""
        units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB']
        ind = int(math.log2(bytelen) / 10.0) - 1
        if ind >= len(units):
            ind = len(units) - 1
        if ind > 0:
            val = round(bytelen / (1 << (10 * ind)), 2)
        else:
            val = int(bytelen)
        return "{} {}".format(val, units[ind])

    def text_discord_to_botnet(self, clean_content, author):
        """Splits long text to be passed from discord to BotNet.
        
        Assumes UTF-8 and maximum string length of 496 bytes, and the given author object."""
        prefix_len = len(author.encode("utf-8")) + 2
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
                if count >= 496:
                    # reached a message that's too long on its own
                    if last_space < 464:
                        # too long an ending word, let's break it
                        left = message[:495] + '-'
                        right = message[495:]
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

    def userlist_botnet_to_discord(self, users):
        """Creates a textual list of users on BotNet for use on discord.
        
        Groups by database."""
        userlist_fmt = ""

        def db(user):
            return user.database

        userlist = sorted(users.values(), key=db)
        for k, g in itertools.groupby(userlist, key=db):
            if not k is None and len(k) > 0:
                userlist_fmt += "__Database: {}__\n".format(k)
            else:
                userlist_fmt += "__*No database*__\n".format(k)
            for user in g:
                bnet_inf = self.user_botnet_to_discord(user)
                userlist_fmt += "#{}: {}\n".format(user.str_bot_id(), bnet_inf)
            userlist_fmt += "\n"

        #for user in users.values():
        #    bnet_inf = self.user_botnet_to_discord(user)
        #    userlist_fmt += "#{}: {}\n".format(user.str_bot_id(),  bnet_inf)

        return "__**Users on BotNet server:**__ ({})\n\n{}".format(len(users), userlist_fmt)

    def user_botnet_to_discord(self, user):
        """Converts a user object to text form to be displayed on discord.

        Used in both userlist and connect/disconnect alerts.
        
        Parts: account name, Battle.net name, Battle.net channel, Battle.net server."""
        if user.is_on_account():
            account = "**{}**".format(self.text_botnet_to_discord(user.account))
        else:
            account = ""

        bnet_name = self.text_botnet_to_discord(user.bnet_name)
        if bnet_name != user.account:
            if len(user.account) > 0:
                bnet_name = ", {}".format(bnet_name)
        else:
            bnet_name = ""

        if user.is_on_bnet():
            server_name = self.address_friendlyname(user.bnet_server)
            bnet_inf = "{}{} @ {}{}".format(account, bnet_name, self.text_botnet_to_discord(user.bnet_channel), server_name)
        else:
            bnet_inf = "{}{}\U0001f4f4".format(account, bnet_name)

        return bnet_inf

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

    def botnet_on_connected(self, feed):
        """On Connected Event

        Respond with a bot logon packet."""
        yield self.send_bot_logon(feed)

    def botnet_on_packet(self, feed, packet):
        """On Packet Event

        Respond with 0 or more packets depending on our state and received packet."""
        if   packet.id == 0x00: # 0x00 S>C keep alive
            pass
        elif packet.id == 0x01: # 0x01 S>C bot logon resp
            success = packet.get_uint32()
            feed["received_logon_resp"] = True
            if feed["server_version"] >= 0x04: # SERVER VERSION 4+
                feed["local_addr"] = packet.get_uint32()
                # send 0x0a
                yield self.send_client_caps(feed)
                # send 0x10
                yield self.send_chat_opts(feed)
            if feed["use_account"] and feed["server_version"] >= 0x02: # SERVER VERSION 2+
                # send 0x0d if on account
                yield self.send_account_logon(feed, 0x00)
            else:
                # send 0x02
                yield self.send_self_update(feed)
        elif packet.id == 0x02: # 0x02 S>C self update resp
            success = packet.get_uint32()
            feed["users"] = {}
            yield self.send_user_info_list(feed)
        elif packet.id == 0x06: # 0x06 S>C user info
            if len(packet) == 4: # end of initial list
                # note: this null-terminator is only received if we are "4.1"!
                # chat ready, so that future user events are events
                feed["chat_ready"] = True
                # save self and put it at end of list
                feed["self"] = feed["users"][next(iter(feed["users"]))]
                del feed["users"][feed["self"].bot_id]
                feed["users"][feed["self"].bot_id] = feed["self"]
                # raise event
                self.botnet_on_userlist(feed, feed["users"])
            else:
                account      = None
                database     = None
                bot_id       = packet.get_uint32()
                if feed["server_version"] >= 0x04: # SERVER VERSION 4+
                    if feed["client_comm_version"] >= 0x01: # CLIENT CAP 1+
                        # db access flags and admin caps, both ignored
                        _    = packet.get_uint32()
                        _    = packet.get_uint32()
                bnet_name    = packet.get_ntstring()
                bnet_channel = packet.get_ntstring()
                bnet_server  = packet.get_uint32()
                if feed["server_version"] >= 0x02:
                    account  = packet.get_ntstring() 
                if feed["server_version"] >= 0x03:
                    database = packet.get_ntstring()

                # this is a connect if the bot_id isn't present yet
                on_connect = (not (bot_id in feed["users"]))

                # save object
                feed["users"][bot_id] = BotNetVLUser(bot_id, bnet_name, bnet_channel, bnet_server, account, database)

                # if chat ready, raise single event
                if feed["chat_ready"]:
                    self.botnet_on_user(feed, feed["users"][bot_id], on_connect)
        elif packet.id == 0x07: # 0x07 S>SC user disc
            bot_id = packet.get_uint32()
            self.botnet_on_userdisc(feed, feed["users"][bot_id])
            del feed["users"][bot_id]
        elif packet.id == 0x0a: # 0x0a S>C version
            feed["server_version"] = packet.get_uint32()
        elif packet.id == 0x09: # 0x09 S>C client opts resp
            feed["client_comm_version"] = packet.get_uint32()
            feed["client_cap_bits"]     = packet.get_uint32()
        elif packet.id == 0x0b: # 0x0b S>C chat
            command = packet.get_uint32()
            action  = packet.get_uint32()
            bot_id  = packet.get_uint32()
            message = packet.get_ntstring()
            self.botnet_on_chat(feed, feed["users"][bot_id], message, command, action)
        elif packet.id == 0x0d: # 0x0d S>C account logon resp
            subcommand = packet.get_uint32()
            success    = packet.get_uint32()

            if success:
                if   subcommand == 0x00: # account logon succeeded
                    # continue with sending status
                    yield self.send_self_update(feed)
                elif subcommand == 0x02: # account create succeeded, logon to it
                    yield self.send_account_logon(feed, 0x00)
                else:
                    print("BotNet ERROR logging in: Account subcommand 0x{:x} is not known".format(subcommand))
                    # continue with sending status
                    yield self.send_self_update(feed)
            else:
                if   subcommand == 0x00: # account logon failed (DNE?)
                    yield self.send_account_logon(feed, 0x02)
                elif subcommand == 0x02: # account create failed (was invalid pass)
                    print("BotNet ERROR logging in: Account could not be logged on to or created with name {}".format(feed["account_name"]))
                    # continue with sending status
                    yield self.send_self_update(feed)
                else:
                    print("BotNet ERROR logging in: Account subcommand 0x{:x} is not known".format(subcommand))
                    # continue with sending status
                    yield self.send_self_update(feed)
        elif packet.id == 0x10: # 0x10 S>C chat opts resp
            # ignore contents; assume server set chat opts to 0,0,2,1
            pass
        else:
            print("BotNet WARNING unknown packet id: 0x{:x}".format(packet.id))

    def send_keep_alive(self, feed): # 0x00 C>S keep alive
        packet = BotNetVLPacket(id = 0x00)
        return packet
    
    def send_bot_logon(self, feed): # 0x01 C>S bot logon
        packet = BotNetVLPacket(id = 0x01)
        packet.append_ntstring(feed["bot_name"])
        packet.append_ntstring(feed["bot_pass"])
        return packet

    def send_self_update(self, feed): # 0x02 C>S self update
        #channel = self.bot.get_channel(feed["discord_channel"])
        dbn     = feed["database_name"]
        dbp     = feed["database_pass"]

        packet = BotNetVLPacket(id = 0x02)
        packet.append_ntstring(self.bot.user.name)
        packet.append_ntstring("<Not logged on>")
        packet.append_uint32(0xffffffff)
        packet.append_ntstring("{n} {p}".format(n=dbn, p=dbp))
        packet.append_uint32(0)
        return packet

    def send_user_info_list(self, feed): # 0x06 C>S user info list
        packet = BotNetVLPacket(id = 0x06)
        return packet

    def send_client_caps(self, feed): # 0x0a C>S client caps
        packet = BotNetVLPacket(id = 0x0a)
        # sending 0x0a since we would send 0+0
        packet.append_uint32(0x01) # comm version 1
        packet.append_uint32(0x01) # client caps 0b1
        return packet

    def send_chat(self, feed, content, *, emote : bool = False, broadcast : bool = False, whisper_to : int = 0): # 0x0b C>S chat
        packet = BotNetVLPacket(id = 0x0b)
        if broadcast:
            packet.append_uint32(0x00) # broadcast
        elif whisper_to != 0:
            packet.append_uint32(0x02) # whisper to
        else:
            packet.append_uint32(0x01) # current database
        if emote:
            packet.append_uint32(0x01) # emote
        else:
            packet.append_uint32(0x00) # not emote
        packet.append_uint32(whisper_to)
        packet.append_ntstring(content)
        return packet

    def send_account_logon(self, feed, subcommand): # 0x0d C>S account logon
        packet = BotNetVLPacket(id = 0x0d)
        packet.append_uint32(subcommand)
        packet.append_ntstring(feed["account_name"])
        packet.append_ntstring(feed["account_pass"])
        return packet

    def send_chat_opts(self, feed): # 0x10 C>S chat opts
        packet = BotNetVLPacket(id = 0x10)
        packet.append_uint8(0x00) # subcommand 0
        packet.append_uint8(0x00) # broadcast option 0 (receive)
        packet.append_uint8(0x00) # database  option 0 (receive)
        packet.append_uint8(0x02) # whisper   option 2 (refuse)
        packet.append_uint8(0x01) # odb whisp option 1 (refuse)
        return packet

class BotNetVLUser:
    """Represents a user currently on the BotNet."""
    def __init__(self, bot_id : int,
            bnet_name : str, bnet_channel : str, bnet_server : int,
            account : str, database : str):
        self.bot_id = bot_id
        self.bnet_name = bnet_name
        self.bnet_channel = bnet_channel
        self.bnet_server = bnet_server
        self.account = account
        self.database = database

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

    def str_bot_id(self):
        if self.bot_id >= 0x40000:
            return "·{}".format(self.bot_id - 0x40000)
        else:
            return str(self.bot_id)

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
