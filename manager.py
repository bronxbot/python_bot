#!/usr/bin/env python3
"""
BronxBot Manager Launcher
Quick launcher with fallback options
"""

import sys
import subprocess
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import textual
        import rich
        return True
    except ImportError:
        return False

def install_dependencies():
    """Install required dependencies"""
    print("Installing required dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "textual", "rich"
        ], check=True)
        print("SUCCESS: Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("ERROR: Failed to install dependencies")
        return False

def run_gui():
    """Run the main GUI application"""
    try:
        from bronx_manager import main
        return main()
    except Exception as e:
        print(f"ERROR: Error running GUI: {e}")
        return 1

def run_fallback():
    """Run a simple fallback menu"""
    scripts_dir = Path("scripts")
    
    while True:
        print("\n" + "="*50)
        print("BronxBot Manager (Fallback Mode)")
        print("="*50)
        print("1. Start Bot")
        print("2. Stop Bot") 
        print("3. Restart Bot")
        print("4. Check Status")
        print("5. View Logs")
        print("6. Start Tray")
        print("7. Setup Background Service")
        print("8. Uninstall Background Service")
        print("9. Exit")
        print()
        
        choice = input("Select option (1-9): ").strip()
        
        script_map = {
            "1": "start_bot.sh",
            "2": "stop_bot.sh", 
            "3": "start_bot.sh",  # restart is just start
            "4": "status_bot.sh",
            "5": "logs_bot.sh",
            "6": "start_tray.sh",
            "7": "setup_background.sh",
            "8": "uninstall_background.sh"
        }
        
        if choice == "9":
            print("Goodbye!")
            break
        elif choice in script_map:
            script = scripts_dir / script_map[choice]
            if script.exists():
                print(f"Running {script.name}...")
                try:
                    result = subprocess.run(["bash", str(script)], 
                                          cwd=str(Path.cwd()))
                    if result.returncode == 0:
                        print("SUCCESS: Command completed successfully!")
                    else:
                        print(f"ERROR: Command failed with code {result.returncode}")
                except Exception as e:
                    print(f"ERROR: Error running script: {e}")
            else:
                print(f"ERROR: Script not found: {script}")
        else:
            print("ERROR: Invalid option, please try again")
        
        input("\nPress Enter to continue...")

def main():
    """Main launcher function"""
    print("Starting BronxBot Manager...")
    
    # Check if we're in the right directory
    if not Path("bronxbot.py").exists():
        print("ERROR: Please run this from the BronxBot directory")
        return 1
    
    # Check if scripts directory exists
    if not Path("scripts").exists():
        print("ERROR: Scripts directory not found")
        return 1
    
    # Try to run the modern GUI
    if check_dependencies():
        print("Starting modern terminal GUI...")
        return run_gui()
    else:
        print("WARNING: Modern GUI dependencies not found")
        install = input("Install them now? (y/N): ").lower().startswith('y')
        
        if install and install_dependencies():
            print("Starting modern terminal GUI...")
            return run_gui()
        else:
            print("Starting fallback menu...")
            run_fallback()
            return 0

if __name__ == "__main__":
    exit(main())
