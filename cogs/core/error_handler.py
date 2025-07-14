"""
Core error handler for BronxBot
"""

import nextcord
from nextcord.ext import commands
import traceback
from utils.logger import get_logger
from utils.bot_utils import create_error_embed

logger = get_logger(__name__)


class ErrorHandler(commands.Cog):
    """Handles errors and exceptions across the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Handle cooldown errors
        if isinstance(error, commands.CommandOnCooldown):
            embed = create_error_embed(
                "Command on Cooldown",
                f"Please wait {error.retry_after:.1f} seconds before using this command again."
            )
            await ctx.send(embed=embed)
            return
        
        # Handle permission errors
        if isinstance(error, commands.MissingPermissions):
            embed = create_error_embed(
                "Missing Permissions",
                "You don't have permission to use this command."
            )
            await ctx.send(embed=embed)
            return
        
        # Handle bot permission errors
        if isinstance(error, commands.BotMissingPermissions):
            embed = create_error_embed(
                "Bot Missing Permissions",
                "I don't have the required permissions to execute this command."
            )
            await ctx.send(embed=embed)
            return
        
        # Handle missing argument errors
        if isinstance(error, commands.MissingRequiredArgument):
            embed = create_error_embed(
                "Missing Argument",
                f"Missing required argument: `{error.param.name}`"
            )
            await ctx.send(embed=embed)
            return
        
        # Handle bad argument errors
        if isinstance(error, commands.BadArgument):
            embed = create_error_embed(
                "Invalid Argument",
                f"Invalid argument provided: {str(error)}"
            )
            await ctx.send(embed=embed)
            return
        
        # Handle user input errors
        if isinstance(error, commands.UserInputError):
            embed = create_error_embed(
                "Input Error",
                f"Invalid input: {str(error)}"
            )
            await ctx.send(embed=embed)
            return
        
        # Handle command invoke errors
        if isinstance(error, commands.CommandInvokeError):
            original_error = error.original
            
            # Log the full error
            logger.error(f"Command {ctx.command.name} failed: {original_error}")
            logger.error(traceback.format_exc())
            
            # Send user-friendly error message
            embed = create_error_embed(
                "Command Error",
                "An error occurred while executing the command. The issue has been logged."
            )
            await ctx.send(embed=embed)
            return
        
        # Handle all other errors
        logger.error(f"Unhandled error in command {ctx.command.name}: {error}")
        logger.error(traceback.format_exc())
        
        embed = create_error_embed(
            "Unexpected Error",
            "An unexpected error occurred. Please try again later."
        )
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_application_command_error(self, interaction: nextcord.Interaction, error):
        """Handle application command errors"""
        
        # Similar error handling for slash commands
        if isinstance(error, nextcord.errors.ApplicationCommandInvokeError):
            original_error = error.original
            
            logger.error(f"Application command {interaction.application_command.name} failed: {original_error}")
            logger.error(traceback.format_exc())
            
            embed = create_error_embed(
                "Command Error",
                "An error occurred while executing the command. The issue has been logged."
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
