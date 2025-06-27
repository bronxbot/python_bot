


# Import the modular economy system
from .economy import Economy

async def setup(bot):
    """Setup function for the economy cog"""
    await bot.add_cog(Economy(bot))
