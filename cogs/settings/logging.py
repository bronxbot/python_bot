# Logging Settings
# Handles server logging configuration, audit trails, and event monitoring

import nextcord
from nextcord.ext import commands
from typing import Optional, List, Dict, Union
import json
import asyncio
from datetime import datetime, timedelta
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('LoggingSettings')

# Available logging events
LOGGING_EVENTS = {
    # Member events
    'member_join': '👤 Member Join',
    'member_leave': '👋 Member Leave',
    'member_update': '✏️ Member Update (nickname, roles)',
    'member_ban': '🔨 Member Ban',
    'member_unban': '🔓 Member Unban',
    'member_kick': '👢 Member Kick',
    'member_timeout': '⏰ Member Timeout',
    
    # Message events
    'message_delete': '🗑️ Message Delete',
    'message_edit': '✏️ Message Edit',
    'message_bulk_delete': '🗂️ Bulk Message Delete',
    
    # Channel events
    'channel_create': '📺 Channel Create',
    'channel_delete': '🗑️ Channel Delete',
    'channel_update': '✏️ Channel Update',
    
    # Role events
    'role_create': '🎭 Role Create',
    'role_delete': '🗑️ Role Delete',
    'role_update': '✏️ Role Update',
    
    # Server events
    'guild_update': '🏰 Server Update',
    'emoji_create': '😀 Emoji Create',
    'emoji_delete': '🗑️ Emoji Delete',
    'emoji_update': '✏️ Emoji Update',
    
    # Voice events
    'voice_join': '🔊 Voice Join',
    'voice_leave': '🔇 Voice Leave',
    'voice_move': '🔀 Voice Move',
    'voice_mute': '🔇 Voice Mute',
    'voice_deafen': '🔕 Voice Deafen',
    
    # Moderation events
    'warn_add': '⚠️ Warning Added',
    'warn_remove': '✅ Warning Removed',
    'case_create': '📋 Moderation Case',
    
    # Invite events
    'invite_create': '📨 Invite Create',
    'invite_delete': '🗑️ Invite Delete',
    
    # Thread events
    'thread_create': '🧵 Thread Create',
    'thread_delete': '🗑️ Thread Delete',
    'thread_update': '✏️ Thread Update',
    
    # Integration events
    'integration_create': '🔗 Integration Create',
    'integration_delete': '🗑️ Integration Delete',
    'integration_update': '✏️ Integration Update',
}

class LoggingSettings(commands.Cog, ErrorHandler):
    """Logging configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='logging', aliases=['logs'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def logging_settings(self, ctx):
        """Logging settings management"""
        embed = nextcord.Embed(
            title="📋 Logging Settings",
            description=(
                "Configure server logging and audit trails\n\n"
                "**Available Commands:**\n"
                "`logging channels` - Manage logging channels\n"
                "`logging events` - Configure logged events\n"
                "`logging audit` - Configure audit trail settings\n"
                "`logging ignore` - Manage ignored users/channels\n"
                "`logging view` - View current logging settings"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)

    @logging_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_logging_settings(self, ctx):
        """View current logging settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        
        embed = nextcord.Embed(
            title="📋 Logging Settings Overview",
            color=0x3498db
        )
        
        # General settings
        general = log_settings.get('general', {})
        embed.add_field(
            name="⚙️ General Settings",
            value=(
                f"**Logging Enabled:** {'✅' if general.get('enabled', False) else '❌'}\n"
                f"**Configured Channels:** {len(log_settings.get('channels', {}))}\n"
                f"**Active Events:** {len(log_settings.get('events', {}))}\n"
                f"**Audit Trail:** {'✅' if log_settings.get('audit', {}).get('enabled', False) else '❌'}"
            ),
            inline=False
        )
        
        # Quick overview of channels
        channels = log_settings.get('channels', {})
        if channels:
            channel_summary = []
            for event_type, channel_id in list(channels.items())[:5]:  # Show first 5
                channel = ctx.guild.get_channel(channel_id)
                channel_name = channel.mention if channel else f"#{channel_id} (Deleted)"
                event_name = LOGGING_EVENTS.get(event_type, event_type.replace('_', ' ').title())
                channel_summary.append(f"{event_name}: {channel_name}")
            
            if len(channels) > 5:
                channel_summary.append(f"... and {len(channels) - 5} more")
            
            embed.add_field(
                name="📺 Channel Configuration (Sample)",
                value='\n'.join(channel_summary),
                inline=False
            )
        
        # Audit trail info
        audit = log_settings.get('audit', {})
        if audit.get('enabled', False):
            embed.add_field(
                name="🔍 Audit Trail",
                value=(
                    f"**Threshold:** {audit.get('action_threshold', 5)} actions\n"
                    f"**Time Window:** {audit.get('time_window', 300)}s\n"
                    f"**Alert Channel:** <#{audit.get('alert_channel')}>" if audit.get('alert_channel') else "Not set"
                ),
                inline=False
            )
        
        await ctx.send(embed=embed)

    # Channel Management
    @logging_settings.group(name='channels', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def channel_settings(self, ctx):
        """Manage logging channels"""
        embed = nextcord.Embed(
            title="📺 Logging Channel Management",
            description="Configure which events get logged to which channels",
            color=0x3498db
        )
        embed.add_field(
            name="Commands",
            value=(
                "`channels set <event> <channel>` - Set channel for event\n"
                "`channels remove <event>` - Remove logging for event\n"
                "`channels list` - List current channel assignments\n"
                "`channels bulk <channel>` - Set channel for multiple events\n"
                "`channels clear` - Clear all channel assignments"
            ),
            inline=False
        )
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Use `logging events` to see all available events\n"
                "• One channel can log multiple event types\n"
                "• Events without channels won't be logged"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='set')
    @commands.has_permissions(manage_guild=True)
    async def set_log_channel(self, ctx, event: str, channel: nextcord.TextChannel):
        """Set logging channel for a specific event"""
        event = event.lower()
        
        if event not in LOGGING_EVENTS:
            # Show available events
            embed = nextcord.Embed(
                title="❌ Invalid Event",
                description=f"'{event}' is not a valid logging event.",
                color=0xe74c3c
            )
            
            # Group events by category for better display
            categories = {
                "👥 Member Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('member_')],
                "💬 Message Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('message_')],
                "📺 Channel Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('channel_')],
                "🎭 Role Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('role_')],
                "🔊 Voice Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('voice_')],
                "⚖️ Moderation Events": [k for k in LOGGING_EVENTS.keys() if 'warn' in k or 'case' in k],
                "🏰 Server Events": [k for k in LOGGING_EVENTS.keys() if k.startswith(('guild_', 'emoji_', 'invite_', 'thread_', 'integration_'))]
            }
            
            for category, events in categories.items():
                if events:
                    event_list = '\n'.join([f"`{e}` - {LOGGING_EVENTS[e]}" for e in events[:3]])
                    if len(events) > 3:
                        event_list += f"\n... and {len(events) - 3} more"
                    embed.add_field(name=category, value=event_list, inline=True)
            
            embed.set_footer(text="Use 'logging events' to see the complete list")
            return await ctx.send(embed=embed)
        
        # Check bot permissions in the channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}!")
        
        # Save the channel assignment
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        channels = log_settings.get('channels', {})
        
        channels[event] = channel.id
        log_settings['channels'] = channels
        
        # Enable logging if not already enabled
        if 'general' not in log_settings:
            log_settings['general'] = {}
        log_settings['general']['enabled'] = True
        
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        embed = nextcord.Embed(
            title="✅ Logging Channel Set",
            description=f"**{LOGGING_EVENTS[event]}** events will now be logged to {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_log_channel(self, ctx, event: str):
        """Remove logging for a specific event"""
        event = event.lower()
        
        if event not in LOGGING_EVENTS:
            return await ctx.send(f"❌ '{event}' is not a valid logging event. Use `logging events` to see available events.")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        channels = log_settings.get('channels', {})
        
        if event not in channels:
            return await ctx.send(f"❌ **{LOGGING_EVENTS[event]}** is not currently being logged.")
        
        del channels[event]
        log_settings['channels'] = channels
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        embed = nextcord.Embed(
            title="✅ Logging Removed",
            description=f"**{LOGGING_EVENTS[event]}** events will no longer be logged",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='list')
    @commands.has_permissions(manage_guild=True)
    async def list_log_channels(self, ctx):
        """List current channel assignments"""
        settings = await db.get_guild_settings(ctx.guild.id)
        channels = settings.get('logging', {}).get('channels', {})
        
        embed = nextcord.Embed(
            title="📺 Current Logging Channels",
            color=0x3498db
        )
        
        if not channels:
            embed.description = "No logging channels configured.\nUse `logging channels set` to configure them!"
            return await ctx.send(embed=embed)
        
        # Group by channel for better organization
        channel_groups = {}
        for event, channel_id in channels.items():
            if channel_id not in channel_groups:
                channel_groups[channel_id] = []
            channel_groups[channel_id].append(event)
        
        for channel_id, events in channel_groups.items():
            channel = ctx.guild.get_channel(channel_id)
            channel_name = channel.mention if channel else f"#{channel_id} (Deleted)"
            
            event_list = []
            for event in events[:5]:  # Show first 5 events per channel
                event_list.append(f"• {LOGGING_EVENTS.get(event, event.replace('_', ' ').title())}")
            
            if len(events) > 5:
                event_list.append(f"• ... and {len(events) - 5} more events")
            
            embed.add_field(
                name=channel_name,
                value='\n'.join(event_list),
                inline=True
            )
        
        embed.set_footer(text=f"Total: {len(channels)} event types configured")
        await ctx.send(embed=embed)

    @channel_settings.command(name='bulk')
    @commands.has_permissions(manage_guild=True)
    async def bulk_set_channel(self, ctx, channel: nextcord.TextChannel):
        """Set one channel for multiple events (Interactive)"""
        embed = nextcord.Embed(
            title="📋 Bulk Channel Assignment",
            description=f"Select event categories to log in {channel.mention}",
            color=0x3498db
        )
        
        # Create view with category selection
        view = BulkChannelView(channel, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    # Event Management
    @logging_settings.command(name='events')
    @commands.has_permissions(manage_guild=True)
    async def list_events(self, ctx):
        """List all available logging events"""
        embed = nextcord.Embed(
            title="📋 Available Logging Events",
            description="Complete list of events that can be logged",
            color=0x3498db
        )
        
        # Group events by category
        categories = {
            "👥 Member Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('member_')],
            "💬 Message Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('message_')],
            "📺 Channel Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('channel_')],
            "🎭 Role Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('role_')],
            "🔊 Voice Events": [k for k in LOGGING_EVENTS.keys() if k.startswith('voice_')],
            "⚖️ Moderation Events": [k for k in LOGGING_EVENTS.keys() if 'warn' in k or 'case' in k],
            "🏰 Server Events": [k for k in LOGGING_EVENTS.keys() if k.startswith(('guild_', 'emoji_', 'invite_', 'thread_', 'integration_'))]
        }
        
        for category, events in categories.items():
            if events:
                event_list = '\n'.join([f"`{e}` - {LOGGING_EVENTS[e]}" for e in events])
                embed.add_field(name=category, value=event_list, inline=False)
        
        embed.set_footer(text="Use 'logging channels set <event> <channel>' to configure logging")
        await ctx.send(embed=embed)

    # Audit Trail
    @logging_settings.group(name='audit', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def audit_settings(self, ctx):
        """Configure audit trail settings"""
        embed = nextcord.Embed(
            title="🔍 Audit Trail Configuration",
            description="Monitor users who make many changes in a short time",
            color=0xff9500
        )
        embed.add_field(
            name="What is Audit Trail?",
            value=(
                "Monitors users who perform many moderation actions quickly:\n"
                "• Mass role changes\n"
                "• Multiple channel edits\n"
                "• Bulk message deletions\n"
                "• Rapid permission changes"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "`audit toggle` - Enable/disable audit trail\n"
                "`audit threshold <number>` - Set action threshold\n"
                "`audit window <seconds>` - Set time window\n"
                "`audit channel <channel>` - Set alert channel\n"
                "`audit view` - View current settings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @audit_settings.command(name='toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle_audit(self, ctx, enabled: bool = None):
        """Toggle audit trail monitoring"""
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        audit = log_settings.get('audit', {})
        
        if enabled is None:
            current_status = audit.get('enabled', False)
            embed = nextcord.Embed(
                title="🔍 Audit Trail Status",
                color=0xff9500
            )
            embed.add_field(
                name="Current Status",
                value=f"Audit Trail: {'✅ Enabled' if current_status else '❌ Disabled'}",
                inline=False
            )
            if current_status:
                embed.add_field(
                    name="Settings",
                    value=(
                        f"**Threshold:** {audit.get('action_threshold', 5)} actions\n"
                        f"**Time Window:** {audit.get('time_window', 300)} seconds\n"
                        f"**Alert Channel:** <#{audit.get('alert_channel')}>" if audit.get('alert_channel') else "Not set"
                    ),
                    inline=False
                )
            return await ctx.send(embed=embed)
        
        audit['enabled'] = enabled
        
        # Set defaults if enabling for first time
        if enabled and 'action_threshold' not in audit:
            audit['action_threshold'] = 5
            audit['time_window'] = 300  # 5 minutes
        
        log_settings['audit'] = audit
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        status = "enabled" if enabled else "disabled"
        embed = nextcord.Embed(
            title=f"✅ Audit Trail {status.title()}",
            description=f"Audit trail monitoring has been {status}!",
            color=0x2ecc71 if enabled else 0x95a5a6
        )
        
        if enabled and not audit.get('alert_channel'):
            embed.add_field(
                name="⚠️ Setup Required",
                value="No alert channel configured! Use `logging audit channel` to set one.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @audit_settings.command(name='threshold')
    @commands.has_permissions(manage_guild=True)
    async def set_audit_threshold(self, ctx, threshold: int):
        """Set the number of actions that trigger an audit alert"""
        if threshold < 2 or threshold > 50:
            return await ctx.send("❌ Threshold must be between 2 and 50 actions!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        audit = log_settings.get('audit', {})
        
        audit['action_threshold'] = threshold
        log_settings['audit'] = audit
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        embed = nextcord.Embed(
            title="✅ Audit Threshold Updated",
            description=f"Audit alerts will trigger after {threshold} actions within the time window",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @audit_settings.command(name='window')
    @commands.has_permissions(manage_guild=True)
    async def set_audit_window(self, ctx, seconds: int):
        """Set the time window for audit trail monitoring"""
        if seconds < 60 or seconds > 3600:
            return await ctx.send("❌ Time window must be between 60 and 3600 seconds (1 hour)!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        audit = log_settings.get('audit', {})
        
        audit['time_window'] = seconds
        log_settings['audit'] = audit
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        minutes = seconds // 60
        embed = nextcord.Embed(
            title="✅ Audit Time Window Updated",
            description=f"Audit monitoring window set to {seconds} seconds ({minutes} minutes)",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @audit_settings.command(name='channel')
    @commands.has_permissions(manage_guild=True)
    async def set_audit_channel(self, ctx, channel: nextcord.TextChannel):
        """Set the channel for audit trail alerts"""
        if not channel.permissions_for(ctx.guild.me).send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        log_settings = settings.get('logging', {})
        audit = log_settings.get('audit', {})
        
        audit['alert_channel'] = channel.id
        log_settings['audit'] = audit
        await db.update_guild_settings(ctx.guild.id, {'logging': log_settings})
        
        embed = nextcord.Embed(
            title="✅ Audit Channel Set",
            description=f"Audit trail alerts will be sent to {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    # Ignore Settings
    @logging_settings.group(name='ignore', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def ignore_settings(self, ctx):
        """Manage ignored users/channels for logging"""
        embed = nextcord.Embed(
            title="🚫 Logging Ignore Settings",
            description="Configure which users/channels to ignore in logs",
            color=0x95a5a6
        )
        embed.add_field(
            name="Commands",
            value=(
                "`ignore user add <user>` - Ignore user in logs\n"
                "`ignore user remove <user>` - Stop ignoring user\n"
                "`ignore channel add <channel>` - Ignore channel in logs\n"
                "`ignore channel remove <channel>` - Stop ignoring channel\n"
                "`ignore list` - List ignored users/channels"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    async def log_event(self, event_type: str, guild: nextcord.Guild, **kwargs):
        """Log an event to the appropriate channel"""
        settings = await db.get_guild_settings(guild.id)
        log_settings = settings.get('logging', {})
        
        # Check if logging is enabled
        if not log_settings.get('general', {}).get('enabled', False):
            return
        
        # Check if this event type has a configured channel
        channels = log_settings.get('channels', {})
        if event_type not in channels:
            return
        
        channel = guild.get_channel(channels[event_type])
        if not channel:
            return
        
        # Check ignore settings
        ignored = log_settings.get('ignore', {})
        if kwargs.get('user') and kwargs['user'].id in ignored.get('users', []):
            return
        if kwargs.get('channel') and kwargs['channel'].id in ignored.get('channels', []):
            return
        
        # Create embed based on event type
        embed = await self.create_log_embed(event_type, **kwargs)
        if embed:
            try:
                await channel.send(embed=embed)
            except nextcord.HTTPException as e:
                logger.error(f"Failed to send log message: {e}")

    async def create_log_embed(self, event_type: str, **kwargs) -> Optional[nextcord.Embed]:
        """Create an embed for a log event"""
        embed = nextcord.Embed(
            title=LOGGING_EVENTS.get(event_type, event_type.replace('_', ' ').title()),
            timestamp=datetime.utcnow(),
            color=self.get_event_color(event_type)
        )
        
        # Add fields based on event type
        if event_type == 'member_join':
            member = kwargs.get('member')
            if member:
                embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=True)
                embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
                embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
                embed.set_thumbnail(url=member.display_avatar.url)
        
        elif event_type == 'member_leave':
            member = kwargs.get('member')
            if member:
                embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
                embed.add_field(name="Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
                embed.add_field(name="Member Count", value=str(member.guild.member_count), inline=True)
        
        elif event_type == 'message_delete':
            message = kwargs.get('message')
            if message:
                embed.add_field(name="Author", value=f"{message.author.mention} ({message.author})", inline=True)
                embed.add_field(name="Channel", value=message.channel.mention, inline=True)
                embed.add_field(name="Message ID", value=str(message.id), inline=True)
                if message.content:
                    embed.add_field(name="Content", value=message.content[:1000], inline=False)
        
        # Add more event types as needed...
        
        return embed

    def get_event_color(self, event_type: str) -> int:
        """Get color for event type"""
        colors = {
            'member_join': 0x2ecc71,    # Green
            'member_leave': 0xe74c3c,   # Red
            'member_ban': 0x992d22,     # Dark red
            'member_unban': 0x27ae60,   # Dark green
            'message_delete': 0xe67e22,  # Orange
            'message_edit': 0xf39c12,    # Yellow
            'channel_create': 0x3498db,  # Blue
            'channel_delete': 0x9b59b6,  # Purple
            'role_create': 0x1abc9c,     # Teal
            'role_delete': 0xe91e63,     # Pink
        }
        return colors.get(event_type, 0x95a5a6)  # Default gray

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "logging settings")

class BulkChannelView(nextcord.ui.View):
    def __init__(self, channel: nextcord.TextChannel, guild_id: int):
        super().__init__(timeout=60)
        self.channel = channel
        self.guild_id = guild_id
        self.selected_categories = set()

    @nextcord.ui.select(
        placeholder="Select event categories to log in this channel...",
        options=[
            nextcord.SelectOption(label="Member Events", value="member", emoji="👥"),
            nextcord.SelectOption(label="Message Events", value="message", emoji="💬"),
            nextcord.SelectOption(label="Channel Events", value="channel", emoji="📺"),
            nextcord.SelectOption(label="Role Events", value="role", emoji="🎭"),
            nextcord.SelectOption(label="Voice Events", value="voice", emoji="🔊"),
            nextcord.SelectOption(label="Moderation Events", value="moderation", emoji="⚖️"),
            nextcord.SelectOption(label="Server Events", value="server", emoji="🏰"),
        ],
        max_values=7
    )
    async def select_categories(self, interaction: nextcord.Interaction, select: nextcord.ui.Select):
        self.selected_categories = set(select.values)
        
        embed = nextcord.Embed(
            title="📋 Selected Categories",
            description=f"Selected categories will be logged to {self.channel.mention}",
            color=0x3498db
        )
        
        category_map = {
            "member": "👥 Member Events",
            "message": "💬 Message Events", 
            "channel": "📺 Channel Events",
            "role": "🎭 Role Events",
            "voice": "🔊 Voice Events",
            "moderation": "⚖️ Moderation Events",
            "server": "🏰 Server Events"
        }
        
        selected_text = '\n'.join([f"• {category_map[cat]}" for cat in self.selected_categories])
        embed.add_field(name="Selected Categories", value=selected_text, inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @nextcord.ui.button(label="Apply Settings", style=nextcord.ButtonStyle.green, emoji="✅")
    async def apply_settings(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not self.selected_categories:
            await interaction.response.send_message("❌ Please select at least one category!", ephemeral=True)
            return
        
        # Apply the settings
        settings = await db.get_guild_settings(self.guild_id)
        log_settings = settings.get('logging', {})
        channels = log_settings.get('channels', {})
        
        # Map categories to events
        category_events = {
            "member": [k for k in LOGGING_EVENTS.keys() if k.startswith('member_')],
            "message": [k for k in LOGGING_EVENTS.keys() if k.startswith('message_')],
            "channel": [k for k in LOGGING_EVENTS.keys() if k.startswith('channel_')],
            "role": [k for k in LOGGING_EVENTS.keys() if k.startswith('role_')],
            "voice": [k for k in LOGGING_EVENTS.keys() if k.startswith('voice_')],
            "moderation": [k for k in LOGGING_EVENTS.keys() if 'warn' in k or 'case' in k],
            "server": [k for k in LOGGING_EVENTS.keys() if k.startswith(('guild_', 'emoji_', 'invite_', 'thread_', 'integration_'))]
        }
        
        total_events = 0
        for category in self.selected_categories:
            for event in category_events.get(category, []):
                channels[event] = self.channel.id
                total_events += 1
        
        log_settings['channels'] = channels
        
        # Enable logging if not already enabled
        if 'general' not in log_settings:
            log_settings['general'] = {}
        log_settings['general']['enabled'] = True
        
        await db.update_guild_settings(self.guild_id, {'logging': log_settings})
        
        embed = nextcord.Embed(
            title="✅ Bulk Assignment Complete",
            description=f"Configured {total_events} events to log in {self.channel.mention}",
            color=0x2ecc71
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

    @nextcord.ui.button(label="Cancel", style=nextcord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        embed = nextcord.Embed(
            title="❌ Cancelled",
            description="Bulk channel assignment cancelled.",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)

def setup(bot):
    bot.add_cog(LoggingSettings(bot))
