import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import escape, info, error
import aiohttp
import asyncio
import os
import re
import string
import traceback
import urllib.parse

class Info(commands.Cog):
    """Commands to view user, channel, role, server, and emoji info."""

    def __init__(self, bot):
        self.bot = bot

    def _display_interval(self, seconds, granularity=2, short=False):
        # What would I ever do without stackoverflow?
        intervals = (  # Source: http://stackoverflow.com/a/24542445
            (' years', 31536000), # 60 * 60 * 24 * 365
            #(' weeks', 604800),  # 60 * 60 * 24 * 7
            (' days', 86400),    # 60 * 60 * 24
            (' hours', 3600),    # 60 * 60
            (' minutes', 60),
            (' seconds', 1),
        )

        if short:
            intervals = (
                ('y ', 31536000), # 60 * 60 * 24 * 365
                #('', 604800),  # 60 * 60 * 24 * 7
                ('d ', 86400),    # 60 * 60 * 24
                (':', 3600),    # 60 * 60
                (':', 60),
                ('', 1),
            )

        result = []

        if granularity is None or granularity <= 0:
            granularity = 5

        seconds = round(seconds)
        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if short:
                    value_s = '{:02,d}'.format(value)
                else:
                    value_s = '{:,}'.format(value)
                if value == 1:
                    key = name.rstrip('s')
                else:
                    key = name
                result.append("{}{}".format(value_s, key))
        if short:
            return ''.join(result[:granularity]).lstrip('0')
        else:
            return ', '.join(result[:granularity])

    def _time_of(self, ctx, time):
        since = (ctx.message.created_at - time).total_seconds()
        return '{}\n{} ago'.format(
                time.strftime('%d %b %Y %H:%M'),
                self._display_interval(since, 2))

    @commands.command()
    async def userinfo(self, ctx, *, search_term = ''):
        #print(search_term)
        search_term = search_term.strip()
        user = None
        # is mention?
        if len(ctx.message.mentions) == 1:
            user = ctx.message.mentions[0]
        # is empty?
        elif len(search_term) == 0:
            user = ctx.author
        else:
            # is search_term on this guild?
            if ctx.guild:
                user = ctx.guild.get_member_named(search_term)
            if user is None:
                # is search_term visible to bot at all?
                all_members = self.bot.get_all_members()
                user = discord.utils.find(lambda m: m.name == search_term, all_members)
                if user is None:
                    # is search_term an ID?
                    if search_term.isnumeric():
                        # get their User object "from anywhere"
                        try:
                            user = await self.bot.get_user_info(int(search_term))
                            if user.id in [m.id for m in all_members]:
                                user = discord.utils.find(lambda m: m.id == user.id, all_members)
                        except discord.NotFound:
                            # user not found
                            user = None

        if user is None:
            ctx.send(error("User not found."))
            return

        def status2emoji(user_obj):
            if not hasattr(user_obj, "game") or user_obj.game is None:
                if   user_obj.status == discord.Status.online: # online
                    return '\U0001f49a'
                elif user_obj.status == discord.Status.idle: # idle
                    return '\U000026a0'
                elif user_obj.status == discord.Status.dnd: # dnd
                    return '\U0001f6d1'
                else: # offline
                    return '\U0001f5a4'
            else:
                if   user_obj.game.type == 1: # stream
                    return '\U0001f4fa'
                elif user_obj.game.type == 2: # music
                    return '\U0001f3b5'
                elif len(str(user_obj.game)) > 0: # game
                    return '\U0001f3ae'

        #print("found {} ID {} {}".format(user, user.id, user.__class__.__name__))
        # defaults
        name = str(user)
        game = '*Cannot be seen by the bot.*'
        color = discord.Color.default()
        roles = []
        pos_text = ''

        # get data
        is_visible = hasattr(user, 'joined_at')
        if is_visible:
            game = '{e}: {status}'.format(e=status2emoji(user), status=user.status)
            if not hasattr(user, "game") or user.game is None:
                pass
            else:
                if   user.game.type == 1: # stream
                    game_type = 'Streaming'
                elif user.game.type == 2: # listening
                    game_type = 'Listening to'
                elif user.game.type == 0: # game
                    game_type = 'Playing'
                if user.game.url:
                    game = '{e}: {text} **[{game}]({url})**'.format(e=status2emoji(user), text=game_type, game=user.game, type=user.game.type, status=user.status, url=user.game.url)
                else:
                    game = '{e}: {text} **{game}**'.format(e=status2emoji(user), text=game_type, game=user.game, type=user.game.type, status=user.status, url=user.game.url)

            pretext = ''
            if user.nick:
                pretext = '**AKA** {nick}'.format(nick=user.nick, user=name, game=game)
            if user.bot: # robot
                pretext = '\U0001f916 {}'.format(pretext)
            #if user.nitro: # nitro
            #    pretext = '<:DiscordNitro:328619248068853760> {}'.format(pretext)
            #if user.partner: # partner
            #    pretext = '<:DiscordPartner:328620241586225153> {}'.format(pretext)
            #if user.staff: # staff
            #    pretext = '<:DiscordStaff:328620818688901120> {}'.format(pretext)
            #if user.hypesquad: # hypesquad
            #    pretext = '<:DiscordHypeSquad:328619256705056770> {}'.format(pretext)
            if ctx.guild and ctx.guild.owner == user: # crown
                pretext = '\U0001f451 {}'.format(pretext)
            if len(pretext):
                game = pretext + '\n\n' + game

            if ctx.guild:
                is_member = user.guild == ctx.guild
                if is_member:
                    color = user.color
                    
                    roles = [str(r) for r in sorted(user.roles, key=lambda r: r.position, reverse=True) if not r.is_default()]

                    guild_members = sorted(ctx.guild.members, key=lambda m: m.joined_at)
                    p = guild_members.index(user) + 1
                    p_before = ''
                    p_before1 = ''
                    p_after = ''
                    p_after1 = ''
                    if p > 1:
                        p_before = guild_members[p - 2]
                        p_before1 = ' > '
                    if p < len(guild_members):
                        p_after = guild_members[p]
                        p_after1 = ' > '

                    pos_text = '**{}**: {}{}**{}**{}{}'.format(p, p_before, p_before1, user, p_after1, p_after)
                else:
                    game = game + '\n\n*Not on this server.*'
            else:
                is_member = False
        else:
            is_member = False

        # embed create
        if color == discord.Color.default():
            data = discord.Embed(description=game)
        else:
            data = discord.Embed(description=game, color=color)

        # embed fields
        data.add_field(name='Joined Discord on', value=self._time_of(ctx, user.created_at))
        if is_member:
            data.add_field(name='Joined this server on', value=self._time_of(ctx, user.joined_at))
            if len(roles):
                data.add_field(name='Roles', value='**{}**: {}'.format(len(roles), ', '.join(roles)))
            else:
                data.add_field(name='Roles', value='*None*')
            data.add_field(name='Position', value=pos_text)
        data.set_footer(text="ID: {}".format(user.id))

        # embed avatar
        if user.avatar_url:
            data.set_author(name=name, url=user.avatar_url)
            data.set_thumbnail(url=user.avatar_url)
        else:
            data.set_author(name=name)

        # send embed
        try:
            await ctx.send(embed=data)
        except discord.errors.Forbidden:
            await ctx.send(error("Requires permissions."))


