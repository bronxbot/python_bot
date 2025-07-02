from nextcord.ext import commands
import nextcord
import time
import logging
import traceback
import asyncio
from utils.command_tracker import usage_tracker
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from utils.scalability import initialize_scalability

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready - start background tasks"""
        print(f"🎉 Bot ready as {self.bot.user.name} ({self.bot.user.id})")
        print(f"🏠 Connected to {len(self.bot.guilds)} guilds")
        
        # Update presence
        activity = nextcord.Activity(
            type=nextcord.ActivityType.playing,
            name=f"with {len(self.bot.guilds)} servers | .help"
        )
        await self.bot.change_presence(activity=activity)
        
        print("✅ Bot fully ready and operational!")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        """Track command usage and check TOS acceptance"""
        start_time = time.time()
        ctx.command_start_time = start_time
        
        exempt_commands = [
            'tos', 'terms', 'termsofservice', 'tosinfo', 'tosdetails',
            'help', 'h', 'commands',
            'support', 'invite',
            'ping', 'pong',
            'balance', 'bal', 'cash', 'bb'
        ]
        
        if ctx.command and ctx.command.name not in exempt_commands:
            accepted = await check_tos_acceptance(ctx.author.id)
            if not accepted:
                await prompt_tos_acceptance(ctx)
                raise commands.CommandError("TOS not accepted")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Track successful command completion"""
        execution_time = time.time() - getattr(ctx, 'command_start_time', time.time())
        usage_tracker.track_command(ctx, ctx.command.qualified_name, execution_time, error=False)
        
        from bronxbot import stats_tracker
        if stats_tracker:
            try:
                await stats_tracker.send_command_update(ctx.command.qualified_name)
            except Exception as e:
                logging.debug(f"Error tracking command with stats tracker: {e}")
        
        await self.bot.send_realtime_command_update(
            command_name=ctx.command.qualified_name,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id if ctx.guild else None,
            execution_time=execution_time,
            error=False
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Track command errors and let Error cog handle the rest"""
        execution_time = time.time() - getattr(ctx, 'command_start_time', time.time())
        command_name = ctx.command.qualified_name if ctx.command else 'unknown'
        usage_tracker.track_command(ctx, command_name, execution_time, error=True)
        
        await self.bot.send_realtime_command_update(
            command_name=command_name,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id if ctx.guild else None,
            execution_time=execution_time,
            error=True
        )
        
        # Don't handle the actual error display - let the Error cog or main bot handle it
        # This listener is only for tracking purposes

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle messages - tracking only, not processing"""
        if message.author.bot:
            return
        # Commands are automatically processed by the AutoShardedBot base class
        # This listener is only for tracking purposes

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Handle message edits and re-process commands if edited"""
        if after.author.bot:
            return
        
        if before.content == after.content:
            return
        
        if not after.content.startswith(self.bot.command_prefix):
            return
        
        current_time = time.time()
        user_id = after.author.id
        
        if not hasattr(self.bot, 'last_edit_times'):
            self.bot.last_edit_times = {}
        
        if user_id in self.bot.last_edit_times:
            if current_time - self.bot.last_edit_times[user_id] < 2.0:
                return
        
        self.bot.last_edit_times[user_id] = current_time
        
        if after.guild and after.guild.id in self.bot.MAIN_GUILD_IDS:
            if after.channel.id in [1378156495144751147, 1260347806699491418]:
                return await after.reply("<#1314685928614264852>")
        
        # Don't re-process commands on edit - this can cause unexpected behavior
        # Users should send a new message if they want to execute a different command

def setup(bot):
    bot.add_cog(Events(bot))
