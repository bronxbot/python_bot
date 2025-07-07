import nextcord
import random
import json
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import db, AsyncDatabase

logger = CogLogger('Welcoming')

# Get async database instance
async_db = AsyncDatabase.get_instance()

def load_welcome_data():
    with open('data/welcome.json', 'r') as f:
        return json.load(f)

WELCOME_DATA = load_welcome_data()

def welcome_embed(member):
    # Get a random character key from the dictionary
    character_name = random.choice(list(WELCOME_DATA["characters"].keys()))
    character = WELCOME_DATA["characters"][character_name]
    character_url = character['image']
    
    return nextcord.Embed(
        description=f"\"{random.choice(character['messages'])}\"\n\n[main](https://discord.gg/furryporn) • [backup](https://discord.gg/W563EnFwed) • [appeal](https://discord.gg/6Th9dsw6rM)",
        color=nextcord.Color.random()
    ).set_author(
        name=character_name,  # Use the character name directly
        icon_url=character_url,
        url="https://discord.gg/6Th9dsw6rM"
    ).set_footer(text="click name to appeal if banned")

class Welcoming(commands.Cog):
    """Welcoming and stats tracking for new and leaving members."""
    def __init__(self, bot):
        self.bot = bot
        self.main_guilds = getattr(self.bot, "MAIN_GUILD_IDS", [])

    async def cog_check(self, ctx):
        """Check if the guild has permission to use this cog's commands."""
        return ctx.guild and ctx.guild.id in self.main_guilds

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id not in self.main_guilds:
            return

        # Get welcome settings from database
        settings = await async_db.get_guild_settings(member.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Check if welcome is enabled
        if not welcome_settings.get('enabled', True):  # Main welcome enabled check
            return
        
        # Get welcome channel from settings, fallback to environment variable or default
        import os
        welcome_channel_id = welcome_settings.get('channel')
        if not welcome_channel_id:
            welcome_channel_id = int(os.getenv('WELCOME_CHANNEL', '1385521743724019853'))

        # Disabled to reduce console spam
        # logger.info(f"[+] Member joined: {member} in guild {member.guild.id}")

        greetings = ["hi", "yo", "hola", "bonjour", "hhhjhhhiiiiii", "haiiiiii :3", "haaaaaaaiiiiiii", "hello", "hhiihihihiihihi", 'welcome to the bronx']
        emoji = random.choice(member.guild.emojis) if member.guild.emojis else ""
        if member.guild.id == 1259717095382319215:
            channel = member.guild.get_channel(welcome_channel_id)
            if channel:
                # Use custom message if set, otherwise use default greeting
                custom_message = welcome_settings.get('message')
                if custom_message:
                    # Replace variables in custom message
                    message = custom_message.replace('{user}', member.mention)
                    message = message.replace('{server}', member.guild.name)
                    message = message.replace('{count}', str(member.guild.member_count))
                    await channel.send(message)
                else:
                    await channel.send(f"{member.mention} {random.choice(greetings)} {emoji}")
            
            # Send DM embed if enabled
            if welcome_settings.get('dm_enabled', True):  # Default to enabled
                embed = welcome_embed(member)
                try:
                    await member.send(embed=embed)
                except nextcord.Forbidden:
                    logger.warning(f"Could not DM {member} (forbidden).")
            
            try:
                await db.store_stats(member.guild.id, "gained")
            except Exception as e:
                logger.error(f"Failed to store join stats: {e}")

    @commands.command()
    async def welcometest(self, ctx):
        """Test the welcome embed in your DMs."""
        try:
            await ctx.author.send(embed=welcome_embed(ctx.author))
            await ctx.reply("Check your DMs for the welcome message!")
        except nextcord.Forbidden:
            await ctx.reply("Couldn't DM you! Please enable DMs from server members.")

    @commands.group(name='welcomeadmin', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome_admin(self, ctx):
        """Admin commands for welcome system management"""
        embed = nextcord.Embed(
            title="🎉 Welcome System Admin",
            description="Manage the main guild welcome system",
            color=nextcord.Color.blue()
        )
        embed.add_field(
            name="Available Commands",
            value=(
                "`welcomeadmin channel <channel>` - Set welcome channel\n"
                "`welcomeadmin message <message>` - Set custom welcome message\n"
                "`welcomeadmin toggle` - Enable/disable welcome system\n"
                "`welcomeadmin dm` - Toggle DM on join\n"
                "`welcomeadmin status` - View current settings"
            ),
            inline=False
        )
        embed.add_field(
            name="Message Variables",
            value=(
                "`{user}` - Mention the user\n"
                "`{server}` - Server name\n"
                "`{count}` - Member count"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @welcome_admin.command(name='channel')
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel(self, ctx, channel: nextcord.TextChannel):
        """Set the welcome channel for the main guild"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Update the channel
        welcome_settings['channel'] = channel.id
        
        await async_db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Welcome Channel Updated",
            description=f"Welcome channel set to {channel.mention}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @welcome_admin.command(name='message')
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(self, ctx, *, message: str):
        """Set custom welcome message"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Update the message
        welcome_settings['message'] = message
        
        await async_db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Welcome Message Updated",
            description=f"Welcome message set to: {message}",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @welcome_admin.command(name='toggle')
    @commands.has_permissions(administrator=True)
    async def toggle_welcome(self, ctx):
        """Toggle welcome system on/off"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Toggle enabled state
        current_status = welcome_settings.get('enabled', True)
        welcome_settings['enabled'] = not current_status
        
        await async_db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        status = "enabled" if not current_status else "disabled"
        embed = nextcord.Embed(
            title=f"✅ Welcome System {status.title()}",
            description=f"Welcome system has been {status}",
            color=nextcord.Color.green() if not current_status else nextcord.Color.red()
        )
        await ctx.send(embed=embed)

    @welcome_admin.command(name='dm')
    @commands.has_permissions(administrator=True)
    async def toggle_dm(self, ctx):
        """Toggle DM on join"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Toggle DM enabled state
        current_status = welcome_settings.get('dm_enabled', True)
        welcome_settings['dm_enabled'] = not current_status
        
        await async_db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        status = "enabled" if not current_status else "disabled"
        embed = nextcord.Embed(
            title=f"✅ Welcome DM {status.title()}",
            description=f"Welcome DM has been {status}",
            color=nextcord.Color.green() if not current_status else nextcord.Color.red()
        )
        await ctx.send(embed=embed)

    @welcome_admin.command(name='status')
    @commands.has_permissions(administrator=True)
    async def welcome_status(self, ctx):
        """View current welcome settings"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Get current settings
        enabled = welcome_settings.get('enabled', True)
        dm_enabled = welcome_settings.get('dm_enabled', True)
        channel_id = welcome_settings.get('channel')
        message = welcome_settings.get('message')
        
        # Get channel info
        import os
        if not channel_id:
            channel_id = int(os.getenv('WELCOME_CHANNEL', '1385521743724019853'))
        
        channel = ctx.guild.get_channel(channel_id)
        channel_info = channel.mention if channel else f"Channel ID: {channel_id} (Not found)"
        
        embed = nextcord.Embed(
            title="🎉 Welcome System Status",
            color=nextcord.Color.blue()
        )
        embed.add_field(
            name="⚙️ Settings",
            value=(
                f"**Welcome Enabled:** {'✅' if enabled else '❌'}\n"
                f"**DM Enabled:** {'✅' if dm_enabled else '❌'}\n"
                f"**Channel:** {channel_info}"
            ),
            inline=False
        )
        
        if message:
            embed.add_field(
                name="💬 Custom Message",
                value=f"```{message}```",
                inline=False
            )
        else:
            embed.add_field(
                name="💬 Message",
                value="Using default random greetings",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='setwelcome')
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel_simple(self, ctx, channel: nextcord.TextChannel):
        """Quick command to set welcome channel"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Update the channel
        welcome_settings['channel'] = channel.id
        welcome_settings['enabled'] = True  # Enable when setting channel
        
        await async_db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Welcome Channel Set",
            description=f"Welcome channel set to {channel.mention} and enabled!",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='migrate_welcome')
    @commands.has_permissions(administrator=True)
    async def migrate_welcome_settings(self, ctx):
        """Migrate old welcome settings to new format"""
        settings = await async_db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        # Check if we have old format settings
        if 'general' in welcome_settings and 'channels' in welcome_settings['general']:
            old_general = welcome_settings['general']
            old_channels = old_general.get('channels', [])
            
            # Create new simplified format
            new_welcome_settings = {
                'enabled': welcome_settings.get('enabled', True),
                'channel': welcome_settings.get('channel', 1314685928614264852),  # Use existing or default
                'message': welcome_settings.get('message', 'Welcome to {server}, {user}! 👋'),
                'dm_enabled': True  # Default to enabled
            }
            
            # If there are old channel settings, try to migrate the first one
            if old_channels and len(old_channels) > 0:
                first_channel = old_channels[0]
                new_welcome_settings['channel'] = first_channel.get('id', new_welcome_settings['channel'])
                if first_channel.get('message') and first_channel['message'] != '.welcome embed':
                    new_welcome_settings['message'] = first_channel['message']
            
            # Update with new format
            await async_db.update_guild_settings(ctx.guild.id, {'welcome': new_welcome_settings})
            
            embed = nextcord.Embed(
                title="✅ Welcome Settings Migrated",
                description="Welcome settings have been updated to the new simplified format",
                color=nextcord.Color.green()
            )
            embed.add_field(
                name="New Settings",
                value=(
                    f"**Enabled:** {'✅' if new_welcome_settings['enabled'] else '❌'}\n"
                    f"**Channel:** <#{new_welcome_settings['channel']}>\n"
                    f"**Message:** {new_welcome_settings['message']}\n"
                    f"**DM Enabled:** {'✅' if new_welcome_settings['dm_enabled'] else '❌'}"
                ),
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("No old format settings found to migrate, or already using new format.")
