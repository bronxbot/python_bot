import discord
from discord.ext import commands
import aiohttp
import os
import json
from datetime import datetime
import pytz
from typing import Optional

TIMEZONE_FILE = "user_timezones.json"

def load_timezones():
    if os.path.exists(TIMEZONE_FILE):
        try:
            with open(TIMEZONE_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    return {}
                return json.loads(data)
        except Exception:
            # If file is corrupt, reset it
            with open(TIMEZONE_FILE, "w", encoding="utf-8") as f:
                f.write("{}")
            return {}
    return {}

def save_timezones(timezones):
    with open(TIMEZONE_FILE, "w", encoding="utf-8") as f:
        json.dump(timezones, f)

class Other(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezones = load_timezones()

    def set_timezone(self, user_id, tz):
        self.timezones[str(user_id)] = tz
        save_timezones(self.timezones)

    def remove_timezone(self, user_id):
        if str(user_id) in self.timezones:
            del self.timezones[str(user_id)]
            save_timezones(self.timezones)

    def get_timezone(self, user_id):
        return self.timezones.get(str(user_id))

    @commands.command(aliases=["settz"])
    async def settimezone(self, ctx, tz: str):
        """Set your timezone (e.g. UTC, Europe/London, US/Eastern)"""
        try:
            pytz.timezone(tz)
        except Exception:
            return await ctx.reply("❌ Invalid timezone! Use a valid tz database name like `UTC`, `Europe/London`, `US/Eastern`.")
        self.set_timezone(ctx.author.id, tz)
        await ctx.reply(f"🕒 Your timezone has been set to `{tz}`.")

    @settimezone.error
    async def settimezone_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("❌ Please provide a timezone. Example: `.settimezone Europe/London`")
        else:
            await ctx.reply(f"❌ Error: {error}")

    @commands.command(aliases=["removetz"])
    async def removetimezone(self, ctx):
        """Remove your saved timezone."""
        try:
            self.remove_timezone(ctx.author.id)
            await ctx.reply("🗑️ Your timezone has been removed.")
        except Exception as e:
            await ctx.reply(f"❌ Error removing timezone: {e}")

    @removetimezone.error
    async def removetimezone_error(self, ctx, error):
        await ctx.reply(f"❌ Error: {error}")
    @commands.command(aliases=["tz"])
    async def timezone(self, ctx, user: Optional[discord.Member] = None):
        """Show a user's current time (or your own)"""
        try:
            user = user or ctx.author
            tz_name = self.get_timezone(user.id)
            if not tz_name:
                return await ctx.reply(f"Timezone not set for {user.display_name}. They can set it with `.settimezone <zone>`.")
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            # Format: "June 05, 02:45 PM"
            pretty_date = now.strftime('%B %d, %I:%M %p').replace(" 0", " ")
            embed = discord.Embed(
                description=f"⏰ {user.mention}: Your current time is **{pretty_date}**",
                color=discord.Color.random()
            )
            await ctx.reply(embed=embed)
        except Exception:
            name = user.display_name if user is not None else "This user"
            await ctx.reply(f"Timezone for {name} is invalid. Please set it again with `.settimezone <zone>`.")

    @timezone.error
    async def timezone_error(self, ctx, error):
        await ctx.reply(f"❌ Error: {error}")

    @commands.command(aliases=["listtz"])
    async def listtimezones(self, ctx):
        """List all users with a set timezone in this server."""
        try:
            members = [m for m in ctx.guild.members if self.get_timezone(m.id)]
            if not members:
                return await ctx.reply("No one in this server has set a timezone yet.")
            desc = "\n".join(
                f"• **{m.display_name}**: `{self.get_timezone(m.id)}`"
                for m in members
            )
            embed = discord.Embed(title="Server Timezones", description=desc, color=discord.Color.blue())
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(f"❌ Error: {e}")

    @listtimezones.error
    async def listtimezones_error(self, ctx, error):
        await ctx.reply(f"❌ Error: {error}")

    @commands.command()
    async def weather(self, ctx, *, city: str):
        """Check the weather for a city (uses wttr.in, no API key needed)"""
        try:
            url = f"https://wttr.in/{city}?format=j1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return await ctx.reply("Could not fetch weather. Check the city name.")
                    data = await resp.json()
            area = data["nearest_area"][0]["areaName"][0]["value"]
            region = data["nearest_area"][0]["region"][0]["value"]
            country = data["nearest_area"][0]["country"][0]["value"]
            current = data["current_condition"][0]
            temp_c = current["temp_C"]
            feels_c = current["FeelsLikeC"]
            weather_desc = current["weatherDesc"][0]["value"]
            humidity = current["humidity"]
            wind = current["windspeedKmph"]
            icon_url = current["weatherIconUrl"][0]["value"]

            embed = discord.Embed(
                title=f"Weather in {area}, {region}, {country}",
                description=f"**{weather_desc}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Temperature", value=f"{temp_c}°C (feels like {feels_c}°C)")
            embed.add_field(name="Humidity", value=f"{humidity}%")
            embed.add_field(name="Wind", value=f"{wind} km/h")
            embed.set_thumbnail(url=icon_url)
            await ctx.reply(embed=embed)
        except Exception as e:
            await ctx.reply(f"Could not parse weather data. Try a different city.\nError: {e}")

    @weather.error
    async def weather_error(self, ctx, error):
        await ctx.reply(f"❌ Error: {error}")

async def setup(bot):
    await bot.add_cog(Other(bot))