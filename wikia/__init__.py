from .wikia import Wikia

async def setup(bot):
    await bot.add_cog(Wikia(bot))

