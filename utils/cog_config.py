#!/usr/bin/env python3
"""
Cog Configuration Manager
Provides easy configuration management for bot cogs
"""

import json
from pathlib import Path
from typing import Dict, List, Set

DEFAULT_COG_CONFIG = {
    "load_strategy": "all",  # "all", "essential", "custom"
    "categories": {
        "essential": True,
        "core": True, 
        "admin": True,
        "bronx": True,
        "economy": True,
        "fun": True,
        "misc": True
    },
    "disabled_cogs": [],
    "development_mode": False,
    "auto_reload": False
}

class CogConfig:
    """Manages cog loading configuration"""
    
    def __init__(self, config_path: str = "data/cog_config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load cog configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**DEFAULT_COG_CONFIG, **config}
            except Exception as e:
                print(f"Warning: Error loading cog config: {e}")
                return DEFAULT_COG_CONFIG.copy()
        else:
            # Create default config file
            self.save_config(DEFAULT_COG_CONFIG)
            return DEFAULT_COG_CONFIG.copy()
    
    def save_config(self, config: Dict = None) -> None:
        """Save configuration to file"""
        config = config or self.config
        self.config_path.parent.mkdir(exist_ok=True)
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Warning: Error saving cog config: {e}")
    
    def get_cogs_to_load(self) -> List[str]:
        """Get list of cogs to load based on configuration"""
        strategy = self.config.get("load_strategy", "all")
        
        # Define all available cogs by category
        all_cogs = {
            'essential': [
                "cogs.events",
                "cogs.Error", 
                "cogs.Utility"
            ],
            'core': [
                "cogs.Stats",
                "cogs.ModMail", 
                "cogs.Reminders",
                "cogs.Status",
                "cogs.ServerSettings",
                "cogs.Moderation"
            ],
            'admin': [
                "cogs.admin.Admin",
                "cogs.admin.SlashCommands"
            ],
            'bronx': [
                "cogs.bronx.AI",
                "cogs.bronx.VoteBans", 
                "cogs.bronx.Welcoming"
            ],
            'economy': [
                "cogs.economy.Economy",
                "cogs.economy.Shop",
                "cogs.economy.Work",
                "cogs.economy.Gambling",
                "cogs.economy.Giveaway",
                "cogs.economy.Bazaar",
                "cogs.economy.Trading"
            ],
            'fun': [
                "cogs.fun.Fun",
                "cogs.fun.Text",
                "cogs.fun.GambleOff"
            ],
            'misc': [
                "cogs.misc.Starboard"
            ]
        }
        
        cogs_to_load = []
        
        if strategy == "essential":
            cogs_to_load = all_cogs['essential']
        elif strategy == "all":
            for category, cogs in all_cogs.items():
                if self.config.get("categories", {}).get(category, True):
                    cogs_to_load.extend(cogs)
        elif strategy == "custom":
            enabled_categories = self.config.get("categories", {})
            for category, enabled in enabled_categories.items():
                if enabled and category in all_cogs:
                    cogs_to_load.extend(all_cogs[category])
        
        # Remove disabled cogs
        disabled_cogs = set(self.config.get("disabled_cogs", []))
        cogs_to_load = [cog for cog in cogs_to_load if cog not in disabled_cogs]
        
        return cogs_to_load
    
    def disable_cogs(self, cog_names: List[str]) -> None:
        """Disable specific cogs"""
        disabled = set(self.config.get("disabled_cogs", []))
        disabled.update(cog_names)
        self.config["disabled_cogs"] = list(disabled)
        self.save_config()
    
    def enable_cogs(self, cog_names: List[str]) -> None:
        """Enable specific cogs"""
        disabled = set(self.config.get("disabled_cogs", []))
        disabled.difference_update(cog_names)
        self.config["disabled_cogs"] = list(disabled)
        self.save_config()
    
    def set_category_enabled(self, category: str, enabled: bool) -> None:
        """Enable or disable an entire category"""
        if "categories" not in self.config:
            self.config["categories"] = {}
        self.config["categories"][category] = enabled
        self.save_config()
    
    def set_load_strategy(self, strategy: str) -> None:
        """Set the loading strategy: 'all', 'essential', or 'custom'"""
        if strategy in ['all', 'essential', 'custom']:
            self.config["load_strategy"] = strategy
            self.save_config()
        else:
            raise ValueError(f"Invalid strategy: {strategy}")
    
    def get_summary(self) -> Dict:
        """Get a summary of the current configuration"""
        cogs_to_load = self.get_cogs_to_load()
        
        return {
            "strategy": self.config.get("load_strategy", "all"),
            "total_cogs_to_load": len(cogs_to_load),
            "disabled_cogs": len(self.config.get("disabled_cogs", [])),
            "categories_enabled": sum(1 for enabled in self.config.get("categories", {}).values() if enabled),
            "development_mode": self.config.get("development_mode", False)
        }

# Convenience functions
def get_cog_config() -> CogConfig:
    """Get the global cog configuration instance"""
    return CogConfig()

def get_cogs_to_load() -> List[str]:
    """Get list of cogs to load based on current configuration"""
    return get_cog_config().get_cogs_to_load()

if __name__ == "__main__":
    # Test the configuration system
    config = CogConfig()
    print("Current cog configuration:")
    print(json.dumps(config.get_summary(), indent=2))
    print(f"\nCogs to load: {len(config.get_cogs_to_load())}")
