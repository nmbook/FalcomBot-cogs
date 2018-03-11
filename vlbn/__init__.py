from .vlbn import BotNetVL

def setup(bot):
    bot.add_cog(BotNetVL(bot))

