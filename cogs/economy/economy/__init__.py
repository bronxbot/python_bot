# Economy System Module
from .economy_cog import Economy

__all__ = ['Economy']

def setup(bot):
    """Setup function for the economy cog"""
    bot.add_cog(Economy(bot))
