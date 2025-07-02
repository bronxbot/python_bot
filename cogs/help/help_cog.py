import nextcord
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler
from .help_paginator import HelpPaginator
from .help_formatter import HelpFormatter
from .help_utils import HelpUtils
import json

logger = CogLogger('Help')

# Load configuration from environment variables
import os
BOT_ADMINS = os.getenv('DISCORD_BOT_OWNER_IDS', '').split(',') if os.getenv('DISCORD_BOT_OWNER_IDS') else []

class Help(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.formatter = HelpFormatter(bot)
        self.utils = HelpUtils(bot)
        self.logger.info("Help cog initialized")

    @commands.command(aliases=['support'])
    async def invite(self, ctx):
        """Get the bot's invite link & support server."""
        self.logger.info(f"Invite link requested by {ctx.author}")
        
        embed = nextcord.Embed(
            title="🔗 Invite BronxBot",
            description=(
                "**Bot Invite Link:**\n"
                f"[Add BronxBot to your server](https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot)\n\n"
                "**Support Server:**\n"
                "[Join our Discord](https://discord.gg/bronx)\n\n"
                "**Features:**\n"
                "• Economy & Gambling\n"
                "• Music & Entertainment\n"
                "• Moderation Tools\n"
                "• And much more!"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed)

    @nextcord.slash_command(description="Get the bot's invite link and support server")
    async def invite_slash(self, interaction: nextcord.Interaction):
        """Slash command version of invite"""
        embed = nextcord.Embed(
            title="🔗 Invite BronxBot",
            description=(
                f"[Add BronxBot to your server](https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot)\n\n"
                "[Support Server](https://discord.gg/jvyYWkj3ts)\n\n"
                "**Features:**\n"
                "• Economy & Gambling\n"
                "• Music & Entertainment\n"
                "• Moderation Tools\n"
                "• And much more!"
            ),
            color=0x2b2d31
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @commands.command(name='help', aliases=['h', 'cmds'])
    async def help(self, ctx, *, command_or_cog: str = None):
        """
        Show help information for commands and cogs
        
        Usage:
        • `.help` - Show main help menu
        • `.help <command>` - Show help for a specific command
        • `.help <cog>` - Show help for a specific cog
        • `.help search <query>` - Search for commands
        
        Examples:
        • `.help balance`
        • `.help Economy`
        • `.help search fish`
        """
        self.logger.info(f"Help requested by {ctx.author}: {command_or_cog or 'main menu'}")
        
        try:
            await self._send_help(ctx, command_or_cog)
        except Exception as e:
            self.logger.error(f"Error in help command: {e}")
            await ctx.reply("❌ An error occurred while generating help. Please try again.")

    async def _send_help(self, ctx, command_or_cog: str = None):
        """Main help logic"""
        if command_or_cog and command_or_cog.lower().startswith('search '):
            # Handle search
            query = command_or_cog[7:].strip()  # Remove 'search ' prefix
            if not query:
                await ctx.reply("❌ Please provide a search query. Example: `.help search fish`")
                return
            
            results = self.utils.search_commands(query, ctx.author.id)
            if not results:
                await ctx.reply(f"❌ No commands found matching '{query}'")
                return
            
            embed = self.formatter.create_search_results_embed(query, results)
            await ctx.reply(embed=embed)
            return

        if command_or_cog:
            # Try to find specific command or cog
            command = self.bot.get_command(command_or_cog.lower())
            if command:
                embed = self.formatter.create_command_embed(command, ctx.prefix)
                await ctx.reply(embed=embed)
                return
            
            # Try to find cog
            cog = self.bot.get_cog(command_or_cog)
            if not cog:
                # Try case-insensitive search
                for cog_name, cog_obj in self.bot.cogs.items():
                    if cog_name.lower() == command_or_cog.lower():
                        cog = cog_obj
                        break
            
            if cog and self.utils.should_show_cog(cog.__class__.__name__, ctx.author.id):
                pages, cog_page_map = self.formatter.create_cog_pages(cog)
                paginator = HelpPaginator(pages, ctx.author, cog_page_map)
                await paginator.start(ctx)
                return
            
            await ctx.reply(f"❌ No command or category found matching '{command_or_cog}'")
            return

        # Show main help menu
        pages, cog_page_map = self.formatter.create_all_pages()
        paginator = HelpPaginator(pages, ctx.author, cog_page_map)
        await paginator.start(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle help command errors only for this cog's commands"""
        # Only handle errors for commands that belong to this cog
        if ctx.command and ctx.command.cog == self:
            await self.handle_error(ctx, error)
            # Don't let the error propagate to other handlers
            return
        # Let other handlers process errors for other cogs

def setup(bot):
    """Setup function for the Help cog"""
    bot.add_cog(Help(bot))
