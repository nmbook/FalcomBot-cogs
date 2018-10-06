import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import escape, info, error
from random import choice, choices, sample, randint
import itertools

class RandomizationTools(commands.Cog):
    """Provides commands for randomized output."""

    def __init__(self, bot):
        """Initialize randomization cog."""
        self.bot = bot

    @commands.command()
    async def choose(self, ctx, *items):
        """Chooses a random item from N multiple items.

        To denote multiple-word items, you should use double quotes."""
        items = [escape(c, mass_mentions=True) for c in items]
        if len(items) < 1:
            await ctx.send(error("Not enough items to choose from."))
        else:
            await ctx.send(info("From {} items, I choose: {}".format(len(items), choice(items))))

    @commands.command()
    async def choosex(self, ctx, x : int, *items):
        """From a set of N items, choose X items and display them.
        
        This is random choosing with replacement, and is the same as using the "choose" command multiple times.

        To denote multiple-word items, use double quotes."""
        items = [escape(c, mass_mentions=True) for c in items]
        if x < 1:
            await ctx.send(error("Must choose a positive number of items."))
        elif len(items) < 1:
            await ctx.send(error("Not enough items to choose from."))
        else:
            await ctx.send(info("From {} items, I choose: {}".format(len(items), ", ".join(choices(items, k=x)))))

    @commands.command()
    async def drawx(self, ctx, x : int, *items):
        """From a set of N items, draw X items and display them.
        
        This is random drawing without replacement.

        To denote multiple-word items, use double quotes."""
        items = [escape(c, mass_mentions=True) for c in items]
        if x < 1:
            await ctx.send(error("Must draw a positive number of items."))
        elif len(items) < 1 or len(items) < x:
            await ctx.send(error("Not enough items to draw from."))
        else:
            drawn = sample(range(len(items)), x)
            drawn = [items[i] for i in sorted(drawn)]
            await ctx.send(info("From {} items, I draw: {}".format(len(items), ", ".join(drawn))))

    @commands.command()
    async def shufflethis(self, ctx, *items):
        """Shuffles a list of items.

        To denote multiple-word items, use double quotes."""
        items = [escape(c, mass_mentions=True) for c in items]
        if len(items) < 1:
            await ctx.send(error("Not enough items to shuffle."))
        else:
            await ctx.send(info("A randomized order of {} items: {}".format(len(items), ", ".join(shuffle(items)))))


    @commands.command()
    async def roll(self, ctx, *bounds):
        """Rolls the specified single or multiple dice.
        
        Possible arguments:

        NONE rolls a 6-sided die.
        
        A single number X: rolls an X-sided die (example: ".roll 17").

        Two numbers X and Y: rolls a strange die with a minimum X and maximum Y (example: ".roll 3 8").

        The text NdX: rolls N dice with X sides (example: ".roll 3d20".

        The NdX "dice specification" can be repeated to roll a variety of dice at once. If multiple dice are used, statistics will be shown."""
        sbounds = " ".join(bounds).lower()
        if "d" in sbounds:
            # dice specifiers: remove the spaces around "d" (so "1 d6" -> "1d6"
            while " d" in sbounds or "d " in sbounds:
                bounds = sbounds.replace(" d", "d").replace("d ", "d").split(" ")
                sbounds = " ".join(bounds)

        if len(bounds) == 0:
            # .roll
            bounds = ["6"]
            # fall through to ".roll 6"
        
        if len(bounds) == 1:
            if bounds[0].isnumeric():
                # .roll X
                # provided maximum, roll is between 1 and X
                r_max = int(bounds[0])
                await self._roll1(ctx, 1, r_max)
                return

        if len(bounds) == 2:
            if bounds[0].isnumeric() and bounds[1].isnumeric():
                # .roll X Y
                # provided minimum and maximum, roll is between X and Y
                r_min = int(bounds[0])
                r_max = int(bounds[1])
                await self._roll1(ctx, r_min, r_max)
                return

        # got here, must have been non-numeric objects, possibly containing "d" dice specifiers?
        dice = []
        valid = True
        try:
            for spec in bounds:
                spec = spec.strip(",()")
                if not "d" in spec:
                    raise ValueError("Invalid input.")

                spspec = spec.split("d")
                if len(spspec) != 2:
                    raise ValueError("Invalid dice.")

                if len(spspec[0]) == 0:
                    r_mul = 1
                elif spspec[0].isnumeric():
                    r_mul = int(spspec[0])
                    if r_mul < 1:
                        raise ValueError("Non-positive number of dice.")
                else:
                    raise ValueError("Non-numeric number of dice.")

                if spspec[1].isnumeric():
                    r_max = int(spspec[1])
                    if r_max < 1:
                        raise ValueError("Non-positive side count on dice.")
                    elif r_max >= 10e100:
                        raise ValueError("Side count on dice too large.")
                else:
                    raise ValueError("Non-numeric side count on dice.")

                if len(dice) + r_mul >= 1000:
                    dice = []
                    raise ValueError("Number of dice too large (over 999).")

                dice += itertools.repeat(r_max, r_mul)
        except ValueError as ex:
            await ctx.send(error(str(ex)))
            return
        
        if len(dice) == 0:
            await ctx.send(error("No collected dice to use."))
            return

        if len(dice) == 1:
            # one die
            await self._roll1(ctx, 1, dice[0])
            return

        d_rol = [randint(1, X) for X in dice]

        d_ind = ""
        if len(dice) < 100:
            d_ind = "\r\nValues: {}".format(", ".join(["`{}`".format(x) for x in d_rol]))

        await ctx.send(info("Collected and rolled {:,} dice!{}\r\nTotal number of sides: {:,}\r\n**Total value: {:,}**".format( \
                len(dice), d_ind, sum(dice), sum(d_rol))))


    async def _roll1(self, ctx, r_min, r_max):
        """Perform and print a single dice roll."""
        if r_min >= 10e100:
            await ctx.send(error("Minimum value too large."))
            return
        if r_max >= 10e100:
            await ctx.send(error("Maximum value too large."))
            return
        r_cnt = r_max - r_min + 1
        strange = "strange "
        a_an = "a"
        r_rng = ""
        if r_min == 1:
            if r_max in [4, 6, 8, 10, 12, 20]:
                strange = ""
                if r_max == 8:
                    a_an = "an"
        else:
            r_rng = " ({:,} to {:,})".format(r_min, r_max)
        if r_max < r_min:
            await ctx.send(error("Between {} and {} is not a valid range.".format(r_min, r_max)))
        else:
            r = randint(r_min, r_max)
            await ctx.send(info("I roll {} {}{}-sided die{}, and it lands on: **{:,}**".format(a_an, strange, r_cnt, r_rng, r)))
