"""
Gambling system for BronxBot
Includes card games, chance games, and special games
"""

import nextcord
from nextcord.ext import commands
import random
import asyncio
from typing import Optional, Dict, List
import json
from pathlib import Path

from database.database_manager import get_database_manager
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed,
    create_info_embed, safe_send, cooldown_manager
)
from utils.logger import get_logger
from config.settings import GAMBLING_CONFIG

logger = get_logger(__name__)


class GamblingCog(commands.Cog):
    """Gambling commands and games"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = get_database_manager()
        self.active_games = {}  # Track active games
        
    # Utility Methods
    async def get_user_balance(self, user_id: int) -> int:
        """Get user's wallet balance"""
        economy_data = await self.db.get_economy_data(user_id)
        return economy_data.get('wallet', 0) if economy_data else 0
    
    async def can_afford_bet(self, user_id: int, amount: int) -> bool:
        """Check if user can afford a bet"""
        balance = await self.get_user_balance(user_id)
        return balance >= amount
    
    async def place_bet(self, user_id: int, amount: int, won: bool, game_type: str) -> bool:
        """Place a bet and update user balance"""
        if not await self.can_afford_bet(user_id, amount):
            return False
        
        # Calculate winnings
        won_amount = amount * 2 if won else 0
        net_change = won_amount - amount
        
        # Update balance
        await self.db.update_balance(user_id, wallet_change=net_change)
        
        # Update gambling stats
        await self.db.update_gambling_stats(user_id, game_type, amount, won_amount)
        
        # Add transaction record
        description = f"{game_type.title()} - {'Won' if won else 'Lost'}"
        await self.db.add_transaction(user_id, "gambling", net_change, description)
        
        return True
    
    def get_bet_limits(self, user_id: int) -> tuple:
        """Get min and max bet limits for user"""
        # TODO: Implement progressive limits based on user tier
        return GAMBLING_CONFIG["min_bet"], GAMBLING_CONFIG["max_bet"]
    
    # Card Games
    @commands.command(name="blackjack", aliases=["bj"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blackjack(self, ctx, bet_amount: int):
        """🃏 Play blackjack against the dealer"""
        
        # Validation
        if bet_amount <= 0:
            await safe_send(ctx, embed=create_error_embed("Invalid Bet", "Bet amount must be positive"))
            return
        
        min_bet, max_bet = self.get_bet_limits(ctx.author.id)
        if bet_amount < min_bet or bet_amount > max_bet:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Bet", f"Bet must be between {format_currency(min_bet)} and {format_currency(max_bet)}"
            ))
            return
        
        if not await self.can_afford_bet(ctx.author.id, bet_amount):
            await safe_send(ctx, embed=create_error_embed("Insufficient Funds", "You don't have enough money to place this bet"))
            return
        
        # Check if user already has an active game
        if ctx.author.id in self.active_games:
            await safe_send(ctx, embed=create_error_embed("Game Active", "You already have an active game"))
            return
        
        # Start blackjack game
        game = BlackjackGame(ctx.author.id, bet_amount)
        self.active_games[ctx.author.id] = game
        
        # Create initial embed
        embed = game.create_embed()
        view = BlackjackView(game, self)
        
        await safe_send(ctx, embed=embed, view=view)
    
    @commands.command(name="slots")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slots(self, ctx, bet_amount: int):
        """🎰 Play the slot machine"""
        
        # Validation
        if bet_amount <= 0:
            await safe_send(ctx, embed=create_error_embed("Invalid Bet", "Bet amount must be positive"))
            return
        
        min_bet, max_bet = self.get_bet_limits(ctx.author.id)
        if bet_amount < min_bet or bet_amount > max_bet:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Bet", f"Bet must be between {format_currency(min_bet)} and {format_currency(max_bet)}"
            ))
            return
        
        if not await self.can_afford_bet(ctx.author.id, bet_amount):
            await safe_send(ctx, embed=create_error_embed("Insufficient Funds", "You don't have enough money to place this bet"))
            return
        
        # Slot machine symbols and their values
        symbols = {
            "🍒": {"weight": 30, "multiplier": 2},
            "🍋": {"weight": 25, "multiplier": 3},
            "🍊": {"weight": 20, "multiplier": 4},
            "🍇": {"weight": 15, "multiplier": 5},
            "🔔": {"weight": 7, "multiplier": 10},
            "💎": {"weight": 2, "multiplier": 20},
            "🎰": {"weight": 1, "multiplier": 50}
        }
        
        # Generate slot results
        symbol_list = []
        for symbol, data in symbols.items():
            symbol_list.extend([symbol] * data["weight"])
        
        result = [random.choice(symbol_list) for _ in range(3)]
        
        # Calculate winnings
        won = False
        multiplier = 0
        
        if result[0] == result[1] == result[2]:  # All three match
            won = True
            multiplier = symbols[result[0]]["multiplier"]
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:  # Two match
            won = True
            multiplier = 1.5
        
        # Place bet
        winnings = int(bet_amount * multiplier) if won else 0
        net_change = winnings - bet_amount
        
        await self.db.update_balance(ctx.author.id, wallet_change=net_change)
        await self.db.update_gambling_stats(ctx.author.id, "slots", bet_amount, winnings)
        
        # Create result embed
        result_str = " ".join(result)
        
        if won:
            embed = create_success_embed(
                "🎰 Slot Machine - You Won!",
                f"**Result:** {result_str}\n"
                f"**Bet:** {format_currency(bet_amount)}\n"
                f"**Winnings:** {format_currency(winnings)}\n"
                f"**Net Gain:** {format_currency(net_change)}"
            )
            embed.color = 0x00ff00
        else:
            embed = create_error_embed(
                "🎰 Slot Machine - You Lost!",
                f"**Result:** {result_str}\n"
                f"**Bet:** {format_currency(bet_amount)}\n"
                f"**Loss:** {format_currency(bet_amount)}"
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="coinflip", aliases=["cf"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def coinflip(self, ctx, bet_amount: int, choice: str):
        """🪙 Flip a coin and guess heads or tails"""
        
        # Validation
        if bet_amount <= 0:
            await safe_send(ctx, embed=create_error_embed("Invalid Bet", "Bet amount must be positive"))
            return
        
        choice = choice.lower()
        if choice not in ["heads", "tails", "h", "t"]:
            await safe_send(ctx, embed=create_error_embed("Invalid Choice", "Choose 'heads' or 'tails'"))
            return
        
        # Normalize choice
        choice = "heads" if choice in ["heads", "h"] else "tails"
        
        min_bet, max_bet = self.get_bet_limits(ctx.author.id)
        if bet_amount < min_bet or bet_amount > max_bet:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Bet", f"Bet must be between {format_currency(min_bet)} and {format_currency(max_bet)}"
            ))
            return
        
        if not await self.can_afford_bet(ctx.author.id, bet_amount):
            await safe_send(ctx, embed=create_error_embed("Insufficient Funds", "You don't have enough money to place this bet"))
            return
        
        # Flip coin
        result = random.choice(["heads", "tails"])
        won = choice == result
        
        # Place bet
        await self.place_bet(ctx.author.id, bet_amount, won, "coinflip")
        
        # Create result embed
        result_emoji = "🙂" if result == "heads" else "👑"
        
        if won:
            embed = create_success_embed(
                f"🪙 Coinflip - You Won!",
                f"**Result:** {result.title()} {result_emoji}\n"
                f"**Your Choice:** {choice.title()}\n"
                f"**Bet:** {format_currency(bet_amount)}\n"
                f"**Winnings:** {format_currency(bet_amount * 2)}\n"
                f"**Net Gain:** {format_currency(bet_amount)}"
            )
        else:
            embed = create_error_embed(
                f"🪙 Coinflip - You Lost!",
                f"**Result:** {result.title()} {result_emoji}\n"
                f"**Your Choice:** {choice.title()}\n"
                f"**Bet:** {format_currency(bet_amount)}\n"
                f"**Loss:** {format_currency(bet_amount)}"
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="roulette")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def roulette(self, ctx, bet_amount: int, bet_type: str, bet_value: str = None):
        """🎡 Play roulette with various betting options"""
        
        # Validation
        if bet_amount <= 0:
            await safe_send(ctx, embed=create_error_embed("Invalid Bet", "Bet amount must be positive"))
            return
        
        min_bet, max_bet = self.get_bet_limits(ctx.author.id)
        if bet_amount < min_bet or bet_amount > max_bet:
            await safe_send(ctx, embed=create_error_embed(
                "Invalid Bet", f"Bet must be between {format_currency(min_bet)} and {format_currency(max_bet)}"
            ))
            return
        
        if not await self.can_afford_bet(ctx.author.id, bet_amount):
            await safe_send(ctx, embed=create_error_embed("Insufficient Funds", "You don't have enough money to place this bet"))
            return
        
        # Roulette logic
        number = random.randint(0, 36)
        is_red = number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        is_black = number != 0 and not is_red
        is_even = number % 2 == 0 and number != 0
        is_odd = number % 2 == 1
        
        won = False
        multiplier = 0
        
        bet_type = bet_type.lower()
        
        if bet_type == "number" and bet_value:
            try:
                bet_num = int(bet_value)
                if 0 <= bet_num <= 36 and bet_num == number:
                    won = True
                    multiplier = 35
            except ValueError:
                await safe_send(ctx, embed=create_error_embed("Invalid Number", "Please provide a valid number (0-36)"))
                return
        elif bet_type == "red" and is_red:
            won = True
            multiplier = 1
        elif bet_type == "black" and is_black:
            won = True
            multiplier = 1
        elif bet_type == "even" and is_even:
            won = True
            multiplier = 1
        elif bet_type == "odd" and is_odd:
            won = True
            multiplier = 1
        
        # Place bet
        winnings = int(bet_amount * (multiplier + 1)) if won else 0
        net_change = winnings - bet_amount
        
        await self.db.update_balance(ctx.author.id, wallet_change=net_change)
        await self.db.update_gambling_stats(ctx.author.id, "roulette", bet_amount, winnings)
        
        # Create result embed
        color_emoji = "🔴" if is_red else "⚫" if is_black else "🟢"
        
        if won:
            embed = create_success_embed(
                "🎡 Roulette - You Won!",
                f"**Result:** {number} {color_emoji}\n"
                f"**Your Bet:** {bet_type.title()} {bet_value or ''}\n"
                f"**Bet Amount:** {format_currency(bet_amount)}\n"
                f"**Winnings:** {format_currency(winnings)}\n"
                f"**Net Gain:** {format_currency(net_change)}"
            )
        else:
            embed = create_error_embed(
                "🎡 Roulette - You Lost!",
                f"**Result:** {number} {color_emoji}\n"
                f"**Your Bet:** {bet_type.title()} {bet_value or ''}\n"
                f"**Bet Amount:** {format_currency(bet_amount)}\n"
                f"**Loss:** {format_currency(bet_amount)}"
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="gamblingstats", aliases=["gstats"])
    async def gambling_stats(self, ctx, member: nextcord.Member = None):
        """📊 View gambling statistics"""
        
        target = member or ctx.author
        user_data = await self.db.get_user(target.id)
        
        if not user_data:
            await safe_send(ctx, embed=create_error_embed("User Not Found", "No data found for this user"))
            return
        
        gambling_data = user_data.get("gambling", {})
        
        total_bet = gambling_data.get("total_bet", 0)
        total_won = gambling_data.get("total_won", 0)
        games_played = gambling_data.get("games_played", 0)
        biggest_win = gambling_data.get("biggest_win", 0)
        
        net_profit = total_won - total_bet
        win_rate = (total_won / total_bet * 100) if total_bet > 0 else 0
        
        embed = create_info_embed(
            f"🎰 Gambling Stats - {target.display_name}",
            f"**Games Played:** {games_played:,}\n"
            f"**Total Bet:** {format_currency(total_bet)}\n"
            f"**Total Won:** {format_currency(total_won)}\n"
            f"**Net Profit:** {format_currency(net_profit)}\n"
            f"**Win Rate:** {win_rate:.1f}%\n"
            f"**Biggest Win:** {format_currency(biggest_win)}"
        )
        
        await safe_send(ctx, embed=embed)


class BlackjackGame:
    """Blackjack game logic"""
    
    def __init__(self, user_id: int, bet_amount: int):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.deck = self.create_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.player_stands = False
        self.result = None
        
        # Deal initial cards
        self.player_hand.append(self.draw_card())
        self.dealer_hand.append(self.draw_card())
        self.player_hand.append(self.draw_card())
        self.dealer_hand.append(self.draw_card())
    
    def create_deck(self) -> List[Dict]:
        """Create a standard deck of cards"""
        suits = ["♠️", "♥️", "♦️", "♣️"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        
        deck = []
        for suit in suits:
            for rank in ranks:
                value = 11 if rank == "A" else 10 if rank in ["J", "Q", "K"] else int(rank)
                deck.append({"suit": suit, "rank": rank, "value": value})
        
        random.shuffle(deck)
        return deck
    
    def draw_card(self) -> Dict:
        """Draw a card from the deck"""
        return self.deck.pop()
    
    def calculate_hand_value(self, hand: List[Dict]) -> int:
        """Calculate the value of a hand"""
        value = sum(card["value"] for card in hand)
        aces = sum(1 for card in hand if card["rank"] == "A")
        
        # Adjust for aces
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
        
        return value
    
    def hand_to_string(self, hand: List[Dict], hide_first: bool = False) -> str:
        """Convert hand to string representation"""
        if hide_first:
            return "🂠 " + " ".join([f"{card['rank']}{card['suit']}" for card in hand[1:]])
        else:
            return " ".join([f"{card['rank']}{card['suit']}" for card in hand])
    
    def hit(self):
        """Player hits (draws a card)"""
        if not self.game_over:
            self.player_hand.append(self.draw_card())
            if self.calculate_hand_value(self.player_hand) > 21:
                self.game_over = True
                self.result = "bust"
    
    def stand(self):
        """Player stands"""
        self.player_stands = True
        self.dealer_play()
    
    def dealer_play(self):
        """Dealer plays their hand"""
        while self.calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.draw_card())
        
        self.game_over = True
        self.determine_winner()
    
    def determine_winner(self):
        """Determine the winner of the game"""
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        if player_value > 21:
            self.result = "bust"
        elif dealer_value > 21:
            self.result = "dealer_bust"
        elif player_value > dealer_value:
            self.result = "player_wins"
        elif dealer_value > player_value:
            self.result = "dealer_wins"
        else:
            self.result = "tie"
    
    def create_embed(self) -> nextcord.Embed:
        """Create embed for the game state"""
        player_value = self.calculate_hand_value(self.player_hand)
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        
        if self.game_over:
            # Game over embed
            if self.result == "bust":
                embed = create_error_embed("Blackjack - Bust!", "You went over 21!")
            elif self.result == "dealer_bust":
                embed = create_success_embed("Blackjack - You Win!", "Dealer went over 21!")
            elif self.result == "player_wins":
                embed = create_success_embed("Blackjack - You Win!", "You beat the dealer!")
            elif self.result == "dealer_wins":
                embed = create_error_embed("Blackjack - You Lose!", "Dealer beat you!")
            else:
                embed = create_info_embed("Blackjack - Tie!", "It's a push!")
            
            embed.add_field(
                name="Your Hand",
                value=f"{self.hand_to_string(self.player_hand)} (Value: {player_value})",
                inline=False
            )
            embed.add_field(
                name="Dealer's Hand",
                value=f"{self.hand_to_string(self.dealer_hand)} (Value: {dealer_value})",
                inline=False
            )
        else:
            # Game in progress embed
            embed = create_info_embed(
                "🃏 Blackjack",
                f"**Bet:** {format_currency(self.bet_amount)}"
            )
            embed.add_field(
                name="Your Hand",
                value=f"{self.hand_to_string(self.player_hand)} (Value: {player_value})",
                inline=False
            )
            embed.add_field(
                name="Dealer's Hand",
                value=f"{self.hand_to_string(self.dealer_hand, hide_first=True)} (Value: ?)",
                inline=False
            )
        
        return embed


class BlackjackView(nextcord.ui.View):
    """View for blackjack game interactions"""
    
    def __init__(self, game: BlackjackGame, gambling_cog):
        super().__init__(timeout=300)
        self.game = game
        self.gambling_cog = gambling_cog
    
    @nextcord.ui.button(label="Hit", style=nextcord.ButtonStyle.primary)
    async def hit(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Hit button"""
        if interaction.user.id != self.game.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.game.hit()
        embed = self.game.create_embed()
        
        if self.game.game_over:
            # Game over, process result
            won = self.game.result in ["dealer_bust", "player_wins"]
            await self.gambling_cog.place_bet(self.game.user_id, self.game.bet_amount, won, "blackjack")
            
            # Remove from active games
            if self.game.user_id in self.gambling_cog.active_games:
                del self.gambling_cog.active_games[self.game.user_id]
            
            # Disable buttons
            for item in self.children:
                item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="Stand", style=nextcord.ButtonStyle.secondary)
    async def stand(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Stand button"""
        if interaction.user.id != self.game.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.game.stand()
        embed = self.game.create_embed()
        
        # Game over, process result
        won = self.game.result in ["dealer_bust", "player_wins"]
        await self.gambling_cog.place_bet(self.game.user_id, self.game.bet_amount, won, "blackjack")
        
        # Remove from active games
        if self.game.user_id in self.gambling_cog.active_games:
            del self.gambling_cog.active_games[self.game.user_id]
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Handle timeout"""
        if self.game.user_id in self.gambling_cog.active_games:
            del self.gambling_cog.active_games[self.game.user_id]
        
        for item in self.children:
            item.disabled = True


def setup(bot):
    bot.add_cog(GamblingCog(bot))
