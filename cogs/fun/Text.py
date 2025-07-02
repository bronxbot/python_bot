import nextcord
import random
from nextcord.ext import commands
import string
from typing import List

# Add the project root to Python path to fix imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

class Text(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)

    def get_command_help(self) -> List[nextcord.Embed]:
        """Get paginated help embeds for this cog"""
        embed = nextcord.Embed(
            title="🔤 Text Transformation Commands",
            color=nextcord.Color.blue()
        )
        
        text_commands = ['spongebob', 'tinytext', 'reverse', 'owoify', 'emojify']
        for cmd_name in text_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        
        return [embed]

    @commands.command(aliases=['mock'])
    async def spongebob(self, ctx, *, text):
        """mOcK sOmE tExT lIkE tHiS"""
        if len(text) > 500:
            return await ctx.reply("```text too long (max 500 chars)```")
        result = ''.join([char.upper() if i % 2 == 0 else char.lower() for i, char in enumerate(text)])
        await ctx.reply(f"```{result}```")

    @commands.command(aliases=['smallcaps', 'tiny'])
    async def tinytext(self, ctx, *, text: str):
        """convert to ᵗⁱⁿʸ ˢᵘᵖᵉʳˢᶜʳⁱᵖᵗ"""
        if len(text) > 200:
            return await ctx.reply("```text too long (max 200 chars)```")
        
        mapping = str.maketrans(
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
            'ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖᵠʳˢᵗᵘᵛʷˣʸᶻᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾᵠᴿˢᵀᵁⱽᵂˣʸᶻ'
        )
        result = text.translate(mapping)
        await ctx.reply(f"```{result}```")

    @commands.command(aliases=['textflip', 'tf'])
    async def reverse(self, ctx, *, text: str):
        """ʇxǝʇ ruoy esreveɹ"""
        if len(text) > 500:
            return await ctx.reply("```text too long (max 500 chars)```")
        await ctx.reply(f"```{text[::-1]}```")
    
    @commands.command(aliases=['owo', 'uwu'])
    async def owoify(self, ctx, *, text: str):
        """uwu-ify youw text owo *nuzzles*"""
        if len(text) > 500:
            return await ctx.reply("```text too long (max 500 chars)```")
        
        replacements = {
            'r': 'w', 'l': 'w', 'R': 'W', 'L': 'W',
            'no': 'nyo', 'No': 'Nyo', 'NO': 'NYO',
            'ove': 'uv', 'th': 'f', 'TH': 'F',
            '!': '! uwu', '?': '? owo'
        }
        
        for k, v in replacements.items():
            text = text.replace(k, v)
        
        # Add random uwu expressions
        if random.random() < 0.3:
            text += random.choice([' uwu', ' owo', ' >w<', ' ^w^'])
            
        await ctx.reply(f"```{text}```")

    @commands.command(aliases=['letters'])
    async def emojify(self, ctx, *, text: str):
        """turn text into 🔤 regional 🔤 indicators"""
        if len(text) > 100:
            return await ctx.reply("```text too long (max 100 chars)```")
        
        emoji_map = {
            'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪', 'f': '🇫',
            'g': '🇬', 'h': '🇭', 'i': '🇮', 'j': '🇯', 'k': '🇰', 'l': '🇱',
            'm': '🇲', 'n': '🇳', 'o': '🇴', 'p': '🇵', 'q': '🇶', 'r': '🇷',
            's': '🇸', 't': '🇹', 'u': '🇺', 'v': '🇻', 'w': '🇼', 'x': '🇽',
            'y': '🇾', 'z': '🇿', '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣',
            '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣',
            '!': '❗', '?': '❓', ' ': '   '
        }
        
        result = ''.join([emoji_map.get(c.lower(), c) for c in text])
        await ctx.reply(result)

    # Error handling for missing arguments
    @spongebob.error
    @tinytext.error  
    @reverse.error
    @owoify.error
    @emojify.error
    async def text_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = nextcord.Embed(
                title="❌ Missing Text",
                description="Please provide some text to transform",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)
            return  # Prevent further error propagation

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Only handle errors for commands that belong to this cog
        if ctx.command and ctx.command.cog == self:
            await self.handle_error(ctx, error)

def setup(bot):
    try:
        logger = CogLogger("Text")
        bot.add_cog(Text(bot))
    except Exception as e:
        logger.error(f"Failed to load Text cog: {e}")
        raise e