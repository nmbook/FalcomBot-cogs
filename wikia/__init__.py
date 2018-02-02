from .wikia import Wikia

def setup(bot):
    bot.add_cog(Wikia(bot))

