"""
Economy System for BronxBot
Handles currency, wallets, banks, and transactions
"""

import nextcord
from nextcord.ext import commands
from datetime import datetime, timedelta
import asyncio
from typing import Optional

from utils.logger import get_logger
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed, 
    create_info_embed, safe_send, cooldown_manager
)
from config.settings import ECONOMY_CONFIG

logger = get_logger(__name__)


class Economy(commands.Cog):
    """Economy commands and functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.daily_cooldowns = {}
    
    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: nextcord.Member = None):
        """Check your or someone else's balance"""
        target = member or ctx.author
        user_id = target.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            if target == ctx.author:
                user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
            else:
                embed = create_error_embed(
                    "User Not Found",
                    f"{target.display_name} hasn't started using the economy system yet."
                )
                await safe_send(ctx, embed=embed)
                return
        
        economy_data = user_data.get("economy", {})
        wallet = economy_data.get("wallet", 0)
        bank = economy_data.get("bank", 0)
        bank_tier = economy_data.get("bank_tier", "bronze")
        
        # Get bank limit
        bank_limit = ECONOMY_CONFIG["bank_upgrades"][bank_tier]["limit"]
        
        embed = nextcord.Embed(
            title=f"💰 {target.display_name}'s Balance",
            color=0x00ff00
        )
        
        embed.add_field(
            name="👛 Wallet",
            value=format_currency(wallet, self.bot.currency_emoji),
            inline=True
        )
        
        embed.add_field(
            name="🏦 Bank",
            value=f"{format_currency(bank, self.bot.currency_emoji)} / {format_currency(bank_limit, self.bot.currency_emoji)}",
            inline=True
        )
        
        embed.add_field(
            name="💎 Total",
            value=format_currency(wallet + bank, self.bot.currency_emoji),
            inline=True
        )
        
        embed.add_field(
            name="🏆 Bank Tier",
            value=bank_tier.title(),
            inline=True
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)  # 24 hour cooldown
    async def daily(self, ctx):
        """Collect your daily bonus"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        # Give daily bonus
        daily_amount = ECONOMY_CONFIG["daily_bonus"]
        
        await self.bot.db.update_balance(user_id, wallet_change=daily_amount)
        await self.bot.db.add_transaction(
            user_id, "daily_bonus", daily_amount, "Daily bonus collected"
        )
        
        embed = create_success_embed(
            "Daily Bonus",
            f"You collected your daily bonus of {format_currency(daily_amount, self.bot.currency_emoji)}!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        """Deposit money into your bank"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        wallet = economy_data.get("wallet", 0)
        bank = economy_data.get("bank", 0)
        bank_tier = economy_data.get("bank_tier", "bronze")
        
        # Get bank limit
        bank_limit = ECONOMY_CONFIG["bank_upgrades"][bank_tier]["limit"]
        
        # Parse amount
        if amount.lower() == "all":
            deposit_amount = wallet
        else:
            try:
                deposit_amount = int(amount)
            except ValueError:
                embed = create_error_embed(
                    "Invalid Amount",
                    "Please enter a valid number or 'all'."
                )
                await safe_send(ctx, embed=embed)
                return
        
        # Validate deposit
        if deposit_amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must deposit a positive amount."
            )
            await safe_send(ctx, embed=embed)
            return
        
        if deposit_amount > wallet:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You only have {format_currency(wallet, self.bot.currency_emoji)} in your wallet."
            )
            await safe_send(ctx, embed=embed)
            return
        
        if bank + deposit_amount > bank_limit:
            max_deposit = bank_limit - bank
            embed = create_error_embed(
                "Bank Limit Exceeded",
                f"Your bank can only hold {format_currency(bank_limit, self.bot.currency_emoji)}.\n"
                f"Maximum deposit: {format_currency(max_deposit, self.bot.currency_emoji)}"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Process deposit
        await self.bot.db.update_balance(user_id, wallet_change=-deposit_amount, bank_change=deposit_amount)
        await self.bot.db.add_transaction(
            user_id, "deposit", deposit_amount, f"Deposited to bank"
        )
        
        embed = create_success_embed(
            "Deposit Successful",
            f"Deposited {format_currency(deposit_amount, self.bot.currency_emoji)} into your bank!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx, amount: str):
        """Withdraw money from your bank"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        wallet = economy_data.get("wallet", 0)
        bank = economy_data.get("bank", 0)
        
        # Parse amount
        if amount.lower() == "all":
            withdraw_amount = bank
        else:
            try:
                withdraw_amount = int(amount)
            except ValueError:
                embed = create_error_embed(
                    "Invalid Amount",
                    "Please enter a valid number or 'all'."
                )
                await safe_send(ctx, embed=embed)
                return
        
        # Validate withdrawal
        if withdraw_amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must withdraw a positive amount."
            )
            await safe_send(ctx, embed=embed)
            return
        
        if withdraw_amount > bank:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You only have {format_currency(bank, self.bot.currency_emoji)} in your bank."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Check wallet limit
        max_wallet = ECONOMY_CONFIG["max_wallet"]
        if wallet + withdraw_amount > max_wallet:
            max_withdraw = max_wallet - wallet
            embed = create_error_embed(
                "Wallet Limit Exceeded",
                f"Your wallet can only hold {format_currency(max_wallet, self.bot.currency_emoji)}.\n"
                f"Maximum withdrawal: {format_currency(max_withdraw, self.bot.currency_emoji)}"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Process withdrawal
        await self.bot.db.update_balance(user_id, wallet_change=withdraw_amount, bank_change=-withdraw_amount)
        await self.bot.db.add_transaction(
            user_id, "withdrawal", withdraw_amount, f"Withdrew from bank"
        )
        
        embed = create_success_embed(
            "Withdrawal Successful",
            f"Withdrew {format_currency(withdraw_amount, self.bot.currency_emoji)} from your bank!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="pay", aliases=["give"])
    async def pay(self, ctx, member: nextcord.Member, amount: int):
        """Pay money to another user"""
        user_id = ctx.author.id
        target_id = member.id
        
        # Can't pay yourself
        if user_id == target_id:
            embed = create_error_embed(
                "Invalid Transaction",
                "You can't pay yourself!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Validate amount
        if amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must pay a positive amount."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        target_data = await self.bot.db.get_user(target_id, ctx.guild.id)
        if not target_data:
            target_data = await self.bot.db.create_user(target_id, ctx.guild.id)
        
        # Check if user has enough money
        user_economy = user_data.get("economy", {})
        wallet = user_economy.get("wallet", 0)
        
        if amount > wallet:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You only have {format_currency(wallet, self.bot.currency_emoji)} in your wallet."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Check target wallet limit
        target_economy = target_data.get("economy", {})
        target_wallet = target_economy.get("wallet", 0)
        max_wallet = ECONOMY_CONFIG["max_wallet"]
        
        if target_wallet + amount > max_wallet:
            embed = create_error_embed(
                "Recipient Wallet Full",
                f"{member.display_name}'s wallet is too full to receive {format_currency(amount, self.bot.currency_emoji)}."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Process payment
        await self.bot.db.update_balance(user_id, wallet_change=-amount)
        await self.bot.db.update_balance(target_id, wallet_change=amount)
        
        # Add transactions
        await self.bot.db.add_transaction(
            user_id, "payment_sent", -amount, f"Paid {member.display_name}"
        )
        await self.bot.db.add_transaction(
            target_id, "payment_received", amount, f"Received from {ctx.author.display_name}"
        )
        
        embed = create_success_embed(
            "Payment Successful",
            f"Paid {format_currency(amount, self.bot.currency_emoji)} to {member.display_name}!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    async def leaderboard(self, ctx):
        """View the richest users"""
        # Get top users by total money (wallet + bank)
        pipeline = [
            {
                "$addFields": {
                    "total_money": {
                        "$add": ["$economy.wallet", "$economy.bank"]
                    }
                }
            },
            {"$sort": {"total_money": -1}},
            {"$limit": 10}
        ]
        
        # For now, use simple leaderboard
        leaderboard = await self.bot.db.get_leaderboard("economy.wallet", 10)
        
        if not leaderboard:
            embed = create_info_embed(
                "Empty Leaderboard",
                "No one has started using the economy system yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        embed = nextcord.Embed(
            title="💰 Wealth Leaderboard",
            color=0x00ff00
        )
        
        leaderboard_text = ""
        for i, user_data in enumerate(leaderboard, 1):
            user = self.bot.get_user(user_data["user_id"])
            username = user.display_name if user else "Unknown User"
            
            economy_data = user_data.get("economy", {})
            wallet = economy_data.get("wallet", 0)
            bank = economy_data.get("bank", 0)
            total = wallet + bank
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{medal} **{username}**\n"
            leaderboard_text += f"   {format_currency(total, self.bot.currency_emoji)}\n\n"
        
        embed.description = leaderboard_text
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="bank")
    async def bank(self, ctx):
        """View bank information and upgrades"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        bank_tier = economy_data.get("bank_tier", "bronze")
        bank_balance = economy_data.get("bank", 0)
        
        embed = nextcord.Embed(
            title="🏦 Bank Information",
            color=0x0080ff
        )
        
        # Current tier info
        current_tier = ECONOMY_CONFIG["bank_upgrades"][bank_tier]
        embed.add_field(
            name="📊 Current Tier",
            value=f"**{bank_tier.title()}**\n"
                  f"Limit: {format_currency(current_tier['limit'], self.bot.currency_emoji)}\n"
                  f"Balance: {format_currency(bank_balance, self.bot.currency_emoji)}",
            inline=False
        )
        
        # Available upgrades
        tier_order = ["bronze", "silver", "gold", "platinum"]
        current_index = tier_order.index(bank_tier)
        
        if current_index < len(tier_order) - 1:
            next_tier = tier_order[current_index + 1]
            next_tier_info = ECONOMY_CONFIG["bank_upgrades"][next_tier]
            
            embed.add_field(
                name="⬆️ Next Upgrade",
                value=f"**{next_tier.title()}**\n"
                      f"Cost: {format_currency(next_tier_info['cost'], self.bot.currency_emoji)}\n"
                      f"Limit: {format_currency(next_tier_info['limit'], self.bot.currency_emoji)}\n"
                      f"Use `!bank upgrade` to upgrade!",
                inline=False
            )
        else:
            embed.add_field(
                name="⭐ Maximum Tier",
                value="You have the highest bank tier available!",
                inline=False
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="bankupgrade", aliases=["upgrade"])
    async def bank_upgrade(self, ctx):
        """Upgrade your bank tier"""
        user_id = ctx.author.id
        
        # Get user data
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        bank_tier = economy_data.get("bank_tier", "bronze")
        wallet = economy_data.get("wallet", 0)
        
        # Check if upgrade is available
        tier_order = ["bronze", "silver", "gold", "platinum"]
        current_index = tier_order.index(bank_tier)
        
        if current_index >= len(tier_order) - 1:
            embed = create_error_embed(
                "Maximum Tier",
                "You already have the highest bank tier available!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get next tier info
        next_tier = tier_order[current_index + 1]
        next_tier_info = ECONOMY_CONFIG["bank_upgrades"][next_tier]
        upgrade_cost = next_tier_info["cost"]
        
        # Check if user can afford upgrade
        if wallet < upgrade_cost:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You need {format_currency(upgrade_cost, self.bot.currency_emoji)} to upgrade to {next_tier.title()}.\n"
                f"You have {format_currency(wallet, self.bot.currency_emoji)} in your wallet."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Process upgrade
        await self.bot.db.update_balance(user_id, wallet_change=-upgrade_cost)
        await self.bot.db.update_user(user_id, {"economy.bank_tier": next_tier})
        await self.bot.db.add_transaction(
            user_id, "bank_upgrade", -upgrade_cost, f"Upgraded bank to {next_tier.title()}"
        )
        
        embed = create_success_embed(
            "Bank Upgraded",
            f"Successfully upgraded your bank to **{next_tier.title()}**!\n"
            f"New limit: {format_currency(next_tier_info['limit'], self.bot.currency_emoji)}"
        )
        
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Economy(bot))
