import motor.motor_asyncio
import pymongo
import json
import datetime
from datetime import timedelta
import os
import asyncio
import logging
from typing import Dict, Any, Optional
import threading
from bson import ObjectId
import re
import time

def load_config() -> dict:
    """Load config from environment variables, then config.json as fallback."""
    config = {
        "MONGO_URI": os.getenv("MONGO_URI"),
        "TOKEN": os.getenv("DISCORD_TOKEN"),
        "CLIENT_ID": os.getenv("DISCORD_CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("DISCORD_CLIENT_SECRET"),
        "OWNER_ID": os.getenv("DISCORD_BOT_OWNER_ID")
    }
    if not all([config["MONGO_URI"], config["TOKEN"], config["CLIENT_ID"]]):
        try:
            with open('data/config.json') as f:
                file_config = json.load(f)
                for key in config:
                    if not config[key] and key in file_config:
                        config[key] = file_config[key]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"Could not load config.json: {e}. Using environment variables only.")
    return config

config = load_config()

class AsyncDatabase:
    """Async database class for use with Discord bot (MongoDB)"""
    _instance = None
    _client = None
    _db = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.logger = logging.getLogger('AsyncDatabase')
        self._connected = False

    @property
    def client(self):
        if self._client is None:
            MONGO_URI = os.getenv('MONGO_URI', config['MONGO_URI'])
            # Configure connection pool settings for better performance
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                MONGO_URI,
                maxPoolSize=50,  # Maximum connections in pool
                minPoolSize=5,   # Minimum connections to maintain
                maxIdleTimeMS=30000,  # Close connections after 30s idle
                waitQueueTimeoutMS=5000,  # Timeout for getting connection
                serverSelectionTimeoutMS=5000,  # Timeout for server selection
                connectTimeoutMS=10000,  # Connection timeout
                socketTimeoutMS=20000,   # Socket timeout
            )
        return self._client

    @property
    def db(self):
        if self._db is None:
            self._db = self.client.bronxbot
        return self._db

    async def ensure_connected(self) -> bool:
        """Ensure database connection is active."""
        if not self._connected:
            try:
                await self.client.admin.command('ping')
                self._connected = True
                self.logger.info("Async database connection established")
            except Exception as e:
                self.logger.error(f"Async database connection failed: {e}")
                return False
        return True

    async def get_wallet_balance(self, user_id: int, guild_id: int = None, session=None) -> int:
        """Get user's wallet balance"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)}, session=session)
        return user.get("wallet", 0) if user else 0

    async def get_badge(self, user_id: int, guild_id: int = None) -> Optional[str]:
        """Get user's badge"""
        if await self.db.users.find_one({"_id": str(user_id), "dev": True}):
            badge = "<:dev:1252043061878325378>"
        elif await self.db.users.find_one({"_id": str(user_id), "h": True}):
            badge = ":purple_heart:"
        elif await self.db.users.find_one({"_id": str(user_id), "admin": True}):
            badge = "<:admin:1252043084091625563>"
        elif await self.db.users.find_one({"_id": str(user_id), "mod": True}):
            badge = "<:mod:1252043167872585831>"
        elif await self.db.users.find_one({"_id": str(user_id), "maintainer": True}):
            badge = "<:maintainer:1252043069231206420>"
        elif await self.db.users.find_one({"_id": str(user_id), "contributor": True}):
            badge = "<:contributor:1252043070426452018>"
        elif await self.db.users.find_one({"_id": str(user_id), "vip": True}):
            badge = "<:vip:1252047732231766198>"
        else:
            badge = ""
        return badge


    async def migrate_to_standard_ids(self):
        """Migrate all fishing items to use standardized _id format"""
        if not await self.ensure_connected():
            return False
        
        try:
            # 1. Migrate user bait (special handling needed)
            users_with_bait = await self.db.users.find({"bait": {"$exists": True}}).to_list(None)
            for user in users_with_bait:
                updated_bait = []
                needs_update = False
                
                for bait in user.get("bait", []):
                    if "id" in bait:
                        # Only add _id if not present
                        if "_id" not in bait:
                            bait["_id"] = bait["id"]
                        # Always remove the old id field
                        del bait["id"]
                        needs_update = True
                    updated_bait.append(bait)
                
                if needs_update:
                    await self.db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"bait": updated_bait}}
                    )

            # 2. Migrate user rods (same approach as bait)
            users_with_rods = await self.db.users.find({"fishing_rods": {"$exists": True}}).to_list(None)
            for user in users_with_rods:
                updated_rods = []
                needs_update = False
                
                for rod in user.get("fishing_rods", []):
                    if "id" in rod:
                        if "_id" not in rod:
                            rod["_id"] = rod["id"]
                        del rod["id"]
                        needs_update = True
                    updated_rods.append(rod)
                
                if needs_update:
                    await self.db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"fishing_rods": updated_rods}}
                    )

            # 3. For shop collections, we need to handle differently since we can't modify _id
            # Create new collections and migrate data
            if await self.db.shop_bait.count_documents({}) > 0:
                all_bait = await self.db.shop_bait.find().to_list(None)
                new_bait = []
                
                for bait in all_bait:
                    new_doc = bait.copy()
                    if "id" in new_doc:
                        if "_id" not in new_doc:
                            new_doc["_id"] = new_doc["id"]
                        del new_doc["id"]
                    new_bait.append(new_doc)
                
                if new_bait:
                    await self.db.bait.insert_many(new_bait)
                    await self.db.shop_bait.drop()

            if await self.db.shop_rods.count_documents({}) > 0:
                all_rods = await self.db.shop_rods.find().to_list(None)
                new_rods = []
                
                for rod in all_rods:
                    new_doc = rod.copy()
                    if "id" in new_doc:
                        if "_id" not in new_doc:
                            new_doc["_id"] = new_doc["id"]
                        del new_doc["id"]
                    new_rods.append(new_doc)
                
                if new_rods:
                    await self.db.rods.insert_many(new_rods)
                    await self.db.shop_rods.drop()

            return True
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False

    def _generate_standard_id(self, item):
        """Generate standardized ID from item name"""
        if not item.get("name"):
            return str(ObjectId())
        
        # Create standardized ID
        standardized = item["name"].lower().strip()
        standardized = re.sub(r'[^a-z0-9]+', '_', standardized)  # Replace special chars with _
        standardized = re.sub(r'_+', '_', standardized)  # Collapse multiple _s
        standardized = standardized.strip('_')  # Remove leading/trailing _
        
        # Ensure ID is valid and unique enough
        if not standardized:
            return str(ObjectId())
        
        # Append hash if needed to ensure uniqueness
        if len(standardized) < 3:
            standardized += f"_{str(ObjectId())[:4]}"
        
        return standardized

    async def get_active_fishing_gear(self, user_id: int) -> dict:
        """Get user's active fishing rod and bait"""
        if not await self.ensure_connected():
            return {"rod": None, "bait": None}
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user:
            return {"rod": None, "bait": None}
        
        # Get active gear or default to best available
        active_gear = user.get("active_fishing", {})
        rods = user.get("fishing_rods", [])
        bait = user.get("bait", [])
        
        # If no active rod, select the one with highest multiplier
        if not active_gear.get("rod") and rods:
            best_rod = max(rods, key=lambda x: x.get("multiplier", 1.0))
            active_gear["rod"] = best_rod["_id"]
        
        # If no active bait, select the first available
        if not active_gear.get("bait") and bait:
            active_gear["bait"] = bait[0]["_id"]
        
        return active_gear

    async def set_active_rod(self, user_id: int, rod_id: str) -> bool:
        """Set user's active fishing rod"""
        if not await self.ensure_connected():
            return False
        
        # Verify user has this rod in inventory
        inventory = await self.get_user_inventory_by_type(user_id, "rod")
        if rod_id not in inventory or inventory[rod_id] <= 0:
            return False
        
        # Update active fishing gear
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"active_fishing.rod": rod_id}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def set_active_bait(self, user_id: int, bait_id: str) -> bool:
        """Set user's active bait"""
        if not await self.ensure_connected():
            print(f"DB not connected when setting active bait for user {user_id}")
            return False
        
        try:
            # Debug logging
            print(f"set_active_bait called: user={user_id}, bait_id='{bait_id}'")
            
            # Handle clearing active bait (bait_id is None)
            if bait_id is None:
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$unset": {"active_fishing.bait": ""}},
                    upsert=True
                )
                success = result.modified_count > 0 or result.upserted_id is not None
                print(f"Cleared active bait for user {user_id}: {'SUCCESS' if success else 'FAILED'}")
                return success
            
            # Verify user has this bait in inventory
            inventory = await self.get_user_inventory_by_type(user_id, "bait")
            print(f"User {user_id} bait inventory: {inventory}")
            
            if bait_id not in inventory:
                print(f"Bait {bait_id} not found in user {user_id} inventory")
                return False
                
            if inventory[bait_id] <= 0:
                print(f"User {user_id} has 0 of bait {bait_id}")
                return False
            
            # Check current active bait before update
            current_user = await self.db.users.find_one({"_id": str(user_id)})
            current_active = current_user.get("active_fishing", {}).get("bait") if current_user else None
            print(f"Current active bait for user {user_id}: {current_active}")
            
            # Update active fishing gear
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$set": {"active_fishing.bait": bait_id}},
                upsert=True
            )
            
            print(f"Database update result: modified_count={result.modified_count}, upserted_id={result.upserted_id}")
            
            # Consider it successful if the document was modified, upserted, OR if the bait is already active
            success = (result.modified_count > 0 or 
                      result.upserted_id is not None or 
                      current_active == bait_id)
            print(f"Set active bait {bait_id} for user {user_id}: {'SUCCESS' if success else 'FAILED'}")
            
            # Verify the update worked - always check final state
            updated_user = await self.db.users.find_one({"_id": str(user_id)})
            final_active = updated_user.get("active_fishing", {}).get("bait") if updated_user else None
            print(f"Verification - User {user_id} active bait is now: {final_active}")
            
            # Consider successful if the final state matches what we wanted
            if final_active == bait_id:
                success = True
                print(f"Final verification: SUCCESS - bait is correctly set to {bait_id}")
            else:
                print(f"Final verification: FAILED - expected {bait_id}, got {final_active}")
            
            return success
            
        except Exception as e:
            print(f"Error setting active bait for user {user_id}: {e}")
            return False

    async def get_bank_balance(self, user_id: int, guild_id: int = None) -> int:
        """Get user's bank balance"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("bank", 0) if user else 0

    async def get_bank_limit(self, user_id: int, guild_id: int = None) -> int:
        """Get user's bank limit"""
        if not await self.ensure_connected():
            return 10000
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("bank_limit", 10000) if user else 10000

    async def update_wallet(self, user_id: int, amount: int, guild_id: int = None, session=None) -> bool:
        """Update user's wallet balance with overflow protection"""
        if not await self.ensure_connected():
            return False
            
        # Get current balance (within the same transaction if provided)
        current = await self.get_wallet_balance(user_id, guild_id, session=session)
        
        # Check for overflow/underflow
        MAX_BALANCE = 9223372036854775807  # PostgreSQL bigint max
        new_balance = current + amount
        
        self.logger.debug(f"update_wallet: user {user_id}, current: {current}, amount: {amount}, new_balance: {new_balance}")
        
        if new_balance > MAX_BALANCE:
            self.logger.warning(f"update_wallet: Balance would exceed maximum for user {user_id}. Capping at {MAX_BALANCE}")
            new_balance = MAX_BALANCE
        elif new_balance < 0:
            self.logger.error(f"update_wallet: Balance would go negative for user {user_id}. Current: {current}, amount: {amount}")
            return False
            
        # Update with the safe balance
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"wallet": new_balance}},
            upsert=True,
            session=session
        )
        success = result.modified_count > 0 or result.upserted_id is not None
        self.logger.debug(f"update_wallet result for user {user_id}: success={success}, modified_count={result.modified_count}, upserted_id={result.upserted_id}")
        return success

    async def update_bank(self, user_id: int, amount: int, guild_id: int = None, session=None) -> bool:
        """Update user's bank balance with overflow protection"""
        if not await self.ensure_connected():
            return False
            
        current = await self.get_bank_balance(user_id)
        MAX_BALANCE = 9223372036854775807
        new_balance = current + amount
        
        if new_balance > MAX_BALANCE:
            new_balance = MAX_BALANCE
        elif new_balance < 0:
            return False
            
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"bank": new_balance}},
            upsert=True,
            session=session
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def update_bank_limit(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Update user's bank storage limit"""
        if not await self.ensure_connected():
            return False
            
        # Prevent negative limits
        current_limit = await self.get_bank_limit(user_id, guild_id)
        new_limit = current_limit + amount
        if new_limit < 0:
            return False
            
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$inc": {"bank_limit": amount}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings"""
        if not await self.ensure_connected():
            return {}
        settings = await self.db.guild_settings.find_one({"_id": str(guild_id)})
        return settings if settings else {}

    async def update_guild_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """Update guild settings"""
        if not await self.ensure_connected():
            return False
        result = await self.db.guild_settings.update_one(
            {"_id": str(guild_id)},
            {"$set": settings},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def store_stats(self, guild_id: int, stat_type: str) -> None:
        """Store guild stats"""
        if not await self.ensure_connected():
            return
        await self.db.stats.update_one(
            {"_id": str(guild_id)},
            {"$inc": {stat_type: 1}},
            upsert=True
        )

    async def get_stats(self, guild_id: int) -> Dict[str, int]:
        """Get guild stats"""
        if not await self.ensure_connected():
            return {}
        stats = await self.db.stats.find_one({"_id": str(guild_id)})
        return stats if stats else {}

    async def reset_stats(self, guild_id: int) -> bool:
        """Reset guild stats"""
        if not await self.ensure_connected():
            return False
        result = await self.db.stats.delete_one({"_id": str(guild_id)})
        return result.deleted_count > 0

    async def add_global_buff(self, buff_data: Dict[str, Any]) -> bool:
        """Add global buff"""
        if not await self.ensure_connected():
            return False
        result = await self.db.global_buffs.insert_one(buff_data)
        return result.inserted_id is not None

    async def get_user_balance(self, user_id: int, guild_id: int = None) -> int:
        """Get user's total balance"""
        wallet = await self.get_wallet_balance(user_id, guild_id)
        bank = await self.get_bank_balance(user_id, guild_id)
        return wallet + bank

    async def transfer_money(self, from_id: int, to_id: int, amount: int, guild_id: int = None) -> bool:
        """Transfer money between users"""
        if not await self.ensure_connected():
            self.logger.error("Database not connected for transfer_money")
            return False
            
        # Check balance outside transaction first for quick validation
        from_balance = await self.get_wallet_balance(from_id, guild_id)
        if from_balance < amount:
            self.logger.info(f"Transfer failed: insufficient funds. User {from_id} has {from_balance}, needs {amount}")
            return False
            
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                try:
                    # Both operations must succeed within the transaction
                    self.logger.info(f"Transfer: Deducting {amount} from user {from_id}")
                    if not await self.update_wallet(from_id, -amount, guild_id, session=session):
                        self.logger.error(f"Transfer failed: could not deduct {amount} from user {from_id}")
                        await session.abort_transaction()
                        return False
                    
                    self.logger.info(f"Transfer: Adding {amount} to user {to_id}")
                    if not await self.update_wallet(to_id, amount, guild_id, session=session):
                        self.logger.error(f"Transfer failed: could not add {amount} to user {to_id}")
                        await session.abort_transaction()
                        return False
                    
                    # If we get here, both operations succeeded
                    self.logger.info(f"Transfer successful: {amount} from {from_id} to {to_id}")
                    await session.commit_transaction()
                    return True
                except Exception as e:
                    self.logger.error(f"Transfer error: {e}")
                    await session.abort_transaction()
                    return False

    async def increase_bank_limit(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Increase user's bank storage limit"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$inc": {"bank_limit": amount}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_bank_level(self, user_id: int, guild_id: int = None) -> int:
        """Get user's bank level based on their current bank limit"""
        if not await self.ensure_connected():
            return 0
        
        current_limit = await self.get_bank_limit(user_id, guild_id)
        
        # Map bank limit to level based on BANK_UPGRADE_LEVELS
        # Import here to avoid circular imports
        from cogs.economy.economy.constants import BANK_UPGRADE_LEVELS
        
        # Default level 0 has limit 5000 (implied)
        if current_limit <= 5000:
            return 0
            
        # Find the highest level that matches the current limit
        for level, info in sorted(BANK_UPGRADE_LEVELS.items(), reverse=True):
            if current_limit >= info["limit"]:
                return level
                
        return 0

    async def set_bank_level(self, user_id: int, guild_id: int, level: int) -> bool:
        """Set user's bank level by updating their bank limit"""
        if not await self.ensure_connected():
            return False
            
        # Import here to avoid circular imports
        from cogs.economy.economy.constants import BANK_UPGRADE_LEVELS
        
        if level not in BANK_UPGRADE_LEVELS:
            return False
            
        new_limit = BANK_UPGRADE_LEVELS[level]["limit"]
        
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"bank_limit": new_limit}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_global_net_worth(self, user_id: int, excluded_guilds: list = None) -> int:
        """Get user's total net worth across all guilds"""
        if not await self.ensure_connected():
            return 0
        excluded_guilds = excluded_guilds or []
        pipeline = [
            {"$match": {"_id": str(user_id)}},
            {"$project": {
                "total": {"$add": ["$wallet", "$bank"]}
            }}
        ]
        result = await self.db.users.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0

    async def get_inventory(self, user_id: int, guild_id: int = None) -> list:
        """Get user's inventory with proper quantity grouping"""
        if not await self.ensure_connected():
            return []
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user:
            return []
        
        # Group items by id and sum quantities
        from collections import defaultdict
        item_counts = defaultdict(int)
        item_data = {}
        
        # Process main inventory array
        inventory = user.get("inventory", [])
        
        # Check if inventory is the new object structure
        if isinstance(inventory, dict):
            # Process nested potions from inventory.potions
            potions = inventory.get("potions", {})
            for potion_id, quantity in potions.items():
                if quantity > 0:
                    # Load potion data from shop files
                    try:
                        import os
                        import json
                        potion_file = os.path.join(os.getcwd(), "data", "shop", "potions.json")
                        with open(potion_file, 'r') as f:
                            potion_data = json.load(f)
                            
                        if potion_id in potion_data:
                            shop_potion = potion_data[potion_id]
                            potion_item = {
                                "id": potion_id,
                                "name": shop_potion.get("name", potion_id),
                                "description": shop_potion.get("description", ""),
                                "type": "potion",
                                "price": shop_potion.get("price", 0),
                                "value": shop_potion.get("price", 0),
                                "quantity": quantity
                            }
                            item_counts[potion_id] += quantity
                            if potion_id not in item_data:
                                item_data[potion_id] = potion_item
                    except Exception as e:
                        self.logger.error(f"Error loading potion data for inventory: {e}")
            
            # Process nested upgrades from inventory.upgrades
            upgrades = inventory.get("upgrades", {})
            for upgrade_id, quantity in upgrades.items():
                if quantity > 0:
                    # Load upgrade data from shop files
                    try:
                        import os
                        import json
                        upgrade_file = os.path.join(os.getcwd(), "data", "shop", "upgrades.json")
                        with open(upgrade_file, 'r') as f:
                            upgrade_data = json.load(f)
                            
                        if upgrade_id in upgrade_data:
                            shop_upgrade = upgrade_data[upgrade_id]
                            upgrade_item = {
                                "id": upgrade_id,
                                "name": shop_upgrade.get("name", upgrade_id),
                                "description": shop_upgrade.get("description", ""),
                                "type": "upgrade",
                                "price": shop_upgrade.get("price", 0),
                                "value": shop_upgrade.get("price", 0),
                                "quantity": quantity
                            }
                            item_counts[upgrade_id] += quantity
                            if upgrade_id not in item_data:
                                item_data[upgrade_id] = upgrade_item
                    except Exception as e:
                        self.logger.error(f"Error loading upgrade data for inventory: {e}")
                        
        elif isinstance(inventory, list):
            # Process legacy array inventory
            for item in inventory:
                # Skip invalid items (strings or non-dict objects)
                if not isinstance(item, dict):
                    self.logger.warning(f"Found invalid inventory item for user {user_id}: {type(item)} - {item}")
                    continue
                    
                item_key = item.get("id", item.get("name", "unknown"))
                item_counts[item_key] += item.get("quantity", 1)  # Add quantity if exists, default to 1
                if item_key not in item_data:
                    item_data[item_key] = item.copy()
        
        # Process legacy potions array for backward compatibility
        potions = user.get("potions", [])
        for potion in potions:
            if not isinstance(potion, dict):
                continue
            
            potion_id = potion.get("_id", potion.get("id", "unknown"))
            amount = potion.get("amount", 1)
            
            # Try to get potion data from shop files
            try:
                import os
                import json
                potion_file = os.path.join(os.getcwd(), "data", "shop", "potions.json")
                with open(potion_file, 'r') as f:
                    potion_data = json.load(f)
                    
                if potion_id in potion_data:
                    shop_potion = potion_data[potion_id]
                    potion_item = {
                        "id": potion_id,
                        "name": shop_potion.get("name", potion_id),
                        "description": shop_potion.get("description", ""),
                        "type": "potion",
                        "price": shop_potion.get("price", 0),
                        "value": shop_potion.get("price", 0)
                    }
                    item_counts[potion_id] += amount
                    if potion_id not in item_data:
                        item_data[potion_id] = potion_item
            except Exception as e:
                self.logger.error(f"Error loading potion data for inventory: {e}")
        
        # Convert to list with quantities
        result = []
        for item_key, quantity in item_counts.items():
            item = item_data[item_key].copy()
            item["quantity"] = quantity
            result.append(item)
        
        return result
    
    async def buy_item(self, user_id: int, item_id: str, guild_id: int = None) -> tuple[bool, str]:
        """Buy an item from any shop"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
            
        try:
            # Check all shop collections for the item
            item = None
            item_type = None
            
            # Check shop_items
            item = await self.db.shop_items.find_one({"id": item_id})
            if item:
                item_type = "item"
            
            # Check shop_fishing
            if not item:
                item = await self.db.shop_fishing.find_one({"id": item_id})
                if item:
                    item_type = "fishing"
            
            # Check shop_potions
            if not item:
                item = await self.db.shop_potions.find_one({"id": item_id})
                if item:
                    item_type = "potion"
                    
            # Check shop_upgrades
            if not item:
                item = await self.db.shop_upgrades.find_one({"id": item_id})
                if item:
                    item_type = "upgrade"
            
            if not item:
                return False, "Item not found in any shop"
                
            # Check if user has enough money
            wallet_balance = await self.get_wallet_balance(user_id, guild_id)
            if wallet_balance < item["price"]:
                return False, f"Insufficient funds. Need {item['price']}, have {wallet_balance}"
                
            # Process the purchase based on item type
            try:
                async with await self.client.start_session() as session:
                    async with session.start_transaction():
                        # Deduct money
                        if not await self.update_wallet(user_id, -item["price"], guild_id):
                            return False, "Failed to deduct payment"
                        
                        # Handle different item types
                        if item_type == "fishing":
                            if item["type"] == "rod":
                                if not await self.add_fishing_item(user_id, item, "rod"):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to add fishing rod"
                            elif item["type"] == "bait":
                                if not await self.add_fishing_item(user_id, item, "bait"):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to add fishing bait"
                                    
                        elif item_type == "potion":
                            if not await self.add_potion(user_id, item):
                                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                return False, "Failed to activate potion"
                                
                        elif item_type == "upgrade":
                            if item["type"] == "bank":
                                if not await self.increase_bank_limit(user_id, item["amount"], guild_id):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to upgrade bank"
                            elif item["type"] == "fishing":
                                # Handle rod upgrade logic here
                                pass
                                
                        elif item_type == "item":
                            # Add to inventory using dictionary structure
                            item_id = item.get("id", item.get("name", "unknown").lower().replace(" ", "_"))
                            # Determine the correct inventory category
                            category = "items"  # Default category for general items
                            if item.get("type") == "potion":
                                category = "potions"
                            elif item.get("type") == "upgrade":
                                category = "upgrades"
                            
                            result = await self.db.users.update_one(
                                {"_id": str(user_id)},
                                {"$inc": {f"inventory.{category}.{item_id}": 1}},
                                upsert=True
                            )
                            if result.modified_count == 0 and not result.upserted_id:
                                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                return False, "Failed to add item to inventory"
                        
                        await session.commit_transaction()
                        return True, f"Successfully purchased {item['name']}!"
                        
            except Exception as transaction_error:
                # If we're here, the transaction should have been automatically aborted
                self.logger.error(f"Transaction failed for item {item_id}: {transaction_error}")
                return False, f"Purchase failed during transaction: {str(transaction_error)}"
                        
        except Exception as e:
            self.logger.error(f"Failed to buy item {item_id}: {e}")
            return False, f"Purchase failed: {str(e)}"


    async def buy_item_simple(self, user_id: int, item_id: str, guild_id: int = None) -> tuple[bool, str]:
        """Buy an item from any shop (fixed version)"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
            
        try:
            # Find the item in shops
            item = None
            item_type = None
            
            # Check shop_items
            item = await self.db.shop_items.find_one({"id": item_id})
            if item:
                item_type = "item"
            
            # Check other shop types...
            if not item:
                item = await self.db.shop_fishing.find_one({"id": item_id})
                if item:
                    item_type = "fishing"
            
            if not item:
                item = await self.db.shop_potions.find_one({"id": item_id})
                if item:
                    item_type = "potion"
                    
            if not item:
                item = await self.db.shop_upgrades.find_one({"id": item_id})
                if item:
                    item_type = "upgrade"
            
            if not item:
                return False, "Item not found in any shop"
                
            # Check if user has enough money
            wallet_balance = await self.get_wallet_balance(user_id, guild_id)
            if wallet_balance < item["price"]:
                return False, f"Insufficient funds. Need {item['price']:,}, have {wallet_balance:,}"
                
            # Deduct money first
            if not await self.update_wallet(user_id, -item["price"], guild_id):
                return False, "Failed to deduct payment"
            
            # Handle different item types
            success = False
            error_msg = ""
            
            if item_type == "item":
                # Add to inventory - create a clean copy without MongoDB ObjectId
                clean_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "description": item.get("description", ""),
                    "type": item.get("type", "item")
                }
                
                # Add to inventory using dictionary structure
                item_id = clean_item.get("id", clean_item.get("name", "unknown").lower().replace(" ", "_"))
                # Determine the correct inventory category
                category = "items"  # Default category for general items
                if clean_item.get("type") == "potion":
                    category = "potions"
                elif clean_item.get("type") == "upgrade":
                    category = "upgrades"
                
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$inc": {f"inventory.{category}.{item_id}": 1}},
                    upsert=True
                )
                success = result.modified_count > 0 or result.upserted_id is not None
                error_msg = "Failed to add item to inventory"
            
            # Handle other item types as before...
            elif item_type == "potion":
                success = await self.add_potion(user_id, item)
                error_msg = "Failed to activate potion"
            
            # If something went wrong, refund the money
            if not success:
                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                return False, error_msg
            
            return True, f"Successfully purchased {item['name']}!"
                        
        except Exception as e:
            # Try to refund if we got this far
            try:
                await self.update_wallet(user_id, item["price"], guild_id)
            except:
                pass
            return False, f"Purchase failed: {str(e)}"

    async def remove_from_inventory(self, user_id: int, guild_id: int, item_id: str, quantity: int = 1) -> bool:
        """Remove specific quantity of items from user's inventory"""
        if not await self.ensure_connected():
            return False
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user:
            return False
        
        remaining_to_remove = quantity
        inventory = user.get("inventory", [])
        
        # Check if inventory is the new object structure
        if isinstance(inventory, dict):
            # Try to remove from nested potions structure
            potions = inventory.get("potions", {})
            if item_id in potions:
                current_qty = potions[item_id]
                if current_qty >= remaining_to_remove:
                    new_qty = current_qty - remaining_to_remove
                    if new_qty <= 0:
                        # Remove the potion entirely
                        result = await self.db.users.update_one(
                            {"_id": str(user_id)},
                            {"$unset": {f"inventory.potions.{item_id}": ""}}
                        )
                    else:
                        # Decrease the quantity
                        result = await self.db.users.update_one(
                            {"_id": str(user_id)},
                            {"$set": {f"inventory.potions.{item_id}": new_qty}}
                        )
                    return result.modified_count > 0
            
            # Try to remove from nested upgrades structure
            upgrades = inventory.get("upgrades", {})
            if item_id in upgrades:
                current_qty = upgrades[item_id]
                if current_qty >= remaining_to_remove:
                    new_qty = current_qty - remaining_to_remove
                    if new_qty <= 0:
                        # Remove the upgrade entirely
                        result = await self.db.users.update_one(
                            {"_id": str(user_id)},
                            {"$unset": {f"inventory.upgrades.{item_id}": ""}}
                        )
                    else:
                        # Decrease the quantity
                        result = await self.db.users.update_one(
                            {"_id": str(user_id)},
                            {"$set": {f"inventory.upgrades.{item_id}": new_qty}}
                        )
                    return result.modified_count > 0
                    
        elif isinstance(inventory, list):
            # Handle legacy array inventory
            items_to_keep = []
            
            # Filter items to keep/remove from main inventory
            for item in inventory:
                # Skip invalid items (strings or non-dict objects)
                if not isinstance(item, dict):
                    self.logger.warning(f"Found invalid inventory item for user {user_id}: {type(item)} - {item}")
                    continue
                    
                if (item.get("id") == item_id or item.get("name") == item_id) and remaining_to_remove > 0:
                    item_quantity = item.get("quantity", 1)
                    if item_quantity > remaining_to_remove:
                        # Keep the item but reduce its quantity
                        new_item = item.copy()
                        new_item["quantity"] = item_quantity - remaining_to_remove
                        items_to_keep.append(new_item)
                        remaining_to_remove = 0
                    else:
                        # Remove the entire item (or reduce quantity to 0)
                        remaining_to_remove -= item_quantity
                else:
                    items_to_keep.append(item.copy())
            
            # Update the main inventory if we modified it
            if len(items_to_keep) != len(inventory):
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {"inventory": items_to_keep}}
                )
                if result.modified_count > 0 and remaining_to_remove == 0:
                    return True
        
        # If we still need to remove items, check legacy potions array
        if remaining_to_remove > 0:
            potions = user.get("potions", [])
            potions_to_keep = []
            
            for potion in potions:
                if not isinstance(potion, dict):
                    potions_to_keep.append(potion)
                    continue
                    
                potion_id = potion.get("_id", potion.get("id"))
                if potion_id == item_id and remaining_to_remove > 0:
                    potion_amount = potion.get("amount", 1)
                    if potion_amount > remaining_to_remove:
                        # Keep the potion but reduce its amount
                        new_potion = potion.copy()
                        new_potion["amount"] = potion_amount - remaining_to_remove
                        potions_to_keep.append(new_potion)
                        remaining_to_remove = 0
                    else:
                        # Remove the entire potion
                        remaining_to_remove -= potion_amount
                else:
                    potions_to_keep.append(potion)
            
            # Update potions array if we removed any
            if len(potions_to_keep) != len(potions):
                await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {"potions": potions_to_keep}}
                )
        
        # Return True if we successfully removed the requested quantity
        return remaining_to_remove == 0

    async def add_fishing_item(self, user_id: int, item: dict, item_type: str) -> bool:
        """Add a fishing item (rod or bait) to user's inventory"""
        if not await self.ensure_connected():
            return False
        field = "fishing_rods" if item_type == "rod" else "bait"
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$push": {field: item}}
        )
        return result.modified_count > 0

    async def add_currency(self, user_id: int, amount: int) -> bool:
        """Add currency to user's wallet"""
        if not await self.ensure_connected():
            return False
        return await self.update_wallet(user_id, amount)

    async def get_user_inventory_by_type(self, user_id: int, item_type: str) -> dict:
        """Get user's inventory organized by item type (rod, bait, etc.)"""
        if not await self.ensure_connected():
            return {}
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user:
            return {}
        
        inventory = user.get("inventory", {})
        return inventory.get(item_type, {})

    async def set_active_rod(self, user_id: int, rod_id: str) -> bool:
        """Set user's active fishing rod"""
        if not await self.ensure_connected():
            return False
        
        # Verify user has this rod in inventory
        inventory = await self.get_user_inventory_by_type(user_id, "rod")
        if rod_id not in inventory or inventory[rod_id] <= 0:
            return False
        
        # Update active fishing gear
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"active_fishing.rod": rod_id}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_active_fishing_gear(self, user_id: int) -> dict:
        """Get user's active fishing rod and bait"""
        if not await self.ensure_connected():
            return {"rod": None, "bait": None}
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user:
            return {"rod": None, "bait": None}
        
        # Get active gear or default to best available
        active_gear = user.get("active_fishing", {})
        
        # Verify the active gear is still valid (user still has the items)
        rod_inventory = user.get("inventory", {}).get("rod", {})
        bait_inventory = user.get("inventory", {}).get("bait", {})
        
        # Check if active rod is still available
        active_rod = active_gear.get("rod")
        if not active_rod or active_rod not in rod_inventory or rod_inventory[active_rod] <= 0:
            # Find best available rod
            if rod_inventory:
                # This would need rod data to determine "best" - for now just pick first available
                active_rod = next(iter([rod_id for rod_id, qty in rod_inventory.items() if qty > 0]), None)
                if active_rod:
                    await self.set_active_rod(user_id, active_rod)
            else:
                active_rod = None
        
        # Check if active bait is still available
        active_bait = active_gear.get("bait")
        if not active_bait or active_bait not in bait_inventory or bait_inventory[active_bait] <= 0:
            # Find first available bait
            if bait_inventory:
                active_bait = next(iter([bait_id for bait_id, qty in bait_inventory.items() if qty > 0]), None)
                if active_bait:
                    await self.set_active_bait(user_id, active_bait)
            else:
                active_bait = None
        
        return {"rod": active_rod, "bait": active_bait}

    async def remove_bait(self, user_id: int, bait_id: str, amount: int = 1) -> bool:
        """Remove bait from user's inventory (new inventory structure)"""
        if not await self.ensure_connected():
            return False
        
        try:
            # Check current amount
            current_amount = await self.db.users.find_one(
                {"_id": str(user_id)},
                {f"inventory.bait.{bait_id}": 1}
            )
            
            if not current_amount:
                return False
                
            current_qty = current_amount.get("inventory", {}).get("bait", {}).get(bait_id, 0)
            
            if current_qty < amount:
                return False
            
            # Update the amount
            new_amount = current_qty - amount
            
            if new_amount <= 0:
                # Remove the bait entirely
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$unset": {f"inventory.bait.{bait_id}": ""}}
                )
            else:
                # Decrease the amount
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {f"inventory.bait.{bait_id}": new_amount}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            self.logger.error(f"Error removing bait: {e}")
            return False

    async def add_fishing_rod(self, user_id: int, rod_id: str, quantity: int = 1) -> bool:
        """Add fishing rod to user's inventory (new structure)"""
        if not await self.ensure_connected():
            return False
        
        try:
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {f"inventory.rod.{rod_id}": quantity}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Error adding fishing rod: {e}")
            return False

    async def add_fishing_bait(self, user_id: int, bait_id: str, quantity: int = 1) -> bool:
        """Add fishing bait to user's inventory (new structure)"""
        if not await self.ensure_connected():
            return False
        
        try:
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {f"inventory.bait.{bait_id}": quantity}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Error adding fishing bait: {e}")
            return False

    async def remove_fishing_rod(self, user_id: int, rod_id: str, quantity: int = 1) -> bool:
        """Remove fishing rod from user's inventory"""
        if not await self.ensure_connected():
            return False
        
        try:
            # Check current quantity
            user = await self.db.users.find_one(
                {"_id": str(user_id)},
                {f"inventory.rod.{rod_id}": 1}
            )
            
            if not user:
                return False
                
            current_qty = user.get("inventory", {}).get("rod", {}).get(rod_id, 0)
            
            if current_qty < quantity:
                return False
            
            new_qty = current_qty - quantity
            
            if new_qty <= 0:
                # Remove the rod entirely
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$unset": {f"inventory.rod.{rod_id}": ""}}
                )
            else:
                # Decrease quantity
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {f"inventory.rod.{rod_id}": new_qty}}
                )
            
            return result.modified_count > 0
            
        except Exception as e:
            self.logger.error(f"Error removing fishing rod: {e}")
            return False

    async def init_collections(self):
        """Initialize database collections and indexes"""
        if not await self.ensure_connected():
            return False
            
        # Create collections if they don't exist
        collections = [
            "users",
            "guild_settings", 
            "stats",
            "shops",
            "shop_items",
            "shop_potions",
            "shop_upgrades",
            "rods",  # Unified rods collection
            "bait",   # Unified bait collection
            "active_potions",
            "active_buffs",
            "reminders"  # Persistent reminders
        ]
        
        for coll_name in collections:
            if coll_name not in await self.db.list_collection_names():
                await self.db.create_collection(coll_name)

        # Set up indexes
        await self.db.users.create_index("_id")  # User ID
        await self.db.shops.create_index([("guild_id", 1), ("type", 1)])  # Shop lookups
        await self.db.active_potions.create_index("expires_at", expireAfterSeconds=0)  # TTL index
        await self.db.active_buffs.create_index("expires_at", expireAfterSeconds=0)  # TTL index
        await self.db.rods.create_index("_id")  # Rod ID index
        await self.db.bait.create_index("_id")  # Bait ID index
        await self.db.reminders.create_index("due_time")  # Reminder due time index
        await self.db.reminders.create_index("user_id")  # Reminder user index
        
        # Initialize user defaults with new inventory structure
        await self.db.users.update_many(
            {"wallet": {"$exists": False}},
            {"$set": {"wallet": 0}}
        )
        
        # Initialize new inventory structure
        await self.db.users.update_many(
            {"inventory": {"$exists": False}},
            {"$set": {
                "inventory": {
                    "rod": {},
                    "bait": {},
                    "item": {}
                }
            }}
        )
        
        # Initialize active fishing gear
        await self.db.users.update_many(
            {"active_fishing": {"$exists": False}},
            {"$set": {"active_fishing": {"rod": None, "bait": None}}}
        )
        
        # Initialize fish collection
        await self.db.users.update_many(
            {"fish": {"$exists": False}},
            {"$set": {"fish": []}}
        )
        
        return True

    async def get_fish(self, user_id: int) -> list:
        """Get user's caught fish"""
        if not await self.ensure_connected():
            return []
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("fish", []) if user else []

    async def add_fish(self, user_id: int, fish: dict) -> bool:
        """Add a fish to user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$push": {"fish": fish}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def remove_fish(self, user_id: int, fish_id: str) -> bool:
        """Remove a specific fish from user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$pull": {"fish": {"id": fish_id}}}
        )
        return result.modified_count > 0

    async def clear_fish(self, user_id: int) -> bool:
        """Clear all fish from user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"fish": []}}
        )
        return result.modified_count > 0

    async def get_all_fish_global(self) -> list:
        """Get all fish from all users for global leaderboard"""
        if not await self.ensure_connected():
            return []
        
        try:
            pipeline = [
                {"$match": {"fish": {"$exists": True, "$ne": []}}},
                {"$unwind": "$fish"},
                {"$addFields": {"fish.user_id": "$_id"}},
                {"$replaceRoot": {"newRoot": "$fish"}},
                {"$sort": {"value": -1}}
            ]
            
            result = await self.db.users.aggregate(pipeline).to_list(None)
            return result
        except Exception as e:
            self.logger.error(f"Failed to get global fish data: {e}")
            return []

    async def get_interest_level(self, user_id: int) -> int:
        """Get user's interest level"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("interest_level", 0) if user else 0

    async def upgrade_interest(self, user_id: int, cost: int, item_required: bool = False) -> tuple[bool, str]:
        """Upgrade user's interest level"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
        
        try:
            current_level = await self.get_interest_level(user_id)
            
            # Check max level
            if current_level >= 60:
                return False, "You've reached the maximum interest level!\n-# for now..."
            
            # Check wallet balance
            wallet_balance = await self.get_wallet_balance(user_id)
            if wallet_balance < cost:
                return False, f"Insufficient funds! You need {cost:,} coins but only have {wallet_balance:,}."
            
            # Check if user has required item (for levels >= 20)
            if item_required:
                inventory = await self.get_inventory(user_id)
                has_token = False
                
                for item in inventory:
                    if not isinstance(item, dict):
                        continue
                    if (item.get("id") == "interest_token" or 
                        item.get("name", "").lower() == "interest token"):
                        has_token = True
                        break
                
                if not has_token:
                    return False, "You need an Interest Token to upgrade beyond level 20!"
            
            # Start transaction-like operations
            # 1. Deduct cost
            if not await self.update_wallet(user_id, -cost):
                return False, "Failed to deduct upgrade cost!"
            
            # 2. Remove ONE interest token if needed (not all of them!)
            if item_required:
                token_removed = await self.remove_from_inventory(user_id, None, "interest_token", 1)
                if not token_removed:
                    # Try with name instead of ID
                    token_removed = await self.remove_from_inventory(user_id, None, "Interest Token", 1)
                
                if not token_removed:
                    # Refund the money
                    await self.update_wallet(user_id, cost)
                    return False, "Failed to consume Interest Token!"
            
            # 3. Update interest level
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {"interest_level": 1}},
                upsert=True
            )
            
            if result.modified_count > 0 or result.upserted_id is not None:
                new_level = current_level + 1
                new_rate = 0.003 + (new_level * 0.05)
                return True, f"✅ Interest level upgraded to **{new_level}**! Your new daily rate is **{new_rate:.3f}%**"
            else:
                # Something went wrong, refund everything
                await self.update_wallet(user_id, cost)
                if item_required:
                    # Add the token back (create new token item)
                    token_item = {
                        "id": "interest_token",
                        "name": "Interest Token",
                        "price": 50000,
                        "description": "Required to upgrade interest rate beyond level 20",
                        "type": "special"
                    }
                    # Add to inventory using dictionary structure
                    result = await self.db.users.update_one(
                        {"_id": str(user_id)},
                        {"$inc": {f"inventory.items.{token_item['id']}": 1}},
                        upsert=True
                    )
                return False, "Failed to upgrade interest level"
                
        except Exception as e:
            # Error occurred, try to refund
            await self.update_wallet(user_id, cost)
            self.logger.error(f"Interest upgrade error: {e}")
            return False, f"Upgrade failed: {str(e)}"

    async def upgrade_interest_with_item(self, user_id: int) -> bool:
        """Upgrade user's interest level using an item (no cost)"""
        if not await self.ensure_connected():
            return False
        
        try:
            current_level = await self.get_interest_level(user_id)
            
            # Check max level
            if current_level >= 60:
                return False
            
            # Update interest level directly (no cost since item was already consumed)
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {"interest_level": 1}},
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
                
        except Exception as e:
            self.logger.error(f"Interest upgrade with item error: {e}")
            return False

    async def add_to_inventory(self, user_id: int, guild_id: int, item: dict, quantity: int = 1) -> bool:
        """Add an item to user's inventory"""
        if not await self.ensure_connected():
            return False
        
        try:
            # First, ensure the user's inventory structure is correct
            await self.migrate_inventory_structure(user_id)
            
            # Create a clean item without unwanted fields
            clean_item = {
                "id": item.get("id", item.get("_id", str(ObjectId()))),
                "name": item.get("name", "Unknown Item"),
                "description": item.get("description", ""),
                "price": item.get("price", 0),
                "value": item.get("value", item.get("price", 0)),
                "type": item.get("type", "item"),
                "quantity": quantity
            }
            
            # Add any additional fields that might be relevant
            if "upgrade_type" in item:
                clean_item["upgrade_type"] = item["upgrade_type"]
            if "amount" in item:
                clean_item["amount"] = item["amount"]
            
            # Add to inventory using dictionary structure
            item_id = clean_item.get("id", clean_item.get("name", "unknown").lower().replace(" ", "_"))
            # Determine the correct inventory category
            category = "items"  # Default category for general items
            if clean_item.get("type") == "potion":
                category = "potions"
            elif clean_item.get("type") == "upgrade":
                category = "upgrades"
            
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {f"inventory.{category}.{item_id}": quantity}},
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error adding item to inventory: {e}")
            return False

    async def cleanup_corrupted_inventory(self) -> int:
        """Clean up corrupted inventory items (non-dict entries) from all users"""
        if not await self.ensure_connected():
            return 0
        
        try:
            cleaned_count = 0
            # Find all users with inventory
            users = await self.db.users.find({"inventory": {"$exists": True}}).to_list(None)
            
            for user in users:
                user_id = user["_id"]
                inventory = user.get("inventory", [])
                
                if not isinstance(inventory, list):
                    continue
                
                # Filter out non-dict items
                original_count = len(inventory)
                clean_inventory = [item for item in inventory if isinstance(item, dict)]
                
                if len(clean_inventory) < original_count:
                    # Update the user's inventory
                    await self.db.users.update_one(
                        {"_id": user_id},
                        {"$set": {"inventory": clean_inventory}}
                    )
                    removed_count = original_count - len(clean_inventory)
                    cleaned_count += removed_count
                    self.logger.info(f"Cleaned {removed_count} corrupted items from user {user_id}")
            
            if cleaned_count > 0:
                self.logger.info(f"Total cleanup: removed {cleaned_count} corrupted inventory items")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during inventory cleanup: {e}")
            return 0

    async def migrate_inventory_structure(self, user_id: int) -> bool:
        """Migrate user's inventory from array to dictionary structure"""
        if not await self.ensure_connected():
            return False
        
        try:
            user = await self.db.users.find_one({"_id": str(user_id)})
            if not user or "inventory" not in user:
                return True  # No inventory to migrate
            
            inventory = user["inventory"]
            
            # If inventory is already a dictionary, nothing to do
            if isinstance(inventory, dict):
                return True
            
            # If inventory is an array, migrate to dictionary structure
            if isinstance(inventory, list):
                new_inventory = {
                    "potions": {},
                    "upgrades": {},
                    "items": {}
                }
                
                # Convert each item in the array to the new structure
                for item in inventory:
                    if not isinstance(item, dict):
                        continue
                    
                    item_id = item.get("id", item.get("name", "unknown").lower().replace(" ", "_"))
                    quantity = item.get("quantity", 1)
                    item_type = item.get("type", "item")
                    
                    # Determine category
                    if item_type == "potion":
                        category = "potions"
                    elif item_type == "upgrade":
                        category = "upgrades"
                    else:
                        category = "items"
                    
                    # Add to new structure (sum quantities if duplicate IDs)
                    if item_id in new_inventory[category]:
                        new_inventory[category][item_id] += quantity
                    else:
                        new_inventory[category][item_id] = quantity
                
                # Update the user's inventory
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {"inventory": new_inventory}}
                )
                
                return result.modified_count > 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error migrating inventory structure for user {user_id}: {e}")
            return False
        

    # Reminder Management Functions
    async def add_reminder(self, user_id: int, message: str, due_time: datetime.datetime, 
                          channel_id: int = None, original_time: str = None) -> bool:
        """Add a reminder to the database"""
        if not await self.ensure_connected():
            return False
        
        try:
            reminder_data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "message": message,
                "due_time": due_time,
                "created_at": datetime.datetime.now(),
                "original_time": original_time
            }
            
            result = await self.db.reminders.insert_one(reminder_data)
            return result.inserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Error adding reminder: {e}")
            return False
    
    async def get_user_reminders(self, user_id: int) -> list:
        """Get all reminders for a user"""
        if not await self.ensure_connected():
            return []
        
        try:
            reminders = await self.db.reminders.find({
                "user_id": user_id
            }).sort("due_time", 1).to_list(None)
            return reminders
        except Exception as e:
            self.logger.error(f"Error getting user reminders: {e}")
            return []
    
    async def get_due_reminders(self) -> list:
        """Get all reminders that are due"""
        if not await self.ensure_connected():
            return []
        
        try:
            current_time = datetime.datetime.now()
            reminders = await self.db.reminders.find({
                "due_time": {"$lte": current_time}
            }).to_list(None)
            return reminders
        except Exception as e:
            self.logger.error(f"Error getting due reminders: {e}")
            return []
    
    async def delete_reminder(self, reminder_id) -> bool:
        """Delete a specific reminder"""
        if not await self.ensure_connected():
            return False
        
        try:
            result = await self.db.reminders.delete_one({"_id": reminder_id})
            return result.deleted_count > 0
        except Exception as e:
            self.logger.error(f"Error deleting reminder: {e}")
            return False
    
    async def delete_user_reminders(self, user_id: int) -> int:
        """Delete all reminders for a user, returns count deleted"""
        if not await self.ensure_connected():
            return 0
        
        try:
            result = await self.db.reminders.delete_many({"user_id": user_id})
            return result.deleted_count
        except Exception as e:
            self.logger.error(f"Error deleting user reminders: {e}")
            return 0
    
    async def cleanup_old_reminders(self, days_old: int = 30) -> int:
        """Clean up old reminders that are past due by specified days"""
        if not await self.ensure_connected():
            return 0
        
        try:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days_old)
            result = await self.db.reminders.delete_many({
                "due_time": {"$lt": cutoff_time}
            })
            return result.deleted_count
        except Exception as e:
            self.logger.error(f"Error cleaning up old reminders: {e}")
            return 0

    async def save_stats(self, stats: dict, key: str = "global") -> None:
        """Save stats to the MongoDB stats collection."""
        if not await self.ensure_connected():
            return
        await self.db.stats.update_one(
            {"_id": key},
            {"$set": stats},
            upsert=True
        )

    async def load_stats(self, key: str = "global") -> Optional[dict]:
        """Load stats from the MongoDB stats collection."""
        if not await self.ensure_connected():
            return None
        doc = await self.db.stats.find_one({"_id": key})
        return doc if doc else None

    # Bazaar-related methods
    async def get_guilds_with_bazaar_activity(self) -> list:
        """Get list of guild IDs with bazaar activity"""
        try:
            await self.ensure_connected()
            collection = self.db['guilds']
            
            # Get all guilds that exist in the database (have some activity)
            cursor = collection.find({}, {'_id': 1})
            guild_ids = []
            async for doc in cursor:
                if isinstance(doc['_id'], int):
                    guild_ids.append(doc['_id'])
            
            return guild_ids
        except Exception as e:
            self.logger.error(f"Error getting guilds with bazaar activity: {e}")
            return []

    async def save_bazaar_stats(self, stats_data: dict) -> bool:
        """Save bazaar statistics to database"""
        try:
            await self.ensure_connected()
            collection = self.db['bazaar_stats']
            
            # Add timestamp
            stats_data['timestamp'] = datetime.datetime.now()
            
            # Insert the stats
            result = await collection.insert_one(stats_data)
            
            # Clean up old stats (keep only last 30 days)
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
            await collection.delete_many({'timestamp': {'$lt': cutoff_date}})
            
            self.logger.debug(f"Saved bazaar stats: {stats_data}")
            return bool(result.inserted_id)
        except Exception as e:
            self.logger.error(f"Error saving bazaar stats: {e}")
            return False

    async def get_leaderboard(self, guild_id: int = None, limit: int = 10) -> list:
        """Get economy leaderboard for a guild or globally"""
        try:
            await self.ensure_connected()
            collection = self.db['users']
            
            if guild_id:
                # Server leaderboard - need to filter by guild members
                # For now, return all users with economy data
                # Note: Ideally we'd have guild membership data in the database
                cursor = collection.find({
                    "$or": [
                        {"wallet": {"$gt": 0}},
                        {"bank": {"$gt": 0}}
                    ]
                }).limit(limit * 5)  # Get more than needed to filter
            else:
                # Global leaderboard
                cursor = collection.find({
                    "$or": [
                        {"wallet": {"$gt": 0}},
                        {"bank": {"$gt": 0}}
                    ]
                }).limit(limit)
            
            users = []
            async for user_doc in cursor:
                try:
                    user_id = int(user_doc["_id"])
                    total_balance = user_doc.get("wallet", 0) + user_doc.get("bank", 0)
                    
                    if total_balance > 0:
                        users.append({
                            "user_id": user_id,
                            "id": user_id,  # For backwards compatibility
                            "total": round(total_balance),
                            "net_worth": round(total_balance),  # For leaderboard format
                            "wallet": user_doc.get("wallet", 0),
                            "bank": user_doc.get("bank", 0)
                        })
                except (ValueError, TypeError):
                    continue
            
            # Sort by total balance and limit results
            users.sort(key=lambda x: x["total"], reverse=True)
            return users[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {e}")
            return []

# Create an instance of AsyncDatabase to be imported elsewhere
async_db = AsyncDatabase.get_instance()

# Add a 'db' alias for backward compatibility
db = async_db

class SyncDatabase:
    """Synchronous database class for use with Flask web interface (SQLite & MongoDB)"""
    _instance = None
    _client = None
    _db = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SyncDatabase, cls).__new__(cls)
                    cls._instance._connected = False
                    cls._instance.logger = logging.getLogger('SyncDatabase')
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._connected = False
        self.logger = logging.getLogger('SyncDatabase')

        # Ensure data directory exists
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.getenv('SQLITE_DATABASE_PATH', os.path.join(data_dir, 'database.sqlite'))
        self.logger.info(f"Using SQLite database at {db_path}")

        try:
            import sqlite3
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._create_tables()
            self.conn.commit()
            self.logger.info("SQLite database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER,
                    guild_id INTEGER DEFAULT 0,
                    wallet INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_stats (
                    guild_id INTEGER,
                    stat_type TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, stat_type)
                )
            """)
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise

    @property
    def client(self):
        if self._client is None:
            MONGO_URI = os.getenv('MONGO_URI', config['MONGO_URI'])
            self._client = pymongo.MongoClient(MONGO_URI)
        return self._client

    @property
    def db(self):
        if self._db is None:
            self._db = self.client.bronxbot
        return self._db

    def ensure_connected(self) -> bool:
        """Ensure database connection is active."""
        if not self._connected:
            try:
                self.client.admin.command('ping')
                self._connected = True
                self.logger.info("Sync database connection established")
            except Exception as e:
                self.logger.error(f"Sync database connection failed: {e}")
                return False
        return True

    def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        """Get guild settings synchronously"""
        if not self.ensure_connected():
            return {}
        try:
            settings = self.db.guild_settings.find_one({"_id": str(guild_id)})
            return settings if settings else {}
        except Exception as e:
            self.logger.error(f"Error getting guild settings: {e}")
            return {}

    def update_guild_settings(self, guild_id: str, settings: Dict[str, Any]) -> bool:
        """Update guild settings synchronously"""
        if not self.ensure_connected():
            return False
        try:
            result = self.db.guild_settings.update_one(
                {"_id": str(guild_id)},
                {"$set": settings},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Error updating guild settings: {e}")
            return False

    def get_user_balance(self, user_id: int, guild_id: int = None):
        """Get user's wallet and bank balance"""
        try:
            self.cursor.execute("""
                SELECT wallet, bank FROM economy 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id or 0))
            result = self.cursor.fetchone()
            if result:
                return {"wallet": result[0], "bank": result[1]}
            return {"wallet": 0, "bank": 0}
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return {"wallet": 0, "bank": 0}

    # Change store_stats to be async-compatible
    async def store_stats(self, guild_id: int, stat_type: str):
        """Store guild statistics asynchronously"""
        return self.store_stats_sync(guild_id, stat_type)
    
    def store_stats_sync(self, guild_id: int, stat_type: str):
        """Store guild statistics synchronously"""
        try:
            valid_types = ["messages", "gained", "lost"]
            if stat_type not in valid_types:
                return False
                
            self.cursor.execute("""
                INSERT INTO guild_stats (guild_id, stat_type, count)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, stat_type) DO UPDATE 
                SET count = count + 1
            """, (guild_id, stat_type))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing stats: {e}")
            return False

    def get_stats(self, guild_id: int):
        """Get guild statistics"""
        try:
            self.cursor.execute("""
                SELECT stat_type, count FROM guild_stats
                WHERE guild_id = ?
            """, (guild_id,))
            results = self.cursor.fetchall()
            return {stat[0]: stat[1] for stat in results}
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}
