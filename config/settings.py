"""
Configuration management for BronxBot
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot configuration settings"""
    
    # Discord Configuration
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    client_id: str = Field(..., env="CLIENT_ID")
    client_secret: str = Field(..., env="CLIENT_SECRET")
    owner_id: int = Field(..., env="OWNER_ID")
    prefix: str = Field("!", env="PREFIX")
    
    # Database Configuration
    mongo_uri: str = Field(..., env="MONGO_URI")
    database_name: str = Field("bronxbot", env="DATABASE_NAME")
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    
    # Bot Configuration
    dev_mode: bool = Field(False, env="DEV_MODE")
    
    # Performance Monitoring
    enable_monitoring: bool = Field(True, env="ENABLE_MONITORING")
    alert_threshold_cpu: int = Field(80, env="ALERT_THRESHOLD_CPU")
    alert_threshold_memory: int = Field(85, env="ALERT_THRESHOLD_MEMORY")
    
    # Feature Flags
    enable_fishing: bool = Field(True, env="ENABLE_FISHING")
    enable_gambling: bool = Field(True, env="ENABLE_GAMBLING")
    enable_trading: bool = Field(True, env="ENABLE_TRADING")
    enable_bazaar: bool = Field(True, env="ENABLE_BAZAAR")
    
    # API Configuration
    dashboard_url: Optional[str] = Field(None, env="DASHBOARD_URL")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields


# Game Configuration
ECONOMY_CONFIG = {
    "currency_name": "bronkbuk",
    "currency_emoji": "<:bronkbuk:123456789>",  # Replace with actual emoji ID
    "starting_balance": 1000,
    "daily_bonus": 500,
    "max_wallet": 50000,
    "bank_interest_rate": 0.02,  # 2% daily
    "bank_upgrades": {
        "bronze": {"cost": 10000, "limit": 100000},
        "silver": {"cost": 50000, "limit": 500000},
        "gold": {"cost": 200000, "limit": 2000000},
        "platinum": {"cost": 1000000, "limit": 10000000}
    }
}

FISHING_CONFIG = {
    "base_catch_time": 5,  # seconds
    "max_catch_time": 30,
    "rarity_multipliers": {
        "common": 1.0,
        "uncommon": 1.5,
        "rare": 2.0,
        "epic": 3.0,
        "legendary": 5.0,
        "galactic": 8.0,
        "intergalactic": 12.0,
        "godlike": 20.0,
        "mythical": 35.0,
        "impossible": 60.0,
        "otherworldly": 100.0
    }
}

GAMBLING_CONFIG = {
    "min_bet": 10,
    "max_bet": 10000,
    "house_edge": 0.02,  # 2%
    "progressive_limits": {
        "bronze": 1000,
        "silver": 5000,
        "gold": 25000,
        "platinum": 100000
    }
}

WORK_CONFIG = {
    "base_wage": 100,
    "max_wage": 1000,
    "cooldown_minutes": 30,
    "boss_relationship_effects": {
        "hostile": 0.7,
        "neutral": 1.0,
        "friendly": 1.3,
        "loyal": 1.5
    }
}
