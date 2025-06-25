import discord
import random
import logging
from discord.ext import commands
import asyncio
import re
import datetime
from datetime import timedelta
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.error_handler import ErrorHandler
import os
import json

def parse_duration(duration: str) -> timedelta | None:
    """Parse duration strings like '1h30m' into timedelta."""
    pattern = r'((?P<weeks>\d+)w)?((?P<days>\d+)d)?((?P<hours>\d+)h)?((?P<minutes>\d+)m)?((?P<seconds>\d+)s)?'
    match = re.fullmatch(pattern, duration.replace(" ", ""))
    if not match or not match.group(0):
        return None
    time_params = {name: int(val) for name, val in match.groupdict(default='0').items()}
    return timedelta(**time_params)

def save_warn_fallback(guild, user, moderator, reason, timestamp):
    """Fallback: Save warning to a JSON file if DB fails."""
    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    warn_file = os.path.join(data_dir, f"warns_{guild.id}.json")
    try:
        if os.path.exists(warn_file):
            with open(warn_file, "r", encoding="utf-8") as f:
                warns = json.load(f)
        else:
            warns = {}
    except Exception:
        warns = {}

    warns.setdefault(str(user.id), []).append({
        "moderator": str(moderator.id),
        "moderator_name": str(moderator),
        "reason": reason,
        "timestamp": timestamp.isoformat(),
        "guild_name": guild.name,
        "user_name": str(user)
    })

    with open(warn_file, "w", encoding="utf-8") as f:
        json.dump(warns, f, indent=2)

class Moderation(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.bot.launch_time = discord.utils.utcnow()
        self.logger.info("Moderation cog initialized")

    async def log_action(self, guild_id: int, embed: discord.Embed):
        """Log moderation action to configured channel"""
        settings = db.get_guild_settings(str(guild_id))
        if log_channel_id := settings.get("moderation", {}).get("log_channel"):
            if channel := self.bot.get_channel(log_channel_id):
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    pass

    async def notify_user(self, user: discord.Member, message: str):
        try:
            await user.send(message)
        except Exception:
            pass

    def can_act(self, ctx, member: discord.Member):
        if member == ctx.author:
            return False, "You can't moderate yourself!"
        if member == ctx.guild.me:
            return False, "You can't moderate the bot!"
        if member.top_role >= ctx.author.top_role:
            return False, "You can't moderate someone with a higher or equal role!"
        return True, None

    @commands.command(aliases=["to"])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: str, *, reason=None):
        """Timeout a member (e.g. 1h, 1d, 1w, 30m)
        Usage: .timeout @user 1h30m [reason]
        """
        can, msg = self.can_act(ctx, member)
        if not can:
            return await ctx.send(msg)
        delta = parse_duration(duration)
        if not delta or delta.total_seconds() < 1:
            return await ctx.send("Invalid duration! Use formats like 1h, 30m, 2d, 1h30m, etc.")
        try:
            await member.timeout(delta, reason=reason)
            embed = discord.Embed(
                description=f"Timed out {member.mention} for `{duration}`\nReason: {reason or 'No reason provided'}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
            await self.notify_user(member, f"You have been timed out in **{ctx.guild.name}** for `{duration}`.\nReason: {reason or 'No reason provided'}")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to timeout: {e}")

    @commands.command(aliases=["uto"])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason=None):
        """Remove timeout from a member
        Usage: .untimeout @user [reason]
        """
        try:
            await member.timeout(None, reason=reason)
            embed = discord.Embed(
                description=f"Removed timeout for {member.mention}\nReason: {reason or 'No reason provided'}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
            await self.notify_user(member, f"Your timeout was removed in **{ctx.guild.name}**.\nReason: {reason or 'No reason provided'}")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to remove timeout: {e}")

    @commands.command(aliases=["k"])
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kick a member from the server
        Usage: .kick @user [reason]
        """
        can, msg = self.can_act(ctx, member)
        if not can:
            return await ctx.send(msg)
        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                description=f"Kicked {member.mention}\nReason: {reason or 'No reason provided'}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
            await self.notify_user(member, f"You have been kicked from **{ctx.guild.name}**.\nReason: {reason or 'No reason provided'}")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to kick: {e}")

    @commands.command(aliases=["b"])
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Ban a member from the server
        Usage: .ban @user [reason]
        """
        can, msg = self.can_act(ctx, member)
        if not can:
            return await ctx.send(msg)
        try:
            await member.ban(reason=reason)
            embed = discord.Embed(
                description=f"Banned {member.mention}\nReason: {reason or 'No reason provided'}",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
            await self.notify_user(member, f"You have been banned from **{ctx.guild.name}**.\nReason: {reason or 'No reason provided'}")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to ban: {e}")

    @commands.command(aliases=["ub"])
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason=None):
        """Unban a user by ID or mention
        Usage: .unban user_id [reason]
        """
        try:
            await ctx.guild.unban(user, reason=reason)
            embed = discord.Embed(
                description=f"Unbanned {user.mention}\nReason: {reason or 'No reason provided'}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
        except discord.HTTPException as e:
            await ctx.send(f"Failed to unban: {e}")

    @commands.command(aliases=["p"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int = 10):
        """Delete a number of messages (default 10, max 100)
        Usage: .purge 25
        """
        if amount < 1 or amount > 100:
            return await ctx.send("Amount must be between 1 and 100.")
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = discord.Embed(
            description=f"Purged {len(deleted)-1} messages.",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        ).set_footer(text=f"by {ctx.author}")
        await ctx.send(embed=embed, delete_after=5)
        await self.log_action(ctx.guild.id, embed)

    @commands.command(aliases=["m"])
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, *, reason=None):
        """Mute a member (adds Muted role)
        Usage: .mute @user [reason]
        """
        can, msg = self.can_act(ctx, member)
        if not can:
            return await ctx.send(msg)
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted_role:
            muted_role = await ctx.guild.create_role(name="Muted", reason="Mute command used")
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, speak=False, send_messages=False, add_reactions=False)
        await member.add_roles(muted_role, reason=reason)
        embed = discord.Embed(
            description=f"Muted {member.mention}\nReason: {reason or 'No reason provided'}",
            color=discord.Color.dark_grey(),
            timestamp=datetime.datetime.utcnow()
        ).set_footer(text=f"by {ctx.author}")
        await ctx.send(embed=embed)
        await self.log_action(ctx.guild.id, embed)
        await self.notify_user(member, f"You have been muted in **{ctx.guild.name}**.\nReason: {reason or 'No reason provided'}")

    @commands.command(aliases=["um"])
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member, *, reason=None):
        """Unmute a member (removes Muted role)
        Usage: .unmute @user [reason]
        """
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role, reason=reason)
            embed = discord.Embed(
                description=f"Unmuted {member.mention}\nReason: {reason or 'No reason provided'}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            ).set_footer(text=f"by {ctx.author}")
            await ctx.send(embed=embed)
            await self.log_action(ctx.guild.id, embed)
            await self.notify_user(member, f"You have been unmuted in **{ctx.guild.name}**.")
        else:
            await ctx.send("User is not muted.")

    @commands.command(aliases=["sm"])
    @commands.has_permissions(manage_messages=True)
    async def slowmode(self, ctx, seconds: int = 0):
        """Set slowmode for the current channel (0 to disable)
        Usage: .slowmode 10
        """
        if seconds < 0 or seconds > 21600:
            return await ctx.send("Slowmode must be between 0 and 21600 seconds (6 hours).")
        await ctx.channel.edit(slowmode_delay=seconds)
        embed = discord.Embed(
            description=f"Set slowmode to {seconds} seconds.",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        ).set_footer(text=f"by {ctx.author}")
        await ctx.send(embed=embed)
        await self.log_action(ctx.guild.id, embed)

    @commands.command(aliases=["w"])
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason=None):
        """Warn a member (logs warning)
        Usage: .warn @user [reason]
        """
        can, msg = self.can_act(ctx, member)
        if not can:
            return await ctx.send(msg)
        timestamp = datetime.datetime.utcnow()
        db_failed = False
        try:
            add_warn_func = getattr(db, "add_warn", None)
            if callable(add_warn_func):
                result = add_warn_func(ctx.guild.id, member.id, ctx.author.id, reason or "No reason provided", timestamp)
                if asyncio.iscoroutine(result):
                    await result
            else:
                db_failed = True
        except Exception as e:
            db_failed = True
            self.logger.error(f"DB warn failed: {e}")

        if db_failed:
            save_warn_fallback(ctx.guild, member, ctx.author, reason or "No reason provided", timestamp)

        embed = discord.Embed(
            title="⚠️ Member Warned",
            description=f"{member.mention} has been warned in **{ctx.guild.name}**.",
            color=discord.Color.gold(),
            timestamp=timestamp
        )
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        embed.add_field(name="Moderator", value=f"{ctx.author} (`{ctx.author.id}`)", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        embed.set_footer(text=f"Guild: {ctx.guild.name}", icon_url=getattr(ctx.guild.icon, 'url', None))

        await ctx.send(embed=embed)
        await self.log_action(ctx.guild.id, embed)
        await self.notify_user(member, f"You have been warned in **{ctx.guild.name}**.\nReason: {reason or 'No reason provided'}")

    # Error handlers for all commands
    async def generic_error(self, ctx, error, command_name):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(f"❌ You don't have permission to use `{command_name}`!")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("❌ Member not found!")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Invalid argument!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"❌ Missing arguments! Use `{ctx.prefix}{command_name} ...`")
        else:
            await self.handle_error(ctx, error, command_name)

    @timeout.error
    async def timeout_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            if error.param.name == "member":
                await ctx.reply(
                    "❌ You must mention a user to timeout!\n"
                    "Example: `.timeout @user 1h30m [reason]`"
                )
            elif error.param.name == "duration":
                await ctx.reply(
                    "❌ You must provide a duration for the timeout!\n"
                    "Example: `.timeout @user 1h30m [reason]`\n"
                    "Duration examples: `10m`, `2h`, `1d`, `1h30m`"
                )
            else:
                await self.generic_error(ctx, error, "timeout")
        else:
            await self.generic_error(ctx, error, "timeout")

    @untimeout.error
    async def untimeout_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to untimeout!\nExample: `.untimeout @user [reason]`")
        else:
            await self.generic_error(ctx, error, "untimeout")

    @kick.error
    async def kick_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to kick!\nExample: `.kick @user [reason]`")
        else:
            await self.generic_error(ctx, error, "kick")

    @ban.error
    async def ban_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to ban!\nExample: `.ban @user [reason]`")
        else:
            await self.generic_error(ctx, error, "ban")

    @unban.error
    async def unban_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "user":
            await ctx.reply("❌ You must provide a user ID or mention to unban!\nExample: `.unban user_id [reason]`")
        else:
            await self.generic_error(ctx, error, "unban")

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Please provide a valid number of messages to purge!\nExample: `.purge 25`")
        else:
            await self.generic_error(ctx, error, "purge")

    @mute.error
    async def mute_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to mute!\nExample: `.mute @user [reason]`")
        else:
            await self.generic_error(ctx, error, "mute")

    @unmute.error
    async def unmute_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to unmute!\nExample: `.unmute @user [reason]`")
        else:
            await self.generic_error(ctx, error, "unmute")

    @slowmode.error
    async def slowmode_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Please provide a valid number of seconds!\nExample: `.slowmode 10`")
        else:
            await self.generic_error(ctx, error, "slowmode")

    @warn.error
    async def warn_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "member":
            await ctx.reply("❌ You must mention a user to warn!\nExample: `.warn @user [reason]`")
        else:
            await self.generic_error(ctx, error, "warn")

async def setup(bot):
    logger = CogLogger("Moderation")
    try:
        await bot.add_cog(Moderation(bot))
    except Exception as e:
        logger.error(f"Failed to load Moderation cog: {e}")
        raise