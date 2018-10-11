from .topic import Topic

def setup(bot):
    bot.add_cog(Topic(bot))

