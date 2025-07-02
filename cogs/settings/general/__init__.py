"""
General Settings Module
Modular general server settings system for permissions, prefixes, whitelists, blacklists, and ignore management.
"""

from .general_cog import GeneralSettings

__all__ = ['GeneralSettings']

def setup(bot):
    """Set up the General Settings cog"""
    bot.add_cog(GeneralSettings(bot))
