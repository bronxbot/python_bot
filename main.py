#!/usr/bin/env python3
"""
BronxBot - Advanced Discord Bot
Main entry point for the bot application
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import nextcord
from nextcord.ext import commands
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from database.database_manager import DatabaseManager
from utils.logger import setup_logger
from utils.bot_utils import get_prefix

# Load environment variables
load_dotenv()

class BronxBot(commands.Bot):
    """Main bot class with integrated systems"""
    
    def __init__(self):
        # Load settings
        self.settings = Settings()
        
        # Setup logging
        self.logger = setup_logger("BronxBot")
        
        # Initialize bot with intents
        intents = nextcord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True
        )
        
        # Initialize database manager
        self.db = DatabaseManager(self.settings.mongo_uri)
        
        # Bot statistics
        self.start_time = None
        self.commands_used = 0
        
        # Custom emoji for currency
        self.currency_emoji = "💰"  # Default currency emoji
        
    async def setup_hook_disabled(self):
        """Setup hook called when bot starts - temporarily disabled"""
        print("🔧 Setup hook started...")
        self.logger.info("Starting bot setup...")
        
        # Connect to database with timeout
        try:
            print("🗄️  Connecting to database...")
            self.logger.info("Connecting to database...")
            await asyncio.wait_for(self.db.connect(), timeout=10.0)
            print("✅ Database connected successfully")
            self.logger.info("Database connected successfully")
        except asyncio.TimeoutError:
            print("⚠️  Database connection timed out")
            self.logger.warning("Database connection timed out, will retry later")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            self.logger.error(f"Database connection failed: {e}")
        
        # Load all cogs in parallel
        print("📦 Loading cogs...")
        self.logger.info("Loading cogs...")
        await self.load_cogs()
        print("✅ Cogs loaded successfully")
        self.logger.info("Cogs loaded successfully")
        
        # Sync slash commands if in development (non-blocking)
        if self.settings.dev_mode:
            print("🔄 Syncing slash commands in background...")
            self.logger.info("Syncing slash commands in background...")
            asyncio.create_task(self.sync_commands())
        
        print("✅ Bot setup completed successfully")
        self.logger.info("Bot setup completed successfully")
    
    async def load_cogs(self):
        """Load all cogs from the cogs directory"""
        print("📋 Starting cog loading process...")
        self.logger.info("Loading cogs...")
        
        # Define cog loading order (important cogs first)
        cog_order = [
            "cogs.core.error_handler",
            "cogs.core.help",
            "cogs.economy.economy",
            "cogs.economy.shop",
            "cogs.economy.fishing",
            "cogs.economy.bazaar",
            "cogs.gambling.gambling",
            "cogs.work.work",
            "cogs.trading.trading",
            "cogs.admin.admin"
        ]
        
        # Load critical cogs first (error handler, help)
        critical_cogs = cog_order[:2]
        print(f"⚡ Loading {len(critical_cogs)} critical cogs...")
        for cog_name in critical_cogs:
            try:
                await self.load_extension(cog_name)
                print(f"  ✅ {cog_name}")
                self.logger.info(f"Loaded critical cog: {cog_name}")
            except Exception as e:
                print(f"  ❌ {cog_name}: {e}")
                self.logger.error(f"Failed to load critical cog {cog_name}: {e}")
        
        # Load remaining cogs in parallel
        remaining_cogs = cog_order[2:]
        print(f"🔄 Loading {len(remaining_cogs)} remaining cogs in parallel...")
        tasks = []
        
        for cog_name in remaining_cogs:
            task = asyncio.create_task(self.load_single_cog(cog_name))
            tasks.append(task)
        
        # Wait for all cogs to load (with timeout)
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30.0)
            except asyncio.TimeoutError:
                print("⚠️  Some cogs took too long to load, continuing anyway")
                self.logger.warning("Some cogs took too long to load, continuing anyway")
        
        print("✅ All cogs processed")
        self.logger.info("Cog loading completed")
    
    async def load_single_cog(self, cog_name: str):
        """Load a single cog with error handling"""
        try:
            await self.load_extension(cog_name)
            print(f"  ✅ {cog_name}")
            self.logger.info(f"Loaded cog: {cog_name}")
        except Exception as e:
            print(f"  ❌ {cog_name}: {e}")
            self.logger.error(f"Failed to load cog {cog_name}: {e}")
            # Don't raise exception to prevent blocking other cogs
    
    async def sync_commands(self):
        """Sync slash commands"""
        try:
            self.logger.info("Syncing slash commands...")
            synced = await asyncio.wait_for(self.tree.sync(), timeout=15.0)
            self.logger.info(f"Synced {len(synced)} slash commands")
        except asyncio.TimeoutError:
            self.logger.warning("Slash command sync timed out")
        except Exception as e:
            self.logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when bot is ready"""
        import time
        self.start_time = time.time()
        
        print(f"Bot is ready! Logged in as {self.user}")
        print(f"Connected to {len(self.guilds)} guilds")
        print(f"Watching {len(self.users)} users")
        
        self.logger.info(f"Bot is ready! Logged in as {self.user}")
        self.logger.info(f"Connected to {len(self.guilds)} guilds")
        self.logger.info(f"Watching {len(self.users)} users")
        
        # Set bot status
        activity = nextcord.Activity(
            type=nextcord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | /help"
        )
        await self.change_presence(activity=activity)
        print("Bot startup completed successfully!")
    
    async def on_command(self, ctx):
        """Called when a command is invoked"""
        self.commands_used += 1
        self.logger.info(f"Command used: {ctx.command.name} by {ctx.author} in {ctx.guild}")
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Command is on cooldown. Try again in {error.retry_after:.1f} seconds.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        else:
            self.logger.error(f"Unhandled error in command {ctx.command}: {error}")
            await ctx.send("An error occurred while processing your command.")
    
    async def close(self):
        """Cleanup when bot shuts down"""
        self.logger.info("Shutting down bot...")
        await self.db.close()
        await super().close()

async def main():
    """Main function to run the bot"""
    print("Creating bot instance...")
    bot = BronxBot()
    
    # Check if Discord token is set
    if not bot.settings.discord_token:
        print("ERROR: DISCORD_TOKEN not set in .env file")
        print("Please add your Discord bot token to the .env file")
        sys.exit(1)
    
    print("Starting bot...")
    print("Connecting to Discord...")
    try:
        await asyncio.wait_for(bot.start(bot.settings.discord_token), timeout=60.0)
    except asyncio.TimeoutError:
        print("Bot startup timed out after 60 seconds")
        print("Possible causes:")
        print("  - Invalid or expired Discord token")
        print("  - Network connectivity issues")
        print("  - Discord API is down")
        print("  - Database connection issues")
        print("\nTroubleshooting:")
        print("  1. Check if your Discord token is valid")
        print("  2. Verify your internet connection")
        print("  3. Check Discord status at https://discordstatus.com")
        print("  4. Verify your MongoDB connection string")
        sys.exit(1)
    except nextcord.LoginFailure:
        print("Discord login failed - Invalid token")
        print("Please check your DISCORD_TOKEN in the .env file")
        sys.exit(1)
    except nextcord.HTTPException as e:
        print(f"Discord HTTP error: {e}")
        print("This might be a temporary Discord API issue")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Bot stopped by user")
        await bot.close()
    except Exception as e:
        print(f"Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        await bot.close()
        sys.exit(1)

if __name__ == "__main__":
    print("Starting asyncio event loop...")
    asyncio.run(main())
