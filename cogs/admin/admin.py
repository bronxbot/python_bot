"""
Administrative features for BronxBot
Server management, statistics, and monitoring
"""

import nextcord
from nextcord.ext import commands
import psutil
import time
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from database.database_manager import get_database_manager
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed,
    create_info_embed, safe_send, format_time
)
from utils.logger import get_logger

logger = get_logger(__name__)


class AdminCog(commands.Cog):
    """Administrative commands and features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = get_database_manager()
        self.start_time = time.time()
        
        # Performance monitoring
        self.performance_data = {
            "cpu_usage": [],
            "memory_usage": [],
            "command_count": 0,
            "errors": 0
        }
        
        # Start monitoring tasks
        self.monitor_performance.start()
    
    def cog_check(self, ctx):
        """Check if user has admin permissions"""
        return ctx.author.guild_permissions.administrator or ctx.author.id == int(self.bot.settings.owner_id)
    
    @commands.Cog.listener()
    async def on_command(self, ctx):
        """Track command usage"""
        self.performance_data["command_count"] += 1
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Track errors"""
        self.performance_data["errors"] += 1
    
    @commands.command(name="stats")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def bot_stats(self, ctx):
        """📊 View bot statistics"""
        
        # Get global stats from database
        global_stats = await self.db.get_global_stats()
        
        # System stats
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # Bot stats
        uptime = time.time() - self.start_time
        
        embed = create_info_embed(
            "📊 BronxBot Statistics",
            f"**Uptime:** {format_time(uptime)}\n"
            f"**Servers:** {len(self.bot.guilds):,}\n"
            f"**Users:** {len(self.bot.users):,}\n"
            f"**Commands Used:** {self.performance_data['command_count']:,}\n"
            f"**Errors:** {self.performance_data['errors']:,}"
        )
        
        embed.add_field(
            name="💰 Economy Stats",
            value=f"**Total Users:** {global_stats.get('total_users', 0):,}\n"
                  f"**Total in Wallets:** {format_currency(global_stats.get('total_wallet', 0))}\n"
                  f"**Total in Banks:** {format_currency(global_stats.get('total_bank', 0))}",
            inline=False
        )
        
        embed.add_field(
            name="🎣 Fishing Stats",
            value=f"**Total Fish Caught:** {global_stats.get('total_fish_caught', 0):,}\n"
                  f"**Total Games Played:** {global_stats.get('total_games_played', 0):,}\n"
                  f"**Total Work Sessions:** {global_stats.get('total_work_sessions', 0):,}",
            inline=False
        )
        
        embed.add_field(
            name="🖥️ System Stats",
            value=f"**CPU Usage:** {cpu_percent}%\n"
                  f"**Memory Usage:** {memory.percent}%\n"
                  f"**Available Memory:** {memory.available // 1024 // 1024} MB",
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="serverinfo")
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def server_info(self, ctx):
        """🏰 View server information"""
        
        guild = ctx.guild
        
        # Get server stats
        total_members = guild.member_count
        bots = sum(1 for member in guild.members if member.bot)
        humans = total_members - bots
        online = sum(1 for member in guild.members if member.status != nextcord.Status.offline)
        
        # Get economy stats for this server
        server_users = [member.id for member in guild.members if not member.bot]
        
        embed = create_info_embed(
            f"🏰 {guild.name} Server Info",
            f"**Owner:** {guild.owner.mention}\n"
            f"**Created:** {guild.created_at.strftime('%Y-%m-%d')}\n"
            f"**Region:** {guild.region}\n"
            f"**Verification Level:** {guild.verification_level}"
        )
        
        embed.add_field(
            name="👥 Members",
            value=f"**Total:** {total_members:,}\n"
                  f"**Humans:** {humans:,}\n"
                  f"**Bots:** {bots:,}\n"
                  f"**Online:** {online:,}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Channels",
            value=f"**Text:** {len(guild.text_channels)}\n"
                  f"**Voice:** {len(guild.voice_channels)}\n"
                  f"**Categories:** {len(guild.categories)}\n"
                  f"**Roles:** {len(guild.roles)}",
            inline=True
        )
        
        embed.add_field(
            name="🎭 Features",
            value=f"**Emojis:** {len(guild.emojis)}/{guild.emoji_limit}\n"
                  f"**Boost Level:** {guild.premium_tier}\n"
                  f"**Boosters:** {guild.premium_subscription_count}\n"
                  f"**Features:** {len(guild.features)}",
            inline=True
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="userinfo")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def user_info(self, ctx, member: nextcord.Member = None):
        """👤 View user information"""
        
        target = member or ctx.author
        
        # Get user data from database
        user_data = await self.db.get_user(target.id)
        
        embed = create_info_embed(
            f"👤 {target.display_name}",
            f"**Username:** {target.name}#{target.discriminator}\n"
            f"**ID:** {target.id}\n"
            f"**Created:** {target.created_at.strftime('%Y-%m-%d')}\n"
            f"**Joined:** {target.joined_at.strftime('%Y-%m-%d')}"
        )
        
        if user_data:
            economy_data = user_data.get("economy", {})
            fishing_data = user_data.get("fishing", {})
            gambling_data = user_data.get("gambling", {})
            work_data = user_data.get("work", {})
            
            embed.add_field(
                name="💰 Economy",
                value=f"**Wallet:** {format_currency(economy_data.get('wallet', 0))}\n"
                      f"**Bank:** {format_currency(economy_data.get('bank', 0))}\n"
                      f"**Bank Tier:** {economy_data.get('bank_tier', 'Bronze').title()}",
                inline=True
            )
            
            embed.add_field(
                name="🎣 Fishing",
                value=f"**Total Catches:** {fishing_data.get('total_catches', 0):,}\n"
                      f"**Total Value:** {format_currency(fishing_data.get('total_value', 0))}\n"
                      f"**Current Rod:** {fishing_data.get('rod', 'None').replace('_', ' ').title()}",
                inline=True
            )
            
            embed.add_field(
                name="🎰 Gambling",
                value=f"**Games Played:** {gambling_data.get('games_played', 0):,}\n"
                      f"**Total Bet:** {format_currency(gambling_data.get('total_bet', 0))}\n"
                      f"**Total Won:** {format_currency(gambling_data.get('total_won', 0))}",
                inline=True
            )
            
            if work_data.get('job'):
                embed.add_field(
                    name="💼 Work",
                    value=f"**Job:** {work_data.get('job', 'None').replace('_', ' ').title()}\n"
                          f"**Times Worked:** {work_data.get('total_worked', 0):,}\n"
                          f"**Total Earned:** {format_currency(work_data.get('total_earned', 0))}",
                    inline=True
                )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="leaderboard", aliases=["lb"])
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def leaderboard(self, ctx, category: str = "money"):
        """🏆 View leaderboards"""
        
        category = category.lower()
        
        if category in ["money", "balance", "wallet"]:
            field = "economy.wallet"
            title = "💰 Richest Users"
            format_func = format_currency
        elif category in ["bank"]:
            field = "economy.bank"
            title = "🏦 Biggest Bank Accounts"
            format_func = format_currency
        elif category in ["fish", "fishing"]:
            field = "fishing.total_catches"
            title = "🎣 Most Fish Caught"
            format_func = lambda x: f"{x:,}"
        elif category in ["gambling", "games"]:
            field = "gambling.games_played"
            title = "🎰 Most Games Played"
            format_func = lambda x: f"{x:,}"
        elif category in ["work"]:
            field = "work.total_worked"
            title = "💼 Most Work Sessions"
            format_func = lambda x: f"{x:,}"
        else:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Category",
                "Available categories: money, bank, fish, gambling, work"
            ))
            return
        
        # Get leaderboard data
        leaderboard_data = await self.db.get_leaderboard(field, limit=10)
        
        if not leaderboard_data:
            await safe_send(ctx, embed=create_error_embed(
                "No Data",
                "No leaderboard data available for this category"
            ))
            return
        
        embed = create_info_embed(title, "")
        
        leaderboard_text = []
        for i, user_data in enumerate(leaderboard_data, 1):
            user_id = user_data.get("user_id")
            value = user_data.get(field.replace(".", "_"), 0)
            
            # Try to get user from bot
            try:
                user = self.bot.get_user(user_id)
                if user:
                    username = user.display_name
                else:
                    username = f"Unknown User ({user_id})"
            except:
                username = f"Unknown User ({user_id})"
            
            # Medals for top 3
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            
            leaderboard_text.append(f"{medal} {username}: {format_func(value)}")
        
        embed.description = "\n".join(leaderboard_text)
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="cleanup")
    @commands.has_permissions(manage_messages=True)
    async def cleanup_messages(self, ctx, amount: int = 10):
        """🧹 Clean up bot messages"""
        
        if amount < 1 or amount > 100:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Amount",
                "Amount must be between 1 and 100"
            ))
            return
        
        def is_bot_message(message):
            return message.author.bot
        
        deleted = await ctx.channel.purge(limit=amount, check=is_bot_message)
        
        embed = create_success_embed(
            "Messages Cleaned",
            f"Deleted {len(deleted)} bot messages"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="maintenance")
    @commands.is_owner()
    async def maintenance_mode(self, ctx, enabled: bool = None):
        """🔧 Toggle maintenance mode"""
        
        if enabled is None:
            # Show current status
            maintenance = getattr(self.bot, 'maintenance_mode', False)
            status = "Enabled" if maintenance else "Disabled"
            
            embed = create_info_embed(
                "Maintenance Mode",
                f"**Status:** {status}"
            )
            
            await safe_send(ctx, embed=embed)
            return
        
        self.bot.maintenance_mode = enabled
        status = "enabled" if enabled else "disabled"
        
        embed = create_success_embed(
            "Maintenance Mode",
            f"Maintenance mode has been {status}"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="announce")
    @commands.is_owner()
    async def announce(self, ctx, *, message: str):
        """📢 Send announcement to all servers"""
        
        sent_count = 0
        failed_count = 0
        
        embed = create_info_embed(
            "📢 Announcement",
            message
        )
        embed.set_footer(text=f"From {ctx.author.display_name}")
        
        for guild in self.bot.guilds:
            try:
                # Try to find a suitable channel
                channel = None
                
                # Try to find general/announcements channel
                for ch in guild.text_channels:
                    if ch.name.lower() in ['general', 'announcements', 'bot-commands']:
                        channel = ch
                        break
                
                # If no suitable channel found, use the first text channel
                if not channel:
                    channel = guild.text_channels[0] if guild.text_channels else None
                
                if channel and channel.permissions_for(guild.me).send_messages:
                    await channel.send(embed=embed)
                    sent_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send announcement to {guild.name}: {e}")
        
        result_embed = create_success_embed(
            "Announcement Sent",
            f"**Sent to:** {sent_count} servers\n"
            f"**Failed:** {failed_count} servers"
        )
        
        await safe_send(ctx, embed=result_embed)
    
    @commands.task
    async def monitor_performance(self):
        """Monitor bot performance"""
        while True:
            try:
                # Record CPU and memory usage
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                
                self.performance_data["cpu_usage"].append(cpu_percent)
                self.performance_data["memory_usage"].append(memory_percent)
                
                # Keep only last 100 measurements
                if len(self.performance_data["cpu_usage"]) > 100:
                    self.performance_data["cpu_usage"] = self.performance_data["cpu_usage"][-100:]
                if len(self.performance_data["memory_usage"]) > 100:
                    self.performance_data["memory_usage"] = self.performance_data["memory_usage"][-100:]
                
                # Check for alerts
                if cpu_percent > 80:
                    logger.warning(f"High CPU usage: {cpu_percent}%")
                
                if memory_percent > 85:
                    logger.warning(f"High memory usage: {memory_percent}%")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error monitoring performance: {e}")
                await asyncio.sleep(60)


def setup(bot):
    bot.add_cog(AdminCog(bot))
