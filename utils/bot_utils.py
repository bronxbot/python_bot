"""
Bot utilities and helper functions
"""

import asyncio
import time
from typing import Union, Optional, Dict, Any
import nextcord
from nextcord.ext import commands

from config.settings import Settings


def get_prefix(bot, message):
    """Get the bot prefix for a message"""
    # Could be customized per guild in the future
    return "!"


def format_currency(amount: int, currency_emoji: str = "<:bronkbuk:123456789>") -> str:
    """Format currency amount with emoji"""
    return f"{currency_emoji} {amount:,}"


def format_time(seconds: float) -> str:
    """Format time in a human-readable way"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def calculate_rarity_chance(rarity: str) -> float:
    """Calculate the chance of getting a specific rarity"""
    rarity_chances = {
        "common": 0.35,
        "uncommon": 0.25,
        "rare": 0.15,
        "epic": 0.10,
        "legendary": 0.07,
        "galactic": 0.04,
        "intergalactic": 0.025,
        "godlike": 0.01,
        "mythical": 0.005,
        "impossible": 0.002,
        "otherworldly": 0.001
    }
    return rarity_chances.get(rarity, 0.0)


def get_rarity_color(rarity: str) -> int:
    """Get the color associated with a rarity"""
    colors = {
        "common": 0x808080,      # Gray
        "uncommon": 0x00ff00,    # Green
        "rare": 0x0080ff,        # Blue
        "epic": 0x8000ff,        # Purple
        "legendary": 0xff8000,   # Orange
        "galactic": 0xff0080,    # Pink
        "intergalactic": 0x00ffff, # Cyan
        "godlike": 0xffff00,     # Yellow
        "mythical": 0xff0000,    # Red
        "impossible": 0x000000,  # Black
        "otherworldly": 0xffffff # White
    }
    return colors.get(rarity, 0x808080)


def get_rarity_emoji(rarity: str) -> str:
    """Get the emoji associated with a rarity"""
    emojis = {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟠",
        "galactic": "🟡",
        "intergalactic": "🔴",
        "godlike": "⚫",
        "mythical": "🌟",
        "impossible": "💀",
        "otherworldly": "✨"
    }
    return emojis.get(rarity, "❓")


class Cooldowns:
    """Manage command cooldowns"""
    
    def __init__(self):
        self.cooldowns: Dict[str, Dict[int, float]] = {}
    
    def is_on_cooldown(self, command: str, user_id: int, cooldown_time: float) -> bool:
        """Check if a user is on cooldown for a command"""
        if command not in self.cooldowns:
            self.cooldowns[command] = {}
        
        user_cooldowns = self.cooldowns[command]
        current_time = time.time()
        
        if user_id in user_cooldowns:
            if current_time - user_cooldowns[user_id] < cooldown_time:
                return True
        
        user_cooldowns[user_id] = current_time
        return False
    
    def get_remaining_cooldown(self, command: str, user_id: int, cooldown_time: float) -> float:
        """Get remaining cooldown time"""
        if command not in self.cooldowns or user_id not in self.cooldowns[command]:
            return 0.0
        
        elapsed = time.time() - self.cooldowns[command][user_id]
        remaining = cooldown_time - elapsed
        return max(0.0, remaining)


class PaginatedEmbed:
    """Create paginated embeds"""
    
    def __init__(self, title: str, description: str = None, color: int = 0x00ff00):
        self.title = title
        self.description = description
        self.color = color
        self.pages = []
        self.current_page = 0
    
    def add_page(self, content: str, title: str = None):
        """Add a page to the embed"""
        page = {
            "title": title or self.title,
            "description": content,
            "color": self.color
        }
        self.pages.append(page)
    
    def get_embed(self, page_num: int = 0) -> nextcord.Embed:
        """Get the embed for a specific page"""
        if not self.pages or page_num >= len(self.pages):
            return nextcord.Embed(title="Error", description="Page not found")
        
        page = self.pages[page_num]
        embed = nextcord.Embed(
            title=page["title"],
            description=page["description"],
            color=page["color"]
        )
        
        if len(self.pages) > 1:
            embed.set_footer(text=f"Page {page_num + 1}/{len(self.pages)}")
        
        return embed
    
    def get_view(self):
        """Get the view with navigation buttons"""
        if len(self.pages) <= 1:
            return None
        
        return PaginationView(self)


class PaginationView(nextcord.ui.View):
    """View for paginated embeds"""
    
    def __init__(self, paginated_embed: PaginatedEmbed):
        super().__init__(timeout=300)
        self.paginated_embed = paginated_embed
        self.current_page = 0
    
    @nextcord.ui.button(label="◀️", style=nextcord.ButtonStyle.primary)
    async def previous_page(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.paginated_embed.get_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="▶️", style=nextcord.ButtonStyle.primary)
    async def next_page(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Go to next page"""
        if self.current_page < len(self.paginated_embed.pages) - 1:
            self.current_page += 1
            embed = self.paginated_embed.get_embed(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for item in self.children:
            item.disabled = True


def create_error_embed(title: str, description: str) -> nextcord.Embed:
    """Create a standardized error embed"""
    embed = nextcord.Embed(
        title=f"❌ {title}",
        description=description,
        color=0xff0000
    )
    return embed


def create_success_embed(title: str, description: str) -> nextcord.Embed:
    """Create a standardized success embed"""
    embed = nextcord.Embed(
        title=f"✅ {title}",
        description=description,
        color=0x00ff00
    )
    return embed


def create_info_embed(title: str, description: str) -> nextcord.Embed:
    """Create a standardized info embed"""
    embed = nextcord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=0x0080ff
    )
    return embed


async def safe_send(ctx, content=None, embed=None, view=None):
    """Safely send a message, handling potential errors"""
    try:
        if hasattr(ctx, 'response'):
            # Interaction context
            if ctx.response.is_done():
                await ctx.followup.send(content=content, embed=embed, view=view)
            else:
                await ctx.response.send_message(content=content, embed=embed, view=view)
        else:
            # Regular context
            await ctx.send(content=content, embed=embed, view=view)
    except Exception as e:
        print(f"Error sending message: {e}")


# Global cooldown manager
cooldown_manager = Cooldowns()
