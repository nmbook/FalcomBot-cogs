# Role Request module
# Ribose

import discord
from discord.ext import commands
from redbot.core import Config
from redbot.core import checks
from redbot.core.utils.chat_formatting import escape

class RoleRequests:
    """Adds or removes a role on users by request."""

    def __init__(self, bot):
        default_guild = {
                "roles": [],
                "max_requestable": 3,
                "request_channel": 0
        }

        default_channel = {
                "role_info_post": -1
        }

        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xff5269620001)
        self.config.register_guild(**default_guild)
        self.config.register_channel(**default_channel)
    
    @commands.group(no_pm=True, aliases=['iam', 'req'])
    async def request(self, ctx):#, *, raw_text):
        """Requests access to a role."""
        if ctx.invoked_subcommand is None:
            #if len(raw_text) > 0:
            #    await self.add(ctx, raw_text)
            #else:
                await ctx.send_help()
    
    @request.command(no_pm=True)
    #@checks.mod_or_permissions(add_reactions=True)
    async def list(self, ctx):
        """Lists the roles that can be requested."""
        msg = await self._get_role_list_message(ctx, ctx.message.channel)

        await ctx.send(msg)
    
    @request.command(no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def postlist(self, ctx, channel : discord.TextChannel):
        """Lists the roles that can be requested and posts them permanently to the specified channel."""
        msg = await self._get_role_list_message(ctx)

        if channel is None:
            channel = ctx.message.channel

        if channel.guild.id != ctx.guild.id:
            await ctx.send("Error: That channel is not on this server.")
            return

        post_id = await self.config.channel(channel).role_info_post()
        updated = False
        if post_id > 0:
            try:
                post = await channel.get_message(post_id)
                updated = True
                if msg != post.content:
                    await post.edit(content=msg)
                else:
                    updated = None
            except discord.NotFound:
                await ctx.send('Warning: A role information post was already posted in that channel but since deleted.')
                post = await channel.send(msg)
        else:
            post = await channel.send(msg)

        await self.config.channel(channel).role_info_post.set(post.id)

        if updated is None:
            await ctx.send('No update needed. Update it later with `{}request postlist #{}`'.format(ctx.prefix[0], channel))
        elif updated:
            await ctx.send('Message updated. Update it later with `{}request postlist #{}`'.format(ctx.prefix[0], channel))
        else:
            await ctx.send('Message posted to channel. Update it later with `{}request postlist #{}`'.format(ctx.prefix[0], channel))

    @request.command(no_pm=True)
    #@checks.mod_or_permissions(add_reactions=True)
    async def add(self, ctx, *, role_name):
        """Gives you a requestable role."""
        author = ctx.message.author

        # requestable list
        role_subset = await self.config.guild(ctx.guild).roles()
        max_requestable = await self.config.guild(ctx.guild).max_requestable()

        # find matches
        role_to_add = await self._find_role(ctx, role_name, role_subset=role_subset)
        if role_to_add is None:
            return

        if role_to_add in author.roles:
            await ctx.send("Error: You already have the role `{}`.".format(role_to_add))
            return

        if not role_to_add.id in role_subset:
            await ctx.send("Error: You cannot request `{}`.".format(role_to_add))
            return

        count = 0
        for role in author.roles:
            if role.id in role_subset:
                count += 1
                if count >= max_requestable:
                    cpl = ''
                    if count != 1:
                        cpl = 's'
                    await ctx.send("Error: You already have {} role{} that can be requested (max: {}). You may ask a moderator or you may remove a role with with `{}request rem NAME`.".format(count, cpl, max_requestable, ctx.prefix[0]))
                    return

        await author.add_roles(role_to_add)
        await ctx.send('Added {} to your roles.'.format(self._get_role_styled(role_to_add, show_stats=True)))

    @request.command(no_pm=True, aliases=['remove'])
    #@checks.mod_or_permissions(add_reactions=True)
    async def rem(self, ctx, *, role_name):
        """Takes a requestable role."""
        author = ctx.message.author

        # requestable list
        role_subset = await self.config.guild(ctx.guild).roles()
        role_ids = [x.id for x in author.roles]
        role_subset = [x for x in role_subset if x in role_ids]

        # find matches
        role_to_add = await self._find_role(ctx, role_name, role_subset=role_subset)
        if role_to_add is None:
            return

        if not role_to_add in author.roles:
            await ctx.send("Error: You do not have the role `{}`.".format(role_to_add))
            return

        if not role_to_add.id in role_subset:
            await ctx.send("Error: You cannot remove `{}`.".format(role_to_add))
            return

        await author.remove_roles(role_to_add)
        await ctx.send('Removed {} from your roles.'.format(self._get_role_styled(role_to_add, show_stats=True)))

    @request.command(no_pm=True, aliases=['clr'])
    async def clear(self, ctx):
        """Clears all requestable roles."""
        author = ctx.message.author

        # requestable list
        role_subset = await self.config.guild(ctx.guild).roles()
        role_objs = [x for x in author.roles if x.id in role_subset]
        role_count = len(role_objs)
        if role_count > 0:
            await author.remove_roles(*role_objs)
            if role_count > 1:
                await ctx.send('Removed {} of your roles.'.format(role_count))
            else:
                await ctx.send('Removed {} from your roles.'.format(self._get_role_styled(role_objs[0], show_stats=True)))
        else:
            await ctx.send("Error: You do not have any requestable roles to remove.")

    @request.command(no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def addrole(self, ctx, *, role_name):
        """Adds a role to be requestable."""
        # find matches
        role_to_add = await self._find_role(ctx, role_name)
        if role_to_add is None:
            return

        async with self.config.guild(ctx.guild).roles() as role_subset:
            if ctx.guild.id in role_subset:
                await ctx.send("Error: Role {} can already be requested.".format(self._get_role_styled(role_to_add, show_stats=True)))
                return

            role_subset.append(role_to_add.id)

            await ctx.send("Added {} to requestable roles list.".format(self._get_role_styled(role_to_add, show_stats=True)))

    @request.command(no_pm=True, aliases=['removerole'])
    @checks.mod_or_permissions(administrator=True)
    async def remrole(self, ctx, *, role_name):
        """Removes a role from being requestable."""
        # find matches
        role_to_add = await self._find_role(ctx, role_name)
        if role_to_add is None:
            return
        
        async with self.config.guild(ctx.guild).roles() as role_subset:
            if not ctx.guild.id in role_subset:
                await ctx.send("Error: Role {} was already not requestable.".format(self._get_role_styled(role_to_add, show_stats=True)))
                return

            role_subset.remove(role_to_add.id)

            await ctx.send("Removed {} from requestable roles list.".format(self._get_role_styled(role_to_add, show_stats=True)))

    @commands.group(no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def reqset(self, ctx):
        """Adjust settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @reqset.command(no_pm=True)
    @checks.mod_or_permissions(administrator=True)
    async def request_channel(self, ctx, channel : discord.TextChannel = None):
        """Where `[p]request list` commands say to use the `[p]request` command."""
        if channel is None:
            channel_id = 0
        elif channel.guild != ctx.guild:
            await ctx.send("Error: Channel not found on this server.")
            return
        else:
            channel_id = channel.id

        await self.config.guild(ctx.guild).request_channel.set(channel_id)
        if channel_id != 0:
            await ctx.send("Set \"request channel\" to {}".format(channel.mention))
        else:
            await ctx.send("Cleared \"request channel\".")

    @request.command(no_pm=True, aliases=['massapplyrole', 'massapply'])
    @checks.mod_or_permissions(administrator=True)
    async def massadd(self, ctx, limit : int = 1000, channel : discord.TextChannel = None, *, role_name):
        """Adds roles to all users who have participated in a channel within the last X messages."""
        # requestable list
        role_subset = await self.config.guild(ctx.guild).roles()

        # find matches
        role_to_add = await self._find_role(ctx, role_name, role_subset=role_subset)
        if role_to_add is None:
            return

        if channel is None:
            channel = ctx.message.channel

        if channel is None:
            await ctx.send("Error: Channel not found.")
            return
        if channel.guild != ctx.guild:
            await ctx.send("Error: Channel not found on this server.")
            return

        async with ctx.message.channel.typing():
            accounts = []
            n = 0
            async for message in channel.history(limit=limit):
                if not message.author.bot and \
                   not message.author == ctx.message.author and \
                   hasattr(message.author, 'roles') and \
                   not message.author in accounts and \
                   not role_to_add in message.author.roles:
                    accounts.append(message.author)
                n += 1

            if len(accounts) == 0:
                await ctx.send("Error: No users have participated in the last {} messages in {}.".format(n, channel.mention))
            elif len(accounts) == 1:
                await accounts[0].add_roles(role_to_add)
                await ctx.send("Added {} to {}'s roles (only participant in the last {} messages in {}).".format(self._get_role_styled(role_to_add, show_stats=True), accounts[0], n, channel.mention))
            else:
                for account in accounts:
                    await account.add_roles(role_to_add)
                await ctx.send("Added {} to {} users' roles (participants in the last {} messages in {}).".format(self._get_role_styled(role_to_add, show_stats=True), len(accounts), n, channel.mention))

    def _get_role_styled(self, role_obj, *, show_stats=False):
        if role_obj.mentionable:
            role_txt = "@{} [pingable]".format(escape(str(role_obj)))
        else:
            role_txt = role_obj.mention

        if show_stats:
            color = ''
            if role_obj.color != discord.Color.default() and role_obj.mentionable:
                color = '{}; '.format(role_obj.color)
            return "{} ({}{})".format(role_txt, color, len(role_obj.members))
        else:
            return role_txt

    async def _get_role_list_message(self, ctx, channel : discord.TextChannel = None):
        n = 0
        msg = ""
        rolereqs = await self.config.guild(ctx.guild).roles()
        reqchan_id = await self.config.guild(ctx.guild).request_channel()
        if not channel is None and channel.id == reqchan_id:
            reqchan_id = 0
        in_chan = ""
        if reqchan_id > 0:
            reqchan = ctx.guild.get_channel(reqchan_id)
            if not reqchan is None:
                in_chan = " in {}".format(reqchan.mention)
        for role_obj in sorted(ctx.guild.role_hierarchy, reverse=True):
            for role_id in rolereqs:
                if role_obj.id == role_id:
                    if (n % 5) == 0:
                        msg += '\n'
                    n += 1
                    msg += "{}  ".format(self._get_role_styled(role_obj, show_stats=True))
                    break
        
        if n == 0:
            return "There are no roles set up on this server.\n\nAdd them with `{}request addrole NAME`".format(ctx.prefix[0])
        else:
            return "__***REQUESTABLE ROLES ON THIS SERVER***__ ({number} roles){roles}\n\nModify your roles{in_chan} with:\n`{prefix}request add NAME`\n`{prefix}request rem NAME`".format(number=n, roles=msg, prefix=ctx.prefix[0], in_chan=in_chan)

    async def _find_role(self, ctx, role_name, *, role_subset=None):
        if role_subset is None:
            # just get all roles on server...
            role_subset = [role.id for role in ctx.guild.role_hierarchy]

        # check if role-mention
        role_to_add = None
        if len(ctx.message.role_mentions) > 0:
            role_to_add = ctx.message.role_mentions[0]

        # check if on this guilda
        found_on_guild = False
        if not role_to_add is None:
            for role_obj in ctx.guild.roles:
                if role_to_add.id == role_obj.id:
                    # found
                    found_on_guild = True


        # if not mention, check role_name text and search for role by name
        role_to_add_results = []
        if role_to_add is None:
            for role_obj in sorted(ctx.guild.role_hierarchy, reverse=True):
                if not role_obj.id in role_subset:
                    # role isn't in "requestable subset", skip this result
                    continue

                if role_name.lower().strip('<>@ ') == str(role_obj).lower().strip('<>@ '):
                    # found exact
                    role_to_add_results = [role_obj]
                    break

                if role_name.lower().strip('<>@ ') in str(role_obj).lower().strip('<>@ '):
                    # found
                    role_to_add_results.append(role_obj)

            if len(role_to_add_results) == 0:
                await ctx.send("Error: Text does not match a role.".format(role_name))
                return None
            elif len(role_to_add_results) == 1:
                role_to_add = role_to_add_results[0]
                found_on_guild = True
            else:
                role_to_add_result_str = ', '.join(['`{}`'.format(x) for x in role_to_add_results])
                await ctx.send("Error: Text matches multiple possible roles: {}".format(role_to_add_result_str))
                return None

        return role_to_add
 
