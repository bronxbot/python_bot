"""
Help System for BronxBot
Custom help commands with categorized command listings
"""

import nextcord
from nextcord.ext import commands
from typing import Dict, List, Optional

from utils.logger import get_logger
from utils.bot_utils import create_info_embed, safe_send

logger = get_logger(__name__)


class Help(commands.Cog):
    """Help system for BronxBot"""
    
    def __init__(self, bot):
        self.bot = bot
        self.command_categories = {
            "💰 Economy": [
                "balance", "daily", "pay", "deposit", "withdraw", 
                "bank", "bankupgrade", "leaderboard"
            ],
            "🎣 Fishing": [
                "fish", "fishstats", "fishbook", "rod", "bait", 
                "sell", "fishshop"
            ],
            "🎲 Gambling": [
                "blackjack", "bj", "slots", "coinflip", "roulette", 
                "gamblestats", "gstats"
            ],
            "💼 Work": [
                "work", "boss", "workstats", "workers", "hire", 
                "fire", "minigame"
            ],
            "🤝 Trading": [
                "trade", "quicksell", "tradeoffer", "viewtrade", 
                "accepttrade", "canceltrade"
            ],
            "📈 Stock Market": [
                "market", "stocks", "stock", "portfolio", "buy stock", 
                "sell stock", "marketleaders"
            ],
            "🛒 Shop": [
                "shop", "buy", "inventory", "inv"
            ],
            "🔧 Admin": [
                "stats", "serverinfo", "userinfo", "performance", 
                "addmoney", "removemoney", "dividend"
            ]
        }
    
    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx, *, category: str = None):
        """Show help information"""
        if category is None:
            # Show main help menu
            embed = nextcord.Embed(
                title="🤖 BronxBot Help",
                description="Welcome to BronxBot! Here are all the available categories.",
                color=0x00ff00
            )
            
            for category_name, commands_list in self.command_categories.items():
                embed.add_field(
                    name=category_name,
                    value=f"{len(commands_list)} commands\n`!help {category_name.split()[1].lower()}`",
                    inline=True
                )
            
            embed.add_field(
                name="💡 Getting Started",
                value="• Use `!daily` to get your daily bonus\n"
                      "• Use `!fish` to start fishing\n"
                      "• Use `!work` to earn money\n"
                      "• Use `!balance` to check your money",
                inline=False
            )
            
            embed.set_footer(text="Use !help <category> for specific command help")
            await safe_send(ctx, embed=embed)
            return
        
        # Show specific category help
        category = category.lower()
        category_found = None
        
        for cat_name, commands_list in self.command_categories.items():
            if category in cat_name.lower():
                category_found = cat_name
                break
        
        if not category_found:
            embed = create_info_embed(
                "Category Not Found",
                f"No help category found for '{category}'.\n"
                f"Use `!help` to see all available categories."
            )
            await safe_send(ctx, embed=embed)
            return
        
        embed = nextcord.Embed(
            title=f"🔍 {category_found} Commands",
            color=0x00ff00
        )
        
        commands_list = self.command_categories[category_found]
        
        # Add detailed command information
        if "economy" in category:
            embed.add_field(
                name="💰 Basic Commands",
                value="`!balance` - Check your balance\n"
                      "`!daily` - Get daily bonus\n"
                      "`!pay @user <amount>` - Pay someone\n"
                      "`!leaderboard` - See richest users",
                inline=False
            )
            
            embed.add_field(
                name="🏦 Bank Commands",
                value="`!deposit <amount>` - Deposit to bank\n"
                      "`!withdraw <amount>` - Withdraw from bank\n"
                      "`!bank` - View bank info\n"
                      "`!bankupgrade` - Upgrade bank tier",
                inline=False
            )
        
        elif "fishing" in category:
            embed.add_field(
                name="🎣 Fishing Commands",
                value="`!fish` - Go fishing\n"
                      "`!fishstats` - View fishing stats\n"
                      "`!fishbook` - View fish collection\n"
                      "`!sell <fish_name>` - Sell fish",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Equipment Commands",
                value="`!rod` - Manage fishing rods\n"
                      "`!rod equip <name>` - Equip rod\n"
                      "`!bait` - Manage bait\n"
                      "`!bait equip <name>` - Equip bait",
                inline=False
            )
        
        elif "gambling" in category:
            embed.add_field(
                name="🎲 Game Commands",
                value="`!blackjack <bet>` - Play blackjack\n"
                      "`!slots <bet>` - Play slots\n"
                      "`!coinflip <bet> <heads/tails>` - Flip coin\n"
                      "`!roulette <bet> <number/color>` - Play roulette",
                inline=False
            )
            
            embed.add_field(
                name="📊 Stats Commands",
                value="`!gamblestats` - View gambling statistics",
                inline=False
            )
        
        elif "work" in category:
            embed.add_field(
                name="💼 Work Commands",
                value="`!work` - Work for money\n"
                      "`!boss` - View boss information\n"
                      "`!workstats` - View work statistics\n"
                      "`!minigame` - Play work minigame",
                inline=False
            )
            
            embed.add_field(
                name="👥 Management Commands",
                value="`!workers` - View your workers\n"
                      "`!hire @user` - Hire a worker\n"
                      "`!fire @user` - Fire a worker",
                inline=False
            )
        
        elif "trading" in category:
            embed.add_field(
                name="🤝 Trading Commands",
                value="`!trade @user` - Start a trade\n"
                      "`!quicksell` - Quick sell items\n"
                      "`!tradeoffer` - View trade offers\n"
                      "`!accepttrade <id>` - Accept trade\n"
                      "`!canceltrade <id>` - Cancel trade",
                inline=False
            )
        
        elif "market" in category or "stock" in category:
            embed.add_field(
                name="📈 Market Commands",
                value="`!market` - View stock prices\n"
                      "`!stock <symbol>` - View stock details\n"
                      "`!portfolio` - View your portfolio\n"
                      "`!marketleaders` - Top investors",
                inline=False
            )
            
            embed.add_field(
                name="💱 Trading Commands",
                value="`!buy stock <symbol> <amount>` - Buy stocks\n"
                      "`!sell stock <symbol> <amount>` - Sell stocks",
                inline=False
            )
        
        elif "shop" in category:
            embed.add_field(
                name="🛒 Shop Commands",
                value="`!shop` - View shop categories\n"
                      "`!shop fishing` - View fishing shop\n"
                      "`!inventory` - View your inventory\n"
                      "`!buy <type> <name> [amount]` - Buy items",
                inline=False
            )
        
        elif "admin" in category:
            embed.add_field(
                name="🔧 Admin Commands",
                value="`!stats` - Bot statistics\n"
                      "`!serverinfo` - Server information\n"
                      "`!userinfo @user` - User information\n"
                      "`!performance` - Performance metrics",
                inline=False
            )
            
            embed.add_field(
                name="💰 Economy Admin",
                value="`!addmoney @user <amount>` - Add money\n"
                      "`!removemoney @user <amount>` - Remove money\n"
                      "`!dividend <symbol> <amount>` - Pay dividends",
                inline=False
            )
        
        embed.set_footer(text="Use !help for the main menu")
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="commands", aliases=["cmds"])
    async def commands_list(self, ctx):
        """Show a compact list of all commands"""
        embed = nextcord.Embed(
            title="📋 All Commands",
            description="Complete list of available commands",
            color=0x00ff00
        )
        
        for category_name, commands_list in self.command_categories.items():
            command_text = ", ".join(f"`{cmd}`" for cmd in commands_list[:10])
            if len(commands_list) > 10:
                command_text += f" and {len(commands_list) - 10} more..."
            
            embed.add_field(
                name=category_name,
                value=command_text,
                inline=False
            )
        
        embed.set_footer(text="Use !help <category> for detailed help")
        await safe_send(ctx, embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
