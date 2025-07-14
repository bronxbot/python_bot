"""
Comprehensive Fishing System for BronxBot
Features scalable rarity tiers, expandable rod/bait effects, and event fish
"""

import nextcord
from nextcord.ext import commands
import json
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from utils.logger import get_logger
from utils.bot_utils import (
    format_currency, get_rarity_color, get_rarity_emoji, 
    create_error_embed, create_success_embed, create_info_embed,
    safe_send, cooldown_manager
)
from config.settings import FISHING_CONFIG

logger = get_logger(__name__)


class FishingSystem:
    """Core fishing system logic"""
    
    def __init__(self):
        self.fish_data = self.load_fish_data()
        self.rod_data = self.load_rod_data()
        self.bait_data = self.load_bait_data()
        self.rarity_order = [
            "common", "uncommon", "rare", "epic", "legendary", 
            "galactic", "intergalactic", "godlike", "mythical", 
            "impossible", "otherworldly"
        ]
    
    def load_fish_data(self) -> Dict[str, Any]:
        """Load fish data from JSON file"""
        try:
            with open(Path("data/fish.json"), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Fish data file not found")
            return {"fish": {}}
    
    def load_rod_data(self) -> Dict[str, Any]:
        """Load rod data from JSON file"""
        try:
            with open(Path("data/rods.json"), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Rod data file not found")
            return {"rods": {}, "rod_effects": {}}
    
    def load_bait_data(self) -> Dict[str, Any]:
        """Load bait data from JSON file"""
        try:
            with open(Path("data/bait.json"), "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("Bait data file not found")
            return {"bait": {}, "bait_effects": {}}
    
    def save_fish_data(self):
        """Save fish data to JSON file"""
        with open(Path("data/fish.json"), "w") as f:
            json.dump(self.fish_data, f, indent=2)
    
    def calculate_catch_chances(self, rod_name: str, bait_name: str) -> Dict[str, float]:
        """Calculate catch chances based on rod and bait"""
        base_chances = {
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
        
        # Apply rod bonuses
        rod = self.rod_data["rods"].get(rod_name, {})
        luck_bonus = rod.get("luck_bonus", 0) / 100
        
        # Apply bait bonuses
        bait = self.bait_data["bait"].get(bait_name, {})
        rarity_bonus = bait.get("rarity_bonus", 0)
        
        # Calculate modified chances
        modified_chances = {}
        for rarity, chance in base_chances.items():
            # Apply bonuses
            modified_chance = chance * (1 + luck_bonus + rarity_bonus)
            modified_chances[rarity] = modified_chance
        
        # Normalize to ensure they sum to 1
        total = sum(modified_chances.values())
        for rarity in modified_chances:
            modified_chances[rarity] /= total
        
        return modified_chances
    
    def select_fish_rarity(self, chances: Dict[str, float]) -> str:
        """Select a fish rarity based on chances"""
        rand = random.random()
        cumulative = 0
        
        for rarity in self.rarity_order:
            cumulative += chances.get(rarity, 0)
            if rand <= cumulative:
                return rarity
        
        return "common"  # Fallback
    
    def get_random_fish(self, rarity: str, event_type: str = None) -> Optional[Dict[str, Any]]:
        """Get a random fish of the specified rarity"""
        fish_list = []
        
        # Check for event fish first
        if event_type and "event" in self.fish_data["fish"]:
            event_fish = self.fish_data["fish"]["event"]
            for fish_id, fish_data in event_fish.items():
                if fish_data.get("event_type") == event_type:
                    fish_list.append((fish_id, fish_data))
        
        # If no event fish or no event type, get regular fish
        if not fish_list and rarity in self.fish_data["fish"]:
            rarity_fish = self.fish_data["fish"][rarity]
            for fish_id, fish_data in rarity_fish.items():
                fish_list.append((fish_id, fish_data))
        
        if not fish_list:
            return None
        
        fish_id, fish_data = random.choice(fish_list)
        fish_data["id"] = fish_id
        return fish_data
    
    def calculate_fish_value(self, fish: Dict[str, Any], rod_name: str, bait_name: str) -> int:
        """Calculate the value of a caught fish"""
        base_value = fish.get("base_value", 0)
        
        # Apply rod bonuses
        rod = self.rod_data["rods"].get(rod_name, {})
        value_bonus = rod.get("value_bonus", 0) / 100
        
        # Apply bait bonuses
        bait = self.bait_data["bait"].get(bait_name, {})
        effectiveness = bait.get("effectiveness", 1.0)
        
        # Apply rarity multiplier
        rarity = self.get_fish_rarity(fish)
        rarity_multiplier = FISHING_CONFIG["rarity_multipliers"].get(rarity, 1.0)
        
        final_value = int(base_value * (1 + value_bonus) * effectiveness * rarity_multiplier)
        return max(final_value, 1)
    
    def get_fish_rarity(self, fish: Dict[str, Any]) -> str:
        """Determine the rarity of a fish"""
        # Check all rarity categories
        for rarity in self.rarity_order:
            if rarity in self.fish_data["fish"]:
                for fish_id, fish_data in self.fish_data["fish"][rarity].items():
                    if fish_data.get("name") == fish.get("name"):
                        return rarity
        
        # Check event fish
        if "event" in self.fish_data["fish"]:
            for fish_id, fish_data in self.fish_data["fish"]["event"].items():
                if fish_data.get("name") == fish.get("name"):
                    return "event"
        
        return "common"  # Fallback
    
    def is_seasonal_available(self, event_type: str) -> bool:
        """Check if seasonal fish are available"""
        now = datetime.now()
        
        if event_type == "christmas":
            return now.month == 12 and now.day >= 20
        elif event_type == "halloween":
            return now.month == 10 and now.day >= 25
        elif event_type == "new_year":
            return (now.month == 12 and now.day >= 30) or (now.month == 1 and now.day <= 5)
        elif event_type == "anniversary":
            # Bot anniversary - adjust date as needed
            return now.month == 1 and now.day == 1
        
        return False
    
    def can_use_bait(self, bait_name: str) -> bool:
        """Check if bait can be used (seasonal restrictions)"""
        bait = self.bait_data["bait"].get(bait_name, {})
        
        if bait.get("seasonal", False):
            event_type = bait.get("event_type")
            return self.is_seasonal_available(event_type)
        
        return True
    
    def apply_rod_effects(self, rod_name: str, fish: Dict[str, Any], value: int) -> tuple:
        """Apply rod effects to caught fish"""
        rod = self.rod_data["rods"].get(rod_name, {})
        effects = rod.get("effects", [])
        
        modified_fish = fish.copy()
        modified_value = value
        
        for effect_name in effects:
            effect = self.rod_data["rod_effects"].get(effect_name, {})
            effect_type = effect.get("effect_type")
            
            if effect_type == "value_multiplier":
                modified_value = int(modified_value * effect.get("value", 1.0))
            elif effect_type == "guaranteed_rarity":
                # This would be handled in the fishing logic
                pass
        
        return modified_fish, modified_value


class Fishing(commands.Cog):
    """Fishing commands and functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.fishing_system = FishingSystem()
        self.active_fishing = {}  # Track active fishing sessions
    
    @commands.group(name="fish", invoke_without_command=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def fish(self, ctx):
        """Go fishing! Cast your line and catch some fish."""
        user_id = ctx.author.id
        
        # Check if user is already fishing
        if user_id in self.active_fishing:
            embed = create_error_embed(
                "Already Fishing",
                "You're already fishing! Wait for your current session to complete."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        fishing_data = user_data.get("fishing", {})
        current_rod = fishing_data.get("rod", "basic_rod")
        current_bait = fishing_data.get("bait", "basic_bait")
        
        # Check if bait can be used
        if not self.fishing_system.can_use_bait(current_bait):
            embed = create_error_embed(
                "Seasonal Bait",
                f"Your current bait ({current_bait}) can only be used during its season!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Start fishing session
        self.active_fishing[user_id] = True
        
        # Create fishing embed
        embed = create_info_embed(
            "🎣 Fishing",
            f"🎣 **Rod:** {current_rod}\n"
            f"🪱 **Bait:** {current_bait}\n\n"
            f"🌊 Casting your line... This may take a moment."
        )
        message = await safe_send(ctx, embed=embed)
        
        try:
            # Calculate fishing time
            base_time = FISHING_CONFIG["base_catch_time"]
            max_time = FISHING_CONFIG["max_catch_time"]
            fishing_time = random.randint(base_time, max_time)
            
            # Wait for fishing time
            await asyncio.sleep(fishing_time)
            
            # Calculate catch chances
            chances = self.fishing_system.calculate_catch_chances(current_rod, current_bait)
            
            # Select fish rarity
            selected_rarity = self.fishing_system.select_fish_rarity(chances)
            
            # Check for event fish
            event_type = None
            bait_data = self.fishing_system.bait_data["bait"].get(current_bait, {})
            if bait_data.get("seasonal", False):
                event_type = bait_data.get("event_type")
            
            # Get random fish
            fish = self.fishing_system.get_random_fish(selected_rarity, event_type)
            
            if not fish:
                # No fish caught
                embed = create_error_embed(
                    "No Catch",
                    "🌊 The fish weren't biting this time. Try again!"
                )
                await message.edit(embed=embed)
                return
            
            # Calculate fish value
            fish_value = self.fishing_system.calculate_fish_value(fish, current_rod, current_bait)
            
            # Apply rod effects
            fish, fish_value = self.fishing_system.apply_rod_effects(current_rod, fish, fish_value)
            
            # Update user data
            await self.bot.db.add_fish_catch(user_id, fish["id"], selected_rarity, fish_value)
            await self.bot.db.update_balance(user_id, wallet_change=fish_value)
            
            # Create success embed
            rarity_color = get_rarity_color(selected_rarity)
            rarity_emoji = get_rarity_emoji(selected_rarity)
            
            embed = nextcord.Embed(
                title="🎣 Fish Caught!",
                color=rarity_color
            )
            embed.add_field(
                name="🐟 Fish",
                value=f"{fish['icon']} **{fish['name']}**",
                inline=True
            )
            embed.add_field(
                name="⭐ Rarity",
                value=f"{rarity_emoji} {selected_rarity.title()}",
                inline=True
            )
            embed.add_field(
                name="💰 Value",
                value=format_currency(fish_value, self.bot.currency_emoji),
                inline=True
            )
            embed.add_field(
                name="📝 Description",
                value=fish["description"],
                inline=False
            )
            embed.add_field(
                name="😊 Personality",
                value=fish["personality"],
                inline=False
            )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in fishing command: {e}")
            embed = create_error_embed(
                "Fishing Error",
                "Something went wrong while fishing. Please try again."
            )
            await message.edit(embed=embed)
        
        finally:
            # Remove from active fishing
            self.active_fishing.pop(user_id, None)
    
    @fish.command(name="inventory", aliases=["inv", "collection"])
    async def fish_inventory(self, ctx):
        """View your fish collection"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Data",
                "You haven't started fishing yet! Use `!fish` to begin."
            )
            await safe_send(ctx, embed=embed)
            return
        
        fishing_data = user_data.get("fishing", {})
        catches = fishing_data.get("catches", {})
        
        if not catches:
            embed = create_info_embed(
                "Empty Collection",
                "You haven't caught any fish yet! Use `!fish` to start fishing."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Group fish by rarity
        rarity_groups = {}
        fish_data = self.fishing_system.fish_data["fish"]
        
        for fish_id, count in catches.items():
            fish_info = None
            fish_rarity = None
            
            # Find fish in data
            for rarity, fish_list in fish_data.items():
                if fish_id in fish_list:
                    fish_info = fish_list[fish_id]
                    fish_rarity = rarity
                    break
            
            if fish_info:
                if fish_rarity not in rarity_groups:
                    rarity_groups[fish_rarity] = []
                rarity_groups[fish_rarity].append({
                    "name": fish_info["name"],
                    "icon": fish_info["icon"],
                    "count": count
                })
        
        # Create embed
        embed = nextcord.Embed(
            title=f"🎣 {ctx.author.display_name}'s Fish Collection",
            color=0x0080ff
        )
        
        # Add fields for each rarity
        for rarity in self.fishing_system.rarity_order:
            if rarity in rarity_groups:
                fish_list = rarity_groups[rarity]
                rarity_emoji = get_rarity_emoji(rarity)
                
                fish_text = "\n".join([
                    f"{fish['icon']} {fish['name']} x{fish['count']}"
                    for fish in fish_list
                ])
                
                embed.add_field(
                    name=f"{rarity_emoji} {rarity.title()}",
                    value=fish_text,
                    inline=True
                )
        
        # Add statistics
        total_catches = fishing_data.get("total_catches", 0)
        total_value = fishing_data.get("total_value", 0)
        
        embed.add_field(
            name="📊 Statistics",
            value=f"**Total Catches:** {total_catches}\n"
                  f"**Total Value:** {format_currency(total_value, self.bot.currency_emoji)}",
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @fish.command(name="rod")
    async def fish_rod(self, ctx, *, rod_name: str = None):
        """View or change your fishing rod"""
        user_id = ctx.author.id
        
        if not rod_name:
            # Show current rod
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            fishing_data = user_data.get("fishing", {})
            current_rod = fishing_data.get("rod", "basic_rod")
            
            rod_info = self.fishing_system.rod_data["rods"].get(current_rod, {})
            
            embed = nextcord.Embed(
                title="🎣 Current Fishing Rod",
                color=0x0080ff
            )
            embed.add_field(
                name="🎣 Rod",
                value=f"{rod_info.get('icon', '🎣')} **{rod_info.get('name', 'Unknown')}**",
                inline=False
            )
            embed.add_field(
                name="📝 Description",
                value=rod_info.get("description", "No description available"),
                inline=False
            )
            
            # Add stats
            stats_text = f"**Durability:** {rod_info.get('durability', 0)}\n"
            stats_text += f"**Catch Bonus:** +{rod_info.get('catch_bonus', 0)}%\n"
            stats_text += f"**Luck Bonus:** +{rod_info.get('luck_bonus', 0)}%\n"
            stats_text += f"**Value Bonus:** +{rod_info.get('value_bonus', 0)}%"
            
            embed.add_field(
                name="📊 Stats",
                value=stats_text,
                inline=False
            )
            
            # Add effects
            effects = rod_info.get("effects", [])
            if effects:
                effect_text = "\n".join([
                    f"• {self.fishing_system.rod_data['rod_effects'].get(effect, {}).get('name', effect)}"
                    for effect in effects
                ])
                embed.add_field(
                    name="✨ Effects",
                    value=effect_text,
                    inline=False
                )
            
            await safe_send(ctx, embed=embed)
        else:
            # Change rod (implementation depends on shop system)
            embed = create_info_embed(
                "Rod Selection",
                f"Rod changing will be available once you purchase `{rod_name}` from the shop!"
            )
            await safe_send(ctx, embed=embed)
    
    @fish.command(name="bait")
    async def fish_bait(self, ctx, *, bait_name: str = None):
        """View or change your fishing bait"""
        user_id = ctx.author.id
        
        if not bait_name:
            # Show current bait
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            fishing_data = user_data.get("fishing", {})
            current_bait = fishing_data.get("bait", "basic_bait")
            
            bait_info = self.fishing_system.bait_data["bait"].get(current_bait, {})
            
            embed = nextcord.Embed(
                title="🪱 Current Fishing Bait",
                color=0x0080ff
            )
            embed.add_field(
                name="🪱 Bait",
                value=f"{bait_info.get('icon', '🪱')} **{bait_info.get('name', 'Unknown')}**",
                inline=False
            )
            embed.add_field(
                name="📝 Description",
                value=bait_info.get("description", "No description available"),
                inline=False
            )
            
            # Add stats
            stats_text = f"**Effectiveness:** {bait_info.get('effectiveness', 1.0)}x\n"
            stats_text += f"**Luck Bonus:** +{bait_info.get('luck_bonus', 0)}%\n"
            stats_text += f"**Rarity Bonus:** +{bait_info.get('rarity_bonus', 0):.1f}"
            
            embed.add_field(
                name="📊 Stats",
                value=stats_text,
                inline=False
            )
            
            # Add seasonal info
            if bait_info.get("seasonal", False):
                event_type = bait_info.get("event_type", "unknown")
                available = self.fishing_system.is_seasonal_available(event_type)
                status = "🟢 Available" if available else "🔴 Not Available"
                
                embed.add_field(
                    name="🗓️ Seasonal",
                    value=f"**Event:** {event_type.title()}\n**Status:** {status}",
                    inline=False
                )
            
            await safe_send(ctx, embed=embed)
        else:
            # Change bait (implementation depends on shop system)
            embed = create_info_embed(
                "Bait Selection",
                f"Bait changing will be available once you purchase `{bait_name}` from the shop!"
            )
            await safe_send(ctx, embed=embed)
    
    @fish.command(name="stats")
    async def fish_stats(self, ctx):
        """View your fishing statistics"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Data",
                "You haven't started fishing yet! Use `!fish` to begin."
            )
            await safe_send(ctx, embed=embed)
            return
        
        fishing_data = user_data.get("fishing", {})
        
        embed = nextcord.Embed(
            title=f"🎣 {ctx.author.display_name}'s Fishing Statistics",
            color=0x0080ff
        )
        
        # Basic stats
        total_catches = fishing_data.get("total_catches", 0)
        total_value = fishing_data.get("total_value", 0)
        
        embed.add_field(
            name="📊 Overall Stats",
            value=f"**Total Catches:** {total_catches}\n"
                  f"**Total Value:** {format_currency(total_value, self.bot.currency_emoji)}\n"
                  f"**Average Value:** {format_currency(total_value // max(total_catches, 1), self.bot.currency_emoji)}",
            inline=False
        )
        
        # Rarity breakdown
        catches = fishing_data.get("catches", {})
        rarity_counts = {}
        
        for fish_id, count in catches.items():
            # Find fish rarity
            fish_rarity = None
            for rarity, fish_list in self.fishing_system.fish_data["fish"].items():
                if fish_id in fish_list:
                    fish_rarity = rarity
                    break
            
            if fish_rarity:
                rarity_counts[fish_rarity] = rarity_counts.get(fish_rarity, 0) + count
        
        if rarity_counts:
            rarity_text = "\n".join([
                f"{get_rarity_emoji(rarity)} {rarity.title()}: {count}"
                for rarity, count in rarity_counts.items()
            ])
            
            embed.add_field(
                name="⭐ Rarity Breakdown",
                value=rarity_text,
                inline=False
            )
        
        await safe_send(ctx, embed=embed)
    
    @fish.command(name="leaderboard", aliases=["lb"])
    async def fish_leaderboard(self, ctx):
        """View the fishing leaderboard"""
        # Get top fishers
        leaderboard = await self.bot.db.get_leaderboard("fishing.total_catches", 10)
        
        if not leaderboard:
            embed = create_info_embed(
                "Empty Leaderboard",
                "No one has started fishing yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        embed = nextcord.Embed(
            title="🎣 Fishing Leaderboard",
            color=0x0080ff
        )
        
        leaderboard_text = ""
        for i, user_data in enumerate(leaderboard, 1):
            user = self.bot.get_user(user_data["user_id"])
            username = user.display_name if user else "Unknown User"
            
            fishing_data = user_data.get("fishing", {})
            total_catches = fishing_data.get("total_catches", 0)
            total_value = fishing_data.get("total_value", 0)
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{medal} **{username}**\n"
            leaderboard_text += f"   Catches: {total_catches} | Value: {format_currency(total_value, self.bot.currency_emoji)}\n\n"
        
        embed.description = leaderboard_text
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Fishing(bot))
