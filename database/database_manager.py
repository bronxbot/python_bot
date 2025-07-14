"""
Database Manager for BronxBot
Handles MongoDB connections and operations
"""

import asyncio
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages all database operations for the bot"""
    
    def __init__(self, mongo_uri: str, database_name: str = "bronxbot"):
        self.mongo_uri = mongo_uri
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        
    async def connect(self):
        """Connect to MongoDB with optimized settings"""
        try:
            # Create client with connection pooling and timeouts
            self.client = AsyncIOMotorClient(
                self.mongo_uri,
                maxPoolSize=50,
                minPoolSize=10,
                maxIdleTimeMS=30000,
                waitQueueMultiple=2,
                connectTimeoutMS=5000,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            self.db = self.client[self.database_name]
            
            # Test connection with timeout
            await asyncio.wait_for(
                self.client.admin.command('ping'), 
                timeout=5.0
            )
            logger.info("Connected to MongoDB successfully")
            
            # Create indexes in background
            asyncio.create_task(self.create_indexes())
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")
    
    async def create_indexes(self):
        """Create necessary database indexes"""
        try:
            logger.info("Creating database indexes...")
            
            # User data indexes
            await self.db.users.create_index("user_id", unique=True)
            await self.db.users.create_index("guild_id")
            await self.db.users.create_index([("user_id", 1), ("guild_id", 1)], unique=True)
            
            # Transaction indexes
            await self.db.transactions.create_index("user_id")
            await self.db.transactions.create_index("timestamp")
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            # Don't raise exception to prevent blocking startup
            await self.db.users.create_index("guild_id")
            
            # Economy indexes
            await self.db.economy.create_index("user_id", unique=True)
            await self.db.transactions.create_index("user_id")
            await self.db.transactions.create_index("timestamp")
            
            # Fishing indexes
            await self.db.fishing.create_index("user_id")
            await self.db.fishing.create_index("fish_name")
            await self.db.fishing_stats.create_index("user_id", unique=True)
            
            # Gambling indexes
            await self.db.gambling_stats.create_index("user_id", unique=True)
            
            # Work indexes
            await self.db.work_stats.create_index("user_id", unique=True)
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    # User Management
    async def get_user(self, user_id: int, guild_id: int = None) -> Optional[Dict[str, Any]]:
        """Get user data"""
        query = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
            
        return await self.db.users.find_one(query)
    
    async def create_user(self, user_id: int, guild_id: int = None) -> Dict[str, Any]:
        """Create a new user"""
        user_data = {
            "user_id": user_id,
            "guild_id": guild_id,
            "created_at": asyncio.get_event_loop().time(),
            "economy": {
                "wallet": 1000,
                "bank": 0,
                "bank_tier": "bronze",
                "total_earned": 0,
                "total_spent": 0
            },
            "fishing": {
                "rod": "basic_rod",
                "bait": "basic_bait",
                "total_catches": 0,
                "total_value": 0,
                "catches": {}
            },
            "gambling": {
                "total_bet": 0,
                "total_won": 0,
                "games_played": 0,
                "biggest_win": 0
            },
            "work": {
                "job": None,
                "boss_relationship": "neutral",
                "total_worked": 0,
                "total_earned": 0,
                "last_work": None
            }
        }
        
        await self.db.users.insert_one(user_data)
        return user_data
    
    async def update_user(self, user_id: int, update_data: Dict[str, Any], guild_id: int = None):
        """Update user data"""
        query = {"user_id": user_id}
        if guild_id:
            query["guild_id"] = guild_id
            
        await self.db.users.update_one(query, {"$set": update_data})
    
    # Economy Operations
    async def get_economy_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user economy data"""
        user = await self.get_user(user_id)
        return user.get("economy") if user else None
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0):
        """Update user balance"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "economy.wallet": wallet_change,
                    "economy.bank": bank_change
                }
            }
        )
    
    async def add_transaction(self, user_id: int, transaction_type: str, amount: int, description: str):
        """Add a transaction record"""
        transaction = {
            "user_id": user_id,
            "type": transaction_type,
            "amount": amount,
            "description": description,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self.db.transactions.insert_one(transaction)
    
    # Fishing Operations
    async def get_fishing_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user fishing data"""
        user = await self.get_user(user_id)
        return user.get("fishing") if user else None
    
    async def add_fish_catch(self, user_id: int, fish_name: str, rarity: str, value: int):
        """Add a fish catch to user's record"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "fishing.total_catches": 1,
                    "fishing.total_value": value,
                    f"fishing.catches.{fish_name}": 1
                }
            }
        )
        
        # Update global fish statistics
        await self.db.fish_stats.update_one(
            {"fish_name": fish_name},
            {
                "$inc": {"total_caught": 1},
                "$setOnInsert": {"rarity": rarity, "value": value}
            },
            upsert=True
        )
    
    # Gambling Operations
    async def update_gambling_stats(self, user_id: int, game_type: str, bet_amount: int, won_amount: int):
        """Update gambling statistics"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "gambling.total_bet": bet_amount,
                    "gambling.total_won": won_amount,
                    "gambling.games_played": 1
                },
                "$max": {
                    "gambling.biggest_win": won_amount
                }
            }
        )
    
    # Work Operations
    async def update_work_stats(self, user_id: int, job: str, earnings: int, boss_relationship: str):
        """Update work statistics"""
        await self.db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "work.job": job,
                    "work.boss_relationship": boss_relationship,
                    "work.last_work": asyncio.get_event_loop().time()
                },
                "$inc": {
                    "work.total_worked": 1,
                    "work.total_earned": earnings
                }
            }
        )
    
    # Leaderboard Operations
    async def get_leaderboard(self, field: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard for a specific field"""
        pipeline = [
            {"$sort": {field: -1}},
            {"$limit": limit}
        ]
        
        return await self.db.users.aggregate(pipeline).to_list(limit)
    
    # Global Statistics
    async def get_global_stats(self) -> Dict[str, Any]:
        """Get global bot statistics"""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_users": {"$sum": 1},
                    "total_wallet": {"$sum": "$economy.wallet"},
                    "total_bank": {"$sum": "$economy.bank"},
                    "total_fish_caught": {"$sum": "$fishing.total_catches"},
                    "total_games_played": {"$sum": "$gambling.games_played"},
                    "total_work_sessions": {"$sum": "$work.total_worked"}
                }
            }
        ]
        
        result = await self.db.users.aggregate(pipeline).to_list(1)
        return result[0] if result else {}


# Singleton instance
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance"""
    global _db_manager
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized")
    return _db_manager

def set_database_manager(manager: DatabaseManager):
    """Set the global database manager instance"""
    global _db_manager
    _db_manager = manager
