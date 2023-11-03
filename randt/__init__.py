from .randt import RandomizationTools

async def setup(bot):
    await bot.add_cog(RandomizationTools(bot))

