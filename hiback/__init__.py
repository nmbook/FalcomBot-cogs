from .hiback import HiBack

async def setup(bot):
    await bot.add_cog(HiBack(bot))

