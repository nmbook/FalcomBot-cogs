import discord
from redbot.core import commands


class HiBack(commands.Cog):
    """Replies to "I'm X" with "Hi, X"."""
    def __init__(self, bot):
        """Initialize Hi, Back cog."""
        self.bot = bot

    async def on_message_without_command(self, message):
        """Handle on_message."""
        if not isinstance(message.channel, discord.TextChannel):
            # this is a DM or group DM, discard early
            return

        if message.type != discord.MessageType.default:
            # this is a system message, discard early
            return

        if message.author.id == self.bot.user.id:
            # this is ours, discard early
            return

        if message.author.bot:
            # this is a bot, discard early
            return

        content = message.clean_content
        if len(content) == 0:
            # nothing to do, exit early
            return
        if content.lower().startswith("i'm "):
            try:
                back = content[4:5].upper() + content[5:]
                if back.endswith('.'):
                    back = back[:-1]
                back += '!'
                await ctx.send("Hi, {back}".format(back=back),
                               allowed_mentions=discord.AllowedMentions(
                               everyone=False, roles=False, users=False))
            except (discord.HTTPException, discord.Forbidden, ):
                pass

