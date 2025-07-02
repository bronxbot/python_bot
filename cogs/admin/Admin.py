"""
Admin System Compatibility Shim
This file maintains backwards compatibility while loading the modular admin system.
"""

# Import the modular admin system
from .admin import Admin

def setup(bot):
    """Setup function for the admin cog"""
    bot.add_cog(Admin(bot))
