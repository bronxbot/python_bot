import nextcord
from nextcord.ext import commands
from typing import Dict, Any, List, Callable, Optional
import asyncio
import datetime
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger

class SetupWizard:
    """Interactive setup wizard system"""
    
    def __init__(self, bot, user: nextcord.Member, guild: nextcord.Guild):
        self.bot = bot
        self.user = user
        self.guild = guild
        self.logger = CogLogger('SetupWizard')
        self.current_step = 0
        self.responses = {}
        self.timeout = 300  # 5 minutes
    
    async def run_server_setup(self, ctx):
        """Run the server setup wizard"""
        if not ctx.author.guild_permissions.administrator:
            return await ctx.reply("❌ You need Administrator permissions to run server setup!")
        
        embed = nextcord.Embed(
            title="🛠️ Server Setup Wizard",
            description="Welcome to the BronxBot setup wizard! I'll help you configure your server.\n"
                       "You can type `cancel` at any time to stop the setup.",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="What we'll set up:",
            value="• Welcome messages and channels\n"
                  "• Moderation settings\n"
                  "• Economy system\n"
                  "• Custom prefixes\n"
                  "• Auto-role configuration",
            inline=False
        )
        
        message = await ctx.reply(embed=embed)
        
        # Define setup steps
        steps = [
            self._setup_welcome,
            self._setup_moderation,
            self._setup_economy,
            self._setup_prefix,
            self._setup_autorole,
            self._setup_complete
        ]
        
        try:
            for step_func in steps:
                result = await step_func(ctx, message)
                if result == "cancelled":
                    return await self._setup_cancelled(message)
                elif result == "timeout":
                    return await self._setup_timeout(message)
        
        except asyncio.TimeoutError:
            await self._setup_timeout(message)
        except Exception as e:
            self.logger.error(f"Setup wizard error: {e}")
            await self._setup_error(message, str(e))
    
    async def run_user_setup(self, ctx):
        """Run the user setup wizard"""
        embed = nextcord.Embed(
            title="👋 Welcome to BronxBot!",
            description="Let's get you set up! This will only take a minute.",
            color=nextcord.Color.green()
        )
        
        embed.add_field(
            name="What we'll do:",
            value="• Set your timezone\n"
                  "• Configure privacy settings\n"
                  "• Set up economy preferences\n"
                  "• Choose notification settings",
            inline=False
        )
        
        message = await ctx.reply(embed=embed)
        
        steps = [
            self._user_timezone,
            self._user_privacy,
            self._user_economy_prefs,
            self._user_notifications,
            self._user_setup_complete
        ]
        
        try:
            for step_func in steps:
                result = await step_func(ctx, message)
                if result == "cancelled":
                    return await self._setup_cancelled(message)
                elif result == "timeout":
                    return await self._setup_timeout(message)
        
        except asyncio.TimeoutError:
            await self._setup_timeout(message)
        except Exception as e:
            self.logger.error(f"User setup wizard error: {e}")
            await self._setup_error(message, str(e))
    
    async def _wait_for_response(self, ctx, message, timeout=None):
        """Wait for user response with timeout handling"""
        timeout = timeout or self.timeout
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            response = await self.bot.wait_for('message', check=check, timeout=timeout)
            
            if response.content.lower() == 'cancel':
                return "cancelled"
            
            return response.content
        
        except asyncio.TimeoutError:
            return "timeout"
    
    # Server Setup Steps
    async def _setup_welcome(self, ctx, message):
        """Setup welcome messages"""
        embed = nextcord.Embed(
            title="📝 Welcome Messages Setup",
            description="Would you like to enable welcome messages for new members?",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Options:",
            value="✅ `yes` - Enable welcome messages\n"
                  "❌ `no` - Skip welcome setup\n"
                  "🔧 `custom` - Set up custom welcome message",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() == "yes":
            # Setup default welcome
            embed.description = "Great! Please mention the channel where welcome messages should be sent."
            embed.clear_fields()
            await message.edit(embed=embed)
            
            channel_response = await self._wait_for_response(ctx, message)
            if channel_response in ["cancelled", "timeout"]:
                return channel_response
            
            # Parse channel mention
            channel = None
            if channel_response.startswith('<#') and channel_response.endswith('>'):
                channel_id = int(channel_response[2:-1])
                channel = ctx.guild.get_channel(channel_id)
            
            if not channel:
                channel = ctx.channel  # Default to current channel
            
            self.responses['welcome'] = {
                'enabled': True,
                'channel': channel.id,
                'message': "Welcome to {guild}, {user}! 👋"
            }
            
        elif response.lower() == "custom":
            # Custom welcome setup
            embed.description = "Please enter your custom welcome message.\n\nVariables you can use:\n`{user}` - User mention\n`{guild}` - Server name\n`{count}` - Member count"
            await message.edit(embed=embed)
            
            custom_msg = await self._wait_for_response(ctx, message)
            if custom_msg in ["cancelled", "timeout"]:
                return custom_msg
            
            embed.description = "Which channel should welcome messages be sent to?"
            await message.edit(embed=embed)
            
            channel_response = await self._wait_for_response(ctx, message)
            if channel_response in ["cancelled", "timeout"]:
                return channel_response
            
            channel = ctx.channel  # Default
            if channel_response.startswith('<#') and channel_response.endswith('>'):
                try:
                    channel_id = int(channel_response[2:-1])
                    channel = ctx.guild.get_channel(channel_id) or ctx.channel
                except:
                    pass
            
            self.responses['welcome'] = {
                'enabled': True,
                'channel': channel.id,
                'message': custom_msg
            }
        
        else:
            self.responses['welcome'] = {'enabled': False}
        
        return "continue"
    
    async def _setup_moderation(self, ctx, message):
        """Setup moderation features"""
        embed = nextcord.Embed(
            title="🛡️ Moderation Setup",
            description="Configure moderation features for your server.",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Enable auto-moderation?",
            value="✅ `yes` - Enable basic auto-mod (spam, caps, etc.)\n"
                  "❌ `no` - Skip auto-moderation\n"
                  "🔧 `advanced` - Configure advanced settings",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() == "yes":
            self.responses['moderation'] = {
                'auto_mod': True,
                'spam_protection': True,
                'caps_protection': True,
                'link_protection': False
            }
        elif response.lower() == "advanced":
            # Advanced moderation setup could be implemented here
            self.responses['moderation'] = {
                'auto_mod': True,
                'spam_protection': True,
                'caps_protection': True,
                'link_protection': True
            }
        else:
            self.responses['moderation'] = {'auto_mod': False}
        
        return "continue"
    
    async def _setup_economy(self, ctx, message):
        """Setup economy system"""
        embed = nextcord.Embed(
            title="💰 Economy Setup",
            description="Configure the economy system for your server.",
            color=nextcord.Color.gold()
        )
        
        embed.add_field(
            name="Enable economy features?",
            value="✅ `yes` - Enable full economy (currency, shop, gambling)\n"
                  "❌ `no` - Disable economy features\n"
                  "💵 `currency-only` - Only enable currency system",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() == "yes":
            self.responses['economy'] = {
                'enabled': True,
                'currency': True,
                'shop': True,
                'gambling': True,
                'fishing': True
            }
        elif response.lower() == "currency-only":
            self.responses['economy'] = {
                'enabled': True,
                'currency': True,
                'shop': False,
                'gambling': False,
                'fishing': False
            }
        else:
            self.responses['economy'] = {'enabled': False}
        
        return "continue"
    
    async def _setup_prefix(self, ctx, message):
        """Setup custom prefix"""
        embed = nextcord.Embed(
            title="⚙️ Command Prefix Setup",
            description=f"Current prefix: `.`\n\nWould you like to change the command prefix?",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Options:",
            value="✅ Enter a new prefix (1-3 characters)\n"
                  "❌ `no` - Keep default prefix (.)",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() != "no" and len(response) <= 3:
            self.responses['prefix'] = response
        else:
            self.responses['prefix'] = "."
        
        return "continue"
    
    async def _setup_autorole(self, ctx, message):
        """Setup auto-role"""
        embed = nextcord.Embed(
            title="🎭 Auto-Role Setup",
            description="Would you like to automatically assign a role to new members?",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Options:",
            value="✅ `yes` - Set up auto-role\n"
                  "❌ `no` - Skip auto-role setup",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() == "yes":
            embed.description = "Please mention the role to automatically assign, or type the role name."
            embed.clear_fields()
            await message.edit(embed=embed)
            
            role_response = await self._wait_for_response(ctx, message)
            if role_response in ["cancelled", "timeout"]:
                return role_response
            
            # Parse role
            role = None
            if role_response.startswith('<@&') and role_response.endswith('>'):
                try:
                    role_id = int(role_response[3:-1])
                    role = ctx.guild.get_role(role_id)
                except:
                    pass
            else:
                # Search by name
                role = nextcord.utils.get(ctx.guild.roles, name=role_response)
            
            if role:
                self.responses['autorole'] = {'enabled': True, 'role': role.id}
            else:
                self.responses['autorole'] = {'enabled': False}
                embed.description = "⚠️ Role not found. Auto-role setup skipped."
                await message.edit(embed=embed)
                await asyncio.sleep(2)
        else:
            self.responses['autorole'] = {'enabled': False}
        
        return "continue"
    
    async def _setup_complete(self, ctx, message):
        """Complete server setup"""
        # Save all settings to database
        settings = {
            'guild_id': str(ctx.guild.id),
            'welcome': self.responses.get('welcome', {}),
            'moderation': self.responses.get('moderation', {}),
            'economy': self.responses.get('economy', {}),
            'prefix': self.responses.get('prefix', '.'),
            'autorole': self.responses.get('autorole', {}),
            'setup_completed': True
        }
        
        await db.update_guild_settings(ctx.guild.id, settings)
        
        embed = nextcord.Embed(
            title="✅ Setup Complete!",
            description="Your server has been successfully configured!",
            color=nextcord.Color.green()
        )
        
        summary = []
        if self.responses.get('welcome', {}).get('enabled'):
            summary.append("✅ Welcome messages enabled")
        if self.responses.get('moderation', {}).get('auto_mod'):
            summary.append("✅ Auto-moderation enabled")
        if self.responses.get('economy', {}).get('enabled'):
            summary.append("✅ Economy system enabled")
        if self.responses.get('autorole', {}).get('enabled'):
            summary.append("✅ Auto-role configured")
        
        embed.add_field(
            name="Configured Features:",
            value="\n".join(summary) if summary else "Basic configuration applied",
            inline=False
        )
        
        embed.add_field(
            name="Next Steps:",
            value=f"• Use `{self.responses.get('prefix', '.')}help` to see all commands\n"
                  f"• Use `{self.responses.get('prefix', '.')}settings` to modify settings\n"
                  "• Invite friends and start using the bot!",
            inline=False
        )
        
        await message.edit(embed=embed)
        return "complete"
    
    # User Setup Steps
    async def _user_timezone(self, ctx, message):
        """Set user timezone"""
        embed = nextcord.Embed(
            title="🌍 Timezone Setup",
            description="What's your timezone? This helps with time-based features.",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Examples:",
            value="`UTC` - Coordinated Universal Time\n"
                  "`EST` or `America/New_York` - Eastern Time\n"
                  "`PST` or `America/Los_Angeles` - Pacific Time\n"
                  "`GMT` - Greenwich Mean Time\n"
                  "`skip` - Skip timezone setup",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        if response.lower() != "skip":
            self.responses['timezone'] = response
        else:
            self.responses['timezone'] = "UTC"
        
        return "continue"
    
    async def _user_privacy(self, ctx, message):
        """Set privacy preferences"""
        embed = nextcord.Embed(
            title="🔒 Privacy Settings",
            description="Configure your privacy preferences.",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Show your statistics publicly?",
            value="✅ `yes` - Others can see your stats\n"
                  "❌ `no` - Keep your stats private\n"
                  "🤷 `friends-only` - Only friends can see stats",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        privacy_level = "public"
        if response.lower() == "no":
            privacy_level = "private"
        elif response.lower() == "friends-only":
            privacy_level = "friends"
        
        self.responses['privacy'] = privacy_level
        return "continue"
    
    async def _user_economy_prefs(self, ctx, message):
        """Set economy preferences"""
        embed = nextcord.Embed(
            title="💰 Economy Preferences",
            description="Configure your economy settings.",
            color=nextcord.Color.gold()
        )
        
        embed.add_field(
            name="Enable auto-investing?",
            value="✅ `yes` - Automatically invest daily earnings\n"
                  "❌ `no` - Manual investment only\n"
                  "❓ `ask` - Ask before each investment",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        auto_invest = "manual"
        if response.lower() == "yes":
            auto_invest = "auto"
        elif response.lower() == "ask":
            auto_invest = "ask"
        
        self.responses['auto_invest'] = auto_invest
        return "continue"
    
    async def _user_notifications(self, ctx, message):
        """Set notification preferences"""
        embed = nextcord.Embed(
            title="🔔 Notification Settings",
            description="Choose what notifications you'd like to receive.",
            color=nextcord.Color.blue()
        )
        
        embed.add_field(
            name="Daily reminder notifications?",
            value="✅ `yes` - Get daily reminders for commands\n"
                  "❌ `no` - No daily reminders\n"
                  "🎯 `important-only` - Only important notifications",
            inline=False
        )
        
        await message.edit(embed=embed)
        response = await self._wait_for_response(ctx, message)
        
        if response in ["cancelled", "timeout"]:
            return response
        
        notifications = "none"
        if response.lower() == "yes":
            notifications = "all"
        elif response.lower() == "important-only":
            notifications = "important"
        
        self.responses['notifications'] = notifications
        return "continue"
    
    async def _user_setup_complete(self, ctx, message):
        """Complete user setup"""
        # Save user preferences
        user_data = {
            'user_id': str(ctx.author.id),
            'timezone': self.responses.get('timezone', 'UTC'),
            'privacy': self.responses.get('privacy', 'public'),
            'auto_invest': self.responses.get('auto_invest', 'manual'),
            'notifications': self.responses.get('notifications', 'none'),
            'setup_completed': True,
            'setup_date': datetime.datetime.now().isoformat()
        }
        
        # Update user in database
        await db.db.users.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"preferences": user_data}},
            upsert=True
        )
        
        embed = nextcord.Embed(
            title="🎉 Welcome to BronxBot!",
            description="Your account has been set up successfully!",
            color=nextcord.Color.green()
        )
        
        summary = [
            f"🌍 Timezone: {self.responses.get('timezone', 'UTC')}",
            f"🔒 Privacy: {self.responses.get('privacy', 'public').title()}",
            f"💰 Auto-invest: {self.responses.get('auto_invest', 'manual').title()}",
            f"🔔 Notifications: {self.responses.get('notifications', 'none').title()}"
        ]
        
        embed.add_field(
            name="Your Settings:",
            value="\n".join(summary),
            inline=False
        )
        
        embed.add_field(
            name="What's Next?",
            value="• Explore the economy system with `.bal`, `.work`, `.fish`\n"
                  "• Play games with `.roulette`, `.blackjack`\n"
                  "• Use `.help` to see all available commands\n"
                  "• Change settings anytime with `.settings`",
            inline=False
        )
        
        await message.edit(embed=embed)
        return "complete"
    
    # Error and utility methods
    async def _setup_cancelled(self, message):
        """Handle setup cancellation"""
        embed = nextcord.Embed(
            title="❌ Setup Cancelled",
            description="Setup has been cancelled. You can run the setup again anytime!",
            color=nextcord.Color.red()
        )
        await message.edit(embed=embed)
    
    async def _setup_timeout(self, message):
        """Handle setup timeout"""
        embed = nextcord.Embed(
            title="⏰ Setup Timed Out",
            description="Setup has timed out due to inactivity. You can run it again anytime!",
            color=nextcord.Color.orange()
        )
        await message.edit(embed=embed)
    
    async def _setup_error(self, message, error):
        """Handle setup error"""
        embed = nextcord.Embed(
            title="❌ Setup Error",
            description=f"An error occurred during setup: {error}\n\nPlease try again or contact support.",
            color=nextcord.Color.red()
        )
        await message.edit(embed=embed)


class Setup(commands.Cog):
    """Setup wizard commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
    
    @commands.command(name="setup", aliases=["serversetup", "configure", 'bronx'])
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def server_setup(self, ctx):
        """Run the interactive server setup wizard"""
        wizard = SetupWizard(self.bot, ctx.author, ctx.guild)
        await wizard.run_server_setup(ctx)
    
    @commands.command(name="usersetup", aliases=["mysetup", "preferences"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def user_setup(self, ctx):
        """Run the interactive user setup wizard"""
        wizard = SetupWizard(self.bot, ctx.author, ctx.guild)
        await wizard.run_user_setup(ctx)
    
    @commands.command(name="quicksetup")
    @commands.has_permissions(administrator=True)
    async def quick_setup(self, ctx):
        """Quick setup with sensible defaults"""
        settings = {
            'guild_id': str(ctx.guild.id),
            'welcome': {'enabled': True, 'channel': ctx.channel.id, 'message': 'Welcome to {guild}, {user}! 👋'},
            'moderation': {'auto_mod': True, 'spam_protection': True},
            'economy': {'enabled': True, 'currency': True, 'shop': True},
            'prefix': '.',
            'autorole': {'enabled': False},
            'setup_completed': True
        }
        
        await db.update_guild_settings(ctx.guild.id, settings)
        
        embed = nextcord.Embed(
            title="⚡ Quick Setup Complete!",
            description="Your server has been configured with sensible defaults!",
            color=nextcord.Color.green()
        )
        
        embed.add_field(
            name="Enabled Features:",
            value="✅ Welcome messages (this channel)\n"
                  "✅ Basic auto-moderation\n"
                  "✅ Full economy system\n"
                  "✅ Default prefix (.)",
            inline=False
        )
        
        embed.add_field(
            name="Customize:",
            value="Use `.setup` for full configuration wizard\n"
                  "Use `.settings` to modify individual settings",
            inline=False
        )
        
        await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(Setup(bot))
