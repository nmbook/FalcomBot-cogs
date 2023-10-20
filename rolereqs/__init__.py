from .rolereqs import RoleRequests

async def setup(bot):
    await bot.add_cog(RoleRequests(bot))

