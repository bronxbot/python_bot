"""
Work system for BronxBot
Includes job types, boss relationships, and minigames
"""

import nextcord
from nextcord.ext import commands
import random
import time
from typing import Dict, List, Optional
import json

from database.database_manager import get_database_manager
from utils.bot_utils import (
    format_currency, create_error_embed, create_success_embed,
    create_info_embed, safe_send, cooldown_manager
)
from utils.logger import get_logger
from config.settings import WORK_CONFIG

logger = get_logger(__name__)


class WorkCog(commands.Cog):
    """Work system with jobs, bosses, and minigames"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = get_database_manager()
        self.jobs = self.load_jobs()
        self.active_work_sessions = {}
    
    def load_jobs(self) -> Dict:
        """Load job definitions"""
        return {
            "cashier": {
                "name": "Cashier",
                "description": "Work at a retail store scanning items",
                "base_wage": 150,
                "max_wage": 400,
                "minigame": "scan_items",
                "icon": "🛒"
            },
            "delivery_driver": {
                "name": "Delivery Driver",
                "description": "Deliver packages around the city",
                "base_wage": 200,
                "max_wage": 500,
                "minigame": "deliver_packages",
                "icon": "🚚"
            },
            "chef": {
                "name": "Chef",
                "description": "Cook meals in a restaurant kitchen",
                "base_wage": 250,
                "max_wage": 600,
                "minigame": "cook_meals",
                "icon": "👨‍🍳"
            },
            "programmer": {
                "name": "Programmer",
                "description": "Write code and fix bugs",
                "base_wage": 400,
                "max_wage": 1000,
                "minigame": "debug_code",
                "icon": "💻"
            },
            "doctor": {
                "name": "Doctor",
                "description": "Treat patients at the hospital",
                "base_wage": 600,
                "max_wage": 1500,
                "minigame": "treat_patients",
                "icon": "👨‍⚕️"
            },
            "lawyer": {
                "name": "Lawyer",
                "description": "Defend clients in court",
                "base_wage": 800,
                "max_wage": 2000,
                "minigame": "court_case",
                "icon": "⚖️"
            }
        }
    
    async def get_user_work_data(self, user_id: int) -> Dict:
        """Get user's work data"""
        user_data = await self.db.get_user(user_id)
        if not user_data:
            user_data = await self.db.create_user(user_id)
        
        return user_data.get("work", {})
    
    def get_boss_relationship_multiplier(self, relationship: str) -> float:
        """Get wage multiplier based on boss relationship"""
        return WORK_CONFIG["boss_relationship_effects"].get(relationship, 1.0)
    
    def can_work(self, user_id: int, last_work: Optional[float]) -> bool:
        """Check if user can work (not on cooldown)"""
        if not last_work:
            return True
        
        cooldown_seconds = WORK_CONFIG["cooldown_minutes"] * 60
        return time.time() - last_work >= cooldown_seconds
    
    def get_remaining_cooldown(self, last_work: Optional[float]) -> float:
        """Get remaining work cooldown in seconds"""
        if not last_work:
            return 0
        
        cooldown_seconds = WORK_CONFIG["cooldown_minutes"] * 60
        elapsed = time.time() - last_work
        return max(0, cooldown_seconds - elapsed)
    
    @commands.command(name="work")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work(self, ctx):
        """💼 Work at your job to earn money"""
        
        work_data = await self.get_user_work_data(ctx.author.id)
        
        # Check if user has a job
        if not work_data.get("job"):
            embed = create_error_embed(
                "No Job",
                "You don't have a job! Use `!job apply <job_name>` to apply for a job.\n"
                "Use `!jobs` to see available jobs."
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Check cooldown
        last_work = work_data.get("last_work")
        if not self.can_work(ctx.author.id, last_work):
            remaining = self.get_remaining_cooldown(last_work)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            
            embed = create_error_embed(
                "Work Cooldown",
                f"You can work again in {minutes}m {seconds}s"
            )
            await safe_send(ctx, embed=embed)
            return
        
        # Get job info
        job_key = work_data["job"]
        job_info = self.jobs.get(job_key)
        
        if not job_info:
            embed = create_error_embed("Invalid Job", "Your job no longer exists. Please apply for a new job.")
            await safe_send(ctx, embed=embed)
            return
        
        # Start work session
        work_session = WorkSession(ctx.author.id, job_key, job_info, work_data)
        self.active_work_sessions[ctx.author.id] = work_session
        
        # Create work embed with minigame
        embed = work_session.create_embed()
        view = WorkView(work_session, self)
        
        await safe_send(ctx, embed=embed, view=view)
    
    @commands.command(name="jobs")
    async def jobs(self, ctx):
        """📋 View available jobs"""
        
        embed = create_info_embed("Available Jobs", "Choose a job to apply for:")
        
        for job_key, job_info in self.jobs.items():
            wage_range = f"{format_currency(job_info['base_wage'])} - {format_currency(job_info['max_wage'])}"
            embed.add_field(
                name=f"{job_info['icon']} {job_info['name']}",
                value=f"{job_info['description']}\n**Wage:** {wage_range}",
                inline=False
            )
        
        embed.add_field(
            name="How to Apply",
            value="Use `!job apply <job_name>` to apply for a job",
            inline=False
        )
        
        await safe_send(ctx, embed=embed)
    
    @commands.group(name="job", invoke_without_command=True)
    async def job_group(self, ctx):
        """💼 Job management commands"""
        await ctx.send_help(ctx.command)
    
    @job_group.command(name="apply")
    async def job_apply(self, ctx, *, job_name: str):
        """Apply for a job"""
        
        # Find job by name
        job_key = None
        for key, job_info in self.jobs.items():
            if job_info["name"].lower() == job_name.lower() or key == job_name.lower():
                job_key = key
                break
        
        if not job_key:
            await safe_send(ctx, embed=create_error_embed("Job Not Found", f"Job '{job_name}' not found. Use `!jobs` to see available jobs."))
            return
        
        # Update user's job
        await self.db.update_user(ctx.author.id, {"work.job": job_key})
        
        job_info = self.jobs[job_key]
        embed = create_success_embed(
            "Job Application Successful",
            f"You've been hired as a {job_info['name']}!\n"
            f"Use `!work` to start working and earn money."
        )
        
        await safe_send(ctx, embed=embed)
    
    @job_group.command(name="quit")
    async def job_quit(self, ctx):
        """Quit your current job"""
        
        work_data = await self.get_user_work_data(ctx.author.id)
        
        if not work_data.get("job"):
            await safe_send(ctx, embed=create_error_embed("No Job", "You don't have a job to quit."))
            return
        
        # Reset work data
        await self.db.update_user(ctx.author.id, {
            "work.job": None,
            "work.boss_relationship": "neutral"
        })
        
        embed = create_success_embed(
            "Job Quit",
            "You've quit your job. You can apply for a new job anytime."
        )
        
        await safe_send(ctx, embed=embed)
    
    @job_group.command(name="info")
    async def job_info(self, ctx):
        """View information about your current job"""
        
        work_data = await self.get_user_work_data(ctx.author.id)
        
        if not work_data.get("job"):
            await safe_send(ctx, embed=create_error_embed("No Job", "You don't have a job. Use `!job apply <job_name>` to apply for one."))
            return
        
        job_key = work_data["job"]
        job_info = self.jobs.get(job_key)
        
        if not job_info:
            await safe_send(ctx, embed=create_error_embed("Invalid Job", "Your job no longer exists."))
            return
        
        boss_relationship = work_data.get("boss_relationship", "neutral")
        total_worked = work_data.get("total_worked", 0)
        total_earned = work_data.get("total_earned", 0)
        
        relationship_emoji = {
            "hostile": "😡",
            "neutral": "😐",
            "friendly": "😊",
            "loyal": "🤝"
        }.get(boss_relationship, "😐")
        
        embed = create_info_embed(
            f"{job_info['icon']} Your Job: {job_info['name']}",
            f"**Description:** {job_info['description']}\n"
            f"**Wage Range:** {format_currency(job_info['base_wage'])} - {format_currency(job_info['max_wage'])}\n"
            f"**Boss Relationship:** {relationship_emoji} {boss_relationship.title()}\n"
            f"**Times Worked:** {total_worked:,}\n"
            f"**Total Earned:** {format_currency(total_earned)}"
        )
        
        # Show cooldown if applicable
        last_work = work_data.get("last_work")
        if last_work and not self.can_work(ctx.author.id, last_work):
            remaining = self.get_remaining_cooldown(last_work)
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            embed.add_field(
                name="Work Cooldown",
                value=f"You can work again in {minutes}m {seconds}s",
                inline=False
            )
        
        await safe_send(ctx, embed=embed)
    
    @commands.command(name="boss")
    async def boss_interaction(self, ctx):
        """🤵 Interact with your boss"""
        
        work_data = await self.get_user_work_data(ctx.author.id)
        
        if not work_data.get("job"):
            await safe_send(ctx, embed=create_error_embed("No Job", "You need a job to interact with your boss."))
            return
        
        boss_session = BossSession(ctx.author.id, work_data)
        
        embed = boss_session.create_embed()
        view = BossView(boss_session, self)
        
        await safe_send(ctx, embed=embed, view=view)


class WorkSession:
    """Represents a work session with minigames"""
    
    def __init__(self, user_id: int, job_key: str, job_info: Dict, work_data: Dict):
        self.user_id = user_id
        self.job_key = job_key
        self.job_info = job_info
        self.work_data = work_data
        self.minigame_type = job_info["minigame"]
        self.performance_score = 0
        self.completed = False
        
        # Generate minigame
        self.minigame = self.generate_minigame()
    
    def generate_minigame(self) -> Dict:
        """Generate a minigame based on job type"""
        
        if self.minigame_type == "scan_items":
            items = ["🍎", "🥛", "🍞", "🥩", "🧻", "🧼", "👕", "📱", "💊", "🔋"]
            return {
                "type": "scan_items",
                "items": random.sample(items, 5),
                "target_order": random.sample(range(5), 5),
                "user_order": []
            }
        
        elif self.minigame_type == "deliver_packages":
            addresses = ["🏠", "🏢", "🏬", "🏨", "🏪"]
            return {
                "type": "deliver_packages",
                "addresses": random.sample(addresses, 4),
                "current_delivery": 0,
                "successful_deliveries": 0
            }
        
        elif self.minigame_type == "cook_meals":
            ingredients = ["🍅", "🧄", "🧅", "🥩", "🧀", "🌶️", "🥖", "🥚"]
            recipe = random.sample(ingredients, 4)
            return {
                "type": "cook_meals",
                "recipe": recipe,
                "added_ingredients": [],
                "burnt": False
            }
        
        elif self.minigame_type == "debug_code":
            bugs = ["🐛", "🐜", "🕷️", "🦗", "🪲"]
            return {
                "type": "debug_code",
                "bugs": random.sample(bugs, 3),
                "fixed_bugs": [],
                "code_lines": 50
            }
        
        elif self.minigame_type == "treat_patients":
            symptoms = ["🤒", "🤕", "😷", "🤧", "😵"]
            treatments = ["💊", "🩹", "🏥", "💉", "🩺"]
            return {
                "type": "treat_patients",
                "patients": random.sample(symptoms, 3),
                "treatments": treatments,
                "treated_patients": 0
            }
        
        elif self.minigame_type == "court_case":
            evidence = ["📄", "🔍", "👁️", "📱", "💻"]
            return {
                "type": "court_case",
                "evidence": random.sample(evidence, 3),
                "arguments_made": 0,
                "case_strength": 0
            }
        
        return {"type": "default"}
    
    def process_action(self, action: str) -> Dict:
        """Process a minigame action"""
        
        if self.minigame["type"] == "scan_items":
            try:
                item_index = int(action)
                if 0 <= item_index < len(self.minigame["items"]):
                    self.minigame["user_order"].append(item_index)
                    
                    if len(self.minigame["user_order"]) == len(self.minigame["target_order"]):
                        # Calculate performance
                        correct = sum(1 for i, target in enumerate(self.minigame["target_order"]) 
                                    if i < len(self.minigame["user_order"]) and self.minigame["user_order"][i] == target)
                        self.performance_score = (correct / len(self.minigame["target_order"])) * 100
                        self.completed = True
                        
                        return {"success": True, "message": f"Scanned all items! Accuracy: {self.performance_score:.1f}%"}
                    
                    return {"success": True, "message": f"Scanned {self.minigame['items'][item_index]}"}
                else:
                    return {"success": False, "message": "Invalid item number"}
            except ValueError:
                return {"success": False, "message": "Please enter a valid number"}
        
        # Add other minigame logic here...
        
        return {"success": False, "message": "Unknown action"}
    
    def calculate_earnings(self) -> int:
        """Calculate earnings based on performance"""
        base_wage = self.job_info["base_wage"]
        max_wage = self.job_info["max_wage"]
        
        # Performance multiplier (0.5 to 1.5)
        performance_multiplier = 0.5 + (self.performance_score / 100)
        
        # Boss relationship multiplier
        boss_relationship = self.work_data.get("boss_relationship", "neutral")
        relationship_multiplier = WORK_CONFIG["boss_relationship_effects"].get(boss_relationship, 1.0)
        
        # Calculate final wage
        wage_range = max_wage - base_wage
        performance_bonus = wage_range * (performance_multiplier - 1)
        final_wage = int((base_wage + performance_bonus) * relationship_multiplier)
        
        return max(base_wage // 2, final_wage)  # Minimum wage protection
    
    def create_embed(self) -> nextcord.Embed:
        """Create embed for work session"""
        
        if self.completed:
            earnings = self.calculate_earnings()
            
            embed = create_success_embed(
                f"{self.job_info['icon']} Work Completed!",
                f"**Job:** {self.job_info['name']}\n"
                f"**Performance:** {self.performance_score:.1f}%\n"
                f"**Earnings:** {format_currency(earnings)}"
            )
        else:
            embed = create_info_embed(
                f"{self.job_info['icon']} Working as {self.job_info['name']}",
                f"**Job:** {self.job_info['name']}\n"
                f"**Task:** {self.get_task_description()}"
            )
            
            # Add minigame specific fields
            if self.minigame["type"] == "scan_items":
                items_str = " ".join([f"{i}: {item}" for i, item in enumerate(self.minigame["items"])])
                target_str = " → ".join([str(i) for i in self.minigame["target_order"]])
                
                embed.add_field(name="Items to Scan", value=items_str, inline=False)
                embed.add_field(name="Correct Order", value=target_str, inline=False)
                
                if self.minigame["user_order"]:
                    user_str = " → ".join([str(i) for i in self.minigame["user_order"]])
                    embed.add_field(name="Your Progress", value=user_str, inline=False)
        
        return embed
    
    def get_task_description(self) -> str:
        """Get description of the current task"""
        
        task_descriptions = {
            "scan_items": "Scan the items in the correct order shown below",
            "deliver_packages": "Deliver packages to the correct addresses",
            "cook_meals": "Follow the recipe and cook the meal",
            "debug_code": "Find and fix the bugs in the code",
            "treat_patients": "Diagnose and treat the patients",
            "court_case": "Present evidence and build your case"
        }
        
        return task_descriptions.get(self.minigame_type, "Complete your work task")


class WorkView(nextcord.ui.View):
    """View for work session interactions"""
    
    def __init__(self, work_session: WorkSession, work_cog):
        super().__init__(timeout=300)
        self.work_session = work_session
        self.work_cog = work_cog
        
        # Add dynamic buttons based on minigame type
        if work_session.minigame["type"] == "scan_items":
            for i in range(len(work_session.minigame["items"])):
                button = nextcord.ui.Button(
                    label=f"Scan {i}",
                    style=nextcord.ButtonStyle.secondary,
                    custom_id=f"scan_{i}"
                )
                button.callback = self.create_scan_callback(i)
                self.add_item(button)
    
    def create_scan_callback(self, item_index: int):
        """Create callback for scan button"""
        async def scan_callback(interaction: nextcord.Interaction):
            if interaction.user.id != self.work_session.user_id:
                await interaction.response.send_message("This is not your work session!", ephemeral=True)
                return
            
            result = self.work_session.process_action(str(item_index))
            embed = self.work_session.create_embed()
            
            if self.work_session.completed:
                # Work completed, process earnings
                earnings = self.work_session.calculate_earnings()
                
                # Update database
                await self.work_cog.db.update_balance(self.work_session.user_id, wallet_change=earnings)
                await self.work_cog.db.update_work_stats(
                    self.work_session.user_id,
                    self.work_session.job_key,
                    earnings,
                    self.work_session.work_data.get("boss_relationship", "neutral")
                )
                
                # Remove from active sessions
                if self.work_session.user_id in self.work_cog.active_work_sessions:
                    del self.work_cog.active_work_sessions[self.work_session.user_id]
                
                # Disable buttons
                for item in self.children:
                    item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
        
        return scan_callback
    
    async def on_timeout(self):
        """Handle timeout"""
        if self.work_session.user_id in self.work_cog.active_work_sessions:
            del self.work_cog.active_work_sessions[self.work_session.user_id]
        
        for item in self.children:
            item.disabled = True


class BossSession:
    """Represents an interaction with the boss"""
    
    def __init__(self, user_id: int, work_data: Dict):
        self.user_id = user_id
        self.work_data = work_data
        self.relationship = work_data.get("boss_relationship", "neutral")
    
    def create_embed(self) -> nextcord.Embed:
        """Create embed for boss interaction"""
        
        relationship_info = {
            "hostile": {"emoji": "😡", "desc": "Your boss is angry with you"},
            "neutral": {"emoji": "😐", "desc": "Your boss is neutral towards you"},
            "friendly": {"emoji": "😊", "desc": "Your boss likes you"},
            "loyal": {"emoji": "🤝", "desc": "Your boss trusts you completely"}
        }
        
        info = relationship_info.get(self.relationship, relationship_info["neutral"])
        
        embed = create_info_embed(
            f"🤵 Boss Interaction",
            f"**Relationship:** {info['emoji']} {self.relationship.title()}\n"
            f"{info['desc']}\n\n"
            f"What would you like to do?"
        )
        
        return embed


class BossView(nextcord.ui.View):
    """View for boss interactions"""
    
    def __init__(self, boss_session: BossSession, work_cog):
        super().__init__(timeout=300)
        self.boss_session = boss_session
        self.work_cog = work_cog
    
    @nextcord.ui.button(label="Ask for Raise", style=nextcord.ButtonStyle.primary)
    async def ask_raise(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Ask boss for a raise"""
        if interaction.user.id != self.boss_session.user_id:
            await interaction.response.send_message("This is not your boss!", ephemeral=True)
            return
        
        # Calculate success chance based on relationship
        success_chances = {
            "hostile": 0.1,
            "neutral": 0.3,
            "friendly": 0.6,
            "loyal": 0.8
        }
        
        success_chance = success_chances.get(self.boss_session.relationship, 0.3)
        success = random.random() < success_chance
        
        if success:
            # TODO: Implement raise logic (increase base wage)
            embed = create_success_embed(
                "Raise Approved!",
                "Your boss has approved your raise request!"
            )
            
            # Improve relationship slightly
            if self.boss_session.relationship == "neutral":
                new_relationship = "friendly"
            elif self.boss_session.relationship == "friendly":
                new_relationship = "loyal"
            else:
                new_relationship = self.boss_session.relationship
            
            await self.work_cog.db.update_user(self.boss_session.user_id, {
                "work.boss_relationship": new_relationship
            })
            
        else:
            embed = create_error_embed(
                "Raise Denied",
                "Your boss has denied your raise request."
            )
            
            # Worsen relationship slightly
            if self.boss_session.relationship == "loyal":
                new_relationship = "friendly"
            elif self.boss_session.relationship == "friendly":
                new_relationship = "neutral"
            elif self.boss_session.relationship == "neutral":
                new_relationship = "hostile"
            else:
                new_relationship = self.boss_session.relationship
            
            await self.work_cog.db.update_user(self.boss_session.user_id, {
                "work.boss_relationship": new_relationship
            })
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @nextcord.ui.button(label="Give Gift", style=nextcord.ButtonStyle.secondary)
    async def give_gift(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        """Give boss a gift to improve relationship"""
        if interaction.user.id != self.boss_session.user_id:
            await interaction.response.send_message("This is not your boss!", ephemeral=True)
            return
        
        # Check if user can afford gift
        gift_cost = 500
        balance = await self.work_cog.db.get_economy_data(self.boss_session.user_id)
        
        if not balance or balance.get("wallet", 0) < gift_cost:
            embed = create_error_embed(
                "Insufficient Funds",
                f"You need {format_currency(gift_cost)} to give your boss a gift."
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Deduct cost and improve relationship
        await self.work_cog.db.update_balance(self.boss_session.user_id, wallet_change=-gift_cost)
        
        # Improve relationship
        relationship_progression = {
            "hostile": "neutral",
            "neutral": "friendly",
            "friendly": "loyal",
            "loyal": "loyal"  # Already at max
        }
        
        new_relationship = relationship_progression.get(self.boss_session.relationship, "neutral")
        
        await self.work_cog.db.update_user(self.boss_session.user_id, {
            "work.boss_relationship": new_relationship
        })
        
        embed = create_success_embed(
            "Gift Given!",
            f"Your boss appreciated the gift!\n"
            f"Relationship improved to: {new_relationship.title()}\n"
            f"Cost: {format_currency(gift_cost)}"
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


def setup(bot):
    bot.add_cog(WorkCog(bot))
