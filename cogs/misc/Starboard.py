import nextcord
import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from nextcord.ext import commands
from nextcord import SlashOption
import sys
import os

# Add the project root to Python path to fix imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler
from utils.db import AsyncDatabase
from utils.safe_reply import safe_reply

db = AsyncDatabase.get_instance()

class StarboardConfig:
    """Configuration class for a starboard"""
    def __init__(self, data: dict = None):
        self.data = data or {}
        
    @property
    def name(self) -> str:
        return self.data.get('name', '')
    
    @property
    def channel_id(self) -> int:
        return self.data.get('channel_id', 0)
    
    @property
    def tracked_emojis(self) -> dict:
        return self.data.get('tracked_emojis', {})
    
    @property
    def show_duplicates(self) -> bool:
        return self.data.get('show_duplicates', True)
    
    @property
    def max_duplicate_emojis(self) -> int:
        return self.data.get('max_duplicate_emojis', 3)
    
    @property
    def show_timestamp(self) -> bool:
        return self.data.get('show_timestamp', True)
    
    @property
    def message_format(self) -> str:
        return self.data.get('message_format', 'embed')  # 'embed' or 'plaintext'
    
    @property
    def thumbnail_source(self) -> str:
        return self.data.get('thumbnail_source', 'author.icon')
    
    @property
    def show_attachments(self) -> bool:
        return self.data.get('show_attachments', True)
    
    @property
    def attachment_filter(self) -> str:
        return self.data.get('attachment_filter', 'off')  # 'off', 'role', 'whitelist', 'blacklist'
    
    @property
    def attachment_roles(self) -> list:
        return self.data.get('attachment_roles', [])
    
    @property
    def color_mode(self) -> str:
        return self.data.get('color_mode', 'default')  # 'none', 'default', 'random', 'hex'
    
    @property
    def custom_color(self) -> str:
        return self.data.get('custom_color', 'FF4A44')
    
    @property
    def embed_title(self) -> Optional[str]:
        return self.data.get('embed_title', None)
    
    @property
    def embed_description(self) -> str:
        return self.data.get('embed_description', '{message.content}')
    
    def update(self, **kwargs):
        self.data.update(kwargs)

class Starboard(commands.Cog, ErrorHandler):
    """Starboard system for highlighting popular messages"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        
        # Cache for starboard configurations
        self.starboard_cache: Dict[int, List[StarboardConfig]] = {}
        
        # Message variables for customization
        self.message_variables = {
            '{message.content}': 'The original message content',
            '{message.author.display_name}': 'Author\'s display name',
            '{message.author.mention}': 'Author mention (@user)',
            '{message.author.name}': 'Author\'s username',
            '{message.channel.name}': 'Channel name where message was posted',
            '{message.channel.mention}': 'Channel mention (#channel)',
            '{message.jump_url}': 'Jump URL to original message',
            '{reactions.count}': 'Total reaction count',
            '{reactions.emojis}': 'List of reaction emojis and counts',
            '{server.name}': 'Server name',
            '{timestamp}': 'Message timestamp',
            '{timestamp.relative}': 'Relative timestamp (e.g., "2 hours ago")',
        }

    async def cog_load(self):
        """Load starboard configurations on cog load"""
        await self.load_starboard_cache()

    async def load_starboard_cache(self):
        """Load all starboard configurations into cache"""
        if not await db.ensure_connected():
            return
        
        try:
            cursor = db.db.starboards.find({})
            async for doc in cursor:
                guild_id = int(doc['guild_id'])
                if guild_id not in self.starboard_cache:
                    self.starboard_cache[guild_id] = []
                
                config = StarboardConfig(doc)
                self.starboard_cache[guild_id].append(config)
        except Exception as e:
            self.logger.error(f"Failed to load starboard cache: {e}")

    async def get_guild_starboards(self, guild_id: int) -> List[StarboardConfig]:
        """Get all starboards for a guild"""
        if guild_id not in self.starboard_cache:
            await self.load_starboard_cache()
        return self.starboard_cache.get(guild_id, [])

    async def save_starboard_config(self, guild_id: int, config: StarboardConfig):
        """Save starboard configuration to database"""
        if not await db.ensure_connected():
            return False
        
        try:
            data = config.data.copy()
            data['guild_id'] = str(guild_id)
            
            await db.db.starboards.update_one(
                {'guild_id': str(guild_id), 'name': config.name},
                {'$set': data},
                upsert=True
            )
            
            # Update cache
            if guild_id not in self.starboard_cache:
                self.starboard_cache[guild_id] = []
            
            # Remove existing config with same name
            self.starboard_cache[guild_id] = [
                sb for sb in self.starboard_cache[guild_id] 
                if sb.name != config.name
            ]
            # Add updated config
            self.starboard_cache[guild_id].append(config)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to save starboard config: {e}")
            return False

    async def delete_starboard_config(self, guild_id: int, name: str) -> bool:
        """Delete starboard configuration"""
        if not await db.ensure_connected():
            return False
        
        try:
            result = await db.db.starboards.delete_one({
                'guild_id': str(guild_id),
                'name': name
            })
            
            if result.deleted_count > 0:
                # Update cache
                if guild_id in self.starboard_cache:
                    self.starboard_cache[guild_id] = [
                        sb for sb in self.starboard_cache[guild_id] 
                        if sb.name != name
                    ]
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete starboard config: {e}")
            return False

    def format_message_variables(self, template: str, message: nextcord.Message, 
                               reactions: Dict[str, int]) -> str:
        """Format message template with variables"""
        formatted = template
        
        # Replace message variables
        formatted = formatted.replace('{message.content}', message.content or '')
        formatted = formatted.replace('{message.author.display_name}', message.author.display_name)
        formatted = formatted.replace('{message.author.mention}', message.author.mention)
        formatted = formatted.replace('{message.author.name}', message.author.name)
        formatted = formatted.replace('{message.channel.name}', message.channel.name)
        formatted = formatted.replace('{message.channel.mention}', message.channel.mention)
        formatted = formatted.replace('{message.jump_url}', message.jump_url)
        formatted = formatted.replace('{server.name}', message.guild.name)
        
        # Format reactions
        total_reactions = sum(reactions.values())
        formatted = formatted.replace('{reactions.count}', str(total_reactions))
        
        emoji_list = [f"{emoji} {count}" for emoji, count in reactions.items()]
        formatted = formatted.replace('{reactions.emojis}', ', '.join(emoji_list))
        
        # Format timestamps
        timestamp = message.created_at
        formatted = formatted.replace('{timestamp}', timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'))
        
        # Calculate relative timestamp
        now = datetime.now(timezone.utc)
        delta = now - timestamp.replace(tzinfo=timezone.utc)
        
        if delta.days > 0:
            relative = f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            relative = f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            relative = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            relative = "just now"
        
        formatted = formatted.replace('{timestamp.relative}', relative)
        
        return formatted

    def get_embed_color(self, config: StarboardConfig, message: nextcord.Message) -> nextcord.Color:
        """Get embed color based on configuration"""
        if config.color_mode == 'none':
            return nextcord.Color.default()
        elif config.color_mode == 'default':
            return message.author.top_role.color if message.author.top_role.color != nextcord.Color.default() else nextcord.Color.blurple()
        elif config.color_mode == 'random':
            import random
            return nextcord.Color.random()
        elif config.color_mode == 'hex':
            try:
                return nextcord.Color(int(config.custom_color, 16))
            except ValueError:
                return nextcord.Color.blurple()
        else:
            return nextcord.Color.blurple()

    async def get_thumbnail_url(self, config: StarboardConfig, message: nextcord.Message) -> Optional[str]:
        """Get thumbnail URL based on configuration"""
        if config.thumbnail_source == 'author.icon':
            return message.author.display_avatar.url
        elif config.thumbnail_source == 'server.icon':
            return message.guild.icon.url if message.guild.icon else None
        elif config.thumbnail_source == 'bot.icon':
            return self.bot.user.display_avatar.url
        elif config.thumbnail_source.startswith('http'):
            return config.thumbnail_source
        else:
            return None

    async def should_show_attachments(self, config: StarboardConfig, message: nextcord.Message) -> bool:
        """Check if attachments should be shown based on configuration"""
        if not config.show_attachments:
            return False
        
        if config.attachment_filter == 'off':
            return True
        elif config.attachment_filter == 'role':
            user_role_ids = [role.id for role in message.author.roles]
            return any(role_id in config.attachment_roles for role_id in user_role_ids)
        # Add whitelist/blacklist logic if needed
        
        return True

    async def create_starboard_message(self, config: StarboardConfig, message: nextcord.Message, 
                                     reactions: Dict[str, int]) -> Union[nextcord.Embed, str]:
        """Create starboard message based on configuration"""
        # Handle duplicate emoji display
        if not config.show_duplicates and len(reactions) > 1:
            # Only show the emoji with the highest count
            max_emoji = max(reactions.items(), key=lambda x: x[1])
            reactions = {max_emoji[0]: max_emoji[1]}
        elif config.show_duplicates and len(reactions) > config.max_duplicate_emojis:
            # Limit to max number of emojis, sorted by count
            sorted_reactions = sorted(reactions.items(), key=lambda x: x[1], reverse=True)
            reactions = dict(sorted_reactions[:config.max_duplicate_emojis])
        
        if config.message_format == 'plaintext':
            # Create plaintext format
            emoji_text = ', '.join([f"{emoji} {count}" for emoji, count in reactions.items()])
            
            content = f"**{emoji_text}** - **{message.author.display_name}**\n\n"
            content += f"{message.author.mention}:\n> \"{message.content or 'No text content'}\"\n\n"
            
            if config.show_timestamp:
                timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
                content += f"-# {timestamp}"
            
            # Add attachments for plaintext format
            if await self.should_show_attachments(config, message) and message.attachments:
                content += "\n\n**Attachments:**\n"
                for att in message.attachments:
                    content += f"• [{att.filename}]({att.url})\n"
            
            return content
        else:
            # Create embed format
            embed = nextcord.Embed(
                title=self.format_message_variables(config.embed_title, message, reactions) if config.embed_title else None,
                description=self.format_message_variables(config.embed_description, message, reactions),
                color=self.get_embed_color(config, message),
                timestamp=message.created_at if config.show_timestamp else None
            )
            
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.display_avatar.url
            )
            
            # Add thumbnail
            thumbnail_url = await self.get_thumbnail_url(config, message)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            # Add reaction info
            emoji_text = ', '.join([f"{emoji} {count}" for emoji, count in reactions.items()])
            embed.add_field(name="Reactions", value=emoji_text, inline=False)
            
            # Add jump link
            embed.add_field(name="Original Message", value=f"[Jump to message]({message.jump_url})", inline=False)
            
            # Handle attachments
            if await self.should_show_attachments(config, message) and message.attachments:
                if len(message.attachments) == 1 and message.attachments[0].url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    embed.set_image(url=message.attachments[0].url)
                else:
                    attachment_list = '\n'.join([f"[{att.filename}]({att.url})" for att in message.attachments])
                    embed.add_field(name="Attachments", value=attachment_list, inline=False)
            
            return embed

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: nextcord.Reaction, user: nextcord.User):
        """Handle reaction additions for starboard"""
        if user.bot or not reaction.message.guild:
            return
        
        message = reaction.message
        guild_id = message.guild.id
        
        # Get starboards for this guild
        starboards = await self.get_guild_starboards(guild_id)
        if not starboards:
            return
        
        # Check each starboard configuration
        for config in starboards:
            emoji_str = str(reaction.emoji)
            if emoji_str not in config.tracked_emojis:
                continue
            
            required_count = config.tracked_emojis[emoji_str]
            if reaction.count >= required_count:
                await self.send_to_starboard(config, message, guild_id)

    async def send_to_starboard(self, config: StarboardConfig, message: nextcord.Message, guild_id: int):
        """Send message to starboard channel"""
        try:
            channel = self.bot.get_channel(config.channel_id)
            if not channel:
                return
            
            # Get all tracked reactions on this message
            tracked_reactions = {}
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji)
                if emoji_str in config.tracked_emojis:
                    if reaction.count >= config.tracked_emojis[emoji_str]:
                        tracked_reactions[emoji_str] = reaction.count
            
            if not tracked_reactions:
                return
            
            # Check if message already exists in starboard
            existing_message = await self.find_existing_starboard_message(config, message, channel)
            
            if existing_message:
                # Update existing message
                new_content = await self.create_starboard_message(config, message, tracked_reactions)
                if isinstance(new_content, nextcord.Embed):
                    await existing_message.edit(embed=new_content)
                else:
                    await existing_message.edit(content=new_content)
            else:
                # Create new starboard message
                new_content = await self.create_starboard_message(config, message, tracked_reactions)
                if isinstance(new_content, nextcord.Embed):
                    sent_message = await channel.send(embed=new_content)
                else:
                    sent_message = await channel.send(content=new_content)
                
                # Store reference for future updates
                await self.store_starboard_message_reference(config, message, sent_message)
        
        except Exception as e:
            self.logger.error(f"Failed to send to starboard: {e}")

    async def find_existing_starboard_message(self, config: StarboardConfig, 
                                            original_message: nextcord.Message, 
                                            starboard_channel: nextcord.TextChannel) -> Optional[nextcord.Message]:
        """Find existing starboard message for the original message"""
        # Check database for stored reference
        if not await db.ensure_connected():
            return None
        
        try:
            doc = await db.db.starboard_messages.find_one({
                'guild_id': str(original_message.guild.id),
                'starboard_name': config.name,
                'original_message_id': str(original_message.id)
            })
            
            if doc:
                try:
                    starboard_message = await starboard_channel.fetch_message(int(doc['starboard_message_id']))
                    return starboard_message
                except nextcord.NotFound:
                    # Message was deleted, remove from database
                    await db.db.starboard_messages.delete_one({'_id': doc['_id']})
                    return None
        except Exception as e:
            self.logger.error(f"Failed to find existing starboard message: {e}")
        
        return None

    async def store_starboard_message_reference(self, config: StarboardConfig, 
                                              original_message: nextcord.Message,
                                              starboard_message: nextcord.Message):
        """Store reference between original and starboard message"""
        if not await db.ensure_connected():
            return
        
        try:
            await db.db.starboard_messages.insert_one({
                'guild_id': str(original_message.guild.id),
                'starboard_name': config.name,
                'original_message_id': str(original_message.id),
                'starboard_message_id': str(starboard_message.id),
                'starboard_channel_id': str(starboard_message.channel.id),
                'created_at': datetime.utcnow()
            })
        except Exception as e:
            self.logger.error(f"Failed to store starboard message reference: {e}")

    @nextcord.slash_command(name="starboard", description="Manage starboard settings")
    async def starboard(self, interaction: nextcord.Interaction):
        pass

    @starboard.subcommand(name="create", description="Create a new starboard")
    async def starboard_create(self, 
                              interaction: nextcord.Interaction,
                              channel: nextcord.TextChannel = SlashOption(description="Channel for the starboard"),
                              name: str = SlashOption(description="Name for the starboard")):
        """Create a new starboard"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to create starboards.")
        
        # Check if starboard with this name already exists
        starboards = await self.get_guild_starboards(interaction.guild.id)
        if any(sb.name == name for sb in starboards):
            return await safe_reply(interaction, f"❌ A starboard named `{name}` already exists.")
        
        # Create new starboard configuration
        config = StarboardConfig({
            'name': name,
            'channel_id': channel.id,
            'tracked_emojis': {},
            'show_duplicates': True,
            'max_duplicate_emojis': 3,
            'show_timestamp': True,
            'message_format': 'embed',
            'thumbnail_source': 'author.icon',
            'show_attachments': True,
            'attachment_filter': 'off',
            'attachment_roles': [],
            'color_mode': 'default',
            'custom_color': 'FF4A44',
            'embed_title': None,
            'embed_description': '{message.content}'
        })
        
        success = await self.save_starboard_config(interaction.guild.id, config)
        if success:
            embed = nextcord.Embed(
                title="✅ Starboard Created",
                description=f"Starboard `{name}` has been created in {channel.mention}",
                color=nextcord.Color.green()
            )
            embed.add_field(
                name="Next Steps",
                value="• Use `/starboard track` to add emojis to track\n• Configure settings with other starboard commands",
                inline=False
            )
            await safe_reply(interaction, embed=embed)
        else:
            await safe_reply(interaction, "❌ Failed to create starboard. Please try again.")

    @starboard.subcommand(name="edit", description="Edit starboard name")
    async def starboard_edit(self,
                            interaction: nextcord.Interaction,
                            old_name: str = SlashOption(description="Current starboard name"),
                            new_name: str = SlashOption(description="New starboard name")):
        """Edit starboard name"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to edit starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == old_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{old_name}` not found.")
        
        # Check if new name already exists
        if any(sb.name == new_name for sb in starboards if sb.name != old_name):
            return await safe_reply(interaction, f"❌ A starboard named `{new_name}` already exists.")
        
        # Delete old config and create new one
        await self.delete_starboard_config(interaction.guild.id, old_name)
        config.update(name=new_name)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Starboard renamed from `{old_name}` to `{new_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to rename starboard. Please try again.")

    @starboard.subcommand(name="delete", description="Delete a starboard")
    async def starboard_delete(self,
                              interaction: nextcord.Interaction,
                              name: str = SlashOption(description="Starboard name to delete")):
        """Delete a starboard"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to delete starboards.")
        
        success = await self.delete_starboard_config(interaction.guild.id, name)
        if success:
            await safe_reply(interaction, f"✅ Starboard `{name}` has been deleted.")
        else:
            await safe_reply(interaction, f"❌ Starboard `{name}` not found.")

    @starboard.subcommand(name="track", description="Manage tracked emojis")
    async def starboard_track(self, interaction: nextcord.Interaction):
        pass

    @starboard_track.subcommand(name="add", description="Add emoji to track")
    async def starboard_track_add(self,
                                 interaction: nextcord.Interaction,
                                 starboard_name: str = SlashOption(description="Starboard name"),
                                 emoji: str = SlashOption(description="Emoji to track"),
                                 threshold: int = SlashOption(description="Number of reactions needed", min_value=1, max_value=50)):
        """Add emoji to track in starboard"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to manage starboard tracking.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        # Add emoji to tracked list
        config.data['tracked_emojis'][emoji] = threshold
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Now tracking {emoji} with threshold of {threshold} reactions in `{starboard_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to add emoji tracking. Please try again.")

    @starboard_track.subcommand(name="remove", description="Remove emoji from tracking")
    async def starboard_track_remove(self,
                                    interaction: nextcord.Interaction,
                                    starboard_name: str = SlashOption(description="Starboard name"),
                                    emoji: str = SlashOption(description="Emoji to stop tracking")):
        """Remove emoji from starboard tracking"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to manage starboard tracking.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if emoji not in config.tracked_emojis:
            return await safe_reply(interaction, f"❌ {emoji} is not being tracked in `{starboard_name}`")
        
        # Remove emoji from tracked list
        del config.data['tracked_emojis'][emoji]
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Stopped tracking {emoji} in `{starboard_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to remove emoji tracking. Please try again.")

    @starboard_track.subcommand(name="view", description="View tracked emojis")
    async def starboard_track_view(self,
                                  interaction: nextcord.Interaction,
                                  starboard_name: str = SlashOption(description="Starboard name")):
        """View tracked emojis for a starboard"""
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if not config.tracked_emojis:
            return await safe_reply(interaction, f"❌ No emojis are being tracked in `{starboard_name}`")
        
        embed = nextcord.Embed(
            title=f"📊 Tracked Emojis - {starboard_name}",
            color=nextcord.Color.blurple()
        )
        
        channel = self.bot.get_channel(config.channel_id)
        embed.description = f"**Channel:** {channel.mention if channel else 'Unknown'}\n\n"
        
        emoji_list = []
        for emoji, threshold in config.tracked_emojis.items():
            emoji_list.append(f"{emoji} → {threshold} reactions")
        
        embed.add_field(name="Tracked Emojis", value='\n'.join(emoji_list), inline=False)
        
        await safe_reply(interaction, embed=embed)

    @starboard.subcommand(name="config", description="Configure starboard settings")
    async def starboard_config(self, interaction: nextcord.Interaction):
        pass

    @starboard_config.subcommand(name="format", description="Set message format")
    async def starboard_config_format(self,
                                     interaction: nextcord.Interaction,
                                     starboard_name: str = SlashOption(description="Starboard name"),
                                     format_type: str = SlashOption(description="Message format", choices=["embed", "plaintext"])):
        """Set starboard message format"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(message_format=format_type)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Message format for `{starboard_name}` set to **{format_type}**")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="timestamp", description="Toggle timestamp display")
    async def starboard_config_timestamp(self,
                                        interaction: nextcord.Interaction,
                                        starboard_name: str = SlashOption(description="Starboard name"),
                                        enabled: bool = SlashOption(description="Show timestamps")):
        """Toggle timestamp display"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(show_timestamp=enabled)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            status = "enabled" if enabled else "disabled"
            await safe_reply(interaction, f"✅ Timestamps {status} for `{starboard_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="color", description="Set embed color")
    async def starboard_config_color(self,
                                    interaction: nextcord.Interaction,
                                    starboard_name: str = SlashOption(description="Starboard name"),
                                    color_mode: str = SlashOption(description="Color mode", 
                                                                choices=["none", "default", "random", "hex"]),
                                    hex_color: str = SlashOption(description="Hex color (if using hex mode)", required=False)):
        """Set embed color mode"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if color_mode == "hex":
            if not hex_color:
                return await safe_reply(interaction, "❌ Hex color is required when using hex mode.")
            
            # Validate hex color
            hex_color = hex_color.replace('#', '')
            if not re.match(r'^[0-9A-Fa-f]{6}$', hex_color):
                return await safe_reply(interaction, "❌ Invalid hex color format. Use format like `FF4A44`")
            
            config.update(color_mode=color_mode, custom_color=hex_color)
        else:
            config.update(color_mode=color_mode)
        
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            if color_mode == "hex":
                await safe_reply(interaction, f"✅ Color for `{starboard_name}` set to **{color_mode}** (`#{hex_color}`)")
            else:
                await safe_reply(interaction, f"✅ Color for `{starboard_name}` set to **{color_mode}**")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="thumbnail", description="Set thumbnail source")
    async def starboard_config_thumbnail(self,
                                        interaction: nextcord.Interaction,
                                        starboard_name: str = SlashOption(description="Starboard name"),
                                        source: str = SlashOption(description="Thumbnail source", 
                                                                choices=["author.icon", "server.icon", "bot.icon", "url", "off"]),
                                        url: str = SlashOption(description="Custom URL (if using url source)", required=False)):
        """Set thumbnail source"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if source == "url":
            if not url:
                return await safe_reply(interaction, "❌ URL is required when using URL source.")
            if not url.startswith(('http://', 'https://')):
                return await safe_reply(interaction, "❌ URL must start with http:// or https://")
            config.update(thumbnail_source=url)
        else:
            config.update(thumbnail_source=source)
        
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            display_source = url if source == "url" else source
            await safe_reply(interaction, f"✅ Thumbnail source for `{starboard_name}` set to **{display_source}**")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="attachments", description="Configure attachment display")
    async def starboard_config_attachments(self,
                                          interaction: nextcord.Interaction,
                                          starboard_name: str = SlashOption(description="Starboard name"),
                                          enabled: bool = SlashOption(description="Show attachments")):
        """Configure attachment display"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(show_attachments=enabled)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            status = "enabled" if enabled else "disabled"
            await safe_reply(interaction, f"✅ Attachments {status} for `{starboard_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="duplicates", description="Configure duplicate emoji display")
    async def starboard_config_duplicates(self,
                                         interaction: nextcord.Interaction,
                                         starboard_name: str = SlashOption(description="Starboard name"),
                                         multiple: bool = SlashOption(description="Show multiple emojis")):
        """Configure duplicate emoji display"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(show_duplicates=multiple)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            status = "enabled" if multiple else "disabled"
            await safe_reply(interaction, f"✅ Multiple emoji display {status} for `{starboard_name}`")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="max_emojis", description="Set maximum duplicate emojis to show")
    async def starboard_config_max_emojis(self,
                                         interaction: nextcord.Interaction,
                                         starboard_name: str = SlashOption(description="Starboard name"),
                                         max_count: int = SlashOption(description="Maximum emojis to show", min_value=1, max_value=20)):
        """Set maximum duplicate emojis to show"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(max_duplicate_emojis=max_count)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Maximum emoji display for `{starboard_name}` set to **{max_count}**")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="title", description="Set custom embed title")
    async def starboard_config_title(self,
                                    interaction: nextcord.Interaction,
                                    starboard_name: str = SlashOption(description="Starboard name"),
                                    title: str = SlashOption(description="Custom title (use 'none' to disable)", required=False)):
        """Set custom embed title"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if title and title.lower() != 'none':
            config.update(embed_title=title)
            await safe_reply(interaction, f"✅ Custom title for `{starboard_name}` set to: **{title}**")
        else:
            config.update(embed_title=None)
            await safe_reply(interaction, f"✅ Custom title disabled for `{starboard_name}`")
        
        await self.save_starboard_config(interaction.guild.id, config)

    @starboard_config.subcommand(name="description", description="Set custom embed description")
    async def starboard_config_description(self,
                                          interaction: nextcord.Interaction,
                                          starboard_name: str = SlashOption(description="Starboard name"),
                                          description: str = SlashOption(description="Custom description template")):
        """Set custom embed description"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        config.update(embed_description=description)
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            await safe_reply(interaction, f"✅ Custom description for `{starboard_name}` updated\n**Preview:** {description[:100]}{'...' if len(description) > 100 else ''}")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard_config.subcommand(name="role_filter", description="Configure role-based attachment filtering")
    async def starboard_config_role_filter(self,
                                          interaction: nextcord.Interaction,
                                          starboard_name: str = SlashOption(description="Starboard name"),
                                          filter_type: str = SlashOption(description="Filter type", 
                                                                       choices=["off", "role", "whitelist", "blacklist"]),
                                          role: nextcord.Role = SlashOption(description="Role for filtering", required=False)):
        """Configure role-based attachment filtering"""
        if not interaction.user.guild_permissions.manage_channels:
            return await safe_reply(interaction, "❌ You need **Manage Channels** permission to configure starboards.")
        
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        if filter_type == "role" and not role:
            return await safe_reply(interaction, "❌ Role is required when using role-based filtering.")
        
        config.update(attachment_filter=filter_type)
        if role:
            config.data['attachment_roles'] = [role.id]
        else:
            config.data['attachment_roles'] = []
        
        success = await self.save_starboard_config(interaction.guild.id, config)
        
        if success:
            if filter_type == "role":
                await safe_reply(interaction, f"✅ Attachment filter for `{starboard_name}` set to **{filter_type}** with role {role.mention}")
            else:
                await safe_reply(interaction, f"✅ Attachment filter for `{starboard_name}` set to **{filter_type}**")
        else:
            await safe_reply(interaction, "❌ Failed to update configuration. Please try again.")

    @starboard.subcommand(name="variables", description="View available message variables")
    async def starboard_variables(self, interaction: nextcord.Interaction):
        """View available message variables"""
        embed = nextcord.Embed(
            title="📝 Starboard Message Variables",
            description="Use these variables in custom embed titles and descriptions:",
            color=nextcord.Color.blurple()
        )
        
        for variable, description in self.message_variables.items():
            embed.add_field(name=f"`{variable}`", value=description, inline=False)
        
        await safe_reply(interaction, embed=embed)

    @starboard.subcommand(name="list", description="List all starboards")
    async def starboard_list(self, interaction: nextcord.Interaction):
        """List all starboards in the server"""
        starboards = await self.get_guild_starboards(interaction.guild.id)
        
        if not starboards:
            return await safe_reply(interaction, "❌ No starboards configured in this server.")
        
        embed = nextcord.Embed(
            title="⭐ Server Starboards",
            color=nextcord.Color.gold()
        )
        
        for config in starboards:
            channel = self.bot.get_channel(config.channel_id)
            channel_mention = channel.mention if channel else "Unknown Channel"
            
            emoji_count = len(config.tracked_emojis)
            format_type = config.message_format.title()
            
            value = f"**Channel:** {channel_mention}\n"
            value += f"**Format:** {format_type}\n"
            value += f"**Tracked Emojis:** {emoji_count}\n"
            value += f"**Timestamp:** {'On' if config.show_timestamp else 'Off'}"
            
            embed.add_field(name=config.name, value=value, inline=True)
        
        await safe_reply(interaction, embed=embed)

    @starboard.subcommand(name="info", description="View starboard configuration")
    async def starboard_info(self,
                            interaction: nextcord.Interaction,
                            starboard_name: str = SlashOption(description="Starboard name")):
        """View detailed starboard configuration"""
        starboards = await self.get_guild_starboards(interaction.guild.id)
        config = None
        for sb in starboards:
            if sb.name == starboard_name:
                config = sb
                break
        
        if not config:
            return await safe_reply(interaction, f"❌ Starboard `{starboard_name}` not found.")
        
        channel = self.bot.get_channel(config.channel_id)
        channel_mention = channel.mention if channel else "Unknown Channel"
        
        embed = nextcord.Embed(
            title=f"⭐ Starboard Configuration: {starboard_name}",
            color=nextcord.Color.gold()
        )
        
        # Basic info
        embed.add_field(
            name="📍 Basic Settings",
            value=f"**Channel:** {channel_mention}\n"
                  f"**Format:** {config.message_format.title()}\n"
                  f"**Timestamp:** {'Enabled' if config.show_timestamp else 'Disabled'}",
            inline=False
        )
        
        # Tracked emojis
        if config.tracked_emojis:
            emoji_list = []
            for emoji, threshold in config.tracked_emojis.items():
                emoji_list.append(f"{emoji} → {threshold}")
            
            embed.add_field(
                name="🎯 Tracked Emojis",
                value='\n'.join(emoji_list),
                inline=False
            )
        else:
            embed.add_field(
                name="🎯 Tracked Emojis",
                value="No emojis configured",
                inline=False
            )
        
        # Display settings
        embed.add_field(
            name="🎨 Display Settings",
            value=f"**Color Mode:** {config.color_mode.title()}\n"
                  f"**Thumbnail:** {config.thumbnail_source}\n"
                  f"**Attachments:** {'Enabled' if config.show_attachments else 'Disabled'}\n"
                  f"**Duplicates:** {'Enabled' if config.show_duplicates else 'Disabled'}\n"
                  f"**Max Emojis:** {config.max_duplicate_emojis}",
            inline=False
        )
        
        # Custom settings
        custom_settings = []
        if config.embed_title:
            custom_settings.append(f"**Title:** {config.embed_title[:50]}{'...' if len(config.embed_title) > 50 else ''}")
        if config.embed_description != '{message.content}':
            custom_settings.append(f"**Description:** {config.embed_description[:50]}{'...' if len(config.embed_description) > 50 else ''}")
        if config.color_mode == 'hex':
            custom_settings.append(f"**Custom Color:** #{config.custom_color}")
        
        if custom_settings:
            embed.add_field(
                name="⚙️ Custom Settings",
                value='\n'.join(custom_settings),
                inline=False
            )
        
        await safe_reply(interaction, embed=embed)

def setup(bot):
    bot.add_cog(Starboard(bot))
