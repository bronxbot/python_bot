#!/usr/bin/env python3
"""
bronx manager launcher
simple launcher with fallback options
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
    """install required dependencies"""
    print("installing dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "textual", "rich"
        ], check=True)
        print("success: dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("error: failed to install dependencies")
        return False

def run_gui():
    """run the main gui application"""
    try:
        from bronx_manager import main
        return main()
    except Exception as e:
        print(f"error: error running gui: {e}")
        return 1

def run_fallback():
    """run a simple fallback menu"""
    scripts_dir = Path("scripts")
    
    while True:
        print("\n" + "="*50)
        print("bronx manager (fallback mode)")
        print("="*50)
        print("1. start bot")
        print("2. stop bot") 
        print("3. restart bot")
        print("4. check status")
        print("5. view logs")
        print("6. start tray")
        print("7. setup background service")
        print("8. uninstall background service")
        print("9. exit")
        print()
        
        choice = input("select option (1-9): ").strip()
        
        script_map = {
            "1": "start_bot.sh",
            "2": "stop_bot.sh", 
            "3": "start_bot.sh",  # restart is just start xd
            "4": "status_bot.sh",
            "5": "logs_bot.sh",
            "6": "start_tray.sh",
            "7": "setup_background.sh",
            "8": "uninstall_background.sh"
        }
        
        if choice == "9":
            print("goodbye!")
            break
        elif choice in script_map:
            script = scripts_dir / script_map[choice]
            if script.exists():
                print(f"running {script.name}...")
                try:
                    result = subprocess.run(["bash", str(script)], 
                                          cwd=str(Path.cwd()))
                    if result.returncode == 0:
                        print("success: command completed")
                    else:
                        print(f"error: command failed with code {result.returncode}")
                except Exception as e:
                    print(f"error: error running script: {e}")
            else:
                print(f"error: script not found: {script}")
        else:
            print("error: invalid option, please try again")
        
        input("\npress enter to continue...")

def main():
    """main launcher function"""
    print("starting bronx manager...")
    
    # Check if we're in the right directory
    if not Path("bronxbot.py").exists():
        print("error: please run this from the bronxbot directory")
        return 1
    
    # Check if scripts directory exists
    if not Path("scripts").exists():
        print("error: scripts directory not found")
        return 1
    
    # Try to run the modern GUI
    if check_dependencies():
        print("starting modern terminal gui...")
        return run_gui()
    else:
        print("warning: modern gui dependencies not found")
        install = input("install them now? (y/n): ").lower().startswith('y')
        
        if install and install_dependencies():
            print("starting modern terminal gui...")
            return run_gui()
        else:
            print("starting fallback menu...")
            run_fallback()
            return 0

if __name__ == "__main__":
    exit(main())
