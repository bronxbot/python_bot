import nextcord
import random
import asyncio
import time
import sys
import os
from nextcord.ext import commands
from typing import Dict, List, Optional, Tuple

# Add the project root to Python path to fix imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cogs.logging.logger import CogLogger
from cogs.logging.stats_logger import StatsLogger
from utils.error_handler import ErrorHandler
from utils.db import AsyncDatabase
from utils.safe_reply import safe_reply
from utils.amount_parser import parse_amount
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
import functools

db = AsyncDatabase.get_instance()

def requires_tos():
    """Decorator to ensure user has accepted ToS before using gambling commands"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            if not await check_tos_acceptance(ctx.author.id):
                await prompt_tos_acceptance(ctx)
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator

class GambleOff(commands.Cog, ErrorHandler):
    """Gambling Elimination - Last person standing wins!"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.stats_logger = StatsLogger()
        self.currency = "<:bronkbuk:1377389238290747582>"
        
        # Active elimination games - key: channel_id, value: game data
        self.active_eliminations: Dict[int, Dict] = {}
        
        # Available gambling games for elimination
        self.elimination_games = [
            "coinflip",
            "slots", 
            "dice",
            "blackjack",
            "higher_lower"
        ]
        
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
        self.logger.info("GambleOff module initialized")

    async def cog_check(self, ctx):
        """Global check for gambling elimination commands"""
        if ctx.channel.id in self.blocked_channels:
            await ctx.reply("❌ Gambling commands are not allowed in this channel!")
            return False
        return True

    def get_command_help(self) -> list[nextcord.Embed]:
        """Get paginated help embeds for this cog"""
        pages = []
        
        embed = nextcord.Embed(
            title="🎰 Gambling Elimination Commands",
            color=nextcord.Color.red()
        )
        embed.add_field(
            name="gambleoff <bet>",
            value="Start a gambling elimination tournament\nAliases: elimination, elim",
            inline=False
        )
        embed.add_field(
            name="How it works:",
            value="• React within 30 seconds to join\n• Random gambling game chosen each round\n• Players eliminated if they bust or perform poorly\n• Last 3 players split the pot (15%, 30%, 55%)",
            inline=False
        )
        pages.append(embed)
        
        return pages

    @commands.command(aliases=['elimination', 'elim'])
    @commands.cooldown(1, 30, commands.BucketType.channel)
    @requires_tos()
    async def gambleoff(self, ctx, bet: str):
        """Start a gambling elimination tournament
        
        Usage: `.gambleoff <bet>`
        Examples: `.gambleoff 1000`, `.gambleoff 50%`, `.gambleoff all`
        
        Rules:
        - React with 🎰 within 30 seconds to join
        - Each round, a random gambling game is chosen
        - Players are eliminated if they bust or perform poorly (bottom 20%)
        - Tournament continues until 3 players remain
        - Final 3 split the total pot: 3rd place (15%), 2nd place (30%), 1st place (55%)
        """
        # Check if elimination already active in this channel
        if ctx.channel.id in self.active_eliminations:
            await safe_reply(ctx, "❌ An elimination tournament is already active in this channel!")
            return

        # Parse and validate bet amount
        wallet = await db.get_wallet_balance(ctx.author.id)
        bet_amount, error = parse_amount(bet, wallet)
        
        if error:
            await safe_reply(ctx, f"❌ {error}")
            return
            
        if bet_amount is None or bet_amount <= 0:
            await safe_reply(ctx, "❌ Invalid bet amount!")
            return
            
        if bet_amount > wallet:
            await safe_reply(ctx, f"❌ You don't have enough {self.currency}! You have {wallet:,}")
            return
            
        if bet_amount < 100:
            await safe_reply(ctx, f"❌ Minimum bet is 100 {self.currency}!")
            return

        # Create elimination game
        elimination_data = {
            "organizer": ctx.author.id,
            "bet_amount": bet_amount,
            "players": {},  # user_id: {"balance": int, "eliminated": bool, "round_results": []}
            "round": 0,
            "status": "signup",
            "start_time": time.time(),
            "channel_id": ctx.channel.id
        }
        
        self.active_eliminations[ctx.channel.id] = elimination_data

        # Create signup embed
        embed = nextcord.Embed(
            title="🎰 Gambling Elimination Tournament",
            description=f"**Entry Fee:** {bet_amount:,} {self.currency}\n\n"
                       f"React with 🎰 to join!\n"
                       f"**Time remaining:** 30 seconds",
            color=nextcord.Color.red()
        )
        embed.add_field(
            name="📋 Rules",
            value="• Each round plays a random gambling game\n"
                  "• Bottom 20% of performers get eliminated\n"
                  "• Last 3 players split the total pot\n"
                  "• 3rd: 15% | 2nd: 30% | 1st: 55%",
            inline=False
        )
        embed.add_field(
            name="👥 Players (0)",
            value="None yet...",
            inline=False
        )
        embed.set_footer(text=f"Started by {ctx.author.display_name}")

        message = await ctx.send(embed=embed)
        await message.add_reaction("🎰")
        
        # Store message for editing
        elimination_data["message"] = message
        
        # Start signup countdown
        await self._handle_signup_phase(ctx, elimination_data)

    async def _handle_signup_phase(self, ctx, elimination_data):
        """Handle the 30-second signup phase"""
        for remaining in range(30, 0, -5):
            await asyncio.sleep(5)
            
            # Check if elimination was cancelled
            if ctx.channel.id not in self.active_eliminations:
                return
                
            # Update embed with remaining time
            embed = elimination_data["message"].embeds[0]
            description = embed.description.split("**Time remaining:**")[0]
            embed.description = f"{description}**Time remaining:** {remaining} seconds"
            
            # Update player count
            player_count = len(elimination_data["players"])
            if player_count > 0:
                player_list = []
                for i, (user_id, data) in enumerate(elimination_data["players"].items(), 1):
                    user = self.bot.get_user(user_id)
                    player_list.append(f"{i}. {user.display_name if user else 'Unknown User'}")
                embed.set_field_at(1, name=f"👥 Players ({player_count})", value="\n".join(player_list), inline=False)
            
            try:
                await elimination_data["message"].edit(embed=embed)
            except nextcord.NotFound:
                # Message was deleted, cancel elimination
                del self.active_eliminations[ctx.channel.id]
                return
            except Exception as e:
                self.logger.error(f"Error updating signup message: {e}")

        # Signup phase ended
        await self._start_elimination(ctx, elimination_data)

    async def _start_elimination(self, ctx, elimination_data):
        """Start the elimination tournament"""
        player_count = len(elimination_data["players"])
        
        if player_count < 3:
            embed = nextcord.Embed(
                title="🎰 Tournament Cancelled",
                description=f"Not enough players joined! Minimum 3 required, got {player_count}.",
                color=nextcord.Color.red()
            )
            await elimination_data["message"].edit(embed=embed)
            del self.active_eliminations[ctx.channel.id]
            return

        # Collect entry fees
        async with db.client.start_session() as session:
            async with session.start_transaction():
                for user_id in elimination_data["players"]:
                    current_balance = await db.get_wallet_balance(user_id, session=session)
                    if current_balance < elimination_data["bet_amount"]:
                        embed = nextcord.Embed(
                            title="🎰 Tournament Cancelled",
                            description=f"<@{user_id}> doesn't have enough {self.currency} to cover their bet!",
                            color=nextcord.Color.red()
                        )
                        await elimination_data["message"].edit(embed=embed)
                        del self.active_eliminations[ctx.channel.id]
                        return
                    
                    await db.adjust_wallet_balance(user_id, -elimination_data["bet_amount"], session=session)

        elimination_data["status"] = "active"
        elimination_data["total_pot"] = player_count * elimination_data["bet_amount"]
        
        # Initialize player data
        for user_id in elimination_data["players"]:
            elimination_data["players"][user_id] = {
                "balance": elimination_data["bet_amount"],
                "eliminated": False,
                "round_results": []
            }

        await self._run_elimination_round(ctx, elimination_data)

    async def _run_elimination_round(self, ctx, elimination_data):
        """Run a single elimination round"""
        elimination_data["round"] += 1
        active_players = [uid for uid, data in elimination_data["players"].items() if not data["eliminated"]]
        
        if len(active_players) <= 3:
            await self._end_elimination(ctx, elimination_data)
            return

        # Choose random game
        game = random.choice(self.elimination_games)
        
        # Announce round
        embed = nextcord.Embed(
            title=f"🎰 Round {elimination_data['round']} - {game.title()}",
            description=f"**Game:** {game.title()}\n"
                       f"**Active Players:** {len(active_players)}\n"
                       f"**Total Pot:** {elimination_data['total_pot']:,} {self.currency}",
            color=nextcord.Color.orange()
        )
        embed.add_field(
            name="⚡ Starting Round...",
            value="Each player will play the game with their current balance as the bet!",
            inline=False
        )
        
        await elimination_data["message"].edit(embed=embed)
        await asyncio.sleep(3)

        # Play the game for each player
        results = []
        for user_id in active_players:
            player_data = elimination_data["players"][user_id]
            current_balance = player_data["balance"]
            
            # Play the chosen game
            result = await self._play_game(game, current_balance)
            player_data["round_results"].append({
                "game": game,
                "bet": current_balance,
                "result": result,
                "round": elimination_data["round"]
            })
            
            # Update balance
            new_balance = max(0, current_balance + result)
            player_data["balance"] = new_balance
            
            user = self.bot.get_user(user_id)
            results.append({
                "user_id": user_id,
                "user": user,
                "old_balance": current_balance,
                "result": result,
                "new_balance": new_balance,
                "busted": new_balance == 0
            })

        # Show round results
        await self._show_round_results(ctx, elimination_data, results, game)
        
        # Eliminate players
        await self._eliminate_players(ctx, elimination_data, results)

    async def _play_game(self, game: str, bet: int) -> int:
        """Simulate playing a gambling game and return the result (profit/loss)"""
        if game == "coinflip":
            if random.random() < 0.45:  # 45% chance to win
                return int(bet * 0.9)  # 0.9x payout
            else:
                return -bet  # Lose entire bet

        elif game == "slots":
            # Simplified slots - various outcomes
            roll = random.random()
            if roll < 0.01:  # 1% jackpot
                return int(bet * 4)
            elif roll < 0.05:  # 4% big win  
                return int(bet * 2)
            elif roll < 0.15:  # 10% medium win
                return int(bet * 1.5)
            elif roll < 0.35:  # 20% small win
                return int(bet * 0.5)
            else:  # 65% loss
                return -bet

        elif game == "dice":
            # Roll 2 dice, need 7 or higher to win
            roll = random.randint(1, 6) + random.randint(1, 6)
            if roll >= 7:
                return int(bet * 0.8)
            else:
                return -bet

        elif game == "blackjack":
            # Simplified blackjack simulation
            player_total = random.randint(12, 21)  # Player's final hand
            dealer_total = random.randint(17, 21)  # Dealer must hit on 16
            
            if player_total > 21:  # Player busts
                return -bet
            elif dealer_total > 21:  # Dealer busts
                return bet
            elif player_total > dealer_total:  # Player wins
                return bet
            elif player_total == dealer_total:  # Push
                return 0
            else:  # Dealer wins
                return -bet

        elif game == "higher_lower":
            # Guess if next card is higher or lower
            card1 = random.randint(1, 13)
            card2 = random.randint(1, 13)
            
            # Randomly choose higher or lower
            guess_higher = random.choice([True, False])
            
            if (guess_higher and card2 > card1) or (not guess_higher and card2 < card1):
                return int(bet * 0.8)
            elif card2 == card1:  # Tie
                return 0
            else:
                return -bet

        return -bet  # Default to loss

    async def _show_round_results(self, ctx, elimination_data, results, game):
        """Show the results of the round"""
        embed = nextcord.Embed(
            title=f"🎲 Round {elimination_data['round']} Results - {game.title()}",
            color=nextcord.Color.blue()
        )
        
        # Sort by performance (new balance descending)
        results.sort(key=lambda x: x["new_balance"], reverse=True)
        
        result_text = ""
        for i, result in enumerate(results, 1):
            user = result["user"]
            username = user.display_name if user else "Unknown User"
            
            if result["busted"]:
                status = "💀 BUSTED"
            elif result["result"] > 0:
                status = f"+{result['result']:,} {self.currency}"
            elif result["result"] == 0:
                status = "±0"
            else:
                status = f"{result['result']:,} {self.currency}"
            
            result_text += f"{i}. **{username}**: {result['new_balance']:,} {self.currency} ({status})\n"
        
        embed.description = result_text
        embed.set_footer(text="Elimination phase starting...")
        
        await elimination_data["message"].edit(embed=embed)
        await asyncio.sleep(5)

    async def _eliminate_players(self, ctx, elimination_data, results):
        """Eliminate the worst performing players"""
        active_results = [r for r in results if not r["busted"]]
        
        # First eliminate all busted players
        busted_count = 0
        for result in results:
            if result["busted"]:
                elimination_data["players"][result["user_id"]]["eliminated"] = True
                busted_count += 1

        remaining_active = len(active_results)
        
        if remaining_active <= 3:
            await self._end_elimination(ctx, elimination_data)
            return

        # Calculate how many more to eliminate (bottom 20%, minimum 1)
        elimination_count = max(1, int(remaining_active * 0.2))
        
        # Don't eliminate if it would bring us below 3 players
        if remaining_active - elimination_count < 3:
            elimination_count = remaining_active - 3

        # Sort by performance and eliminate the worst
        active_results.sort(key=lambda x: x["new_balance"])
        eliminated_this_round = []
        
        for i in range(elimination_count):
            result = active_results[i]
            elimination_data["players"][result["user_id"]]["eliminated"] = True
            eliminated_this_round.append(result)

        # Show elimination results
        if busted_count > 0 or eliminated_this_round:
            embed = nextcord.Embed(
                title="💀 Elimination Results",
                color=nextcord.Color.red()
            )
            
            elimination_text = ""
            if busted_count > 0:
                elimination_text += f"**{busted_count} player(s) busted!**\n\n"
            
            if eliminated_this_round:
                elimination_text += "**Bottom performers eliminated:**\n"
                for result in eliminated_this_round:
                    user = result["user"]
                    username = user.display_name if user else "Unknown User"
                    elimination_text += f"• {username} ({result['new_balance']:,} {self.currency})\n"
            
            remaining = len([p for p in elimination_data["players"].values() if not p["eliminated"]])
            elimination_text += f"\n**Players remaining:** {remaining}"
            
            embed.description = elimination_text
            embed.set_footer(text="Next round starting in 5 seconds...")
            
            await elimination_data["message"].edit(embed=embed)
            await asyncio.sleep(5)

        # Continue to next round
        await self._run_elimination_round(ctx, elimination_data)

    async def _end_elimination(self, ctx, elimination_data):
        """End the elimination and distribute prizes"""
        final_players = [(uid, data) for uid, data in elimination_data["players"].items() if not data["eliminated"]]
        final_players.sort(key=lambda x: x[1]["balance"], reverse=True)
        
        total_pot = elimination_data["total_pot"]
        
        # Calculate payouts (55%, 30%, 15%)
        payouts = [
            int(total_pot * 0.55),  # 1st place
            int(total_pot * 0.30),  # 2nd place  
            int(total_pot * 0.15)   # 3rd place
        ]
        
        # Adjust for any rounding errors
        payout_sum = sum(payouts)
        if payout_sum != total_pot:
            payouts[0] += total_pot - payout_sum

        # Distribute prizes
        async with db.client.start_session() as session:
            async with session.start_transaction():
                for i, (user_id, player_data) in enumerate(final_players[:3]):
                    if i < len(payouts):
                        await db.adjust_wallet_balance(user_id, payouts[i], session=session)

        # Create final results embed
        embed = nextcord.Embed(
            title="🏆 Gambling Elimination Tournament - Final Results!",
            color=nextcord.Color.gold()
        )
        
        places = ["🥇", "🥈", "🥉"]
        place_names = ["1st Place", "2nd Place", "3rd Place"]
        
        results_text = f"**Total Pot:** {total_pot:,} {self.currency}\n\n"
        
        for i, (user_id, player_data) in enumerate(final_players[:3]):
            user = self.bot.get_user(user_id)
            username = user.display_name if user else "Unknown User"
            payout = payouts[i] if i < len(payouts) else 0
            percentage = (payout / total_pot * 100) if total_pot > 0 else 0
            
            results_text += f"{places[i]} **{place_names[i]}:** {username}\n"
            results_text += f"Final Balance: {player_data['balance']:,} {self.currency}\n"
            results_text += f"Prize: {payout:,} {self.currency} ({percentage:.1f}%)\n\n"
        
        embed.description = results_text
        embed.set_footer(text=f"Tournament lasted {elimination_data['round']} rounds")
        
        await elimination_data["message"].edit(embed=embed)
        
        # Log stats
        await self.stats_logger.log_command_use(
            ctx.author.id, 
            ctx.guild.id if ctx.guild else None,
            "gambleoff", 
            {"players": len(elimination_data["players"]), "pot": total_pot, "rounds": elimination_data["round"]}
        )
        
        # Clean up
        del self.active_eliminations[ctx.channel.id]

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle signup reactions"""
        if user.bot or reaction.emoji != "🎰":
            return
            
        channel_id = reaction.message.channel.id
        if channel_id not in self.active_eliminations:
            return
            
        elimination_data = self.active_eliminations[channel_id]
        if elimination_data["status"] != "signup":
            return
            
        if reaction.message.id != elimination_data["message"].id:
            return

        # Check if user already joined
        if user.id in elimination_data["players"]:
            return

        # Check if user has enough money
        wallet = await db.get_wallet_balance(user.id)
        if wallet < elimination_data["bet_amount"]:
            try:
                await user.send(f"❌ You don't have enough {self.currency} to join this elimination! "
                              f"Need: {elimination_data['bet_amount']:,}, Have: {wallet:,}")
            except:
                pass  # User has DMs disabled
            return

        # Add player
        elimination_data["players"][user.id] = {}
        
        # Update embed with new player count
        embed = elimination_data["message"].embeds[0]
        player_count = len(elimination_data["players"])
        
        player_list = []
        for i, (user_id, data) in enumerate(elimination_data["players"].items(), 1):
            player_user = self.bot.get_user(user_id)
            player_list.append(f"{i}. {player_user.display_name if player_user else 'Unknown User'}")
        
        embed.set_field_at(1, name=f"👥 Players ({player_count})", value="\n".join(player_list), inline=False)
        
        try:
            await elimination_data["message"].edit(embed=embed)
        except Exception as e:
            self.logger.error(f"Error updating elimination embed: {e}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        """Handle signup reaction removals"""
        if user.bot or reaction.emoji != "🎰":
            return
            
        channel_id = reaction.message.channel.id
        if channel_id not in self.active_eliminations:
            return
            
        elimination_data = self.active_eliminations[channel_id]
        if elimination_data["status"] != "signup":
            return
            
        if reaction.message.id != elimination_data["message"].id:
            return

        # Remove player if they were joined
        if user.id in elimination_data["players"]:
            del elimination_data["players"][user.id]
            
            # Update embed
            embed = elimination_data["message"].embeds[0]
            player_count = len(elimination_data["players"])
            
            if player_count > 0:
                player_list = []
                for i, (user_id, data) in enumerate(elimination_data["players"].items(), 1):
                    player_user = self.bot.get_user(user_id)
                    player_list.append(f"{i}. {player_user.display_name if player_user else 'Unknown User'}")
                embed.set_field_at(1, name=f"👥 Players ({player_count})", value="\n".join(player_list), inline=False)
            else:
                embed.set_field_at(1, name="👥 Players (0)", value="None yet...", inline=False)
            
            try:
                await elimination_data["message"].edit(embed=embed)
            except Exception as e:
                self.logger.error(f"Error updating elimination embed: {e}")

def setup(bot):
    bot.add_cog(GambleOff(bot))
