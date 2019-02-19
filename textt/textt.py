import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import escape, info, error
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
import base64
import codecs
from random import choice
import unicodedata


class TextTools(commands.Cog):
    """Provides commands for text modification and encoding."""

    def __init__(self, bot):
        """Initialize text cog."""
        self.bot = bot
        
        self._widemap = dict((i, i + 0xFF00 - 0x20) for i in range(0x21, 0x7F))
        self._widemap[0x20] = 0x3000 # IDEOGRAPHIC SPACE

        # table flip src: http://www.fileformat.info/convert/text/upside-down-map.htm
        self._flipmap = dict()
        self._flipmap[0x0021] = 0x00A1
        self._flipmap[0x0022] = 0x201E
        self._flipmap[0x0026] = 0x214B
        self._flipmap[0x0027] = 0x002C
        self._flipmap[0x0028] = 0x0029
        self._flipmap[0x002E] = 0x02D9
        self._flipmap[0x0033] = 0x0190
        self._flipmap[0x0034] = 0x152D
        self._flipmap[0x0036] = 0x0039
        self._flipmap[0x0037] = 0x2C62
        self._flipmap[0x003B] = 0x061B
        self._flipmap[0x003C] = 0x003E
        self._flipmap[0x003F] = 0x00BF
        self._flipmap[0x0041] = 0x2200
        self._flipmap[0x0042] = 0x10412
        self._flipmap[0x0043] = 0x2183
        self._flipmap[0x0044] = 0x25D6
        self._flipmap[0x0045] = 0x018E
        self._flipmap[0x0046] = 0x2132
        self._flipmap[0x0047] = 0x2141
        self._flipmap[0x004A] = 0x017F
        self._flipmap[0x004B] = 0x22CA
        self._flipmap[0x004C] = 0x2142
        self._flipmap[0x004D] = 0x0057
        self._flipmap[0x004E] = 0x1D0E
        self._flipmap[0x0050] = 0x0500
        self._flipmap[0x0051] = 0x038C
        self._flipmap[0x0052] = 0x1D1A
        self._flipmap[0x0054] = 0x22A5
        self._flipmap[0x0055] = 0x2229
        self._flipmap[0x0056] = 0x1D27
        self._flipmap[0x0059] = 0x2144
        self._flipmap[0x005B] = 0x005D
        self._flipmap[0x005F] = 0x203E
        self._flipmap[0x0061] = 0x0250
        self._flipmap[0x0062] = 0x0071
        self._flipmap[0x0063] = 0x0254
        self._flipmap[0x0064] = 0x0070
        self._flipmap[0x0065] = 0x01DD
        self._flipmap[0x0066] = 0x025F
        self._flipmap[0x0067] = 0x0183
        self._flipmap[0x0068] = 0x0265
        self._flipmap[0x0069] = 0x0131
        self._flipmap[0x006A] = 0x027E
        self._flipmap[0x006B] = 0x029E
        self._flipmap[0x006C] = 0x0283
        self._flipmap[0x006D] = 0x026F
        self._flipmap[0x006E] = 0x0075
        self._flipmap[0x0072] = 0x0279
        self._flipmap[0x0074] = 0x0287a
        for k, v in list(self._flipmap.items()):
            self._flipmap[v] = k

    @commands.command(hidden=True)
    async def __flipx(self, ctx, *, text = None):
        """Flips a coin... or text/mention.

        Defaults to coin.
        """
        if text != None and len(text) > 0:
            if len(ctx.message.mentions) > 0:
                member = ctx.message.mentions[0]
            elif len(ctx.message.channel_mentions) > 0:
                channel = ctx.message.channel_mentions[0]
                text = "#" + channel.name
                member = None
            elif len(ctx.message.role_mentions) > 0:
                role = ctx.message.role_mentions[0]
                text = role.name
                member = None
            else:
                member = discord.utils.find(lambda m: m.name.lower() == text.lower(), ctx.bot.get_all_members())
            msg = ""
            if member != None:
                if member.id == self.bot.user.id:
                    member = ctx.message.author
                    msg = "Nice try. You think this is funny? How about *this* instead:\n\n"
                text = member.display_name
            new_text = text.translate(self._flipmap)[::-1]
            await ctx.send("{} (╯°□°）╯︵ {}".format(msg, escape(new_text, mass_mentions = True)))
        else:
            author = ctx.message.author
            await ctx.send("I Choose: ***{}***".format(choice(["HEADS", "TAILS"])))


    @commands.command(aliases=["aesthetic"])
    async def fullwidth(self, ctx, *, arg):
        """Converts narrow characters to wide characters."""

        result = arg.translate(self._widemap)
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command(aliases=["unorm"])
    async def uninormalize(self, ctx, form, *, arg = ""):
        """Normalizes the given Unicode. "NFC", "NFD", "NFKC", and "NFKD" are the forms."""

        if form != "NFC" and form != "NFD" and form != "NFKC" and form != "NFKD":
            s = unicodedata.normalize("NFKC", "{} {}".format(form, arg))
            #await ctx.send("Normalization form not supported: `{a}`\nSupported forms: `NFC`, `NFD`, `NFKC`, `NFKD`.".format(form))
        else:
            s = unicodedata.normalize(form, arg)
        await ctx.send("Normalized: {}".format(escape(s, mass_mentions = True)))


    @commands.command()
    async def unicode(self, ctx, *, arg):
        """Returns the information on a Unicode character or named character."""

        if len(arg) == 1:
            chars = [arg]
        else:
            #if " " in arg[1:-1] or "," in arg[1:-1] or ";" in arg[1:-1]:
            #    arg = arg[:0] + arg[1:-1].replace(",", " ").replace(";", " ") + arg[-1:]

            # try to find what character is meant
            # if starts with "U+", "\x", "\u", it"s hex
            
            if arg.upper().startswith("U+") or arg.upper().startswith("\\U") or arg.upper().startswith("\\X"):
                arg = "0x" + arg[2:].strip()
            try:
                if arg.lower().startswith("0x"):
                    arg = arg[2:]
                chars = [chr(int(arg, 16))]
            except ValueError:
                # otherwise, use name lookup
                try:
                    chars = [unicodedata.lookup(arg)]
                except KeyError:
                    chars = arg
                    #await ctx.send(error("Character not found: `{}`".format(arg)))
                    #return
        
        embeds = []
        n = 0
        for char in chars:
            n += 1
            value = ord(char)
            name = unicodedata.name(char, None)
            #name_url = name.lower().replace(" ", "-")
            dt = {}
            dt["Character"]        = char
            dt["Name"]             = name # str or None
            dt["Decimal"]          = unicodedata.decimal(char, None) # int or None
            dt["Digit"]            = unicodedata.digit(char, None) # int or None
            dt["Numeric"]          = unicodedata.numeric(char, None) # float or None
            dt["Category"]         = unicodedata.category(char) # str
            dt["Bidirectional"]    = unicodedata.bidirectional(char) # str
            dt["Combining class"]  = unicodedata.combining(char) # str
            dt["East Asian width"] = unicodedata.east_asian_width(char) # str
            dt["Mirrored"]         = unicodedata.mirrored(char) # int
            dt["Decomposition"]    = unicodedata.decomposition(char) # str

            embed = discord.Embed(
                title="Unicode codepoints of: {input}".format(input=arg),
                #url="https://emojipedia.org/{}/".format(name_url),
                description="About Unicode U+{codepoint:04X}.".format(codepoint=value))

            for k, v in dt.items():
                if not v is None and len(str(v)):
                    if len(str(v).strip(" \t\r\n\v\f\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000")) == 0:
                        v = '"{}"'.format(v)
                    embed.add_field(name=k, value=str(v), inline=False)
            embed.set_footer(text="Character {index} of {count}".format(index=n, count=len(arg)))
            embeds.append(embed)

        if len(embeds) > 1:
            await menu(ctx, embeds, DEFAULT_CONTROLS)
        else:
            await ctx.send(embed=embeds[0])

    @commands.command(aliases=["shout"])
    async def upper(self, ctx, *, text):
        """Returns the uppercase of the given text."""

        result = text.upper()
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command()
    async def lower(self, ctx, *, text):
        """Returns the lowercase of the given text."""

        result = text.lower()
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command()
    async def echo(self, ctx, *, text):
        """Returns the given text."""

        result = text
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command()
    async def reverse(self, ctx, *, text):
        """Returns the reverse-order of the given text."""

        result = text[::-1]
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command()
    async def base64(self, ctx, *, text):
        """Returns the base-64 of the given text."""

        result = base64.b64encode(text.encode("utf-8")).decode("ascii")
        await ctx.send(escape(result, mass_mentions = True))


    @commands.command()
    async def hex2str(self, ctx, *, text):
        """Converts the given hex bytes to a string assuming UTF-8."""

        result = codecs.decode(text.replace(" ", ""), "hex")
        resultx = result.decode("utf-8")
        await ctx.send(escape(resultx, mass_mentions = True))


    @commands.command()
    async def hex2strx(self, ctx, encoding, *, text):
        """Converts the given hex bytes to a string given an encoding."""

        result = codecs.decode(text.replace(" ", ""), "hex")
        resultx = result.decode(encoding)
        await ctx.send(escape(resultx, mass_mentions = True))

