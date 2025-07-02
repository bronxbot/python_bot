import nextcord
import random
import json
import logging
from nextcord.ext import commands
from datetime import timedelta
import datetime
import asyncio
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.error_handler import ErrorHandler

# this is super wip
class Moderation(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.bot.launch_time = datetime.datetime.now()
        self.logger.info("Moderation cog initialized")

    async def log_action(self, guild_id: int, embed: nextcord.Embed):
        """Log moderation action to configured channel"""
        settings = await db.get_guild_settings(guild_id)
        if log_channel_id := settings.get("moderation", {}).get("log_channel"):
            if channel := self.bot.get_channel(log_channel_id):
                try:
                    await channel.send(embed=embed)
                except nextcord.HTTPException:
                    pass

    @commands.command(aliases=["to"])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: nextcord.Member, duration: str, *, reason=None):
        """Timeout a member (e.g. 1h, 1d, 1w)"""
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You can't timeout someone with a higher or equal role!")

        # Convert duration string to timedelta
        time_units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
        amount = int(''.join(filter(str.isdigit, duration)))
        unit = ''.join(filter(str.isalpha, duration)).lower()
        
        if unit not in time_units:
            return await ctx.send("Invalid duration format! Use s/m/h/d/w (e.g. 1h, 1d)")

        delta = timedelta(**{time_units[unit]: amount})
        
        try:
            await member.timeout(delta, reason=reason)
            embed = nextcord.Embed(
                description=f"timed out {member.mention} • {duration}\n{reason or 'no reason provided'}",
                color=nextcord.Color.orange()
            ).set_footer(text=f"by {ctx.author.name}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
        except nextcord.HTTPException as e:
            await ctx.send(f"failed to timeout: {e}")

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: nextcord.Member, *, reason=None):
        await member.kick(reason=reason)
        embed = nextcord.Embed(
            description=f"kicked {member.mention}\n{reason or 'no reason provided'}",
            color=nextcord.Color.red()
        ).set_footer(text=f"by {ctx.author.name}")
        await ctx.send(embed=embed)

    @timeout.error
    async def timeout_error(self, ctx, error):
        """Handle timeout command errors"""
        if isinstance(error, commands.MissingPermissions):
            embed = nextcord.Embed(
                title="❌ Missing Permissions",
                description="You need the `Moderate Members` permission to timeout members!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return  # Prevent further error propagation
        elif isinstance(error, commands.MemberNotFound):
            embed = nextcord.Embed(
                title="❌ Member Not Found",
                description="Could not find the specified member!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return
        elif isinstance(error, commands.BadArgument):
            embed = nextcord.Embed(
                title="❌ Invalid Duration",
                description="Invalid duration format! Use s/m/h/d/w (e.g. 1h, 1d)",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = nextcord.Embed(
                title="❌ Missing Arguments",
                description=f"Please mention a member to timeout.\n**Usage:** `{ctx.prefix}timeout <member> <duration> [reason]`",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return
        else:
            # Let the global error handler deal with unexpected errors
            await self.handle_error(ctx, error, "timeout")

    @kick.error
    async def kick_error(self, ctx, error):
        """Handle kick command errors"""
        if isinstance(error, commands.MissingPermissions):
            embed = nextcord.Embed(
                title="❌ Missing Permissions",
                description="You need the `Kick Members` permission to kick members!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return  # Prevent further error propagation
        elif isinstance(error, commands.MemberNotFound):
            embed = nextcord.Embed(
                title="❌ Member Not Found",
                description="The specified member could not be found!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed, delete_after=10)
            return  # Prevent further error propagation
        else:
            await self.handle_error(ctx, error, "kick")

def setup(bot):
    logger = CogLogger("Moderation")
    try:
        bot.add_cog(Moderation(bot))
    except Exception as e:
        logger.error(f"Failed to load Moderation cog: {e}")
        raise