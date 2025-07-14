"""
Bazaar/Stock Market System for BronxBot
Virtual stock market with fluctuating prices
"""

import nextcord
from nextcord.ext import commands, tasks
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


class Bazaar(commands.Cog):
    """Bazaar stock market system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.stocks = {
            "BRONX": {
                "name": "Bronx Corp",
                "symbol": "BRONX",
                "price": 100,
                "base_price": 100,
                "volatility": 0.05,
                "trend": 0.0,
                "history": []
            },
            "FISH": {
                "name": "Fish Industries",
                "symbol": "FISH",
                "price": 50,
                "base_price": 50,
                "volatility": 0.08,
                "trend": 0.0,
                "history": []
            },
            "GAMBLE": {
                "name": "Lucky Games Inc",
                "symbol": "GAMBLE",
                "price": 75,
                "base_price": 75,
                "volatility": 0.12,
                "trend": 0.0,
                "history": []
            },
            "WORK": {
                "name": "Labor United",
                "symbol": "WORK",
                "price": 80,
                "base_price": 80,
                "volatility": 0.06,
                "trend": 0.0,
                "history": []
            },
            "TECH": {
                "name": "Tech Innovations",
                "symbol": "TECH",
                "price": 120,
                "base_price": 120,
                "volatility": 0.10,
                "trend": 0.0,
                "history": []
            }
        }
        self.update_prices.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.update_prices.cancel()
    
    @tasks.loop(minutes=5)
    async def update_prices(self):
        """Update stock prices every 5 minutes"""
        for symbol, stock in self.stocks.items():
            # Calculate price change
            volatility = stock["volatility"]
            trend = stock["trend"]
            
            # Random price movement
            change_percent = random.gauss(trend, volatility)
            
            # Update price
            old_price = stock["price"]
            new_price = old_price * (1 + change_percent)
            
            # Prevent prices from going too low or too high
            min_price = stock["base_price"] * 0.1
            max_price = stock["base_price"] * 5.0
            
            new_price = max(min_price, min(max_price, new_price))
            stock["price"] = round(new_price, 2)
            
            # Update trend (mean reversion)
            if new_price > stock["base_price"] * 1.5:
                stock["trend"] = -0.02
            elif new_price < stock["base_price"] * 0.5:
                stock["trend"] = 0.02
            else:
                stock["trend"] = random.uniform(-0.01, 0.01)
            
            # Store price history
            stock["history"].append({
                "timestamp": datetime.now(),
                "price": new_price,
                "change": (new_price - old_price) / old_price * 100
            })
            
            # Keep only last 100 price points
            if len(stock["history"]) > 100:
                stock["history"] = stock["history"][-100:]
    
    @update_prices.before_loop
    async def before_update_prices(self):
        """Wait for bot to be ready before starting price updates"""
        await self.bot.wait_until_ready()
    
    @commands.command(name="market", aliases=["stocks"])
    async def market(self, ctx):
        """View current stock market prices"""
        embed = nextcord.Embed(
            title="📈 Bronx Stock Market",
            description="Current stock prices and trends",
            color=0x00ff00
        )
        
        for symbol, stock in self.stocks.items():
            current_price = stock["price"]
            
            # Calculate change from last price
            change = 0
            change_icon = "📊"
            if len(stock["history"]) > 0:
                last_record = stock["history"][-1]
                change = last_record["change"]
                
                if change > 0:
                    change_icon = "📈"
                elif change < 0:
                    change_icon = "📉"
            
            embed.add_field(
                name=f"{change_icon} {stock['name']} ({symbol})",
                value=f"Price: {format_currency(current_price, self.bot.currency_emoji)}\n"
                      f"Change: {change:+.2f}%",
                inline=True
            )
        
        embed.add_field(
            name="💡 Commands",
            value="`!buy stock <symbol> <amount>` - Buy stocks\n"
                  "`!sell stock <symbol> <amount>` - Sell stocks\n"
                  "`!portfolio` - View your portfolio\n"
                  "`!stock <symbol>` - View stock details",
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="stock")
    async def stock_info(self, ctx, symbol: str):
        """View detailed information about a stock"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            embed = create_error_embed(
                "Stock Not Found",
                f"No stock found with symbol '{symbol}'.\n"
                f"Available stocks: {', '.join(self.stocks.keys())}"
            )
            await safe_send(ctx, embed=embed)
            return
        
        stock = self.stocks[symbol]
        current_price = stock["price"]
        
        embed = nextcord.Embed(
            title=f"📊 {stock['name']} ({symbol})",
            color=0x0080ff
        )
        
        embed.add_field(
            name="💰 Current Price",
            value=format_currency(current_price, self.bot.currency_emoji),
            inline=True
        )
        
        embed.add_field(
            name="📈 Base Price",
            value=format_currency(stock["base_price"], self.bot.currency_emoji),
            inline=True
        )
        
        embed.add_field(
            name="⚡ Volatility",
            value=f"{stock['volatility']*100:.1f}%",
            inline=True
        )
        
        # Price history
        if len(stock["history"]) >= 2:
            history_text = ""
            recent_history = stock["history"][-5:]  # Last 5 price points
            
            for record in recent_history:
                change_icon = "📈" if record["change"] > 0 else "📉" if record["change"] < 0 else "📊"
                history_text += f"{change_icon} {format_currency(record['price'], self.bot.currency_emoji)} ({record['change']:+.1f}%)\n"
            
            embed.add_field(
                name="📉 Recent History",
                value=history_text,
                inline=False
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="portfolio", aliases=["port"])
    async def portfolio(self, ctx, member: nextcord.Member = None):
        """View your or someone else's stock portfolio"""
        target = member or ctx.author
        user_id = target.id
        
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Portfolio",
                f"{target.display_name} doesn't have a portfolio yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        portfolio = user_data.get("portfolio", {})
        
        if not portfolio:
            embed = create_error_embed(
                "Empty Portfolio",
                f"{target.display_name} doesn't own any stocks yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        embed = nextcord.Embed(
            title=f"📊 {target.display_name}'s Portfolio",
            color=0x00ff00
        )
        
        total_value = 0
        portfolio_text = ""
        
        for symbol, amount in portfolio.items():
            if symbol in self.stocks and amount > 0:
                stock = self.stocks[symbol]
                current_price = stock["price"]
                position_value = current_price * amount
                total_value += position_value
                
                portfolio_text += f"**{stock['name']} ({symbol})**\n"
                portfolio_text += f"Amount: {amount}\n"
                portfolio_text += f"Price: {format_currency(current_price, self.bot.currency_emoji)}\n"
                portfolio_text += f"Value: {format_currency(position_value, self.bot.currency_emoji)}\n\n"
        
        embed.description = portfolio_text
        embed.add_field(
            name="💎 Total Portfolio Value",
            value=format_currency(total_value, self.bot.currency_emoji),
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="buy")
    async def buy_stock(self, ctx, item_type: str, symbol: str, amount: int):
        """Buy stocks from the market"""
        if item_type.lower() != "stock":
            # This command is shared with other systems
            return
        
        user_id = ctx.author.id
        symbol = symbol.upper()
        
        # Validate stock
        if symbol not in self.stocks:
            embed = create_error_embed(
                "Stock Not Found",
                f"No stock found with symbol '{symbol}'.\n"
                f"Available stocks: {', '.join(self.stocks.keys())}"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Validate amount
        if amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must buy a positive amount of stocks."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Calculate cost
        stock = self.stocks[symbol]
        cost = stock["price"] * amount
        
        # Check if user has enough money
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            user_data = await self.bot.db.create_user(user_id, ctx.guild.id)
        
        economy_data = user_data.get("economy", {})
        wallet = economy_data.get("wallet", 0)
        
        if cost > wallet:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You need {format_currency(cost, self.bot.currency_emoji)} to buy {amount} {symbol} stocks.\n"
                f"You have {format_currency(wallet, self.bot.currency_emoji)} in your wallet."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Process purchase
        await self.bot.db.update_balance(user_id, wallet_change=-cost)
        
        # Update portfolio
        portfolio = user_data.get("portfolio", {})
        portfolio[symbol] = portfolio.get(symbol, 0) + amount
        await self.bot.db.update_user(user_id, {"portfolio": portfolio})
        
        # Add transaction
        await self.bot.db.add_transaction(
            user_id, "stock_purchase", -cost, f"Bought {amount} {symbol} stocks"
        )
        
        embed = create_success_embed(
            "Stock Purchase",
            f"Successfully bought {amount} **{stock['name']} ({symbol})** stocks for {format_currency(cost, self.bot.currency_emoji)}!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="sell")
    async def sell_stock(self, ctx, item_type: str, symbol: str, amount: int):
        """Sell stocks to the market"""
        if item_type.lower() != "stock":
            # This command is shared with other systems
            return
        
        user_id = ctx.author.id
        symbol = symbol.upper()
        
        # Validate stock
        if symbol not in self.stocks:
            embed = create_error_embed(
                "Stock Not Found",
                f"No stock found with symbol '{symbol}'.\n"
                f"Available stocks: {', '.join(self.stocks.keys())}"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Validate amount
        if amount <= 0:
            embed = create_error_embed(
                "Invalid Amount",
                "You must sell a positive amount of stocks."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Check if user has enough stocks
        user_data = await self.bot.db.get_user(user_id, ctx.guild.id)
        if not user_data:
            embed = create_error_embed(
                "No Stocks",
                f"You don't own any {symbol} stocks."
            )
            await safe_send(ctx, embed=embed)
            return
        
        portfolio = user_data.get("portfolio", {})
        owned_amount = portfolio.get(symbol, 0)
        
        if owned_amount < amount:
            embed = create_error_embed(
                "Insufficient Stocks",
                f"You only own {owned_amount} {symbol} stocks."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Calculate sale value
        stock = self.stocks[symbol]
        sale_value = stock["price"] * amount
        
        # Process sale
        await self.bot.db.update_balance(user_id, wallet_change=sale_value)
        
        # Update portfolio
        portfolio[symbol] = owned_amount - amount
        if portfolio[symbol] <= 0:
            del portfolio[symbol]
        
        await self.bot.db.update_user(user_id, {"portfolio": portfolio})
        
        # Add transaction
        await self.bot.db.add_transaction(
            user_id, "stock_sale", sale_value, f"Sold {amount} {symbol} stocks"
        )
        
        embed = create_success_embed(
            "Stock Sale",
            f"Successfully sold {amount} **{stock['name']} ({symbol})** stocks for {format_currency(sale_value, self.bot.currency_emoji)}!"
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="marketleaders", aliases=["mleaders"])
    async def market_leaders(self, ctx):
        """View top stock portfolio holders"""
        # Get users with portfolios
        users = await self.bot.db.get_users_with_data("portfolio")
        
        if not users:
            embed = create_info_embed(
                "No Investors",
                "No one has started investing in the stock market yet!"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Calculate portfolio values
        user_values = []
        for user_data in users:
            portfolio = user_data.get("portfolio", {})
            total_value = 0
            
            for symbol, amount in portfolio.items():
                if symbol in self.stocks and amount > 0:
                    stock_price = self.stocks[symbol]["price"]
                    total_value += stock_price * amount
            
            if total_value > 0:
                user_values.append({
                    "user_id": user_data["user_id"],
                    "value": total_value
                })
        
        # Sort by value
        user_values.sort(key=lambda x: x["value"], reverse=True)
        
        embed = nextcord.Embed(
            title="📊 Top Stock Investors",
            color=0x00ff00
        )
        
        leaderboard_text = ""
        for i, user_data in enumerate(user_values[:10], 1):
            user = self.bot.get_user(user_data["user_id"])
            username = user.display_name if user else "Unknown User"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{medal} **{username}**\n"
            leaderboard_text += f"   {format_currency(user_data['value'], self.bot.currency_emoji)}\n\n"
        
        embed.description = leaderboard_text
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="dividend")
    @commands.has_permissions(administrator=True)
    async def pay_dividend(self, ctx, symbol: str, amount: float):
        """Pay dividends to stock holders (Admin only)"""
        symbol = symbol.upper()
        
        if symbol not in self.stocks:
            embed = create_error_embed(
                "Stock Not Found",
                f"No stock found with symbol '{symbol}'."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get all users with this stock
        users = await self.bot.db.get_users_with_data("portfolio")
        total_paid = 0
        recipients = 0
        
        for user_data in users:
            portfolio = user_data.get("portfolio", {})
            owned_amount = portfolio.get(symbol, 0)
            
            if owned_amount > 0:
                dividend_payment = owned_amount * amount
                user_id = user_data["user_id"]
                
                # Pay dividend
                await self.bot.db.update_balance(user_id, wallet_change=dividend_payment)
                await self.bot.db.add_transaction(
                    user_id, "dividend", dividend_payment, f"Dividend from {symbol}"
                )
                
                total_paid += dividend_payment
                recipients += 1
        
        embed = create_success_embed(
            "Dividend Paid",
            f"Paid {format_currency(amount, self.bot.currency_emoji)} per share dividend for **{self.stocks[symbol]['name']} ({symbol})**.\n"
            f"Total paid: {format_currency(total_paid, self.bot.currency_emoji)}\n"
            f"Recipients: {recipients}"
        )
        
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Bazaar(bot))
