from .textt import TextTools

async def setup(bot):
    await bot.add_cog(TextTools(bot))

