"""
Fishing System for BronxBot
Comprehensive fishing system with rods, bait, and scalable rarities
"""

import nextcord
from nextcord.ext import commands
import json
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed, 
    create_info_embed, safe_send, cooldown_manager
)
from config.settings import ECONOMY_CONFIG

logger = get_logger(__name__)


class Fishing(commands.Cog):
    """Fishing system with rods, bait, and catches"""
    
    def __init__(self, bot):
        self.bot = bot
        self.fish_data = {}
        self.rod_data = {}
        self.bait_data = {}
        self._data_loaded = False
        self.rarity_weights = {
            "common": 50,
            "uncommon": 30,
            "rare": 12,
            "epic": 5,
            "legendary": 2,
            "galactic": 0.7,
            "intergalactic": 0.2,
            "godlike": 0.08,
            "mythical": 0.02,
            "impossible": 0.005,
            "otherworldly": 0.001
        }
        # Load data in background during cog initialization
        asyncio.create_task(self.load_fishing_data())
    
    async def load_fishing_data(self):
        """Load fishing data from JSON files asynchronously"""
        try:
            import aiofiles
            
            async with aiofiles.open("data/fish.json", "r") as f:
                content = await f.read()
                self.fish_data = json.loads(content)
                
            async with aiofiles.open("data/rods.json", "r") as f:
                content = await f.read()
                self.rod_data = json.loads(content)
                
            async with aiofiles.open("data/bait.json", "r") as f:
                content = await f.read()
                self.bait_data = json.loads(content)
                
            self._data_loaded = True
            logger.info("Fishing data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading fishing data: {e}")
            # Fallback to synchronous loading
            self.load_fishing_data_sync()
    
    def load_fishing_data_sync(self):
        """Fallback synchronous data loading"""
        try:
            with open("data/fish.json", "r") as f:
                self.fish_data = json.load(f)
            with open("data/rods.json", "r") as f:
                self.rod_data = json.load(f)
            with open("data/bait.json", "r") as f:
                self.bait_data = json.load(f)
            self._data_loaded = True
            logger.info("Fishing data loaded successfully (sync)")
        except Exception as e:
            logger.error(f"Error loading fishing data: {e}")
            self.fish_data = {}
            self.rod_data = {}
            self.bait_data = {}
    
    async def ensure_data_loaded(self):
        """Ensure fishing data is loaded before use"""
        if not self._data_loaded:
            await self.load_fishing_data()
        
        # Wait up to 5 seconds for data to load
        for _ in range(50):
            if self._data_loaded:
                break
            await asyncio.sleep(0.1)
        
        if not self._data_loaded:
            logger.warning("Fishing data not loaded, using empty data")
    
    def calculate_catch_chances(self, rod_id: str, bait_id: str) -> Dict[str, float]:
        """Calculate catch chances based on rod and bait"""
        base_weights = self.rarity_weights.copy()
        
        # Apply rod effects
        if rod_id in self.rod_data:
            rod = self.rod_data[rod_id]
            for effect in rod.get("effects", []):
                if effect["type"] == "rarity_boost":
                    target_rarity = effect["target_rarity"]
                    multiplier = effect["multiplier"]
                    if target_rarity in base_weights:
                        base_weights[target_rarity] *= multiplier
        
        # Apply bait effects
        if bait_id in self.bait_data:
            bait = self.bait_data[bait_id]
            for effect in bait.get("effects", []):
                if effect["type"] == "rarity_boost":
                    target_rarity = effect["target_rarity"]
                    multiplier = effect["multiplier"]
                    if target_rarity in base_weights:
                        base_weights[target_rarity] *= multiplier
        
        return base_weights
    
    def select_fish(self, weights: Dict[str, float]) -> Tuple[str, Dict]:
        """Select a fish based on weighted rarities"""
        # Choose rarity first
        rarities = list(weights.keys())
        rarity_weights = list(weights.values())
        chosen_rarity = random.choices(rarities, weights=rarity_weights)[0]
        
        # Get fish of chosen rarity
        available_fish = []
        for fish_id, fish_data in self.fish_data.items():
            if fish_data["rarity"] == chosen_rarity:
                # Check if fish is available (not event-only or if event is active)
                if not fish_data.get("event_only", False):
                    available_fish.append((fish_id, fish_data))
                # TODO: Add event checking logic here
        
        if not available_fish:
            # Fallback to common fish
            for fish_id, fish_data in self.fish_data.items():
                if fish_data["rarity"] == "common":
                    available_fish.append((fish_id, fish_data))
        
        if available_fish:
            fish_id, fish_data = random.choice(available_fish)
            return fish_id, fish_data
        
        # Ultimate fallback
        return "basic_fish", {"name": "Basic Fish", "rarity": "common", "value": 10}
    
    def calculate_catch_value(self, fish_data: Dict, rod_id: str, bait_id: str) -> int:
        """Calculate the value of a caught fish"""
        base_value = fish_data.get("value", 0)
        
        # Apply rod value multiplier
        if rod_id in self.rod_data:
            rod = self.rod_data[rod_id]
            for effect in rod.get("effects", []):
                if effect["type"] == "value_multiplier":
                    base_value = int(base_value * effect["multiplier"])
        
        # Apply bait value multiplier
        if bait_id in self.bait_data:
            bait = self.bait_data[bait_id]
            for effect in bait.get("effects", []):
                if effect["type"] == "value_multiplier":
                    base_value = int(base_value * effect["multiplier"])
        
        return base_value
    
    @commands.command(name="fish")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def fish(self, ctx):
        """Go fishing!"""
        # Ensure data is loaded
        await self.ensure_data_loaded()
        
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        fishing_data = user_data.get("fishing", {})
        inventory = user_data.get("inventory", {})
        
        # Check if user has a rod
        current_rod = fishing_data.get("current_rod", "basic_rod")
        if current_rod not in inventory.get("rods", {}):
            # Give basic rod if they don't have one
            await self.bot.db.add_item(user_id, "rods", "basic_rod", 1)
        
        # Check if user has bait
        current_bait = fishing_data.get("current_bait", "basic_worms")
        bait_count = inventory.get("bait", {}).get(current_bait, 0)
        
        if bait_count <= 0:
            embed = create_error_embed(
                "No Bait",
                f"You don't have any {self.bait_data.get(current_bait, {}).get('name', 'bait')}!\n"
                f"Use `!bait` to see available bait or `!fishshop` to buy more."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Use bait
        await self.bot.db.remove_item(user_id, "bait", current_bait, 1)
        
        # Calculate catch chances
        weights = self.calculate_catch_chances(current_rod, current_bait)
        
        # Select fish
        fish_id, fish_data = self.select_fish(weights)
        fish_value = self.calculate_catch_value(fish_data, current_rod, current_bait)
        
        # Add fish to inventory and give money
        await self.bot.db.add_item(user_id, "fish", fish_id, 1)
        await self.bot.db.update_balance(user_id, wallet_change=fish_value)
        
        # Update fishing stats
        await self.bot.db.update_user(user_id, {
            "fishing.total_catches": fishing_data.get("total_catches", 0) + 1,
            f"fishing.fish_caught.{fish_id}": fishing_data.get("fish_caught", {}).get(fish_id, 0) + 1,
            "fishing.total_value": fishing_data.get("total_value", 0) + fish_value
        })
        
        # Create success embed
        rarity_colors = {
            "common": 0x808080,
            "uncommon": 0x00ff00,
            "rare": 0x0080ff,
            "epic": 0x8000ff,
            "legendary": 0xff8000,
            "galactic": 0xff00ff,
            "intergalactic": 0x00ffff,
            "godlike": 0xffd700,
            "mythical": 0xff0080,
            "impossible": 0x800040,
            "otherworldly": 0x400080
        }
        
        rarity = fish_data.get("rarity", "common")
        embed = nextcord.Embed(
            title="🎣 Fishing Success!",
            description=f"You caught a **{fish_data.get('name', 'Unknown Fish')}**!",
            color=rarity_colors.get(rarity, 0x00ff00)
        )
        
        embed.add_field(
            name="🐟 Fish",
            value=f"**{fish_data.get('name', 'Unknown Fish')}**\n"
                  f"Rarity: {rarity.title()}\n"
                  f"Value: {format_currency(fish_value, self.bot.currency_emoji)}",
            inline=True
        )
        
        embed.add_field(
            name="🎣 Equipment Used",
            value=f"Rod: {self.rod_data.get(current_rod, {}).get('name', 'Unknown Rod')}\n"
                  f"Bait: {self.bait_data.get(current_bait, {}).get('name', 'Unknown Bait')}\n"
                  f"Remaining: {bait_count - 1}",
            inline=True
        )
        
        embed.set_thumbnail(url=fish_data.get("image_url", ""))
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="fishstats", aliases=["fstats"])
    async def fish_stats(self, ctx, member: nextcord.Member = None):
        """View fishing statistics"""
        target = member or ctx.author
        user_id = target.id
        
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Data",
                f"{target.display_name} hasn't started fishing yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        fishing_data = user_data.get("fishing", {})
        total_catches = fishing_data.get("total_catches", 0)
        total_value = fishing_data.get("total_value", 0)
        fish_caught = fishing_data.get("fish_caught", {})
        
        embed = nextcord.Embed(
            title=f"🎣 {target.display_name}'s Fishing Stats",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📊 Overview",
            value=f"Total Catches: {total_catches}\n"
                  f"Total Value: {format_currency(total_value, self.bot.currency_emoji)}\n"
                  f"Unique Fish: {len(fish_caught)}",
            inline=False
        )
        
        # Show top 5 most caught fish
        if fish_caught:
            sorted_fish = sorted(fish_caught.items(), key=lambda x: x[1], reverse=True)[:5]
            fish_text = ""
            for fish_id, count in sorted_fish:
                fish_name = self.fish_data.get(fish_id, {}).get("name", "Unknown Fish")
                fish_text += f"{fish_name}: {count}\n"
            
            embed.add_field(
                name="🐟 Top Catches",
                value=fish_text or "No fish caught yet",
                inline=True
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="fishbook", aliases=["fbook"])
    async def fish_book(self, ctx):
        """View your fish collection"""
        user_id = ctx.author.id
        
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Data",
                "You haven't started fishing yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        fishing_data = user_data.get("fishing", {})
        fish_caught = fishing_data.get("fish_caught", {})
        
        if not fish_caught:
            embed = create_error_embed(
                "Empty Collection",
                "You haven't caught any fish yet! Use `!fish` to start fishing."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Group fish by rarity
        rarity_groups = {}
        for fish_id, count in fish_caught.items():
            fish_info = self.fish_data.get(fish_id, {})
            rarity = fish_info.get("rarity", "common")
            
            if rarity not in rarity_groups:
                rarity_groups[rarity] = []
            
            rarity_groups[rarity].append({
                "name": fish_info.get("name", "Unknown Fish"),
                "count": count,
                "value": fish_info.get("value", 0)
            })
        
        embed = nextcord.Embed(
            title="📖 Fish Collection",
            color=0x00ff00
        )
        
        # Sort rarities by rarity order
        rarity_order = ["common", "uncommon", "rare", "epic", "legendary", 
                       "galactic", "intergalactic", "godlike", "mythical", "impossible", "otherworldly"]
        
        for rarity in rarity_order:
            if rarity in rarity_groups:
                fish_text = ""
                for fish in sorted(rarity_groups[rarity], key=lambda x: x["count"], reverse=True):
                    fish_text += f"{fish['name']}: {fish['count']}\n"
                
                embed.add_field(
                    name=f"{rarity.title()} Fish",
                    value=fish_text,
                    inline=True
                )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="rod", aliases=["rods"])
    async def rod(self, ctx, action: str = None, *, rod_name: str = None):
        """Manage your fishing rods"""
        user_id = ctx.author.id
        
        if action is None:
            # Show current rod and available rods
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            fishing_data = user_data.get("fishing", {})
            inventory = user_data.get("inventory", {})
            current_rod = fishing_data.get("current_rod", "basic_rod")
            owned_rods = inventory.get("rods", {})
            
            embed = nextcord.Embed(
                title="🎣 Fishing Rods",
                color=0x8B4513
            )
            
            # Current rod
            current_rod_data = self.rod_data.get(current_rod, {})
            embed.add_field(
                name="🎯 Current Rod",
                value=f"**{current_rod_data.get('name', 'Unknown Rod')}**\n"
                      f"{current_rod_data.get('description', 'No description')}",
                inline=False
            )
            
            # Owned rods
            if owned_rods:
                rod_text = ""
                for rod_id, count in owned_rods.items():
                    rod_info = self.rod_data.get(rod_id, {})
                    rod_text += f"{rod_info.get('name', 'Unknown Rod')}: {count}\n"
                
                embed.add_field(
                    name="📦 Owned Rods",
                    value=rod_text,
                    inline=True
                )
            
            embed.add_field(
                name="💡 Commands",
                value="`!rod equip <rod_name>` - Equip a rod\n"
                      "`!rod info <rod_name>` - View rod details",
                inline=False
            )
            
            await safe_send(ctx, embed=embed)
            return
        
        if action.lower() == "equip":
            if not rod_name:
                embed = create_error_embed(
                    "Missing Rod Name",
                    "Please specify which rod to equip."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Find rod by name
            rod_id = None
            for rid, rod_data in self.rod_data.items():
                if rod_data.get("name", "").lower() == rod_name.lower():
                    rod_id = rid
                    break
            
            if not rod_id:
                embed = create_error_embed(
                    "Rod Not Found",
                    f"No rod found with name '{rod_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Check if user owns the rod
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            inventory = user_data.get("inventory", {})
            owned_rods = inventory.get("rods", {})
            
            if rod_id not in owned_rods or owned_rods[rod_id] <= 0:
                embed = create_error_embed(
                    "Rod Not Owned",
                    f"You don't own a {self.rod_data[rod_id].get('name', 'Unknown Rod')}."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Equip rod
            await self.bot.db.update_user(user_id, {"fishing.current_rod": rod_id})
            
            embed = create_success_embed(
                "Rod Equipped",
                f"Successfully equipped **{self.rod_data[rod_id].get('name', 'Unknown Rod')}**!"
            )
            await safe_send(ctx, embed=embed)
        
        elif action.lower() == "info":
            if not rod_name:
                embed = create_error_embed(
                    "Missing Rod Name",
                    "Please specify which rod to view."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Find rod by name
            rod_id = None
            for rid, rod_data in self.rod_data.items():
                if rod_data.get("name", "").lower() == rod_name.lower():
                    rod_id = rid
                    break
            
            if not rod_id:
                embed = create_error_embed(
                    "Rod Not Found",
                    f"No rod found with name '{rod_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            rod_data = self.rod_data[rod_id]
            
            embed = nextcord.Embed(
                title=f"🎣 {rod_data.get('name', 'Unknown Rod')}",
                description=rod_data.get('description', 'No description'),
                color=0x8B4513
            )
            
            embed.add_field(
                name="💰 Value",
                value=format_currency(rod_data.get('value', 0), self.bot.currency_emoji),
                inline=True
            )
            
            if rod_data.get('effects'):
                effects_text = ""
                for effect in rod_data['effects']:
                    if effect['type'] == 'rarity_boost':
                        effects_text += f"• {effect['multiplier']}x {effect['target_rarity']} fish chance\n"
                    elif effect['type'] == 'value_multiplier':
                        effects_text += f"• {effect['multiplier']}x fish value\n"
                
                embed.add_field(
                    name="✨ Effects",
                    value=effects_text or "No special effects",
                    inline=False
                )
            
            await safe_send(ctx, embed=embed)
    
    @commands.command(name="bait")
    async def bait(self, ctx, action: str = None, *, bait_name: str = None):
        """Manage your fishing bait"""
        user_id = ctx.author.id
        
        if action is None:
            # Show current bait and available bait
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            fishing_data = user_data.get("fishing", {})
            inventory = user_data.get("inventory", {})
            current_bait = fishing_data.get("current_bait", "basic_worms")
            owned_bait = inventory.get("bait", {})
            
            embed = nextcord.Embed(
                title="🪱 Fishing Bait",
                color=0x228B22
            )
            
            # Current bait
            current_bait_data = self.bait_data.get(current_bait, {})
            embed.add_field(
                name="🎯 Current Bait",
                value=f"**{current_bait_data.get('name', 'Unknown Bait')}**\n"
                      f"{current_bait_data.get('description', 'No description')}",
                inline=False
            )
            
            # Owned bait
            if owned_bait:
                bait_text = ""
                for bait_id, count in owned_bait.items():
                    bait_info = self.bait_data.get(bait_id, {})
                    bait_text += f"{bait_info.get('name', 'Unknown Bait')}: {count}\n"
                
                embed.add_field(
                    name="📦 Owned Bait",
                    value=bait_text,
                    inline=True
                )
            
            embed.add_field(
                name="💡 Commands",
                value="`!bait equip <bait_name>` - Equip bait\n"
                      "`!bait info <bait_name>` - View bait details",
                inline=False
            )
            
            await safe_send(ctx, embed=embed)
            return
        
        if action.lower() == "equip":
            if not bait_name:
                embed = create_error_embed(
                    "Missing Bait Name",
                    "Please specify which bait to equip."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Find bait by name
            bait_id = None
            for bid, bait_data in self.bait_data.items():
                if bait_data.get("name", "").lower() == bait_name.lower():
                    bait_id = bid
                    break
            
            if not bait_id:
                embed = create_error_embed(
                    "Bait Not Found",
                    f"No bait found with name '{bait_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Check if user owns the bait
            user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
            if not user_data:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            
            inventory = user_data.get("inventory", {})
            owned_bait = inventory.get("bait", {})
            
            if bait_id not in owned_bait or owned_bait[bait_id] <= 0:
                embed = create_error_embed(
                    "Bait Not Owned",
                    f"You don't own any {self.bait_data[bait_id].get('name', 'Unknown Bait')}."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Equip bait
            await self.bot.db.update_user(user_id, {"fishing.current_bait": bait_id})
            
            embed = create_success_embed(
                "Bait Equipped",
                f"Successfully equipped **{self.bait_data[bait_id].get('name', 'Unknown Bait')}**!"
            )
            await safe_send(ctx, embed=embed)
        
        elif action.lower() == "info":
            if not bait_name:
                embed = create_error_embed(
                    "Missing Bait Name",
                    "Please specify which bait to view."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Find bait by name
            bait_id = None
            for bid, bait_data in self.bait_data.items():
                if bait_data.get("name", "").lower() == bait_name.lower():
                    bait_id = bid
                    break
            
            if not bait_id:
                embed = create_error_embed(
                    "Bait Not Found",
                    f"No bait found with name '{bait_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            bait_data = self.bait_data[bait_id]
            
            embed = nextcord.Embed(
                title=f"🪱 {bait_data.get('name', 'Unknown Bait')}",
                description=bait_data.get('description', 'No description'),
                color=0x228B22
            )
            
            embed.add_field(
                name="💰 Value",
                value=format_currency(bait_data.get('value', 0), self.bot.currency_emoji),
                inline=True
            )
            
            if bait_data.get('effects'):
                effects_text = ""
                for effect in bait_data['effects']:
                    if effect['type'] == 'rarity_boost':
                        effects_text += f"• {effect['multiplier']}x {effect['target_rarity']} fish chance\n"
                    elif effect['type'] == 'value_multiplier':
                        effects_text += f"• {effect['multiplier']}x fish value\n"
                
                embed.add_field(
                    name="✨ Effects",
                    value=effects_text or "No special effects",
                    inline=False
                )
            
            await safe_send(ctx, embed=embed)
    
    @commands.command(name="fishshop", aliases=["fshop"])
    async def fish_shop(self, ctx):
        """View the fishing shop"""
        embed = nextcord.Embed(
            title="🛒 Fishing Shop",
            description="Buy rods and bait for your fishing adventures!",
            color=0x00ff00
        )
        
        # Show available rods
        rod_text = ""
        for rod_id, rod_data in self.rod_data.items():
            if rod_data.get("purchasable", True):
                rod_text += f"**{rod_data.get('name', 'Unknown Rod')}**\n"
                rod_text += f"Price: {format_currency(rod_data.get('value', 0), self.bot.currency_emoji)}\n"
                rod_text += f"{rod_data.get('description', 'No description')}\n\n"
        
        embed.add_field(
            name="🎣 Rods",
            value=rod_text or "No rods available",
            inline=False
        )
        
        # Show available bait
        bait_text = ""
        for bait_id, bait_data in self.bait_data.items():
            if bait_data.get("purchasable", True):
                bait_text += f"**{bait_data.get('name', 'Unknown Bait')}**\n"
                bait_text += f"Price: {format_currency(bait_data.get('value', 0), self.bot.currency_emoji)}\n"
                bait_text += f"{bait_data.get('description', 'No description')}\n\n"
        
        embed.add_field(
            name="🪱 Bait",
            value=bait_text or "No bait available",
            inline=False
        )
        
        embed.add_field(
            name="💡 How to Buy",
            value="Use `!buy rod <rod_name>` or `!buy bait <bait_name> <amount>` to purchase items.",
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="sell")
    async def sell_fish(self, ctx, fish_name: str = None, amount: int = 1):
        """Sell your caught fish"""
        user_id = ctx.author.id
        
        if not fish_name:
            embed = create_error_embed(
                "Missing Fish Name",
                "Please specify which fish to sell.\nUse `!fishbook` to see your collection."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Find fish by name
        fish_id = None
        for fid, fish_data in self.fish_data.items():
            if fish_data.get("name", "").lower() == fish_name.lower():
                fish_id = fid
                break
        
        if not fish_id:
            embed = create_error_embed(
                "Fish Not Found",
                f"No fish found with name '{fish_name}'."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Check if user has the fish
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Fish",
                "You don't have any fish to sell!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        inventory = user_data.get("inventory", {})
        fish_inventory = inventory.get("fish", {})
        
        if fish_id not in fish_inventory or fish_inventory[fish_id] < amount:
            embed = create_error_embed(
                "Insufficient Fish",
                f"You don't have {amount} {self.fish_data[fish_id].get('name', 'Unknown Fish')}."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Calculate sell value
        fish_data = self.fish_data[fish_id]
        sell_value = fish_data.get("value", 0) * amount
        
        # Process sale
        await self.bot.db.remove_item(user_id, "fish", fish_id, amount)
        await self.bot.db.update_balance(user_id, wallet_change=sell_value)
        await self.bot.db.add_transaction(
            user_id, "fish_sale", sell_value, f"Sold {amount} {fish_data.get('name', 'Unknown Fish')}"
        )
        
        embed = create_success_embed(
            "Fish Sold",
            f"Successfully sold {amount} **{fish_data.get('name', 'Unknown Fish')}** for {format_currency(sell_value, self.bot.currency_emoji)}!"
        )
        
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Fishing(bot))
