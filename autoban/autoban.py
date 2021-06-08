# Auto-Ban module
# Ribose

from datetime import timezone

import discord
from redbot.core import commands, Config, checks, modlog
from redbot.core.utils.chat_formatting import escape, info, error, humanize_list

class AutoBan(commands.Cog):
    """Automatically bans based on criteria."""

    guild_conf = {
            "terms": []
            }

    def __init__(self, bot):
        """Initialize cog. Set up config."""
        self.bot = bot

        self.config = Config.get_conf(self, 0xff5269620001)
        self.config.register_guild(**self.guild_conf)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_message(self, message):
        """Handle on_message"""
        if not isinstance(message.channel, discord.TextChannel):
            # this is a DM or group DM, discard early
            return
        if message.type != discord.MessageType.default:
            # this is a system message, discard early
            return
        author = message.author
        if author.id == self.bot.user.id:
            # this is ours, discard early
            return
        if author.bot:
            # this is a bot, discard early
            return
        if len(message.clean_content) == 0:
            # nothing to do, exit early
            return
        if len([role for role in author.roles if role != message.guild.default_role]) > 0:
            # ignore if has roles
            return

        terms = await self.config.guild(message.guild).terms()
        counter = 0
        content = message.content
        term = ''
        last_term = None
        for term in terms:
            if len(term) > 0:
                if len(content) > 0 and term.lower() in content.lower():
                    counter += 1
                    last_term = term
                if len(author.name) > 0 and term.lower() in author.name.lower():
                    counter += 1
                    last_term = term

        if counter >= 1 and len(terms) > 0 and len(term) > 0:
            #print("caught word " + term.lower() + " from " + str(message.author) + " with " + str(len(author.roles)))
            s = "Autoban: {q}{term}{q}\nUsername: {name} - Text: {text}"
            reason = s.format(
                    term=last_term,
                    q='"',
                    name=author.name,
                    text=content[:512-len(last_term)-len(author.name)-len(s)])
            try:
                await message.delete(delay=0)
            except:
                pass
            try:
                await author.ban(reason=reason[:512], delete_message_days=0)
            except discord.HTTPException:
                log.warning(
                    "Failed to ban a member ({member}) for mention spam in server {guild}.".format(
                        member=author.id, guild=message.guild.id
                    )
                )
            else:
                await modlog.create_case(
                    self.bot,
                    guild,
                    message.created_at.replace(tzinfo=timezone.utc),
                    "ban",
                    author,
                    guild.me,
                    reason,
                    until=None,
                    channel=message.channel,
                )

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def autoban(self, ctx, *, term):
        """Add term to the auto-ban list."""
        await ctx.invoke(self.add, term=term)

    @autoban.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def add(self, ctx, *, term):
        """Add term to the auto-ban list."""
        async with self.config.guild(ctx.guild).terms() as terms:
            if not term in terms:
                terms.append(term)
                await ctx.send(info("Term added."))
            else:
                await ctx.send(error("Term was already present on this server."))

    @autoban.command(aliases=["rem", "delete", "del"])
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def remove(self, ctx, *, term):
        """Remove term from the auto-ban list."""
        async with self.config.guild(ctx.guild).terms() as terms:
            if term in terms:
                terms.remove(term)
                await ctx.send(info("Term removed."))
            else:
                await ctx.send(error("Term was not present on this server."))

    @autoban.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def list(self, ctx):
        """List terms from the auto-ban list."""
        async with self.config.guild(ctx.guild).terms() as terms:
            if len(terms) == 0:
                await ctx.send(info("No terms set on this server."))
            else:
                ls = humanize_list(["`{}`".format(term) for term in terms])
                await ctx.send(info("Terms on this server:\n{}".format(ls)))

    @autoban.command()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_guild=True)
    async def clear(self, ctx):
        """Clear terms from the auto-ban list."""
        await self.config.guild(ctx.guild).terms.set([])
        await ctx.send(info("Terms cleared on this server."))

