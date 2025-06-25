from discord.ext import commands
import discord
import random
import asyncio
from utils.db import async_db as db

class AutoFishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.BASE_PRICE = 1000
        self.PRICE_MULTIPLIER = 2.5
        self.MAX_AUTOFISHERS = 10
        self.BAIT_COST = 50
        self.CATCH_CHANCE = 0.5
        self.autofishing_task = self.bot.loop.create_task(self.autofishing_loop())

<<<<<<< HEAD
    async def cog_unload(self):
        """Cancel the autofishing task when cog is unloaded"""
=======
    def cog_unload(self):
>>>>>>> 8347f2e296550847d482727eb8e2f0210b51ae8b
        if hasattr(self, 'autofishing_task'):
            self.autofishing_task.cancel()

    async def autofishing_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                users = await db.get_all_autofisher_users()
                for user_id in users:
                    await self.process_autofishing(user_id)
                await asyncio.sleep(30)
            except Exception:
                await asyncio.sleep(60)

    async def process_autofishing(self, user_id):
        data = await db.get_autofisher_data(user_id)
        if not data or not data.get("count", 0):
            return
            
        items = await db.get_fishing_items(user_id)
        if not items.get("rods"):
            return
            
        balance = data.get("balance", 0)
        for _ in range(data["count"]):
            if random.random() > self.CATCH_CHANCE:
                continue
                
            if not items.get("bait"):
                if balance >= self.BAIT_COST and await self.buy_bait(user_id):
                    balance -= self.BAIT_COST
                    items["bait"] = [{"_id": "pro_bait", "amount": 10}]
                else:
                    continue
                    
            if not await db.remove_bait(user_id, "pro_bait"):
                continue
                
            fish = {
                "type": "normal",
                "value": random.randint(10, 100),
                "auto_caught": True
            }
            await db.add_fish(user_id, fish)
            
        await db.update_autofisher_data(user_id, {"balance": balance})

    async def buy_bait(self, user_id):
        bait = {
            "_id": "pro_bait",
            "amount": 10,
            "description": "Standard bait for autofishers"
        }
        return await db.add_bait(user_id, bait)

    @commands.group(invoke_without_command=True)
    async def auto(self, ctx):
        """Autofisher management system"""
        data = await db.get_autofisher_data(ctx.author.id)
        embed = discord.Embed(title="🤖 Autofisher System", color=0x2b2d31)
        
        if not data:
            embed.description = "You don't have any autofishers yet!"
            embed.add_field(name="First Autofisher Cost", 
                           value=f"{self.BASE_PRICE} {self.currency}")
            return await ctx.send(embed=embed)
            
        next_cost = int(self.BASE_PRICE * (self.PRICE_MULTIPLIER ** data["count"]))
        embed.add_field(name="Autofishers", value=f"{data['count']}/{self.MAX_AUTOFISHERS}", inline=False)
        embed.add_field(name="Balance", value=f"{data.get('balance', 0)} {self.currency}", inline=False)
        embed.add_field(name="Next Autofisher Cost", value=f"{next_cost} {self.currency}", inline=False)
        await ctx.send(embed=embed)

    @auto.command()
    async def buy(self, ctx):
        """Buy an autofisher"""
        data = await db.get_autofisher_data(ctx.author.id) or {"count": 0, "balance": 0}
        
        if data["count"] >= self.MAX_AUTOFISHERS:
            return await ctx.send(f"You've reached the max of {self.MAX_AUTOFISHERS} autofishers!")
            
        cost = int(self.BASE_PRICE * (self.PRICE_MULTIPLIER ** data["count"]))
        balance = await db.get_balance(ctx.author.id)
        
        if balance < cost:
            return await ctx.send(f"Need {cost} {self.currency} (You have {balance})")
            
        if await db.update_balance(ctx.author.id, -cost):
            data["count"] += 1
            await db.set_autofisher_data(ctx.author.id, data)
            await ctx.send(f"✅ Purchased autofisher #{data['count']}!")

    @auto.command()
    async def deposit(self, ctx, amount: int):
        """Deposit money into autofisher balance"""
        if amount <= 0:
            return await ctx.send("Amount must be positive!")
            
        data = await db.get_autofisher_data(ctx.author.id)
        if not data:
            return await ctx.send("Buy an autofisher first!")
            
        balance = await db.get_balance(ctx.author.id)
        if balance < amount:
            return await ctx.send(f"You only have {balance} {self.currency}")
            
        if await db.update_balance(ctx.author.id, -amount):
            data["balance"] = data.get("balance", 0) + amount
            await db.set_autofisher_data(ctx.author.id, data)
            await ctx.send(f"✅ Deposited {amount} {self.currency}!")

    @auto.command()
    async def collect(self, ctx):
        """Collect and sell auto-caught fish"""
        fish = await db.get_fish(ctx.author.id)
        auto_fish = [f for f in fish if f.get("auto_caught")]
        
        if not auto_fish:
            return await ctx.send("No auto-caught fish!")
            
        total = sum(f["value"] for f in auto_fish)
        for fish_item in auto_fish:
            await db.remove_fish(ctx.author.id, fish_item["id"])
            
        if await db.update_balance(ctx.author.id, total):
            await ctx.send(f"✅ Sold {len(auto_fish)} fish for {total} {self.currency}!")

async def setup(bot):
    await bot.add_cog(AutoFishing(bot))