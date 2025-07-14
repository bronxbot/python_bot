"""
Core events handler for BronxBot
"""

import nextcord
from nextcord.ext import commands
from utils.logger import get_logger

logger = get_logger(__name__)


class Events(commands.Cog):
    """Handles bot events and logging"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        
        # Update bot status
        activity = nextcord.Activity(
            type=nextcord.ActivityType.watching,
            name=f"{len(self.bot.guilds)} servers | !help"
        )
        await self.bot.change_presence(activity=activity)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Called when the bot leaves a guild"""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
        
        # Update bot status
        activity = nextcord.Activity(
            type=nextcord.ActivityType.watching,
            name=f"{len(self.bot.guilds)} servers | !help"
        )
        await self.bot.change_presence(activity=activity)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Called when a new member joins a guild"""
        logger.info(f"New member joined {member.guild.name}: {member.name}")
        
        # Initialize user in database if needed
        user_data = await self.bot.db.get_user(member.id, member.guild.id)
        if not user_data:
            await self.bot.db.create_user(member.id, member.guild.id)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Called when a message is sent"""
        
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Initialize user in database if needed
        if message.guild:
            user_data = await self.bot.db.get_user(message.author.id, message.guild.id)
            if not user_data:
                await self.bot.db.create_user(message.author.id, message.guild.id)
    
    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Called when a command completes successfully"""
        logger.info(f"Command completed: {ctx.command.name} by {ctx.author} in {ctx.guild}")
        
        # Track command usage
        await self.bot.db.add_transaction(
            ctx.author.id,
            "command_usage",
            0,
            f"Used command: {ctx.command.name}"
        )


def setup(bot):
    bot.add_cog(Events(bot))
