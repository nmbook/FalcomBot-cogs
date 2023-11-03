from .topic import Topic

async def setup(bot):
    await bot.add_cog(Topic(bot))

