from .rot13 import Rot13

async def setup(bot):
    await bot.add_cog(Rot13(bot))

