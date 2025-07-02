#!/usr/bin/env python3
"""
Simple and robust cog loading utility for BronxBot
This module provides a clean interface for loading cogs with proper error handling
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from nextcord.ext import commands

logger = logging.getLogger(__name__)

class CogLoader:
    """Simple, robust cog loader with categorization and error handling"""
    
    # Define cog categories with their respective modules
    COG_CATEGORIES = {
        "essential": [
            "cogs.events",
            "cogs.Error", 
            "cogs.Utility"
        ],
        "core": [
            "cogs.Stats",
            "cogs.ModMail", 
            "cogs.Reminders",
            "cogs.Status",
            "cogs.ServerSettings",
            "cogs.Moderation"
        ],
        "admin": [
            "cogs.admin.Admin",
            "cogs.admin.SlashCommands"
        ],
        "bronx": [
            "cogs.bronx.AI",
            "cogs.bronx.VoteBans", 
            "cogs.bronx.Welcoming"
        ],
        "economy": [
            "cogs.economy.Economy",
            "cogs.economy.Shop",
            "cogs.economy.Work",
            "cogs.economy.Gambling",
            "cogs.economy.Giveaway",
            "cogs.economy.Bazaar",
            "cogs.economy.Trading"
        ],
        "fun": [
            "cogs.fun.Fun",
            "cogs.fun.Text",
            "cogs.fun.GambleOff"
        ],
        "misc": [
            "cogs.misc.Starboard"
        ]
    }
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loaded_cogs: List[str] = []
        self.failed_cogs: List[Tuple[str, str]] = []  # (cog_name, error_message)
        self.total_attempted = 0
    
    async def load_all_cogs(self, categories: Optional[List[str]] = None, exclude_categories: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Load all cogs from specified categories
        
        Args:
            categories: List of category names to load. If None, loads all categories.
            exclude_categories: List of category names to exclude.
            
        Returns:
            Dict with loading statistics
        """
        if categories is None:
            categories = list(self.COG_CATEGORIES.keys())
        
        if exclude_categories:
            categories = [cat for cat in categories if cat not in exclude_categories]
        
        print(f"🔄 Loading cogs from categories: {', '.join(categories)}")
        
        for category in categories:
            if category in self.COG_CATEGORIES:
                await self.load_category(category)
            else:
                print(f"⚠️  Unknown category: {category}")
        
        return self.get_loading_stats()
    
    async def load_category(self, category: str) -> None:
        """Load all cogs from a specific category"""
        if category not in self.COG_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        
        cogs = self.COG_CATEGORIES[category]
        print(f"📂 Loading {category} cogs ({len(cogs)} total)")
        
        for cog_name in cogs:
            await self.load_single_cog(cog_name)
            await asyncio.sleep(0.01)  # Small delay to prevent overwhelming
    
    async def load_single_cog(self, cog_name: str) -> bool:
        """
        Load a single cog safely
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        self.total_attempted += 1
        
        try:
            # Check if already loaded
            if cog_name in self.bot.extensions:
                self.loaded_cogs.append(cog_name)
                return True
            
            # Load the cog
            await self.bot.load_extension(cog_name)
            
            # Verify it was actually loaded
            if cog_name in self.bot.extensions:
                self.loaded_cogs.append(cog_name)
                short_name = cog_name.split('.')[-1]
                print(f"  ✅ {short_name}")
                return True
            else:
                # Extension load call succeeded but extension not found
                error_msg = "Load succeeded but extension not registered"
                self.failed_cogs.append((cog_name, error_msg))
                short_name = cog_name.split('.')[-1]
                print(f"  ❌ {short_name}: {error_msg}")
                return False
            
        except commands.ExtensionNotFound:
            error_msg = "Module not found"
        except commands.ExtensionAlreadyLoaded:
            # This shouldn't happen due to our check, but handle it anyway
            self.loaded_cogs.append(cog_name)
            return True
        except commands.NoEntryPointError:
            error_msg = "Missing setup() function"
        except commands.ExtensionFailed as e:
            error_msg = f"Extension failed: {str(e.original)[:100]}"
        except Exception as e:
            # Check if the cog actually loaded despite the exception
            if cog_name in self.bot.extensions:
                self.loaded_cogs.append(cog_name)
                short_name = cog_name.split('.')[-1]
                print(f"  ✅ {short_name} (loaded with warnings)")
                return True
            else:
                error_msg = f"Unexpected error: {str(e)[:100]}"
        
        # Log the failure
        self.failed_cogs.append((cog_name, error_msg))
        short_name = cog_name.split('.')[-1]
        print(f"  ❌ {short_name}: {error_msg}")
        return False
    
    async def load_essential_only(self) -> Dict[str, any]:
        """Load only essential cogs - useful for minimal functionality"""
        return await self.load_all_cogs(categories=["essential"])
    
    async def load_core_cogs(self) -> Dict[str, any]:
        """Load essential + core cogs - good for basic functionality"""
        return await self.load_all_cogs(categories=["essential", "core"])
    
    def get_loading_stats(self) -> Dict[str, any]:
        """Get comprehensive loading statistics"""
        success_count = len(self.loaded_cogs)
        failure_count = len(self.failed_cogs)
        success_rate = (success_count / self.total_attempted) * 100 if self.total_attempted > 0 else 0
        
        return {
            "total_attempted": self.total_attempted,
            "successful": success_count,
            "failed": failure_count,
            "success_rate": success_rate,
            "loaded_cogs": self.loaded_cogs.copy(),
            "failed_cogs": self.failed_cogs.copy()
        }
    
    def print_summary(self) -> None:
        """Print a comprehensive loading summary"""
        stats = self.get_loading_stats()
        
        print("\n" + "="*60)
        print("🤖 COG LOADING SUMMARY")
        print("="*60)
        print(f"📊 Total Attempted: {stats['total_attempted']}")
        print(f"✅ Successful: {stats['successful']}")
        print(f"❌ Failed: {stats['failed']}")
        print(f"📈 Success Rate: {stats['success_rate']:.1f}%")
        
        if stats['failed_cogs']:
            print("\n❌ FAILED COGS:")
            for cog_name, error in stats['failed_cogs']:
                short_name = cog_name.split('.')[-1]
                print(f"  • {short_name}: {error}")
        
        print("="*60)


# Convenience function for simple usage
async def load_cogs_simple(bot: commands.Bot, essential_only: bool = False) -> CogLoader:
    """
    Simple function to load cogs with minimal configuration
    
    Args:
        bot: The Discord bot instance
        essential_only: If True, only loads essential cogs
        
    Returns:
        CogLoader instance with loading results
    """
    loader = CogLoader(bot)
    
    if essential_only:
        await loader.load_essential_only()
    else:
        await loader.load_all_cogs()
    
    return loader
