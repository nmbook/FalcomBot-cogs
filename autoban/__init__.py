from .autoban import AutoBan

def setup(bot):
    bot.add_cog(AutoBan(bot))

