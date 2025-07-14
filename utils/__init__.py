"""Utils module init"""

from .logger import setup_logger, get_logger
from .bot_utils import (
    get_prefix, format_currency, format_time, calculate_rarity_chance,
    get_rarity_color, get_rarity_emoji, Cooldowns, PaginatedEmbed,
    create_error_embed, create_success_embed, create_info_embed,
    safe_send, cooldown_manager
)

__all__ = [
    "setup_logger", "get_logger", "get_prefix", "format_currency",
    "format_time", "calculate_rarity_chance", "get_rarity_color",
    "get_rarity_emoji", "Cooldowns", "PaginatedEmbed", "create_error_embed",
    "create_success_embed", "create_info_embed", "safe_send", "cooldown_manager"
]
