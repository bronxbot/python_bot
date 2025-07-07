import logging
import sys
import os
from datetime import datetime
from typing import Optional

class CogLogger:
    """Enhanced logger with file output and better error handling"""
    def __init__(self, name: str, level: int = logging.INFO):
        self._logger = logging.getLogger(f"bronxbot.{name}")
        self._logger.setLevel(level)
        
        if not self._logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_formatter = ColoredFormatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)
            
            # File handler for errors and critical logs
            try:
                os.makedirs('logs', exist_ok=True)
                file_handler = logging.FileHandler(
                    f'logs/bronxbot_{datetime.now().strftime("%Y%m%d")}.log',
                    encoding='utf-8'
                )
                file_handler.setLevel(logging.WARNING)  # Only warnings and above to file
                file_formatter = logging.Formatter(
                    '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                self._logger.addHandler(file_handler)
            except Exception:
                pass  # File logging is optional
    
    # Delegate logging methods to make usage cleaner



class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        return super().format(record)