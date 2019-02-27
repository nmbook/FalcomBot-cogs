# https://github.com/nmbook/FalcomBot-cogs topic
# cog for Red V3

"""Topic cog module."""

import discord

from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import escape, info, error


class Topic(commands.Cog):
    """Provides Topic command to retrieve and edit topics."""

    def __init__(self, bot):
        """Initialize Topic cog."""
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def topic(self, ctx, channel: discord.TextChannel=None):
        """Get the channel topic.

        If the channel is omitted, the current channel is assumed."""
        if channel is None:
            # Did not provide channel; get current channel
            channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # This not is a DM or group DM
            # async with ctx.typing():
            if len(channel.topic) == 0:
                guild = escape(channel.guild, mass_mentions=True)
                result = "No topic is set for {channel} on {guild}." \
                    .format(channel=channel.mention, guild=guild)
                await ctx.send(content=info(result))
                return

            title = "#{}".format(str(channel))
            url = "https://discordapp.com/channels/{}/{}/" \
                .format(channel.guild.id, channel.id)
            description = channel.topic.replace("](", "]\\(")
            embed = discord.Embed(
                    title=title,
                    url=url,
                    description=description)
            embed.set_footer(text=channel.guild)
            try:
                await ctx.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error(
                        "I don't have permission to post an embed!"))
        else:
            # Private location: only reply with text
            await ctx.send(content=error(
                    "This channel type cannot have a topic."))
    
    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def set(self, ctx, channel: discord.TextChannel, *, topic: str):
        """Set the channel topic to the given value.

        Any custom emojis, mentions, links, and other formatting are
        supported.
        Note that mentions (including @here and @everyone) in your own
        message will ping, so best to set the channel from another
        channel (or the server's settings) if those are needed."""
        # if isinstance(channel, str):
        #     # Did not provide channel; get current channel
        #     topic = "{} {}".format(channel, topic)
        #     channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # This not is a DM or group DM
            # async with ctx.typing():
            reason = "Topic edit by request of {author} ({id})" \
                    .format(author=ctx.author, id=ctx.author.id)
            try:
                await channel.edit(topic=topic, reason=reason)
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error(
                        "I don't have permission to edit this topic!"))
                return

            await ctx.send(content=info(
                    "Channel {channel}'s topic has been updated."
                    .format(channel=channel.mention)))
        else:
            # Private location: only reply with text
            await ctx.send(content=error(
                    "This channel type cannot have a topic."))

    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def amend(self, ctx, channel: discord.TextChannel, *, topic: str):
        """Add the given value to the channel topic.

        Places new text after a newline.
        Any custom emojis, mentions, links, and other formatting are
        supported.
        Note that mentions (including @here and @everyone) in your own
        message will ping, so best to set the channel from another
        channel (or the server's settings) if those are needed."""
        # if isinstance(channel, str):
        #     # Did not provide channel; get current channel
        #     topic = "{} {}".format(channel, topic)
        #     channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # This not is a DM or group DM
            # async with ctx.typing():
            new_topic = "{}\r\n{}".format(channel.topic, topic)
            reason = "Topic edit [amend] by request of {author} ({id})" \
                .format(author=ctx.author, id=ctx.author.id)
            try:
                await channel.edit(topic=new_topic, reason=reason)
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error(
                        "I don't have permission to edit this topic!"))
                return

            await ctx.send(content=info(
                    "Channel {channel}'s topic has been amended to."
                    .format(channel=channel.mention)))
        else:
            # Private location: only reply with text
            await ctx.send(content=error(
                    "This channel type cannot have a topic."))

    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def clear(self, ctx, channel: discord.TextChannel=None):
        """Clear the channel topic.

        If the channel is omitted, the current channel is assumed."""
        if channel is None:
            # Did not provide channel; get current channel
            channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # This not is a DM or group DM
            # async with ctx.typing():
            reason = "Topic edit [clear] by request of {author} ({id})" \
                .format(author=ctx.author, id=ctx.author.id)
            try:
                await channel.edit(topic="", reason=reason)
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error(
                        "I don't have permission to edit this topic!"))
                return

            await ctx.send(content=info(
                    "Channel {channel}'s topic has been cleared."
                    .format(channel=channel.mention)))
        else:
            # Private location: only reply with text
            await ctx.send(content=error(
                    "This channel type cannot have a topic."))

