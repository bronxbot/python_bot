# Work System Module
from .work_cog import Work

def setup(bot):
    bot.add_cog(Work(bot))
