import sys
import os
import subprocess
import json
import signal
import time
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QStyle
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPainter, QBrush, QColor, QPen

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class BotStatusThread(QThread):
    """Thread to monitor bot status"""
    status_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.bot_process = None
        self.last_good_stats = {
            'guilds': 0,
            'users': 0,
            'latency': 0
        }
    
    def run(self):
        while self.running:
            status = self.check_bot_status()
            self.status_updated.emit(status)
            time.sleep(3)  # Check every 3 seconds for better responsiveness
    
    def check_bot_status(self):
        """Check if the bot is running and get stats"""
        try:
            # Check if systemd service is running
            result = subprocess.run(['systemctl', '--user', 'is-active', 'bronxbot'], 
                                  capture_output=True, text=True)
            service_active = result.stdout.strip() == 'active'
            
            stats = {
                'service_active': service_active,
                'bot_connected': False,
                'guilds': 0,
                'users': 0,
                'uptime': 'Unknown',
                'last_activity': 'Unknown',
                'latency': 0
            }
            
            if not service_active:
                # Clear cached stats when service is not running
                self.last_good_stats = {'guilds': 0, 'users': 0, 'latency': 0}
                return stats
            
            # Get stats from multiple sources
            bot_connected = False
            guilds = 0
            users = 0
            latency = 0
            best_stats_found = False
            
            # Method 1: Check recent systemd journal logs
            try:
                journal_result = subprocess.run([
                    'journalctl', '--user', '-u', 'bronxbot', 
                    '--since', '1 hour ago', '--no-pager'  # Extended window
                ], capture_output=True, text=True, timeout=5)
                
                if journal_result.returncode == 0:
                    journal_lines = journal_result.stdout.split('\n')
                    
                    # Process lines in reverse order but keep track of best stats
                    for line in reversed(journal_lines[-100:]):  # Check last 100 lines
                        if 'BOT READY' in line:
                            bot_connected = True
                        elif 'Events:' in line and 'Guilds:' in line and 'Users:' in line:
                            # Parse complete stats line: "Events: 27 | Guilds: 76 | Users: 30499 | Latency: 39ms"
                            try:
                                import re
                                temp_guilds = guilds
                                temp_users = users
                                temp_latency = latency
                                
                                # Parse all components
                                guilds_match = re.search(r'Guilds:\s*(\d+)', line)
                                users_match = re.search(r'Users:\s*(\d+)', line)
                                latency_match = re.search(r'Latency:\s*(\d+)ms', line)
                                
                                if guilds_match:
                                    temp_guilds = int(guilds_match.group(1))
                                if users_match:
                                    temp_users = int(users_match.group(1))
                                if latency_match:
                                    temp_latency = int(latency_match.group(1))
                                
                                # Only update if we got a complete set of stats
                                if temp_guilds > 0 and temp_users > 0:
                                    guilds = temp_guilds
                                    users = temp_users
                                    latency = temp_latency
                                    bot_connected = True
                                    best_stats_found = True
                                    print(f"[DEBUG] Complete stats found: Guilds={guilds}, Users={users}, Latency={latency}")
                                    break  # Use the most recent complete stats
                                
                            except Exception as e:
                                print(f"[DEBUG] Error parsing stats line: {e}")
                                continue
                        
                        # Fallback: parse individual stats if no complete line found
                        elif not best_stats_found:
                            if 'Guilds Connected:' in line or 'Guilds:' in line:
                                try:
                                    import re
                                    guild_match = re.search(r'(?:Guilds Connected|Guilds):\s*(\d+)', line)
                                    if guild_match and int(guild_match.group(1)) > 0:
                                        guilds = int(guild_match.group(1))
                                        bot_connected = True
                                except:
                                    pass
                            elif 'Users Accessible:' in line or 'Users:' in line:
                                try:
                                    import re
                                    user_match = re.search(r'(?:Users Accessible|Users):\s*(\d+)', line)
                                    if user_match and int(user_match.group(1)) > 0:
                                        users = int(user_match.group(1))
                                except:
                                    pass
                            elif 'Latency:' in line:
                                try:
                                    import re
                                    latency_match = re.search(r'Latency[:\s]+(\d+)ms', line)
                                    if latency_match:
                                        latency = int(latency_match.group(1))
                                except:
                                    pass
                                    
                print(f"[DEBUG] Final stats: Connected={bot_connected}, Guilds={guilds}, Users={users}, Latency={latency}")
            except Exception as e:
                print(f"Journal check failed: {e}")
            
            # Method 2: Check log files if journal didn't work
            if not bot_connected or guilds == 0:
                try:
                    log_files = list(Path('logs').glob('bronxbot_*.log'))
                    if log_files:
                        latest_log = max(log_files, key=os.path.getctime)
                        
                        # Only check recent entries (last 5 minutes worth)
                        import time
                        current_time = time.time()
                        five_minutes_ago = current_time - 300
                        
                        with open(latest_log, 'r') as f:
                            lines = f.readlines()[-200:]  # Last 200 lines
                            
                        for line in reversed(lines):
                            # Skip old entries
                            try:
                                # Extract timestamp if present
                                if line.startswith('2025-'):
                                    timestamp_str = line.split(' - ')[0]
                                    log_time = time.mktime(time.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f'))
                                    if log_time < five_minutes_ago:
                                        continue
                            except:
                                pass
                            
                            if 'BOT READY' in line:
                                bot_connected = True
                            elif 'Events:' in line and 'Guilds:' in line and 'Users:' in line:
                                # Parse console stats output
                                try:
                                    import re
                                    guilds_match = re.search(r'Guilds:\s*(\d+)', line)
                                    users_match = re.search(r'Users:\s*(\d+)', line)
                                    latency_match = re.search(r'Latency:\s*(\d+)ms', line)
                                    
                                    if guilds_match:
                                        guilds = int(guilds_match.group(1))
                                        bot_connected = True
                                    if users_match:
                                        users = int(users_match.group(1))
                                    if latency_match:
                                        latency = int(latency_match.group(1))
                                except:
                                    pass
                except Exception as e:
                    print(f"Log file check failed: {e}")
            
            # Method 3: If still no connection detected but service is active, assume connecting
            if service_active and not bot_connected and guilds == 0:
                # Check if service just started
                try:
                    status_result = subprocess.run([
                        'systemctl', '--user', 'show', 'bronxbot', 
                        '--property=ActiveEnterTimestamp'
                    ], capture_output=True, text=True, timeout=5)
                    
                    if 'ActiveEnterTimestamp=' in status_result.stdout:
                        # Service is active but might be starting up
                        stats['last_activity'] = 'Starting...'
                except:
                    pass
            
            # Update stats
            stats.update({
                'bot_connected': bot_connected,
                'guilds': guilds,
                'users': users,
                'latency': latency,
                'last_activity': 'Connected' if bot_connected else ('Starting...' if service_active else 'Offline')
            })
            
            # If we got complete stats, save them as last good stats
            if guilds > 0 and users > 0:
                self.last_good_stats = {
                    'guilds': guilds,
                    'users': users,
                    'latency': latency
                }
            # If current stats are incomplete but we have last good stats, use them
            elif self.last_good_stats['guilds'] > 0 and self.last_good_stats['users'] > 0:
                if guilds == 0:
                    stats['guilds'] = self.last_good_stats['guilds']
                if users == 0:
                    stats['users'] = self.last_good_stats['users']
                if latency == 0:
                    stats['latency'] = self.last_good_stats['latency']
                print(f"[DEBUG] Using cached stats: Guilds={stats['guilds']}, Users={stats['users']}, Latency={stats['latency']}")
            
            # Debug output
            if bot_connected or stats['guilds'] > 0 or stats['users'] > 0:
                print(f"[DEBUG] Final stats: Connected={bot_connected}, Guilds={stats['guilds']}, Users={stats['users']}, Latency={stats['latency']}")
            
            return stats
            
        except Exception as e:
            return {
                'service_active': False,
                'bot_connected': False,
                'guilds': 0,
                'users': 0,
                'uptime': 'Error',
                'last_activity': str(e),
                'latency': 0
            }
    
    def stop(self):
        self.running = False

class BotLogWindow(QWidget):
    """Window to display bot logs"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BronxBot Logs")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_display)
        
        # Control buttons
        refresh_btn = QPushButton("Refresh Logs")
        refresh_btn.clicked.connect(self.refresh_logs)
        layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear Display")
        clear_btn.clicked.connect(self.log_display.clear)
        layout.addWidget(clear_btn)
        
        self.setLayout(layout)
        self.refresh_logs()
    
    def refresh_logs(self):
        """Load and display recent logs"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.log_display.setText("No log files found.")
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            with open(latest_log, 'r') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
                
                # Strip ANSI escape codes for clean display
                import re
                clean_lines = []
                ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
                for line in lines:
                    clean_line = ansi_escape.sub('', line)
                    clean_lines.append(clean_line)
                
                self.log_display.setText(''.join(clean_lines))
                
            # Scroll to bottom
            self.log_display.moveCursor(self.log_display.textCursor().End)
            
        except Exception as e:
            self.log_display.setText(f"Error reading logs: {e}")

class BronxBotTray(QSystemTrayIcon):
    """System tray icon for BronxBot management"""
    
    def __init__(self):
        super().__init__()
        
        # Create tray icon using custom BronxBot icon
        self.set_tray_icon()
        self.setToolTip("BronxBot Discord Bot")
        
        # Create context menu
        self.menu = QMenu()
        self.create_menu()
        self.setContextMenu(self.menu)
        
        # Status monitoring thread
        self.status_thread = BotStatusThread()
        self.status_thread.status_updated.connect(self.update_status)
        self.status_thread.start()
        
        # Log window
        self.log_window = None
        
        # Current status
        self.current_status = {}
        
        # Show initial notification
        self.showMessage("BronxBot Tray", "BronxBot tray manager started", 
                        QSystemTrayIcon.Information, 3000)
    
    def create_menu(self):
        """Create the context menu"""
        # Status section
        self.status_action = QAction("Status: Checking...", self)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        
        self.stats_action = QAction("Stats: Loading...", self)
        self.stats_action.setEnabled(False)
        self.menu.addAction(self.stats_action)
        
        self.menu.addSeparator()
        
        # Control actions
        self.start_action = QAction("Start Bot", self)
        self.start_action.triggered.connect(self.start_bot)
        self.menu.addAction(self.start_action)
        
        self.stop_action = QAction("Stop Bot", self)
        self.stop_action.triggered.connect(self.stop_bot)
        self.menu.addAction(self.stop_action)
        
        self.restart_action = QAction("Restart Bot", self)
        self.restart_action.triggered.connect(self.restart_bot)
        self.menu.addAction(self.restart_action)
        
        self.menu.addSeparator()
        
        # Log actions with submenu
        logs_menu = self.menu.addMenu("View Logs")
        
        # Built-in log window
        view_logs_window_action = QAction("Built-in Log Window", self)
        view_logs_window_action.triggered.connect(self.show_logs)
        logs_menu.addAction(view_logs_window_action)
        
        # External terminal options
        logs_menu.addSeparator()
        
        view_logs_kitty_action = QAction("Open in Kitty Terminal", self)
        view_logs_kitty_action.triggered.connect(self.show_logs_kitty)
        logs_menu.addAction(view_logs_kitty_action)
        
        view_logs_kitty_clean_action = QAction("Open in Kitty (Clean Text)", self)
        view_logs_kitty_clean_action.triggered.connect(self.show_logs_kitty_clean)
        logs_menu.addAction(view_logs_kitty_clean_action)
        
        view_logs_terminal_action = QAction("Open in System Terminal", self)
        view_logs_terminal_action.triggered.connect(self.show_logs_terminal)
        logs_menu.addAction(view_logs_terminal_action)
        
        view_logs_follow_action = QAction("Follow Logs (tail -f)", self)
        view_logs_follow_action.triggered.connect(self.show_logs_follow)
        logs_menu.addAction(view_logs_follow_action)
        
        view_logs_follow_clean_action = QAction("Follow Logs (Clean Text)", self)
        view_logs_follow_clean_action.triggered.connect(self.show_logs_follow_clean)
        logs_menu.addAction(view_logs_follow_clean_action)
        
        self.menu.addSeparator()
        
        # Service management
        enable_service_action = QAction("Enable Auto-Start", self)
        enable_service_action.triggered.connect(self.enable_service)
        self.menu.addAction(enable_service_action)
        
        disable_service_action = QAction("Disable Auto-Start", self)
        disable_service_action.triggered.connect(self.disable_service)
        self.menu.addAction(disable_service_action)
        
        self.menu.addSeparator()
        
        # Exit
        exit_action = QAction("Exit Tray Manager", self)
        exit_action.triggered.connect(self.exit_application)
        self.menu.addAction(exit_action)
    
    def update_status(self, status):
        """Update the tray icon status"""
        self.current_status = status
        
        # Update status text and icon
        if status['bot_connected']:
            if status['latency'] > 0:
                status_text = f"Status: Online ({status['latency']}ms)"
            else:
                status_text = "Status: Online"
            self.set_tray_icon('online')
        elif status['service_active']:
            status_text = "Status: Starting..."
            self.set_tray_icon('starting')
        else:
            status_text = "Status: Offline"
            self.set_tray_icon('offline')
        
        self.status_action.setText(status_text)
        
        # Update stats with more detailed information
        if status['bot_connected'] and (status['guilds'] > 0 or status['users'] > 0):
            stats_text = f"Stats: {status['guilds']} guilds, {status['users']:,} users"
        elif status['service_active']:
            stats_text = f"Stats: {status['last_activity']}"
        else:
            stats_text = "Stats: Bot offline"
        
        self.stats_action.setText(stats_text)
        
        # Update tooltip with comprehensive information
        tooltip_parts = [f"BronxBot - {status_text}"]
        if status['bot_connected']:
            tooltip_parts.append(f"Servers: {status['guilds']}")
            tooltip_parts.append(f"Users: {status['users']:,}")
            if status['latency'] > 0:
                tooltip_parts.append(f"Latency: {status['latency']}ms")
        tooltip = "\n".join(tooltip_parts)
        self.setToolTip(tooltip)
        
        # Update menu item states
        self.start_action.setEnabled(not status['service_active'])
        self.stop_action.setEnabled(status['service_active'])
        self.restart_action.setEnabled(status['service_active'])
    
    def start_bot(self):
        """Start the bot service"""
        try:
            subprocess.run(['systemctl', '--user', 'start', 'bronxbot'], check=True)
            self.showMessage("BronxBot", "Bot service started", QSystemTrayIcon.Information)
        except subprocess.CalledProcessError as e:
            self.showMessage("BronxBot Error", f"Failed to start bot: {e}", QSystemTrayIcon.Critical)
    
    def stop_bot(self):
        """Stop the bot service"""
        try:
            subprocess.run(['systemctl', '--user', 'stop', 'bronxbot'], check=True)
            self.showMessage("BronxBot", "Bot service stopped", QSystemTrayIcon.Information)
        except subprocess.CalledProcessError as e:
            self.showMessage("BronxBot Error", f"Failed to stop bot: {e}", QSystemTrayIcon.Critical)
    
    def restart_bot(self):
        """Restart the bot service"""
        try:
            subprocess.run(['systemctl', '--user', 'restart', 'bronxbot'], check=True)
            self.showMessage("BronxBot", "Bot service restarted", QSystemTrayIcon.Information)
        except subprocess.CalledProcessError as e:
            self.showMessage("BronxBot Error", f"Failed to restart bot: {e}", QSystemTrayIcon.Critical)
    
    def show_logs(self):
        """Show the log window"""
        if self.log_window is None:
            self.log_window = BotLogWindow()
        
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()
        self.log_window.refresh_logs()
    
    def show_logs_kitty(self):
        """Open logs in Kitty terminal with colors"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.showMessage("BronxBot", "No log files found", QSystemTrayIcon.Warning)
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Check if kitty is available
            try:
                subprocess.run(['which', 'kitty'], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.showMessage("BronxBot Error", "Kitty terminal not found. Please install kitty or use another option.", QSystemTrayIcon.Critical)
                return
            
            # Open in kitty with less for better navigation, preserving colors
            subprocess.Popen([
                'kitty', '--title', 'BronxBot Logs (Colored)',
                'sh', '-c', f'less -R +G "{latest_log}"'
            ])
            
        except Exception as e:
            self.showMessage("BronxBot Error", f"Failed to open logs in Kitty: {e}", QSystemTrayIcon.Critical)
    
    def show_logs_kitty_clean(self):
        """Open logs in Kitty terminal with ANSI codes stripped"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.showMessage("BronxBot", "No log files found", QSystemTrayIcon.Warning)
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Check if kitty is available
            try:
                subprocess.run(['which', 'kitty'], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                self.showMessage("BronxBot Error", "Kitty terminal not found. Please install kitty or use another option.", QSystemTrayIcon.Critical)
                return
            
            # Open in kitty with sed to strip ANSI codes, then less
            subprocess.Popen([
                'kitty', '--title', 'BronxBot Logs (Clean)',
                'sh', '-c', f'sed "s/\\x1b\\[[0-9;]*m//g" "{latest_log}" | less +G'
            ])
            
        except Exception as e:
            self.showMessage("BronxBot Error", f"Failed to open clean logs in Kitty: {e}", QSystemTrayIcon.Critical)
    
    def show_logs_terminal(self):
        """Open logs in default system terminal"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.showMessage("BronxBot", "No log files found", QSystemTrayIcon.Warning)
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Try different terminal emulators in order of preference
            terminals = [
                ['gnome-terminal', '--title=BronxBot Logs', '--', 'sh', '-c', f'less -R +G "{latest_log}"; read -p "Press Enter to close..."'],
                ['konsole', '--title', 'BronxBot Logs', '-e', 'sh', '-c', f'less -R +G "{latest_log}"; read -p "Press Enter to close..."'],
                ['xfce4-terminal', '--title=BronxBot Logs', '--command', f'sh -c \'less -R +G "{latest_log}"; read -p "Press Enter to close..."\''],
                ['terminator', '--title=BronxBot Logs', '-x', 'sh', '-c', f'less -R +G "{latest_log}"; read -p "Press Enter to close..."'],
                ['xterm', '-title', 'BronxBot Logs', '-e', 'sh', '-c', f'less -R +G "{latest_log}"; read -p "Press Enter to close..."']
            ]
            
            terminal_opened = False
            for terminal_cmd in terminals:
                try:
                    subprocess.run(['which', terminal_cmd[0]], check=True, capture_output=True)
                    subprocess.Popen(terminal_cmd)
                    terminal_opened = True
                    break
                except subprocess.CalledProcessError:
                    continue
            
            if not terminal_opened:
                self.showMessage("BronxBot Error", "No supported terminal emulator found", QSystemTrayIcon.Critical)
                
        except Exception as e:
            self.showMessage("BronxBot Error", f"Failed to open logs in terminal: {e}", QSystemTrayIcon.Critical)
    
    def show_logs_follow(self):
        """Open logs with tail -f to follow in real-time"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.showMessage("BronxBot", "No log files found", QSystemTrayIcon.Warning)
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Try kitty first, then fall back to other terminals
            terminals = [
                ['kitty', '--title', 'BronxBot Logs (Live)', 'tail', '-f', str(latest_log)],
                ['gnome-terminal', '--title=BronxBot Logs (Live)', '--', 'tail', '-f', str(latest_log)],
                ['konsole', '--title', 'BronxBot Logs (Live)', '-e', 'tail', '-f', str(latest_log)],
                ['xfce4-terminal', '--title=BronxBot Logs (Live)', '--command', f'tail -f {latest_log}'],
                ['terminator', '--title=BronxBot Logs (Live)', '-x', 'tail', '-f', str(latest_log)],
                ['xterm', '-title', 'BronxBot Logs (Live)', '-e', 'tail', '-f', str(latest_log)]
            ]
            
            terminal_opened = False
            for terminal_cmd in terminals:
                try:
                    subprocess.run(['which', terminal_cmd[0]], check=True, capture_output=True)
                    subprocess.Popen(terminal_cmd)
                    terminal_opened = True
                    break
                except subprocess.CalledProcessError:
                    continue
            
            if not terminal_opened:
                self.showMessage("BronxBot Error", "No supported terminal emulator found", QSystemTrayIcon.Critical)
                
        except Exception as e:
            self.showMessage("BronxBot Error", f"Failed to open live logs: {e}", QSystemTrayIcon.Critical)
    
    def show_logs_follow_clean(self):
        """Open logs with tail -f to follow in real-time with clean text"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                self.showMessage("BronxBot", "No log files found", QSystemTrayIcon.Warning)
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Try kitty first, then fall back to other terminals
            terminals = [
                ['kitty', '--title', 'BronxBot Logs (Live Clean)', 'sh', '-c', f'tail -f "{latest_log}" | sed "s/\\x1b\\[[0-9;]*m//g"'],
                ['gnome-terminal', '--title=BronxBot Logs (Live Clean)', '--', 'sh', '-c', f'tail -f "{latest_log}" | sed "s/\\x1b\\[[0-9;]*m//g"'],
                ['konsole', '--title', 'BronxBot Logs (Live Clean)', '-e', 'sh', '-c', f'tail -f "{latest_log}" | sed "s/\\x1b\\[[0-9;]*m//g"'],
                ['xfce4-terminal', '--title=BronxBot Logs (Live Clean)', '--command', f'sh -c \'tail -f "{latest_log}" | sed "s/\\\\x1b\\\\[[0-9;]*m//g"\''],
                ['terminator', '--title=BronxBot Logs (Live Clean)', '-x', 'sh', '-c', f'tail -f "{latest_log}" | sed "s/\\x1b\\[[0-9;]*m//g"'],
                ['xterm', '-title', 'BronxBot Logs (Live Clean)', '-e', 'sh', '-c', f'tail -f "{latest_log}" | sed "s/\\x1b\\[[0-9;]*m//g"']
            ]
            
            terminal_opened = False
            for terminal_cmd in terminals:
                try:
                    subprocess.run(['which', terminal_cmd[0]], check=True, capture_output=True)
                    subprocess.Popen(terminal_cmd)
                    terminal_opened = True
                    break
                except subprocess.CalledProcessError:
                    continue
            
            if not terminal_opened:
                self.showMessage("BronxBot Error", "No supported terminal emulator found", QSystemTrayIcon.Critical)
                
        except Exception as e:
            self.showMessage("BronxBot Error", f"Failed to open live clean logs: {e}", QSystemTrayIcon.Critical)
    
    def enable_service(self):
        """Enable the bot service for auto-start"""
        try:
            subprocess.run(['systemctl', '--user', 'enable', 'bronxbot'], check=True)
            self.showMessage("BronxBot", "Auto-start enabled", QSystemTrayIcon.Information)
        except subprocess.CalledProcessError as e:
            self.showMessage("BronxBot Error", f"Failed to enable auto-start: {e}", QSystemTrayIcon.Critical)
    
    def disable_service(self):
        """Disable the bot service auto-start"""
        try:
            subprocess.run(['systemctl', '--user', 'disable', 'bronxbot'], check=True)
            self.showMessage("BronxBot", "Auto-start disabled", QSystemTrayIcon.Information)
        except subprocess.CalledProcessError as e:
            self.showMessage("BronxBot Error", f"Failed to disable auto-start: {e}", QSystemTrayIcon.Critical)
    
    def exit_application(self):
        """Exit the tray application"""
        if self.status_thread:
            self.status_thread.stop()
            self.status_thread.wait()
        
        if self.log_window:
            self.log_window.close()
        
        QApplication.quit()
    
    def set_tray_icon(self, status='normal'):
        """Set the tray icon based on status"""
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'data', 'images', 'bronx.png')
            
            if os.path.exists(icon_path):
                # Load the custom BronxBot icon
                pixmap = QPixmap(icon_path)
                
                # Resize to appropriate tray icon size (16x16 or 32x32)
                size = 24  # Good size for most system trays
                pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                # Apply status overlay if needed
                if status == 'offline':
                    # Add a red overlay for offline status
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setBrush(QBrush(QColor(255, 0, 0, 100)))  # Semi-transparent red
                    painter.setPen(QPen(QColor(255, 0, 0), 2))
                    painter.drawEllipse(pixmap.width() - 8, pixmap.height() - 8, 6, 6)
                    painter.end()
                elif status == 'starting':
                    # Add a yellow overlay for starting status
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setBrush(QBrush(QColor(255, 255, 0, 150)))  # Semi-transparent yellow
                    painter.setPen(QPen(QColor(255, 165, 0), 2))
                    painter.drawEllipse(pixmap.width() - 8, pixmap.height() - 8, 6, 6)
                    painter.end()
                elif status == 'online':
                    # Add a green overlay for online status
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    painter.setBrush(QBrush(QColor(0, 255, 0, 150)))  # Semi-transparent green
                    painter.setPen(QPen(QColor(0, 200, 0), 2))
                    painter.drawEllipse(pixmap.width() - 8, pixmap.height() - 8, 6, 6)
                    painter.end()
                
                self.setIcon(QIcon(pixmap))
                return True
                
            else:
                print(f"Warning: BronxBot icon not found at {icon_path}")
                raise FileNotFoundError("Icon file not found")
                
        except Exception as e:
            print(f"Warning: Could not set custom tray icon: {e}")
            # Fallback to system icons
            try:
                app = QApplication.instance()
                if app and status == 'online':
                    icon = app.style().standardIcon(QStyle.SP_DialogApplyButton)
                elif app and status == 'offline':
                    icon = app.style().standardIcon(QStyle.SP_DialogCancelButton) 
                elif app and status == 'starting':
                    icon = app.style().standardIcon(QStyle.SP_BrowserReload)
                else:
                    icon = app.style().standardIcon(QStyle.SP_ComputerIcon)
                self.setIcon(icon)
            except:
                # Ultimate fallback: create a simple colored square
                pixmap = QPixmap(16, 16)
                if status == 'online':
                    pixmap.fill(QColor(0, 255, 0))  # Green
                elif status == 'offline':
                    pixmap.fill(QColor(255, 0, 0))  # Red
                elif status == 'starting':
                    pixmap.fill(QColor(255, 255, 0))  # Yellow
                else:
                    pixmap.fill(QColor(128, 128, 128))  # Gray
                self.setIcon(QIcon(pixmap))
            return False
    
def main():
    """Main function"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running when windows are closed
    
    # Check for system tray support
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "System Tray", 
                           "System tray is not available on this system.")
        sys.exit(1)
    
    # Create and show tray icon
    tray = BronxBotTray()
    tray.show()
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
