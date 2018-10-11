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
    async def topic(self, ctx, channel : discord.TextChannel = None):
        """Get the channel topic.
        
        If the channel is omitted, the current channel is assumed."""
        if channel is None:
            # did not provide channel, get current channel
            channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # this not is a DM or group DM
            #async with ctx.typing():
            if len(channel.topic) == 0:
                await ctx.send(content=info("No topic is set for {channel_mention} on {guild}.".format(channel_mention = channel.mention, guild = escape(channel.guild, mass_mentions = True))))
                return

            embed = discord.Embed(description=channel.topic.replace("](", "]\\("))
            embed.set_footer(text="#{channel} on {guild}".format(channel = channel, guild = channel.guild))
            try:
                await ctx.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error("I don't have permission to post an embed!"))
        else:
            # private location: only reply with text
            await ctx.send(content=error("This channel type cannot have a topic."))

    
    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def set(self, ctx, channel : discord.TextChannel, *, topic : str):
        """Set the channel topic to the given value.

        Any custom emojis, mentions, links, and other formatting are supported.
        Note that mentions (including @here and @everyone) in your own message will ping, so best to set the channel from another channel (or the settings) if those are needed."""
        #if isinstance(channel, str):
        #    # did not provide channel, get current channel
        #    topic = "{} {}".format(channel, topic)
        #    channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # this not is a DM or group DM
            #async with ctx.typing():
            try:
                await channel.edit(topic=topic, reason="Topic edit by request of {author} ({author_id})".format(author = ctx.author, author_id = ctx.author.id))
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error("I don't have permission to edit this channel topic!"))
                return

            await ctx.send(content=info("Channel {channel_mention}'s topic has been updated.".format(channel_mention = channel.mention)))
        else:
            # private location: only reply with text
            await ctx.send(content=error("This channel type cannot have a topic."))

    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def amend(self, ctx, channel : discord.TextChannel, *, topic : str):
        """Add the given value to the channel topic. Places new text after a newline.

        Any custom emojis, mentions, links, and other formatting are supported.
        Note that mentions (including @here and @everyone) in your own message will ping, so best to set the channel from another channel (or the settings) if those are needed."""
        #if isinstance(channel, str):
        #    # did not provide channel, get current channel
        #    topic = "{} {}".format(channel, topic)
        #    channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # this not is a DM or group DM
            #async with ctx.typing():
            try:
                await channel.edit(topic="{}\r\n{}".format(channel.topic, topic), reason="Topic edit [amend] by request of {author} ({author_id})".format(author = ctx.author, author_id = ctx.author.id))
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error("I don't have permission to edit this channel topic!"))
                return

            await ctx.send(content=info("Channel {channel_mention}'s topic has been amended to.".format(channel_mention = channel.mention)))
        else:
            # private location: only reply with text
            await ctx.send(content=error("This channel type cannot have a topic."))

    @topic.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def clear(self, ctx, channel : discord.TextChannel = None):
        """Clear the channel topic.
a
        If the channel is omitted, the current channel is assumed."""
        if channel is None:
            # did not provide channel, get current channel
            channel = ctx.channel
        if channel.guild != ctx.guild:
            await ctx.send(content=error("I cannot do that."))
            return
        if isinstance(channel, discord.TextChannel):
            # this not is a DM or group DM
            #async with ctx.typing():
            try:
                await channel.edit(topic="", reason="Topic edit [clear] by request of {author} ({author_id})".format(author = ctx.author, author_id = ctx.author.id))
            except (discord.Forbidden, discord.HTTPException):
                await ctx.send(content=error("I don't have permission to edit this channel topic!"))
                return

            await ctx.send(content=info("Channel {channel_mention}'s topic has been cleared.".format(channel_mention = channel.mention)))
        else:
            # private location: only reply with text
            await ctx.send(content=error("This channel type cannot have a topic."))
