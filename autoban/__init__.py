from .autoban import AutoBan

async def setup(bot):
    await bot.add_cog(AutoBan(bot))

