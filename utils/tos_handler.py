import nextcord
from nextcord.ext import commands
from datetime import datetime
from utils.db import db
from cogs.logging.logger import CogLogger

class TermsOfService:
    """Terms of Service handler"""
    
    def __init__(self):
        self.db = db
    
    TOS_VERSION = "1.0"
    TOS_TEXT = """
**BronxBot Terms of Service**

By using BronxBot, you agree to the following terms:

**1. Data Collection**
• We collect command usage statistics for improvement
• User IDs and basic profile information are stored
• Economy data (balance, items) is stored per server
• No private message content is stored

**2. Acceptable Use**
• No spam or abuse of bot commands
• No exploitation of bugs or vulnerabilities
• No harassment of other users through bot features
• Follow Discord's Terms of Service

**3. Economy System**
• Virtual currency has no real-world value
• We may reset economy data for balance purposes
• Exploiting economy bugs will result in data reset

**4. Privacy**
• Your data is never sold or shared with third parties
• You can request data deletion by contacting support
• Statistics may be aggregated anonymously

**5. Liability**
• BronxBot is provided "as is" without warranties
• We're not liable for any data loss or service interruption
• Bot functionality may change without notice

**6. Termination**
• We may restrict bot access for Terms violations
• You may stop using the bot at any time
• Data may be retained for security purposes

**Contact**: Join our support server for questions or issues.

**Last Updated**: January 2025
**Version**: 1.0
"""

class TOSModal(nextcord.ui.Modal):
    """Terms of Service acceptance modal"""
    
    def __init__(self, original_user_id: int, prefix: str = "."):
        super().__init__(title="Terms of Service Agreement")
        self.original_user_id = original_user_id
        self.prefix = prefix
    
    agreement = nextcord.ui.TextInput(
        label="Type 'I AGREE' to accept the Terms of Service",
        placeholder="I AGREE",
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: nextcord.Interaction):
        # Check if the user interacting is the original user
        if interaction.user.id != self.original_user_id:
            embed = nextcord.Embed(
                title="❌ Access Denied",
                description=f"You cannot accept terms for someone else. Use `{self.prefix}tos` to accept your own terms.",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if self.agreement.value.upper() == "I AGREE":
            # Check if user exists to avoid resetting existing data
            existing_user = await db.db.users.find_one({"_id": str(interaction.user.id)})
            
            if existing_user:
                # Existing user - only update TOS fields
                await db.db.users.update_one(
                    {"_id": str(interaction.user.id)},
                    {
                        "$set": {
                            "tos_accepted": True,
                            "tos_version": TermsOfService.TOS_VERSION,
                            "tos_accepted_at": datetime.now().isoformat()
                        }
                    }
                )
                
                # Check if they already have a welcome bonus recorded
                if not existing_user.get("tos_welcome_bonus_given", False):
                    # Give welcome bonus and mark as given
                    await db.update_wallet(interaction.user.id, 1000)
                    await db.db.users.update_one(
                        {"_id": str(interaction.user.id)},
                        {"$set": {"tos_welcome_bonus_given": True}}
                    )
                    welcome_bonus_text = "You've received **1,000** coins to get started!"
                else:
                    welcome_bonus_text = "Welcome back! Your account is already set up."
            else:
                # New user - initialize with default values
                await db.db.users.update_one(
                    {"_id": str(interaction.user.id)},
                    {
                        "$set": {
                            "tos_accepted": True,
                            "tos_version": TermsOfService.TOS_VERSION,
                            "tos_accepted_at": datetime.now().isoformat(),
                            "wallet": 1000,  # Give welcome bonus immediately
                            "bank": 0,
                            "created_at": datetime.now().isoformat(),
                            "tos_welcome_bonus_given": True
                        }
                    },
                    upsert=True
                )
                welcome_bonus_text = "You've received **1,000** coins to get started!"
            
            embed = nextcord.Embed(
                title="✅ Terms Accepted",
                description="Thank you for accepting our Terms of Service! You can now use all bot features.",
                color=nextcord.Color.green()
            )
            
            embed.add_field(
                name="🎁 Welcome Bonus",
                value=welcome_bonus_text,
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = nextcord.Embed(
                title="❌ Invalid Response",
                description="Please type exactly 'I AGREE' to accept the Terms of Service.",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class TOSView(nextcord.ui.View):
    """Terms of Service view with buttons"""
    
    def __init__(self, original_user_id: int, prefix: str = "."):
        super().__init__(timeout=300)
        self.original_user_id = original_user_id
        self.prefix = prefix
    
    async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
        """Check if the user interacting is the original user"""
        if interaction.user.id != self.original_user_id:
            embed = nextcord.Embed(
                title="❌ Access Denied",
                description=f"This is not your Terms of Service prompt. Use `{self.prefix}tos` to accept your own terms.",
                color=nextcord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    
    @nextcord.ui.button(label="📋 Read Full Terms", style=nextcord.ButtonStyle.secondary)
    async def read_terms(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        embed = nextcord.Embed(
            title="📋 BronxBot Terms of Service",
            description=TermsOfService.TOS_TEXT,
            color=nextcord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @nextcord.ui.button(label="✅ Accept Terms", style=nextcord.ButtonStyle.success)
    async def accept_terms(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        modal = TOSModal(self.original_user_id, self.prefix)
        await interaction.response.send_modal(modal)
    
    @nextcord.ui.button(label="❌ Decline", style=nextcord.ButtonStyle.danger)
    async def decline_terms(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        embed = nextcord.Embed(
            title="❌ Terms Declined",
            description="You must accept our Terms of Service to use BronxBot features.\n"
                       f"You can review and accept them anytime with `{self.prefix}tos`",
            color=nextcord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

async def check_tos_acceptance(user_id: int) -> bool:
    """Check if user has accepted current TOS version"""
    user = await db.db.users.find_one({"_id": str(user_id)})
    
    if not user:
        return False
    
    return (user.get("tos_accepted", False) and 
            user.get("tos_version") == TermsOfService.TOS_VERSION)

async def prompt_tos_acceptance(ctx) -> bool:
    """Prompt user to accept TOS if not already accepted"""
    if await check_tos_acceptance(ctx.author.id):
        return True
    
    prefix = ctx.prefix
    embed = nextcord.Embed(
        title="📋 Terms of Service Required",
        description="Welcome to BronxBot! Before you can use our features, please review and accept our Terms of Service.",
        color=nextcord.Color.yellow()
    )
    
    embed.add_field(
        name="Why do I need to accept?",
        value="• Required for data protection compliance\n"
              "• Helps us provide better service\n"
              "• Protects both you and our community\n"
              "• One-time requirement per major update",
        inline=False
    )
    
    embed.add_field(
        name="What happens next?",
        value="• Review our terms by clicking the button below\n"
              "• Accept to unlock all bot features\n"
              "• Get a welcome bonus of 1,000 coins!",
        inline=False
    )
    
    view = TOSView(ctx.author.id, prefix)
    await ctx.reply(embed=embed, view=view)
    return False

class TOSCommands(commands.Cog):
    """Terms of Service related commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
    
    @commands.command(name="tos", aliases=["terms", "termsofservice"])
    async def show_tos(self, ctx):
        """Show Terms of Service"""
        user_accepted = await check_tos_acceptance(ctx.author.id)
        
        embed = nextcord.Embed(
            title="our tos",
            color=nextcord.Color.blue() if user_accepted else nextcord.Color.yellow()
        )
        
        if user_accepted:
            embed.description = f"thx for accepting v{TermsOfService.TOS_VERSION}! we hope you enjoy <3"
            embed.add_field(
                name="Need to review?",
                value="Click the button below to read the full terms.",
                inline=False
            )
            
            view = nextcord.ui.View(timeout=300)
            
            async def show_full_terms(interaction):
                # Only allow the original user to interact
                if interaction.user.id != ctx.author.id:
                    embed = nextcord.Embed(
                        title="❌ Access Denied",
                        description=f"This is not your Terms of Service display. Use `{ctx.prefix}tos` to view your own terms.",
                        color=nextcord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                terms_embed = nextcord.Embed(
                    title="full tos",
                    description=TermsOfService.TOS_TEXT,
                    color=nextcord.Color.blue()
                )
                await interaction.response.send_message(embed=terms_embed, ephemeral=True)
            
            button = nextcord.ui.Button(label="read full terms", style=nextcord.ButtonStyle.secondary)
            button.callback = show_full_terms
            view.add_item(button)
            
            await ctx.reply(embed=embed, view=view)
        else:
            await prompt_tos_acceptance(ctx)
    
    @commands.command(name="tosinfo", aliases=["tosdetails"])
    async def tos_info(self, ctx):
        """Show detailed TOS information"""
        embed = nextcord.Embed(
            title="our tos",
            color=nextcord.Color.blue()
        )
        
        user_accepted = await check_tos_acceptance(ctx.author.id)
        
        embed.add_field(
            name="current version",
            value=f"Version {TermsOfService.TOS_VERSION}",
            inline=True
        )
        
        embed.add_field(
            name="current status",
            value="accepted" if user_accepted else "not accepted",
            inline=True
        )
        
        if user_accepted:
            user = await db.db.users.find_one({"_id": str(ctx.author.id)})
            if user and user.get("tos_accepted_at"):
                accepted_date = user["tos_accepted_at"][:10]  # Just the date
                embed.add_field(
                    name="accepted on",
                    value=accepted_date,
                    inline=True
                )
        
        embed.add_field(
            name="what's covered",
            value="• data collection and privacy\n"
              "• acceptable use policies\n"
              "• economy system rules\n",
            inline=False
        )
        
        embed.add_field(
            name="commands",
            value=f"`{ctx.prefix}tos` - view/accept terms\n"
              f"`{ctx.prefix}privacy` - privacy policy\n"
              f"`{ctx.prefix}support` - get help",
            inline=False
        )
        
        await ctx.reply(embed=embed)

async def setup(bot):
    bot.add_cog(TOSCommands(bot))
