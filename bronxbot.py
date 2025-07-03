#!/usr/bin/env python3
"""
BronxBot - Discord Bot with Integrated Live Event Tracking
Modern console interface with real-time monitoring and configurable cog loading
"""

import asyncio
import nextcord
from nextcord.ext import commands, tasks
import json
import logging
import os
import sys
import time
import platform
import aiohttp
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Project Utilities
from utils.command_tracker import usage_tracker
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from utils.scalability import initialize_scalability

# Load environment variables
load_dotenv()

def load_config():
    """Load configuration"""
    token = os.getenv('DISCORD_TOKEN')
    if token:
        return {'TOKEN': token, 'DEV': os.getenv('DEV', 'false').lower() == 'true'}
    
    with open("data/config.json", "r") as f:
        config = json.load(f)
        return config

# ANSI color codes for modern console styling
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BRIGHT_RED = '\033[101m'
    BRIGHT_GREEN = '\033[102m'
    BRIGHT_YELLOW = '\033[103m'
    BRIGHT_BLUE = '\033[104m'
    BRIGHT_CYAN = '\033[106m'

def clear_screen():
    """Clear the console screen"""
    try:
        # Only clear if we have a TTY (interactive terminal)
        if sys.stdout.isatty():
            os.system('clear' if os.name == 'posix' else 'cls')
    except:
        # Silently fail if no terminal is available (e.g., systemd service)
        pass

def get_terminal_width():
    """Get terminal width for centering"""
    try:
        return os.get_terminal_size().columns
    except:
        return 80

def center_text(text, width=None, fill_char=' '):
    """Center text in terminal"""
    if width is None:
        width = get_terminal_width()
    return text.center(width, fill_char)

def print_modern_header():
    """Print modern styled header with system info"""
    width = get_terminal_width()
    
    # Top border with modern design
    print(Colors.BRIGHT_CYAN + '╔' + '═' * (width-2) + '╗' + Colors.RESET)
    print(Colors.CYAN + '║' + ' ' * (width-2) + '║' + Colors.RESET)
    
    # Main title
    title = "B R O N X"
    print(Colors.CYAN + '║' + Colors.BOLD + Colors.WHITE + center_text(title, width-2) + Colors.RESET + Colors.CYAN + '║' + Colors.RESET)
    
    # Subtitle with versions
    subtitle = f"Discord Bot v2.0 • Python {platform.python_version()} • nextcord {nextcord.__version__}"
    print(Colors.CYAN + '║' + Colors.DIM + Colors.WHITE + center_text(subtitle, width-2) + Colors.RESET + Colors.CYAN + '║' + Colors.RESET)
    
    print(Colors.CYAN + '║' + ' ' * (width-2) + '║' + Colors.RESET)
    
    # Support link (clickable in most terminals)
    support_text = f"{Colors.UNDERLINE}https://discord.gg/jvyYWkj3ts{Colors.RESET}"
    support_label = "Support Server: "
    full_support = support_label + support_text
    print(Colors.CYAN + '║' + Colors.BLUE + center_text(full_support, width-2) + Colors.RESET + Colors.CYAN + '║' + Colors.RESET)
    
    print(Colors.CYAN + '║' + ' ' * (width-2) + '║' + Colors.RESET)
    print(Colors.BRIGHT_CYAN + '╚' + '═' * (width-2) + '╝' + Colors.RESET)
    print()

def format_event(event_name, details="", color=Colors.GREEN):
    """Format an event message with timestamp and centering"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if details:
        message = f"[{timestamp}] {event_name}: {details}"
    else:
        message = f"[{timestamp}] {event_name}"
    
    return color + center_text(message) + Colors.RESET

def format_cog_status(loaded, total):
    """Format cog loading status with colors"""
    if loaded == total:
        return f"{Colors.BRIGHT_GREEN}{loaded}{Colors.RESET}/{Colors.WHITE}{total}{Colors.RESET}"
    elif loaded == 0:
        return f"{Colors.RED}{loaded}{Colors.RESET}/{Colors.WHITE}{total}{Colors.RESET}"
    else:
        return f"{Colors.YELLOW}{loaded}{Colors.RESET}/{Colors.WHITE}{total}{Colors.RESET}"

def format_startup_info(key, value, color=Colors.CYAN):
    """Format startup information"""
    return f"{color}{center_text(f'{key}: {value}')}{Colors.RESET}"

# Main guild IDs
MAIN_GUILD_IDS = [
    1259717095382319215,  # Main server
    1299747094449623111,  # South Bronx
    1142088882222022786   # Long Island
]

class BronxBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Boot metrics
        self.boot_metrics = {
            'start_time': time.time(),
            'config_load_time': 0,
            'cog_load_times': {},
            'total_cog_load_time': 0,
            'ready_time': 0
        }
        
        # Cog tracking
        self.total_cogs = 61  # Total available cogs
        self.loaded_cogs = 0
        self.failed_cogs = []
        self.events_tracked = 0
        self._events_since_stats = 0  # Track events since last stats update
        
        # Setup tracking
        self._setup_completed = False
        
        # Main guild IDs for the bot
        self.MAIN_GUILD_IDS = MAIN_GUILD_IDS
        
        # Load console settings
        self.console_settings = self.load_console_settings()
        
        # Session management
        self.session = None
        
        print(format_event("INIT", "Bot instance created", Colors.GREEN))
    
    def _track_event(self):
        """Helper method to track events"""
        try:
            self.events_tracked += 1
            self._events_since_stats += 1
        except Exception:
            # Avoid recursion by not calling _track_event in error handling
            pass
    
    def load_console_settings(self):
        """Load console display settings from config"""
        try:
            with open('data/config.json', 'r') as f:
                config = json.load(f)
            
            return config.get('console_settings', {
                'show_cog_loading': True,
                'show_message_events': True,
                'show_connection_events': True,
                'show_ready_events': True,
                'quiet_mode': False
            })
        except Exception:
            return {
                'show_cog_loading': True,
                'show_message_events': True,
                'show_connection_events': True,
                'show_ready_events': True,
                'quiet_mode': False
            }
    
    async def setup_hook(self):
        """Enhanced setup hook with integrated cog loading system"""
        print(format_event("SETUP", "Starting bot initialization", Colors.CYAN))
        
        # Load cog configuration first
        self.load_cog_configuration()
        
        # Initialize aiohttp session
        self.session = aiohttp.ClientSession()
        print(format_event("SETUP", "HTTP session initialized", Colors.GREEN))
        
        # Initialize scalability features (optional, don't fail if missing)
        try:
            await initialize_scalability(self)
            print(format_event("SETUP", "Scalability features initialized", Colors.GREEN))
        except Exception as e:
            print(format_event("SETUP", f"Scalability init skipped: {e}", Colors.YELLOW))
        
        # Load cogs with integrated system
        await self.load_cogs_integrated()
        
        # Mark setup as completed
        self._setup_completed = True
        
        print(format_event("SETUP", "Bot initialization completed", Colors.BRIGHT_GREEN))

    async def load_cogs_integrated(self):
        """Integrated cog loading system - no external dependencies"""
        print(format_event("COG_LOAD", "Starting cog loading...", Colors.BLUE))
        
        # Define cog categories with priority loading
        cog_categories = {
            'essential': [
                "cogs.events",
                "cogs.Error", 
                "cogs.Utility",
                "cogs.help.help_cog"
            ],
            'core': [
                "cogs.Stats",
                "cogs.ModMail", 
                "cogs.Reminders",
                "cogs.Status",
                "cogs.ServerSettings",
                "cogs.Moderation"
            ],
            'admin': [
                "cogs.admin.Admin",
                "cogs.admin.SlashCommands"
            ],
            'bronx': [
                "cogs.bronx.AI",
                "cogs.bronx.VoteBans", 
                "cogs.bronx.Welcoming"
            ],
            'economy': [
                "cogs.economy.Economy",
                "cogs.economy.Shop",
                "cogs.economy.Work",
                "cogs.economy.Gambling",
                "cogs.economy.Giveaway",
                "cogs.economy.Bazaar",
                "cogs.economy.Trading"
            ],
            'fun': [
                "cogs.fun.Fun",
                "cogs.fun.Text",
                "cogs.fun.GambleOff"
            ],
            'misc': [
                "cogs.misc.Starboard"
            ]
        }
        
        # Load configuration for which categories to load
        load_config = getattr(self, 'cog_load_config', {
            'categories': ['essential', 'core'],
            'disabled_cogs': [],
            'essential_only': False
        })
        
        # Determine which cogs to load
        if load_config.get('essential_only', False):
            categories_to_load = ['essential']
            print(format_event("COG_LOAD", "Essential mode enabled", Colors.YELLOW))
        else:
            categories_to_load = load_config.get('categories', ['essential', 'core'])
        
        # Build final cog list
        cogs_to_load = []
        for category in categories_to_load:
            if category in cog_categories:
                cogs_to_load.extend(cog_categories[category])
        
        # Remove disabled cogs
        disabled_cogs = load_config.get('disabled_cogs', [])
        if disabled_cogs:
            cogs_to_load = [cog for cog in cogs_to_load if cog not in disabled_cogs]
            print(format_event("COG_LOAD", f"Disabled {len(disabled_cogs)} cogs", Colors.YELLOW))
        
        self.total_cogs = len(cogs_to_load)
        self.loaded_cogs = 0
        self.failed_cogs = []
        
        # Load cogs with progress tracking
        for i, cog_name in enumerate(cogs_to_load, 1):
            success = await self.load_single_cog_integrated(cog_name)
            
            # Show progress for essential cogs or every 5 cogs
            if not self.console_settings.get('quiet_mode', False):
                if cog_name in cog_categories.get('essential', []) or i % 5 == 0 or i == len(cogs_to_load):
                    cog_status = format_cog_status(self.loaded_cogs, self.total_cogs)
                    print(format_event("COG_LOAD", f"Progress: {cog_status} [{i}/{len(cogs_to_load)}]", Colors.CYAN))
            
            await asyncio.sleep(0.01)  # Small delay
        
        # Display final results
        if not self.console_settings.get('quiet_mode', False):
            success_rate = (self.loaded_cogs / self.total_cogs) * 100 if self.total_cogs > 0 else 0
            status_color = Colors.BRIGHT_GREEN if success_rate >= 90 else Colors.YELLOW if success_rate >= 70 else Colors.RED
            
            cog_status = format_cog_status(self.loaded_cogs, self.total_cogs)
            print(format_event("COG_LOAD", f"Completed: {cog_status} ({success_rate:.1f}%)", status_color))
            
            if self.failed_cogs:
                failed_names = [c.split('.')[-1] for c in self.failed_cogs[:5]]
                more_text = f" (+{len(self.failed_cogs)-5} more)" if len(self.failed_cogs) > 5 else ""
                print(format_event("COG_LOAD", f"Failed: {', '.join(failed_names)}{more_text}", Colors.RED))

    async def load_single_cog_integrated(self, cog_name):
        """Load a single cog with integrated error handling"""
        try:
            # Check if already loaded
            if cog_name in self.extensions:
                self.loaded_cogs += 1
                return True
            
            # Load the cog
            await self.load_extension(cog_name)
            
            # Verify it was actually loaded
            if cog_name in self.extensions:
                self.loaded_cogs += 1
                
                # Only show individual cog loading if not in quiet mode and for essential cogs
                if (not self.console_settings.get('quiet_mode', False) and 
                    self.console_settings.get('show_cog_loading', True)):
                    short_name = cog_name.split('.')[-1]
                    print(format_event("COG_LOAD", f"{short_name} loaded", Colors.GREEN))
                return True
            else:
                # Extension load succeeded but not registered (shouldn't happen)
                self.failed_cogs.append(cog_name)
                return False
            
        except Exception as e:
            # Check if the cog actually loaded despite the exception
            if cog_name in self.extensions:
                self.loaded_cogs += 1
                if (not self.console_settings.get('quiet_mode', False) and 
                    self.console_settings.get('show_cog_loading', True)):
                    short_name = cog_name.split('.')[-1]
                    print(format_event("COG_LOAD", f"{short_name} loaded (with warnings)", Colors.YELLOW))
                return True
            else:
                self.failed_cogs.append(cog_name)
                short_name = cog_name.split('.')[-1]
                error_msg = str(e)[:50] + "..." if len(str(e)) > 50 else str(e)
                # Always show errors, even in quiet mode, but only for critical failures
                if "ModuleNotFoundError" in str(type(e)) or "ImportError" in str(type(e)):
                    print(format_event("COG_LOAD", f"{short_name} failed: {error_msg}", Colors.RED))
                return False
    
    # Enhanced event tracking methods
    async def on_connect(self):
        self._track_event()
        if self.console_settings.get('show_connection_events', True) and not self.console_settings.get('quiet_mode', False):
            print(format_event("CONNECT", "Connected to Discord Gateway", Colors.BRIGHT_GREEN))
    
    async def on_disconnect(self):
        self._track_event()
        if self.console_settings.get('show_connection_events', True) and not self.console_settings.get('quiet_mode', False):
            print(format_event("DISCONNECT", "Disconnected from Discord", Colors.RED))
    
    async def on_resumed(self):
        self._track_event()
        if self.console_settings.get('show_connection_events', True) and not self.console_settings.get('quiet_mode', False):
            print(format_event("RESUMED", "Connection resumed", Colors.YELLOW))
    
    async def on_ready(self):
        self._track_event()
        self.boot_metrics['ready_time'] = time.time()
        
        # Check if cogs have been loaded, if not, trigger setup manually
        if not hasattr(self, '_setup_completed') or not self._setup_completed:
            print(format_event("SETUP", "Manual setup triggered in on_ready", Colors.YELLOW))
            try:
                await self.setup_hook()
                self._setup_completed = True
            except Exception as e:
                print(format_event("SETUP", f"Setup hook failed: {e}", Colors.RED))
        
        startup_time = self.boot_metrics['ready_time'] - self.boot_metrics['start_time']
        
        print()
        print(Colors.BRIGHT_GREEN + '╔' + '═' * (get_terminal_width()-2) + '╗' + Colors.RESET)
        print(Colors.GREEN + '║' + center_text("BOT READY", get_terminal_width()-2) + '║' + Colors.RESET)
        print(Colors.BRIGHT_GREEN + '╚' + '═' * (get_terminal_width()-2) + '╝' + Colors.RESET)
        print()
        
        print(format_startup_info("Bot Name", self.user.name, Colors.BRIGHT_CYAN))
        print(format_startup_info("Bot ID", self.user.id, Colors.CYAN))
        print(format_startup_info("Guilds Connected", len(self.guilds), Colors.GREEN))
        print(format_startup_info("Users Accessible", len(self.users), Colors.GREEN))
        print(format_startup_info("Startup Time", f"{startup_time:.2f}s", Colors.YELLOW))
        print(format_startup_info("Cogs Loaded", format_cog_status(self.loaded_cogs, self.total_cogs), Colors.WHITE))
        print(format_startup_info("Latency", f"{round(self.latency * 1000)}ms", Colors.BLUE))
        
        print()
        print(Colors.GRAY + center_text("Live event tracking enabled - Press Ctrl+C to stop") + Colors.RESET)
        print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
        
        # Set presence
        activity = nextcord.Activity(
            type=nextcord.ActivityType.watching,
            name=f"{len(self.guilds)} servers | /help"
        )
        await self.change_presence(activity=activity)
        
        # Start background tasks
        if not self.event_statistics.is_running():
            self.event_statistics.start()
    
    # Message Events (condensed for less spam)
    async def on_message(self, message):
        self._track_event()
        if message.author.bot:
            return
        
        # Only show messages if enabled and in main guilds to reduce spam
        if (self.console_settings.get('show_message_events', True) and 
            not self.console_settings.get('quiet_mode', False) and
            message.guild and message.guild.id in MAIN_GUILD_IDS):
            author = message.author.display_name[:15]
            content = message.content[:30] + "..." if len(message.content) > 30 else message.content
            print(format_event("MESSAGE", f"{author}: {content}", Colors.BLUE))
        
        await self.process_commands(message)
    
    async def on_message_edit(self, before, after):
        self._track_event()
        if (before.author.bot or before.guild.id not in MAIN_GUILD_IDS or
            not self.console_settings.get('show_message_events', True) or
            self.console_settings.get('quiet_mode', False)):
            return
        author = before.author.display_name[:15]
        print(format_event("EDIT", f"{author} edited a message", Colors.CYAN))
    
    async def on_message_delete(self, message):
        self._track_event()
        if (message.author.bot or message.guild.id not in MAIN_GUILD_IDS or
            not self.console_settings.get('show_message_events', True) or
            self.console_settings.get('quiet_mode', False)):
            return
        author = message.author.display_name[:15]
        print(format_event("DELETE", f"{author}'s message deleted", Colors.RED))
    
    # Guild Events
    async def on_guild_join(self, guild):
        self._track_event()
        print(format_event("GUILD_JOIN", f"Joined: {guild.name} ({guild.member_count} members)", Colors.BRIGHT_GREEN))
    
    async def on_guild_remove(self, guild):
        self._track_event()
        print(format_event("GUILD_LEAVE", f"Left: {guild.name}", Colors.RED))
    
    # Command Events
    async def on_command(self, ctx):
        """Log command execution to console"""
        self._track_event()
        cmd_name = ctx.command.name if ctx.command else "unknown"
        print(format_event("COMMAND", f"{ctx.author.display_name}: {cmd_name}", Colors.BRIGHT_BLUE))
    
    async def on_command_error(self, ctx, error):
        """Handle command errors safely - fallback handler"""
        try:
            self._track_event()
            cmd_name = ctx.command.name if ctx.command else "unknown"
            error_type = type(error).__name__
            
            # Handle specific error types - this is the global fallback
            if isinstance(error, commands.CommandNotFound):
                # Completely disable command not found logging to reduce spam
                return
            elif isinstance(error, commands.MissingRequiredArgument):
                print(format_event("CMD_ERROR", f"{cmd_name}: Missing argument", Colors.RED))
            elif isinstance(error, commands.BadArgument):
                print(format_event("CMD_ERROR", f"{cmd_name}: Bad argument", Colors.RED))
            else:
                # Only log if it's not already handled by Error cog
                if not self.get_cog('Error'):
                    print(format_event("CMD_ERROR", f"{cmd_name}: {error_type}", Colors.RED))
                
        except Exception as e:
            # Prevent recursive error loops
            print(format_event("ERROR", f"Error in error handler: {e}", Colors.BRIGHT_RED))
    
    async def on_application_command(self, interaction):
        self._track_event()
        cmd_name = interaction.data.get('name', 'unknown')
        print(format_event("SLASH", f"{interaction.user.display_name}: /{cmd_name}", Colors.BRIGHT_BLUE))
    
    # Voice Events (only for main guilds)
    async def on_voice_state_update(self, member, before, after):
        if member.guild.id not in MAIN_GUILD_IDS:
            return
        
        self._track_event()
        if before.channel != after.channel:
            if before.channel is None:
                print(format_event("VOICE_JOIN", f"{member.display_name} joined {after.channel.name}", Colors.GREEN))
            elif after.channel is None:
                print(format_event("VOICE_LEAVE", f"{member.display_name} left {before.channel.name}", Colors.YELLOW))
            else:
                print(format_event("VOICE_MOVE", f"{member.display_name}: {before.channel.name} → {after.channel.name}", Colors.CYAN))
    
    # Member Events (only for main guilds) - console logging disabled to reduce spam
    async def on_member_join(self, member):
        if member.guild.id not in MAIN_GUILD_IDS:
            return
        
        self._track_event()
        # Commented out to reduce console spam
        # print(format_event("MEMBER_JOIN", f"{member.display_name} joined {member.guild.name}", Colors.GREEN))
    
    async def on_member_remove(self, member):
        if member.guild.id not in MAIN_GUILD_IDS:
            return
        
        self._track_event()
        # Commented out to reduce console spam
        # print(format_event("MEMBER_LEAVE", f"{member.display_name} left {member.guild.name}", Colors.YELLOW))
    
    # Error handling
    async def on_error(self, event, *args, **kwargs):
        try:
            self._track_event()
        except Exception:
            # Avoid recursion if _track_event fails
            pass
        print(format_event("ERROR", f"Error in {event}", Colors.BRIGHT_RED))
    
    @tasks.loop(seconds=30)
    async def event_statistics(self):
        """Display periodic statistics with smart positioning"""
        import sys
        
        # If there's high activity, update more frequently
        if hasattr(self, '_events_since_stats') and self._events_since_stats > 10:
            # High activity - change loop interval temporarily
            self.event_statistics.change_interval(seconds=10)
        else:
            # Normal activity - use standard interval
            self.event_statistics.change_interval(seconds=30)
        
        # Check if terminal supports cursor movement
        try:
            # Only attempt terminal operations if we have a TTY
            if not sys.stdout.isatty():
                # No terminal available, just print normally
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
                stats_text = f"Events: {self.events_tracked} | Guilds: {len(self.guilds)} | Users: {len(self.users)} | Latency: {round(self.latency * 1000)}ms"
                print(Colors.CYAN + center_text(stats_text) + Colors.RESET)
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
                self._events_since_stats = 0
                self._stats_printed = True
                return
                
            # Get current terminal height
            import os
            rows, cols = os.popen('stty size', 'r').read().split()
            terminal_height = int(rows)
            
            # If we've printed stats before and there have been recent events,
            # check if we should update in place or create new stats
            recent_events = getattr(self, '_events_since_stats', 0)
            
            if hasattr(self, '_stats_printed') and recent_events < 5:
                # Try to update in place if not too many events happened
                sys.stdout.write('\033[s')  # Save cursor position
                sys.stdout.write(f'\033[{terminal_height-2};1H')  # Move to bottom
                sys.stdout.write('\033[0K')  # Clear line
                sys.stdout.write('\033[1A\033[0K')  # Move up and clear
                sys.stdout.write('\033[1A\033[0K')  # Move up and clear again
                
                # Print stats at bottom
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
                stats_text = f"Events: {self.events_tracked} | Guilds: {len(self.guilds)} | Users: {len(self.users)} | Latency: {round(self.latency * 1000)}ms"
                print(Colors.CYAN + center_text(stats_text) + Colors.RESET)
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
                
                sys.stdout.write('\033[u')  # Restore cursor position
            else:
                # Too many events or first time - just print normally
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
                stats_text = f"Events: {self.events_tracked} | Guilds: {len(self.guilds)} | Users: {len(self.users)} | Latency: {round(self.latency * 1000)}ms"
                print(Colors.CYAN + center_text(stats_text) + Colors.RESET)
                print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
            
            # Reset event counter and mark stats as printed
            self._events_since_stats = 0
            self._stats_printed = True
            sys.stdout.flush()
            
        except Exception:
            # Fallback to simple stats if terminal operations fail
            print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
            stats_text = f"Events: {self.events_tracked} | Guilds: {len(self.guilds)} | Users: {len(self.users)} | Latency: {round(self.latency * 1000)}ms"
            print(Colors.CYAN + center_text(stats_text) + Colors.RESET)
            print(Colors.BRIGHT_CYAN + '─' * get_terminal_width() + Colors.RESET)
            self._stats_printed = True
    
    async def close(self):
        """Clean shutdown"""
        print(format_event("SHUTDOWN", "Bot shutdown initiated", Colors.YELLOW))
        
        if self.session:
            await self.session.close()
            print(format_event("SHUTDOWN", "HTTP session closed", Colors.CYAN))
        
        await super().close()
        print(format_event("SHUTDOWN", "Bot shutdown complete", Colors.GREEN))
    
    # Cog management methods
    def set_cog_config(self, **config):
        """Configure cog loading behavior"""
        if not hasattr(self, 'cog_load_config'):
            self.cog_load_config = {
                'categories': ['essential', 'core', 'admin', 'bronx', 'economy', 'fun', 'misc'],
                'disabled_cogs': [],
                'essential_only': False
            }
        
        self.cog_load_config.update(config)
        
        if not self.console_settings.get('quiet_mode', False):
            print(format_event("CONFIG", "Cog configuration updated", Colors.CYAN))
    
    def enable_essential_only(self):
        """Enable essential-only mode for minimal functionality"""
        self.set_cog_config(essential_only=True)
        print(format_event("CONFIG", "Essential-only mode enabled", Colors.YELLOW))
    
    def disable_cogs(self, cog_names):
        """Disable specific cogs from loading"""
        if not hasattr(self, 'cog_load_config'):
            self.cog_load_config = {'disabled_cogs': []}
        
        disabled = set(self.cog_load_config.get('disabled_cogs', []))
        disabled.update(cog_names)
        self.cog_load_config['disabled_cogs'] = list(disabled)
        
        print(format_event("CONFIG", f"Disabled {len(cog_names)} cogs", Colors.YELLOW))
    
    def enable_categories(self, categories):
        """Enable specific cog categories"""
        self.set_cog_config(categories=categories)
        print(format_event("CONFIG", f"Enabled categories: {', '.join(categories)}", Colors.GREEN))
    
    async def reload_cog_safe(self, cog_name):
        """Safely reload a cog with error handling"""
        try:
            await self.reload_extension(cog_name)
            short_name = cog_name.split('.')[-1]
            print(format_event("RELOAD", f"{short_name} reloaded successfully", Colors.GREEN))
            return True
        except Exception as e:
            short_name = cog_name.split('.')[-1]
            error_msg = str(e)[:50] + "..." if len(str(e)) > 50 else str(e)
            print(format_event("RELOAD", f"{short_name} reload failed: {error_msg}", Colors.RED))
            return False

    def load_cog_configuration(self):
        """Load cog configuration from file"""
        try:
            config_path = Path("data/cog_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                
                # Map the file config to our internal format
                categories_to_load = []
                for category, enabled in config_data.get('categories', {}).items():
                    if enabled:
                        categories_to_load.append(category)
                
                self.cog_load_config = {
                    'categories': categories_to_load,
                    'disabled_cogs': config_data.get('disabled_cogs', []),
                    'essential_only': config_data.get('load_strategy') == 'essential'
                }
                
                print(format_event("CONFIG", f"Loaded config: {len(categories_to_load)} categories enabled", Colors.GREEN))
            else:
                # Use defaults
                self.cog_load_config = {
                    'categories': ['essential', 'core', 'admin', 'bronx', 'economy', 'fun', 'misc'],
                    'disabled_cogs': [],
                    'essential_only': False
                }
                print(format_event("CONFIG", "Using default cog configuration", Colors.YELLOW))
                
        except Exception as e:
            print(format_event("CONFIG", f"Config load failed, using defaults: {e}", Colors.RED))
            self.cog_load_config = {
                'categories': ['essential', 'core'],  # Safe fallback
                'disabled_cogs': [],
                'essential_only': False
            }
    
    async def send_realtime_command_update(self, command_name: str, user_id: int, guild_id: int = None, execution_time: float = 0.0, error: bool = False):
        """Send realtime command update - stub method for events cog compatibility"""
        try:
            # Try to delegate to stats cog if available
            stats_cog = self.get_cog('Stats')
            if stats_cog and hasattr(stats_cog, 'send_realtime_command_update'):
                await stats_cog.send_realtime_command_update(command_name, user_id, guild_id, execution_time, error)
        except Exception as e:
            # Silently fail - this is not critical functionality
            pass

def parse_arguments():
    """Parse command line arguments for bot configuration"""
    parser = argparse.ArgumentParser(
        description='BronxBot - Discord Bot with Live Event Tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bronxbot.py                     # Run with all cogs (default)
  python bronxbot.py --essential-only    # Run with essential cogs only
  python bronxbot.py --disable economy   # Run without economy cogs
  python bronxbot.py --disable fun misc  # Run without fun and misc cogs
  python bronxbot.py --enable-only core admin  # Run with only core and admin cogs
        """
    )
    
    parser.add_argument(
        '--essential-only',
        action='store_true',
        help='Load only essential cogs (Error, Utility, Events)'
    )
    
    parser.add_argument(
        '--disable',
        nargs='*',
        choices=['core', 'admin', 'bronx', 'economy', 'fun', 'misc'],
        help='Disable specific cog categories'
    )
    
    parser.add_argument(
        '--enable-only',
        nargs='*',
        choices=['essential', 'core', 'admin', 'bronx', 'economy', 'fun', 'misc'],
        help='Enable only specific cog categories (essential is always included)'
    )
    
    parser.add_argument(
        '--disable-cogs',
        nargs='*',
        help='Disable specific cogs by name (e.g., Economy, Shop, Gambling)'
    )
    
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode'
    )
    
    parser.add_argument(
        '--list-cogs',
        action='store_true',
        help='List all available cogs and categories, then exit'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Quiet mode - minimal console output'
    )
    
    parser.add_argument(
        '--no-cog-progress',
        action='store_true',
        help='Disable individual cog loading progress display'
    )
    
    parser.add_argument(
        '--no-messages',
        action='store_true',
        help='Disable message event tracking display'
    )
    
    parser.add_argument(
        '--no-connections',
        action='store_true',
        help='Disable connection event display'
    )
    
    return parser.parse_args()

def apply_cli_config(config, args):
    """Apply command line arguments to configuration"""
    if not config.get('cog_settings'):
        config['cog_settings'] = {
            'load_all': True,
            'enabled_categories': {
                'essential': True,
                'core': True,
                'admin': True,
                'bronx': True,
                'economy': True,
                'fun': True,
                'misc': True
            },
            'disabled_cogs': [],
            'essential_only': False
        }
    
    cog_settings = config['cog_settings']
    
    # Apply essential-only mode
    if args.essential_only:
        cog_settings['essential_only'] = True
        cog_settings['load_all'] = False
        print(format_event("CLI_CONFIG", "Essential-only mode enabled via CLI", Colors.YELLOW))
    
    # Apply category disabling
    if args.disable:
        cog_settings['load_all'] = False
        for category in args.disable:
            cog_settings['enabled_categories'][category] = False
        disabled_list = ', '.join(args.disable)
        print(format_event("CLI_CONFIG", f"Disabled categories: {disabled_list}", Colors.YELLOW))
    
    # Apply enable-only mode
    if args.enable_only:
        cog_settings['load_all'] = False
        # Disable all categories first
        for category in cog_settings['enabled_categories']:
            cog_settings['enabled_categories'][category] = False
        # Enable essential and specified categories
        cog_settings['enabled_categories']['essential'] = True
        for category in args.enable_only:
            cog_settings['enabled_categories'][category] = True
        enabled_list = ', '.join(['essential'] + args.enable_only)
        print(format_event("CLI_CONFIG", f"Enabled categories only: {enabled_list}", Colors.CYAN))
    
    # Apply individual cog disabling
    if args.disable_cogs:
        disabled_cogs = []
        for cog_name in args.disable_cogs:
            # Convert to full module path if needed
            if '.' not in cog_name:
                # Try to find the cog in various categories
                possible_paths = [
                    f"cogs.{cog_name}",
                    f"cogs.admin.{cog_name}",
                    f"cogs.bronx.{cog_name}",
                    f"cogs.economy.{cog_name}",
                    f"cogs.fun.{cog_name}",
                    f"cogs.misc.{cog_name}"
                ]
                disabled_cogs.extend(possible_paths)
            else:
                disabled_cogs.append(cog_name)
        
        cog_settings['disabled_cogs'].extend(disabled_cogs)
        disabled_list = ', '.join(args.disable_cogs)
        print(format_event("CLI_CONFIG", f"Disabled individual cogs: {disabled_list}", Colors.YELLOW))
    
    # Apply dev mode
    if args.dev:
        config['dev'] = True
        print(format_event("CLI_CONFIG", "Development mode enabled via CLI", Colors.YELLOW))
    
    # Apply console settings
    if not config.get('console_settings'):
        config['console_settings'] = {
            'show_cog_loading': True,
            'show_message_events': True,
            'show_connection_events': True,
            'show_ready_events': True,
            'quiet_mode': False
        }
    
    console_settings = config['console_settings']
    
    if args.quiet:
        console_settings['quiet_mode'] = True
        print(format_event("CLI_CONFIG", "Quiet mode enabled via CLI", Colors.YELLOW))
    
    if args.no_cog_progress:
        console_settings['show_cog_loading'] = False
        print(format_event("CLI_CONFIG", "Cog loading progress disabled via CLI", Colors.YELLOW))
    
    if args.no_messages:
        console_settings['show_message_events'] = False
        print(format_event("CLI_CONFIG", "Message event tracking disabled via CLI", Colors.YELLOW))
    
    if args.no_connections:
        console_settings['show_connection_events'] = False
        print(format_event("CLI_CONFIG", "Connection event tracking disabled via CLI", Colors.YELLOW))
    
    return config

def list_available_cogs():
    """List all available cogs and categories"""
    print()
    print(Colors.BRIGHT_CYAN + '╔' + '═' * (get_terminal_width()-2) + '╗' + Colors.RESET)
    print(Colors.CYAN + '║' + center_text("AVAILABLE COGS", get_terminal_width()-2) + '║' + Colors.RESET)
    print(Colors.BRIGHT_CYAN + '╚' + '═' * (get_terminal_width()-2) + '╝' + Colors.RESET)
    print()
    
    categories = {
        'Essential': ["cogs.events", "cogs.Error", "cogs.Utility"],
        'Core': ["cogs.Stats", "cogs.ModMail", "cogs.Reminders", "cogs.Status", "cogs.ServerSettings"],
        'Admin': ["cogs.admin.Admin", "cogs.admin.Performance", "cogs.admin.SlashCommands"],
        'Bronx': ["cogs.bronx.AI", "cogs.bronx.VoteBans", "cogs.bronx.Welcoming"],
        'Economy': ["cogs.economy.Economy", "cogs.economy.Shop", "cogs.economy.Work", 
                   "cogs.economy.Gambling", "cogs.economy.Giveaway", "cogs.economy.Bazaar", "cogs.economy.Trading"],
        'Fun': ["cogs.fun.Fun", "cogs.fun.Text", "cogs.fun.GambleOff"],
        'Misc': ["cogs.misc.Starboard", "cogs.Moderation"]
    }
    
    for category, cogs in categories.items():
        print(f"{Colors.BRIGHT_GREEN}{category}:{Colors.RESET}")
        for cog in cogs:
            cog_name = cog.split('.')[-1]
            print(f"  {Colors.CYAN}• {cog_name}{Colors.RESET} ({cog})")
        print()
    
    print(f"{Colors.YELLOW}Total: {sum(len(cogs) for cogs in categories.values())} cogs{Colors.RESET}")
    print()

def main():
    """Main function with enhanced startup and CLI support"""
    args = parse_arguments()
    
    # Handle list-cogs command
    if args.list_cogs:
        clear_screen()
        print_modern_header()
        list_available_cogs()
        return
    
    clear_screen()
    print_modern_header()
    
    print(format_event("STARTUP", "Initializing BronxBot...", Colors.CYAN))
    
    # Load configuration
    try:
        config = load_config()
        print(format_event("CONFIG", "Configuration loaded", Colors.GREEN))
    except Exception as e:
        print(format_event("CONFIG", f"Failed to load config: {e}", Colors.RED))
        sys.exit(1)
    
    # Apply CLI configuration
    config = apply_cli_config(config, args)
    
    # Check TOS acceptance (simplified for now)
    try:
        # TOS check disabled for now - was causing async issues
        print(format_event("TOS", "Terms of Service check skipped", Colors.YELLOW))
    except Exception as e:
        print(format_event("TOS", f"TOS check failed: {e}", Colors.YELLOW))
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/bronxbot_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce Discord logging noise
    logging.getLogger('nextcord').setLevel(logging.WARNING)
    logging.getLogger('nextcord.gateway').setLevel(logging.WARNING)
    logging.getLogger('nextcord.client').setLevel(logging.WARNING)
    
    print(format_event("LOGGING", "Logging system configured", Colors.GREEN))
    
    # Bot setup
    intents = nextcord.Intents.all()
    intents.message_content = True
    
    dev_mode = config.get('dev', False)
    mode_text = "DEVELOPMENT" if dev_mode else "PRODUCTION"
    mode_color = Colors.YELLOW if dev_mode else Colors.GREEN
    print(format_event("MODE", f"Running in {mode_text} mode", mode_color))
    
    # Create bot instance
    bot = BronxBot(
        command_prefix='.',
        intents=intents,
        shard_count=1,
        case_insensitive=True,
        help_command=None,
        strip_after_prefix=True
    )
    
    # Get token
    token = config['DEV_TOKEN'] if dev_mode else config['TOKEN']
    
    try:
        print(format_event("STARTUP", "Connecting to Discord...", Colors.BLUE))
        bot.run(token)
    except KeyboardInterrupt:
        print()
        print(format_event("SHUTDOWN", "Shutdown requested by user (Ctrl+C)", Colors.YELLOW))
    except Exception as e:
        print(format_event("STARTUP", f"Failed to start: {e}", Colors.RED))
        sys.exit(1)
    finally:
        # Ensure bot is properly closed
        if not bot.is_closed():
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(bot.close())
                else:
                    loop.run_until_complete(bot.close())
            except Exception:
                pass  # Best effort cleanup
        
        print()
        print(Colors.BRIGHT_CYAN + '╔' + '═' * (get_terminal_width()-2) + '╗' + Colors.RESET)
        print(Colors.CYAN + '║' + center_text("BronxBot Stopped", get_terminal_width()-2) + '║' + Colors.RESET)
        print(Colors.BRIGHT_CYAN + '╚' + '═' * (get_terminal_width()-2) + '╝' + Colors.RESET)

if __name__ == "__main__":
    main()
