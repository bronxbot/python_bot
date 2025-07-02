import nextcord
from nextcord.ext import commands
import traceback
from cogs.logging.logger import CogLogger

class ErrorHandler:
    """Base class for error handling in cogs"""
    
    def __init__(self):
        self.logger = CogLogger(self.__class__.__name__)

    async def handle_error(self, ctx, error, command_name=None):
        """Common error handling logic for all cogs"""
        # Get error context
        command = command_name or ctx.command.qualified_name if ctx.command else "Unknown"
        author = f"{ctx.author} ({ctx.author.id})"
        guild = f"{ctx.guild} ({ctx.guild.id})" if ctx.guild else "DM"
        
        # Generate error trace
        error_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        error_id = hex(abs(hash(str(error))))[-6:]
        
        # Log the error
        self.logger.error(
            f"Command error in {command} (ID: {error_id}):\n"
            f"User: {author}\n"
            f"Guild: {guild}\n"
            f"Error: {str(error)}\n"
            f"Traceback:\n{error_trace}"
        )

        # Handle common error types
        try:
            if isinstance(error, commands.MissingPermissions):
                embed = nextcord.Embed(
                    title="❌ Missing Permissions",
                    description=f"You need {', '.join(error.missing_permissions)} permission(s) to use this command!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.BotMissingPermissions):
                embed = nextcord.Embed(
                    title="❌ Bot Missing Permissions",
                    description="I don't have the required permissions for this command!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.BadArgument):
                embed = nextcord.Embed(
                    title="❌ Invalid Argument",
                    description=f"Invalid argument provided: {str(error)}",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.DisabledCommand):
                embed = nextcord.Embed(
                    title="❌ Command Disabled",
                    description="This command is currently disabled",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.NoPrivateMessage):
                embed = nextcord.Embed(
                    title="❌ Server Only",
                    description="This command cannot be used in DMs",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.CheckFailure):
                embed = nextcord.Embed(
                    title="❌ Access Denied",
                    description="You don't meet the requirements to use this command",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            else:
                # For unexpected errors, let the global Error cog handle it
                # Don't send a user-facing message here
                pass
                
        except Exception as e:
            self.logger.error(f"Error handling error: {e}")
        
        # Mark that this error has been handled to prevent duplicate processing
        setattr(error, '_handled_by_cog', True)
        return error_id
