from .rot13 import Rot13

def setup(bot):
    bot.add_cog(Rot13(bot))

