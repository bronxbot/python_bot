"""
Trading system for BronxBot
Allows users to trade items and currency
"""

import nextcord
from nextcord.ext import commands
import time
from typing import Dict, Optional, List
import json

from database.database_manager import get_database_manager
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed,
    create_info_embed, safe_send
)
from utils.logger import get_logger

logger = get_logger(__name__)


class TradingCog(commands.Cog):
    """Trading system for items and currency"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = get_database_manager()
        self.active_trades = {}  # Track active trade offers
        self.trade_cooldowns = {}  # Track trade cooldowns
    
    async def get_user_items(self, user_id: int) -> Dict:
        """Get user's inventory"""
        user_data = await self.db.get_user(user_id)
        if not user_data:
            return {}
        
        # Get fishing catches as tradeable items
        fishing_data = user_data.get("fishing", {})
        catches = fishing_data.get("catches", {})
        
        # Add other tradeable items here (rods, bait, etc.)
        inventory = {"fish": catches}
        
        return inventory
    
    async def get_user_balance(self, user_id: int) -> int:
        """Get user's wallet balance"""
        economy_data = await self.db.get_economy_data(user_id)
        return economy_data.get("wallet", 0) if economy_data else 0
    
    def can_trade(self, user_id: int) -> bool:
        """Check if user can initiate a trade (not on cooldown)"""
        if user_id not in self.trade_cooldowns:
            return True
        
        cooldown_time = 60  # 1 minute cooldown
        elapsed = time.time() - self.trade_cooldowns[user_id]
        return elapsed >= cooldown_time
    
    def get_trade_cooldown(self, user_id: int) -> float:
        """Get remaining trade cooldown"""
        if user_id not in self.trade_cooldowns:
            return 0.0
        
        cooldown_time = 60
        elapsed = time.time() - self.trade_cooldowns[user_id]
        return max(0.0, cooldown_time - elapsed)
    
    @commands.group(name="trade", invoke_without_command=True)
    async def trade_group(self, ctx):
        """💱 Trading commands"""
        await ctx.send_help(ctx.command)
    
    @trade_group.command(name="offer")
    async def trade_offer(self, ctx, target: nextcord.Member, *, offer_details: str):
        """📤 Offer a trade to another user"""
        
        # Validation
        if target.id == ctx.author.id:
            await safe_send(ctx, embed=create_error_embed("Invalid Target", "You can't trade with yourself!"))
            return
        
        if target.bot:
            await safe_send(ctx, embed=create_error_embed("Invalid Target", "You can't trade with bots!"))
            return
        
        # Check cooldown
        if not self.can_trade(ctx.author.id):
            remaining = self.get_trade_cooldown(ctx.author.id)
            await safe_send(ctx, embed=create_error_embed(
                "Trade Cooldown",
                f"You can make another trade offer in {remaining:.1f} seconds"
            ))
            return
        
        # Check if user already has an active trade
        if ctx.author.id in self.active_trades:
            await safe_send(ctx, embed=create_error_embed("Active Trade", "You already have an active trade offer!"))
            return
        
        # Parse offer details
        try:
            offer = self.parse_trade_offer(offer_details)
        except ValueError as e:
            await safe_send(ctx, embed=create_error_embed("Invalid Offer", str(e)))
            return
        
        # Validate user has the items/money they're offering
        user_balance = await self.get_user_balance(ctx.author.id)
        user_items = await self.get_user_items(ctx.author.id)
        
        if offer["money"] > user_balance:
            await safe_send(ctx, embed=create_error_embed(
                "Insufficient Funds",
                f"You don't have {format_currency(offer['money'])} to offer"
            ))
            return
        
        # Check if user has the items they're offering
        for item_type, items in offer["items"].items():
            user_type_items = user_items.get(item_type, {})
            for item_name, quantity in items.items():
                if user_type_items.get(item_name, 0) < quantity:
                    await safe_send(ctx, embed=create_error_embed(
                        "Insufficient Items",
                        f"You don't have {quantity} {item_name} to offer"
                    ))
                    return
        
        # Create trade offer
        trade_offer = TradeOffer(
            ctx.author.id,
            target.id,
            offer["money"],
            offer["items"],
            offer["requested_money"],
            offer["requested_items"]
        )
        
        self.active_trades[ctx.author.id] = trade_offer
        self.trade_cooldowns[ctx.author.id] = time.time()
        
        # Create offer embed
        embed = trade_offer.create_embed(ctx.author, target)
        view = TradeView(trade_offer, self)
        
        # Send to both users
        await safe_send(ctx, embed=embed, view=view)
        
        # Try to DM the target user
        try:
            dm_embed = create_info_embed(
                "Trade Offer Received",
                f"{ctx.author.mention} has offered you a trade in {ctx.guild.name}!\n"
                f"Check the channel for details."
            )
            await target.send(embed=dm_embed)
        except:
            pass  # User might have DMs disabled
    
    @trade_group.command(name="quicksell")
    async def quick_sell(self, ctx, item_type: str, item_name: str, quantity: int = 1):
        """🏪 Quickly sell items for automatic pricing"""
        
        # Check cooldown
        if not self.can_trade(ctx.author.id):
            remaining = self.get_trade_cooldown(ctx.author.id)
            await safe_send(ctx, embed=create_error_embed(
                "Trade Cooldown",
                f"You can make another trade in {remaining:.1f} seconds"
            ))
            return
        
        # Validate quantity
        if quantity <= 0:
            await safe_send(ctx, embed=create_error_embed("Invalid Quantity", "Quantity must be positive"))
            return
        
        # Get user items
        user_items = await self.get_user_items(ctx.author.id)
        
        if item_type not in user_items:
            await safe_send(ctx, embed=create_error_embed("Invalid Item Type", f"Item type '{item_type}' not found"))
            return
        
        if item_name not in user_items[item_type]:
            await safe_send(ctx, embed=create_error_embed("Item Not Found", f"You don't have any {item_name}"))
            return
        
        if user_items[item_type][item_name] < quantity:
            await safe_send(ctx, embed=create_error_embed(
                "Insufficient Items",
                f"You only have {user_items[item_type][item_name]} {item_name}"
            ))
            return
        
        # Calculate selling price
        base_price = self.get_item_base_price(item_type, item_name)
        if base_price == 0:
            await safe_send(ctx, embed=create_error_embed("Not Sellable", "This item cannot be sold"))
            return
        
        total_price = base_price * quantity
        
        # Process sale
        await self.process_item_sale(ctx.author.id, item_type, item_name, quantity, total_price)
        
        self.trade_cooldowns[ctx.author.id] = time.time()
        
        embed = create_success_embed(
            "Item Sold!",
            f"**Item:** {quantity}x {item_name}\n"
            f"**Price:** {format_currency(total_price)}\n"
            f"**Your Balance:** {format_currency(await self.get_user_balance(ctx.author.id))}"
        )
        
        await safe_send(ctx, embed=embed)
    
    @trade_group.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, member: nextcord.Member = None):
        """🎒 View your or another user's inventory"""
        
        target = member or ctx.author
        items = await self.get_user_items(target.id)
        balance = await self.get_user_balance(target.id)
        
        embed = create_info_embed(
            f"🎒 {target.display_name}'s Inventory",
            f"**Balance:** {format_currency(balance)}"
        )
        
        # Add item categories
        for item_type, type_items in items.items():
            if type_items:
                item_list = []
                for item_name, quantity in type_items.items():
                    if quantity > 0:
                        item_list.append(f"{item_name}: {quantity}")
                
                if item_list:
                    embed.add_field(
                        name=f"{item_type.title()}",
                        value="\n".join(item_list) if item_list else "None",
                        inline=False
                    )
        
        await safe_send(ctx, embed=embed)
    
    @trade_group.command(name="cancel")
    async def cancel_trade(self, ctx):
        """❌ Cancel your active trade offer"""
        
        if ctx.author.id not in self.active_trades:
            await safe_send(ctx, embed=create_error_embed("No Active Trade", "You don't have an active trade offer"))
            return
        
        del self.active_trades[ctx.author.id]
        
        embed = create_success_embed(
            "Trade Cancelled",
            "Your trade offer has been cancelled"
        )
        
        await safe_send(ctx, embed=embed)
    
    def parse_trade_offer(self, offer_details: str) -> Dict:
        """Parse trade offer details"""
        # Simple format: "give 100 money, 5 bass for 200 money, 3 trout"
        
        try:
            parts = offer_details.lower().split(" for ")
            if len(parts) != 2:
                raise ValueError("Use format: 'give X for Y'")
            
            give_part = parts[0].replace("give ", "").strip()
            want_part = parts[1].strip()
            
            # Parse what they're giving
            give_money, give_items = self.parse_trade_items(give_part)
            
            # Parse what they want
            want_money, want_items = self.parse_trade_items(want_part)
            
            return {
                "money": give_money,
                "items": give_items,
                "requested_money": want_money,
                "requested_items": want_items
            }
        
        except Exception as e:
            raise ValueError(f"Invalid trade format: {e}")
    
    def parse_trade_items(self, item_string: str) -> tuple:
        """Parse items from a string"""
        money = 0
        items = {"fish": {}}
        
        # Split by comma
        parts = [part.strip() for part in item_string.split(",")]
        
        for part in parts:
            if "money" in part or "bronkbuk" in part:
                # Extract money amount
                import re
                match = re.search(r'(\d+)', part)
                if match:
                    money = int(match.group(1))
            else:
                # Extract item quantity and name
                import re
                match = re.search(r'(\d+)\s+(.+)', part)
                if match:
                    quantity = int(match.group(1))
                    item_name = match.group(2).strip()
                    items["fish"][item_name] = quantity
        
        return money, items
    
    def get_item_base_price(self, item_type: str, item_name: str) -> int:
        """Get base selling price for an item"""
        
        # Load fish data to get base prices
        try:
            with open("data/fish.json", "r") as f:
                fish_data = json.load(f)
            
            if item_type == "fish":
                for rarity, fish_list in fish_data["fish"].items():
                    if item_name in fish_list:
                        return fish_list[item_name]["base_value"]
        except:
            pass
        
        return 0
    
    async def process_item_sale(self, user_id: int, item_type: str, item_name: str, quantity: int, total_price: int):
        """Process the sale of items"""
        
        # Remove items from inventory
        if item_type == "fish":
            await self.db.update_user(user_id, {
                f"fishing.catches.{item_name}": -quantity
            })
        
        # Add money to wallet
        await self.db.update_balance(user_id, wallet_change=total_price)
        
        # Add transaction record
        await self.db.add_transaction(
            user_id,
            "item_sale",
            total_price,
            f"Sold {quantity}x {item_name}"
        )


class TradeOffer:
    """Represents a trade offer between two users"""
    
    def __init__(self, offerer_id: int, target_id: int, offer_money: int, 
                 offer_items: Dict, requested_money: int, requested_items: Dict):
        self.offerer_id = offerer_id
        self.target_id = target_id
        self.offer_money = offer_money
        self.offer_items = offer_items
        self.requested_money = requested_money
        self.requested_items = requested_items
        self.created_at = time.time()
    
    def create_embed(self, offerer: nextcord.Member, target: nextcord.Member) -> nextcord.Embed:
        """Create embed for trade offer"""
        
        embed = create_info_embed(
            "💱 Trade Offer",
            f"**From:** {offerer.mention}\n**To:** {target.mention}"
        )
        
        # What's being offered
        offered_items = []
        if self.offer_money > 0:
            offered_items.append(f"{format_currency(self.offer_money)}")
        
        for item_type, items in self.offer_items.items():
            for item_name, quantity in items.items():
                if quantity > 0:
                    offered_items.append(f"{quantity}x {item_name}")
        
        embed.add_field(
            name="🎁 Offering",
            value="\n".join(offered_items) if offered_items else "Nothing",
            inline=True
        )
        
        # What's being requested
        requested_items = []
        if self.requested_money > 0:
            requested_items.append(f"{format_currency(self.requested_money)}")
        
        for item_type, items in self.requested_items.items():
            for item_name, quantity in items.items():
                if quantity > 0:
                    requested_items.append(f"{quantity}x {item_name}")
        
        embed.add_field(
            name="💰 Requesting",
            value="\n".join(requested_items) if requested_items else "Nothing",
            inline=True
        )
        
        embed.set_footer(text=f"Trade expires in 10 minutes")
        
        return embed
    
    def is_expired(self) -> bool:
        """Check if trade offer has expired"""
        return time.time() - self.created_at > 600  # 10 minutes


class TradeView(nextcord.ui.View):
    """View for trade interactions"""
    
    def __init__(self, trade_offer: TradeOffer, trading_cog):
        super().__init__(timeout=600)  # 10 minutes
        self.trade_offer = trade_offer
        self.trading_cog = trading_cog
    
    @nextcord.ui.button(label="Accept", style=nextcord.ButtonStyle.success)
    async def accept_trade(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Accept the trade"""
        
        if interaction.user.id != self.trade_offer.target_id:
            await interaction.response.send_message("This trade is not for you!", ephemeral=True)
            return
        
        # Validate that both users still have what they're trading
        if not await self.validate_trade():
            embed = create_error_embed(
                "Trade Invalid",
                "One or both users no longer have the items/money for this trade"
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Execute the trade
        await self.execute_trade()
        
        # Remove from active trades
        if self.trade_offer.offerer_id in self.trading_cog.active_trades:
            del self.trading_cog.active_trades[self.trade_offer.offerer_id]
        
        embed = create_success_embed(
            "Trade Completed!",
            "The trade has been successfully completed!"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @nextcord.ui.button(label="Decline", style=nextcord.ButtonStyle.danger)
    async def decline_trade(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Decline the trade"""
        
        if interaction.user.id != self.trade_offer.target_id:
            await interaction.response.send_message("This trade is not for you!", ephemeral=True)
            return
        
        # Remove from active trades
        if self.trade_offer.offerer_id in self.trading_cog.active_trades:
            del self.trading_cog.active_trades[self.trade_offer.offerer_id]
        
        embed = create_error_embed(
            "Trade Declined",
            "The trade has been declined"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def validate_trade(self) -> bool:
        """Validate that both users can still complete the trade"""
        
        # Check offerer's resources
        offerer_balance = await self.trading_cog.get_user_balance(self.trade_offer.offerer_id)
        offerer_items = await self.trading_cog.get_user_items(self.trade_offer.offerer_id)
        
        if offerer_balance < self.trade_offer.offer_money:
            return False
        
        for item_type, items in self.trade_offer.offer_items.items():
            user_type_items = offerer_items.get(item_type, {})
            for item_name, quantity in items.items():
                if user_type_items.get(item_name, 0) < quantity:
                    return False
        
        # Check target's resources
        target_balance = await self.trading_cog.get_user_balance(self.trade_offer.target_id)
        target_items = await self.trading_cog.get_user_items(self.trade_offer.target_id)
        
        if target_balance < self.trade_offer.requested_money:
            return False
        
        for item_type, items in self.trade_offer.requested_items.items():
            user_type_items = target_items.get(item_type, {})
            for item_name, quantity in items.items():
                if user_type_items.get(item_name, 0) < quantity:
                    return False
        
        return True
    
    async def execute_trade(self):
        """Execute the trade between users"""
        
        # Transfer money
        if self.trade_offer.offer_money > 0:
            await self.trading_cog.db.update_balance(
                self.trade_offer.offerer_id,
                wallet_change=-self.trade_offer.offer_money
            )
            await self.trading_cog.db.update_balance(
                self.trade_offer.target_id,
                wallet_change=self.trade_offer.offer_money
            )
        
        if self.trade_offer.requested_money > 0:
            await self.trading_cog.db.update_balance(
                self.trade_offer.target_id,
                wallet_change=-self.trade_offer.requested_money
            )
            await self.trading_cog.db.update_balance(
                self.trade_offer.offerer_id,
                wallet_change=self.trade_offer.requested_money
            )
        
        # Transfer items
        for item_type, items in self.trade_offer.offer_items.items():
            for item_name, quantity in items.items():
                if quantity > 0:
                    if item_type == "fish":
                        # Remove from offerer
                        await self.trading_cog.db.update_user(
                            self.trade_offer.offerer_id,
                            {f"fishing.catches.{item_name}": -quantity}
                        )
                        # Add to target
                        await self.trading_cog.db.update_user(
                            self.trade_offer.target_id,
                            {f"fishing.catches.{item_name}": quantity}
                        )
        
        for item_type, items in self.trade_offer.requested_items.items():
            for item_name, quantity in items.items():
                if quantity > 0:
                    if item_type == "fish":
                        # Remove from target
                        await self.trading_cog.db.update_user(
                            self.trade_offer.target_id,
                            {f"fishing.catches.{item_name}": -quantity}
                        )
                        # Add to offerer
                        await self.trading_cog.db.update_user(
                            self.trade_offer.offerer_id,
                            {f"fishing.catches.{item_name}": quantity}
                        )
        
        # Add transaction records
        await self.trading_cog.db.add_transaction(
            self.trade_offer.offerer_id,
            "trade",
            self.trade_offer.requested_money - self.trade_offer.offer_money,
            f"Trade with user {self.trade_offer.target_id}"
        )
        
        await self.trading_cog.db.add_transaction(
            self.trade_offer.target_id,
            "trade",
            self.trade_offer.offer_money - self.trade_offer.requested_money,
            f"Trade with user {self.trade_offer.offerer_id}"
        )
    
    async def on_timeout(self):
        """Handle timeout"""
        if self.trade_offer.offerer_id in self.trading_cog.active_trades:
            del self.trading_cog.active_trades[self.trade_offer.offerer_id]
        
        for item in self.children:
            item.disabled = True


def setup(bot):
    bot.add_cog(TradingCog(bot))
