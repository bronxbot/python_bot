"""
Shop System for BronxBot
Centralized shop for all items including fishing gear, work tools, and more
"""

import nextcord
from nextcord.ext import commands
import json
import asyncio
from typing import Dict, List, Optional

from utils.logger import get_logger
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed, 
    create_info_embed, safe_send
)
from config.settings import ECONOMY_CONFIG

logger = get_logger(__name__)


class Shop(commands.Cog):
    """Centralized shop system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.fish_data = {}
        self.rod_data = {}
        self.bait_data = {}
        self._data_loaded = False
        # Load data in background
        asyncio.create_task(self.load_shop_data())
    
    async def load_shop_data(self):
        """Load shop data from JSON files asynchronously"""
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
            logger.info("Shop data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading shop data: {e}")
            # Fallback to synchronous loading
            self.load_shop_data_sync()
    
    def load_shop_data_sync(self):
        """Fallback synchronous data loading"""
        try:
            with open("data/fish.json", "r") as f:
                self.fish_data = json.load(f)
            with open("data/rods.json", "r") as f:
                self.rod_data = json.load(f)
            with open("data/bait.json", "r") as f:
                self.bait_data = json.load(f)
            self._data_loaded = True
            logger.info("Shop data loaded successfully (sync)")
        except Exception as e:
            logger.error(f"Error loading shop data: {e}")
            self.fish_data = {}
            self.rod_data = {}
            self.bait_data = {}
    
    async def ensure_data_loaded(self):
        """Ensure shop data is loaded before use"""
        if not self._data_loaded:
            await self.load_shop_data()
        
        # Wait up to 5 seconds for data to load
        for _ in range(50):
            if self._data_loaded:
                break
            await asyncio.sleep(0.1)
        
        if not self._data_loaded:
            logger.warning("Shop data not loaded, using empty data")
    
    @commands.command(name="buy")
    async def buy(self, ctx, item_type: str, item_name: str, amount: int = 1):
        """Buy items from the shop"""
        user_id = ctx.author.id
        item_type = item_type.lower()
        
        # Check for bazaar stocks
        if item_type == "stock":
            # This will be handled by the bazaar cog
            return
        
        # Validate amount
        if amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must buy a positive amount."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        wallet = economy_data.get("wallet", 0)
        
        item_data = None
        cost = 0
        
        # Handle different item types
        if item_type == "rod":
            # Find rod by name
            rod_id = None
            for rid, rod_data in self.rod_data.items():
                if rod_data.get("name", "").lower() == item_name.lower():
                    rod_id = rid
                    item_data = rod_data
                    break
            
            if not item_data or not item_data.get("purchasable", True):
                embed = create_error_embed(
                    "Rod Not Found",
                    f"No purchasable rod found with name '{item_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            cost = item_data.get("value", 0)
            
            # Check if user already owns this rod
            inventory = user_data.get("inventory", {})
            if rod_id in inventory.get("rods", {}):
                embed = create_error_embed(
                    "Already Owned",
                    f"You already own a **{item_data.get('name', 'Unknown Rod')}**!"
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Check if user can afford it
            if cost > wallet:
                embed = create_error_embed(
                    "Insufficient Funds",
                    f"You need {format_currency(cost, self.bot.currency_emoji)} to buy this rod.\n"
                    f"You have {format_currency(wallet, self.bot.currency_emoji)}."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Process purchase
            await self.bot.db.update_balance(user_id, wallet_change=-cost)
            await self.bot.db.add_item(user_id, "rods", rod_id, 1)
            await self.bot.db.add_transaction(
                user_id, "shop_purchase", -cost, f"Bought {item_data.get('name', 'Unknown Rod')}"
            )
            
            embed = create_success_embed(
                "Purchase Successful",
                f"Successfully bought **{item_data.get('name', 'Unknown Rod')}** for {format_currency(cost, self.bot.currency_emoji)}!"
            )
            await safe_send(ctx, embed=embed)
        
        elif item_type == "bait":
            # Find bait by name
            bait_id = None
            for bid, bait_data in self.bait_data.items():
                if bait_data.get("name", "").lower() == item_name.lower():
                    bait_id = bid
                    item_data = bait_data
                    break
            
            if not item_data or not item_data.get("purchasable", True):
                embed = create_error_embed(
                    "Bait Not Found",
                    f"No purchasable bait found with name '{item_name}'."
                )
                await safe_send(ctx, embed=embed)
                return
            
            cost = item_data.get("value", 0) * amount
            
            # Check if user can afford it
            if cost > wallet:
                embed = create_error_embed(
                    "Insufficient Funds",
                    f"You need {format_currency(cost, self.bot.currency_emoji)} to buy {amount} {item_data.get('name', 'Unknown Bait')}.\n"
                    f"You have {format_currency(wallet, self.bot.currency_emoji)}."
                )
                await safe_send(ctx, embed=embed)
                return
            
            # Process purchase
            await self.bot.db.update_balance(user_id, wallet_change=-cost)
            await self.bot.db.add_item(user_id, "bait", bait_id, amount)
            await self.bot.db.add_transaction(
                user_id, "shop_purchase", -cost, f"Bought {amount} {item_data.get('name', 'Unknown Bait')}"
            )
            
            embed = create_success_embed(
                "Purchase Successful",
                f"Successfully bought {amount} **{item_data.get('name', 'Unknown Bait')}** for {format_currency(cost, self.bot.currency_emoji)}!"
            )
            await safe_send(ctx, embed=embed)
        
        else:
            embed = create_error_embed(
                "Invalid Item Type",
                f"Unknown item type '{item_type}'.\n"
                f"Valid types: rod, bait, stock"
            )
            await safe_send(ctx, embed=embed)
    
    @commands.command(name="shop")
    async def shop(self, ctx, category: str = None):
        """View the shop catalog"""
        if category is None:
            # Show all categories
            embed = nextcord.Embed(
                title="🛒 BronxBot Shop",
                description="Welcome to the shop! Here you can buy various items to enhance your experience.",
                color=0x00ff00
            )
            
            embed.add_field(
                name="🎣 Fishing Gear",
                value="`!shop fishing` - View rods and bait",
                inline=True
            )
            
            embed.add_field(
                name="📈 Stock Market",
                value="`!market` - View available stocks",
                inline=True
            )
            
            embed.add_field(
                name="💡 How to Buy",
                value="• `!buy rod <name>` - Buy a fishing rod\n"
                      "• `!buy bait <name> <amount>` - Buy bait\n"
                      "• `!buy stock <symbol> <amount>` - Buy stocks",
                inline=False
            )
            
            await safe_send(ctx, embed=embed)
            return
        
        category = category.lower()
        
        if category in ["fishing", "fish"]:
            embed = nextcord.Embed(
                title="🎣 Fishing Shop",
                description="Rods and bait for your fishing adventures!",
                color=0x00ff00
            )
            
            # Show available rods
            rod_text = ""
            for rod_id, rod_data in self.rod_data.items():
                if rod_data.get("purchasable", True):
                    rod_text += f"**{rod_data.get('name', 'Unknown Rod')}**\n"
                    rod_text += f"Price: {format_currency(rod_data.get('value', 0), self.bot.currency_emoji)}\n"
                    rod_text += f"{rod_data.get('description', 'No description')}\n\n"
            
            if rod_text:
                embed.add_field(
                    name="🎣 Fishing Rods",
                    value=rod_text,
                    inline=False
                )
            
            # Show available bait
            bait_text = ""
            for bait_id, bait_data in self.bait_data.items():
                if bait_data.get("purchasable", True):
                    bait_text += f"**{bait_data.get('name', 'Unknown Bait')}**\n"
                    bait_text += f"Price: {format_currency(bait_data.get('value', 0), self.bot.currency_emoji)} each\n"
                    bait_text += f"{bait_data.get('description', 'No description')}\n\n"
            
            if bait_text:
                embed.add_field(
                    name="🪱 Bait",
                    value=bait_text,
                    inline=False
                )
            
            await safe_send(ctx, embed=embed)
        
        else:
            embed = create_error_embed(
                "Invalid Category",
                f"Unknown shop category '{category}'.\n"
                f"Available categories: fishing"
            )
            await safe_send(ctx, embed=embed)
    
    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: nextcord.Member = None):
        """View your or someone else's inventory"""
        target = member or ctx.author
        user_id = target.id
        
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "Empty Inventory",
                f"{target.display_name} doesn't have any items yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        inventory = user_data.get("inventory", {})
        
        if not inventory:
            embed = create_error_embed(
                "Empty Inventory",
                f"{target.display_name} doesn't have any items yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        embed = nextcord.Embed(
            title=f"🎒 {target.display_name}'s Inventory",
            color=0x00ff00
        )
        
        # Show fishing rods
        rods = inventory.get("rods", {})
        if rods:
            rod_text = ""
            for rod_id, count in rods.items():
                if count > 0:
                    rod_name = self.rod_data.get(rod_id, {}).get("name", "Unknown Rod")
                    rod_text += f"{rod_name}: {count}\n"
            
            if rod_text:
                embed.add_field(
                    name="🎣 Fishing Rods",
                    value=rod_text,
                    inline=True
                )
        
        # Show bait
        bait = inventory.get("bait", {})
        if bait:
            bait_text = ""
            for bait_id, count in bait.items():
                if count > 0:
                    bait_name = self.bait_data.get(bait_id, {}).get("name", "Unknown Bait")
                    bait_text += f"{bait_name}: {count}\n"
            
            if bait_text:
                embed.add_field(
                    name="🪱 Bait",
                    value=bait_text,
                    inline=True
                )
        
        # Show fish
        fish = inventory.get("fish", {})
        if fish:
            fish_text = ""
            total_fish = 0
            for fish_id, count in fish.items():
                if count > 0:
                    fish_name = self.fish_data.get(fish_id, {}).get("name", "Unknown Fish")
                    fish_text += f"{fish_name}: {count}\n"
                    total_fish += count
            
            if fish_text:
                embed.add_field(
                    name=f"🐟 Fish ({total_fish} total)",
                    value=fish_text[:1024],  # Discord field limit
                    inline=False
                )
        
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Shop(bot))
