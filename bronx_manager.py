#!/usr/bin/env python3
"""
bronx manager
async terminal interface for managing bronx services
"""

import asyncio
import subprocess
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Button, Footer, Header, Static, Log, DataTable, 
    ProgressBar, LoadingIndicator, Tabs, TabPane, Label
)
from textual.reactive import reactive
from textual.timer import Timer
from textual.screen import ModalScreen
from textual import events
from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live


class StatusWidget(Static):
    """Widget to display bot status"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status_data = {
            'service_active': False,
            'bot_connected': False,
            'guilds': 0,
            'users': 0,
            'latency': 0,
            'last_activity': 'Unknown'
        }
    
    def compose(self) -> ComposeResult:
        yield Static("bronx status", classes="status-title")
        yield Static("", id="status-content")
    
    async def update_status(self):
        """Update bot status"""
        try:
            # Check service status
            result = await asyncio.create_subprocess_exec(
                'systemctl', '--user', 'is-active', 'bronxbot',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            service_active = stdout.decode().strip() == 'active'
            
            self.status_data['service_active'] = service_active
            
            # Get detailed stats from logs if service is active
            if service_active:
                await self._parse_bot_stats()
            
            # Update display
            await self._render_status()
            
        except Exception as e:
            self.status_data['last_activity'] = f"Error: {e}"
            await self._render_status()
    
    async def _parse_bot_stats(self):
        """Parse bot statistics from logs"""
        try:
            # Get recent journal logs
            result = await asyncio.create_subprocess_exec(
                'journalctl', '--user', '-u', 'bronxbot', 
                '--since', '1 hour ago', '--no-pager',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                logs = stdout.decode().split('\n')
                
                for line in reversed(logs[-100:]):  # Check last 100 lines
                    if 'BOT READY' in line:
                        self.status_data['bot_connected'] = True
                    elif 'Events:' in line and 'Guilds:' in line:
                        # Parse stats line
                        import re
                        guilds_match = re.search(r'Guilds:\s*(\d+)', line)
                        users_match = re.search(r'Users:\s*(\d+)', line)
                        latency_match = re.search(r'Latency:\s*(\d+)ms', line)
                        
                        if guilds_match:
                            self.status_data['guilds'] = int(guilds_match.group(1))
                            self.status_data['bot_connected'] = True
                        if users_match:
                            self.status_data['users'] = int(users_match.group(1))
                        if latency_match:
                            self.status_data['latency'] = int(latency_match.group(1))
                        
                        if self.status_data['guilds'] > 0:
                            break
                            
        except Exception:
            pass
    
    async def _render_status(self):
        """Render the status display"""
        status = self.status_data
        
        # Create status content
        if status['bot_connected']:
            status_emoji = "ONLINE"
            status_text = "Online"
            if status['latency'] > 0:
                status_text += f" ({status['latency']}ms)"
        elif status['service_active']:
            status_emoji = "STARTING"
            status_text = "Starting..."
        else:
            status_emoji = "OFFLINE"
            status_text = "Offline"
        
        content = f"""
Status: [bold]{status_text}[/bold]
Servers: [cyan]{status['guilds']}[/cyan]
Users: [cyan]{status['users']:,}[/cyan]
Last Activity: {status['last_activity']}
        """.strip()
        
        content_widget = self.query_one("#status-content", Static)
        content_widget.update(content)


class LogViewer(Static):
    """Widget for viewing logs"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_log_size = 0
        self.last_modified = 0
    
    def compose(self) -> ComposeResult:
        yield Static("logs (live)", classes="log-title")
        yield Log(id="log-content", auto_scroll=True)
    
    async def refresh_logs(self):
        """Refresh log content only if file has changed"""
        try:
            log_files = list(Path('logs').glob('bronxbot_*.log'))
            if not log_files:
                return
            
            latest_log = max(log_files, key=os.path.getctime)
            
            # Check if file has been modified
            current_modified = latest_log.stat().st_mtime
            current_size = latest_log.stat().st_size
            
            if (current_modified == self.last_modified and 
                current_size == self.last_log_size):
                return  # No changes, skip update
            
            self.last_modified = current_modified
            self.last_log_size = current_size
            
            with open(latest_log, 'r') as f:
                lines = f.readlines()[-50:]  # Last 50 lines
            
            log_widget = self.query_one("#log-content", Log)
            log_widget.clear()
            
            # Strip ANSI codes and add to log
            import re
            ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
            for line in lines:
                clean_line = ansi_escape.sub('', line.rstrip())
                if clean_line:
                    log_widget.write_line(clean_line)
                    
        except Exception as e:
            log_widget = self.query_one("#log-content", Log)
            log_widget.write_line(f"Error reading logs: {e}")


class ScriptOutput(Static):
    """Widget for displaying script output"""
    
    def compose(self) -> ComposeResult:
        yield Static("output", classes="output-title")
        yield Log(id="script-output", auto_scroll=True)
    
    def add_output(self, text: str):
        """Add text to script output"""
        output_widget = self.query_one("#script-output", Log)
        for line in text.split('\n'):
            if line.strip():
                output_widget.write_line(line)
    
    def clear_output(self):
        """Clear script output"""
        output_widget = self.query_one("#script-output", Log)
        output_widget.clear()


class ServiceControls(Static):
    """Widget for service control buttons"""
    
    def compose(self) -> ComposeResult:
        yield Static("controls", classes="controls-title")
        with Horizontal(classes="controls-container"):
            with Vertical(classes="buttons-column"):
                with Horizontal(classes="control-buttons"):
                    yield Button("start", id="start-btn", variant="success")
                    yield Button("stop", id="stop-btn", variant="error") 
                    yield Button("restart", id="restart-btn", variant="warning")
                with Horizontal(classes="control-buttons"):
                    yield Button("status", id="status-btn")
                    yield Button("logs", id="logs-btn")
                    yield Button("setup", id="setup-btn")
                with Horizontal(classes="control-buttons"):
                    yield Button("tray", id="tray-btn", variant="primary")
                    yield Button("stop tray", id="stop-tray-btn", variant="error")
                    yield Button("uninstall", id="uninstall-btn", variant="error")
            with Container(classes="overview-column"):
                yield Static("hover over buttons for details", id="overview-text", classes="overview-text")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        app = self.app
        
        if button_id == "start-btn":
            app.run_script("start_bot.sh", "starting bronx service...")
        elif button_id == "stop-btn":
            app.run_script("stop_bot.sh", "stopping bronx service...")
        elif button_id == "restart-btn":
            app.run_script("start_bot.sh", "restarting bronx service...")
        elif button_id == "tray-btn":
            app.run_script("start_tray.sh", "starting system tray...")
        elif button_id == "stop-tray-btn":
            app.stop_tray_application()
        elif button_id == "status-btn":
            app.run_script("status_bot.sh", "checking bot status...")
        elif button_id == "logs-btn":
            app.run_script("logs_bot.sh", "opening logs...")
        elif button_id == "setup-btn":
            app.run_script("setup_background.sh", "running setup...")
        elif button_id == "uninstall-btn":
            app.show_confirmation("are you sure you want to uninstall?", "uninstall_background.sh")
    
    def on_enter(self, event: events.Enter) -> None:
        """Handle mouse enter events on buttons"""
        if (hasattr(event, 'control') and 
            event.control is not None and 
            hasattr(event.control, 'id') and 
            event.control.id is not None):
            button_id = event.control.id
            overview_text = self.query_one("#overview-text", Static)
            
            descriptions = {
                "start-btn": "Start the BronxBot Discord service",
                "stop-btn": "Stop the BronxBot Discord service",
                "restart-btn": "Restart the BronxBot Discord service",
                "status-btn": "Check the current status of the bot",
                "logs-btn": "View recent bot logs in terminal",
                "setup-btn": "Run initial setup and configuration",
                "tray-btn": "Start the system tray monitor",
                "stop-tray-btn": "Stop the system tray monitor",
                "uninstall-btn": "Remove BronxBot from the system"
            }
            
            if button_id in descriptions:
                overview_text.update(descriptions[button_id])
    
    def on_leave(self, event: events.Leave) -> None:
        """Handle mouse leave events"""
        if (hasattr(event, 'control') and 
            event.control is not None and 
            hasattr(event.control, 'id') and 
            event.control.id is not None and 
            event.control.id.endswith('-btn')):
            overview_text = self.query_one("#overview-text", Static)
            overview_text.update("hover over buttons for details")


class ConfirmationScreen(ModalScreen):
    """Confirmation dialog screen"""
    
    def __init__(self, message: str, script: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.script = script
    
    def compose(self) -> ComposeResult:
        with Container(id="confirmation-dialog"):
            yield Static(f"WARNING: {self.message}", id="confirmation-message")
            with Horizontal(id="confirmation-buttons"):
                yield Button("Yes", id="confirm-yes", variant="error")
                yield Button("No", id="confirm-no", variant="primary")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            if self.script.startswith("kill_process_"):
                # Extract PID and kill specific process
                pid = int(self.script.replace("kill_process_", ""))
                process_manager = self.app.query_one("#process-manager", ProcessManager)
                self.app.call_later(process_manager.kill_process, pid)
            elif self.script == "kill_all_bronx_processes":
                # Kill all processes
                process_manager = self.app.query_one("#process-manager", ProcessManager)
                self.app.call_later(process_manager.kill_all_processes)
            else:
                # Regular script execution
                self.app.run_script(self.script, f"Running {self.script}...")
        self.dismiss()


class ProcessManager(Static):
    """Widget for managing BronxBot processes"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.processes = []
    
    def compose(self) -> ComposeResult:
        yield Static("process manager", classes="process-title")
        yield DataTable(id="process-table", show_header=True, zebra_stripes=True)
        with Horizontal(classes="process-buttons"):
            yield Button("refresh", id="refresh-processes-btn", variant="primary")
            yield Button("kill selected", id="kill-process-btn", variant="error")
            yield Button("kill all", id="kill-all-btn", variant="error")
    
    async def refresh_processes(self):
        """Refresh the process list"""
        try:
            # Get BronxBot related processes
            process_data = await self._get_bronx_processes()
            
            # Update the data table
            table = self.query_one("#process-table", DataTable)
            table.clear(columns=True)
            
            # Add columns
            table.add_columns("PID", "Command", "CPU%", "Memory", "Status", "Runtime")
            
            # Add process data
            for proc in process_data:
                table.add_row(
                    str(proc['pid']),
                    proc['command'][:50] + "..." if len(proc['command']) > 50 else proc['command'],
                    f"{proc['cpu']:.1f}%",
                    proc['memory'],
                    proc['status'],
                    proc['runtime']
                )
            
            self.processes = process_data
            
        except Exception as e:
            # Show error in table
            table = self.query_one("#process-table", DataTable)
            table.clear(columns=True)
            table.add_columns("Error", "", "", "", "", "")
            table.add_row(f"Failed to get processes: {e}", "", "", "", "", "")
    
    async def _get_bronx_processes(self):
        """Get BronxBot related processes"""
        processes = []
        
        try:
            # Use ps to get detailed process information
            result = await asyncio.create_subprocess_exec(
                'ps', 'aux',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                lines = stdout.decode().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    # Check if line contains bronx-related processes
                    if any(keyword in line.lower() for keyword in ['bronx', 'tray']):
                        parts = line.split(None, 10)
                        if len(parts) >= 11:
                            try:
                                processes.append({
                                    'user': parts[0],
                                    'pid': int(parts[1]),
                                    'cpu': float(parts[2]),
                                    'memory': parts[3] + "MB",
                                    'status': parts[7],
                                    'runtime': parts[9],
                                    'command': parts[10]
                                })
                            except (ValueError, IndexError):
                                continue
            
            # Also check systemd service
            try:
                systemd_result = await asyncio.create_subprocess_exec(
                    'systemctl', '--user', 'show', 'bronxbot', '--property=MainPID,ActiveState,SubState',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                systemd_stdout, _ = await systemd_result.communicate()
                
                if systemd_result.returncode == 0:
                    systemd_info = {}
                    for line in systemd_stdout.decode().split('\n'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            systemd_info[key] = value
                    
                    if systemd_info.get('MainPID', '0') != '0':
                        # Add systemd service info
                        processes.append({
                            'user': 'systemd',
                            'pid': int(systemd_info.get('MainPID', 0)),
                            'cpu': 0.0,
                            'memory': "N/A",
                            'status': f"{systemd_info.get('ActiveState', 'unknown')}/{systemd_info.get('SubState', 'unknown')}",
                            'runtime': "N/A",
                            'command': "bronxbot.service (systemd)"
                        })
            except:
                pass
                
        except Exception as e:
            print(f"Error getting processes: {e}")
        
        return processes
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle process manager button presses"""
        button_id = event.button.id
        app = self.app
        
        if button_id == "refresh-processes-btn":
            app.call_later(self.refresh_processes)
            app.update_footer_status("Refreshing processes...")
        elif button_id == "kill-process-btn":
            table = self.query_one("#process-table", DataTable)
            if table.cursor_row is not None and table.cursor_row < len(self.processes):
                selected_process = self.processes[table.cursor_row]
                app.show_confirmation(
                    f"kill process {selected_process['pid']} ({selected_process['command'][:30]}...)?",
                    f"kill_process_{selected_process['pid']}"
                )
        elif button_id == "kill-all-btn":
            if self.processes:
                app.show_confirmation(
                    f"kill all {len(self.processes)} BronxBot processes?",
                    "kill_all_bronx_processes"
                )
    
    async def kill_process(self, pid: int):
        """Kill a specific process"""
        try:
            result = await asyncio.create_subprocess_exec(
                'kill', '-TERM', str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.wait()
            
            if result.returncode == 0:
                self.app.update_footer_status(f"Process {pid} terminated")
            else:
                # Try force kill
                force_result = await asyncio.create_subprocess_exec(
                    'kill', '-KILL', str(pid),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await force_result.wait()
                self.app.update_footer_status(f"Process {pid} force killed")
            
            # Refresh process list
            await asyncio.sleep(1)
            await self.refresh_processes()
            
        except Exception as e:
            self.app.update_footer_status(f"Failed to kill process {pid}: {e}")
    
    async def kill_all_processes(self):
        """Kill all BronxBot processes"""
        killed_count = 0
        
        for proc in self.processes:
            try:
                if proc['user'] != 'systemd':  # Don't kill systemd service directly
                    await self.kill_process(proc['pid'])
                    killed_count += 1
                else:
                    # Stop systemd service properly
                    result = await asyncio.create_subprocess_exec(
                        'systemctl', '--user', 'stop', 'bronxbot',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.wait()
                    killed_count += 1
            except:
                continue
        
        self.app.update_footer_status(f"Stopped {killed_count} processes")
        await asyncio.sleep(2)
        await self.refresh_processes()


class BronxManager(App):
    """Main application class"""
    
    CSS = """
    Screen {
        background: $background;
    }
    
    .status-title, .log-title, .controls-title, .output-title, .process-title {
        color: $accent;
        text-style: bold;
        margin: 1;
    }
    
    #status-content {
        border: solid $primary;
        padding: 1;
        margin: 1 0;
        height: 8;
    }
    
    #process-table {
        border: solid $primary;
        height: 12;
        margin: 1 0;
    }
    
    .process-buttons {
        margin: 1 0;
        height: 3;
    }
    
    .process-buttons > Button {
        margin: 0 1;
        min-width: 12;
    }
    
    #log-content, #script-output {
        border: solid $primary;
        height: 35;
        margin: 1 0;
        overflow: auto auto;
    }
    
    #log-viewer {
        width: 35%;
    }
    
    #script-output {
        width: 65%;
    }
    
    .controls-container {
        height: 12;
        margin: 1 0;
    }
    
    .buttons-column {
        width: 60%;
        margin-right: 2;
    }
    
    .overview-column {
        width: 40%;
        border: solid $secondary;
        padding: 1;
        height: 10;
    }
    
    .overview-text {
        text-align: center;
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }
    
    .control-buttons {
        margin: 1 0;
        height: 3;
    }
    
    .control-buttons > Button {
        margin: 0 1;
        min-width: 12;
    }
    
    #confirmation-dialog {
        width: 60;
        height: 10;
        border: solid $error;
        background: $surface;
        padding: 2;
    }
    
    #confirmation-message {
        text-align: center;
        margin: 1 0;
    }
    
    #confirmation-buttons {
        align: center middle;
        margin: 1 0;
    }
    
    #confirmation-buttons > Button {
        margin: 0 2;
    }
    
    #footer-status {
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("s", "toggle_status", "Status"),
        ("l", "toggle_logs", "Logs"),
        ("ctrl+c", "quit", "Quit"),
    ]
    
    current_operation: reactive[str] = reactive("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scripts_dir = Path("scripts")
        self.status_timer: Optional[Timer] = None
        self.log_timer: Optional[Timer] = None
        self.process_timer: Optional[Timer] = None
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with ScrollableContainer():
            with Vertical():
                yield StatusWidget(id="status-widget")
                yield ServiceControls(id="service-controls")
                with Horizontal():
                    yield LogViewer(id="log-viewer")
                    yield ScriptOutput(id="script-output")
                yield ProcessManager(id="process-manager")
        yield Footer()
        yield Static("ready", id="footer-status")
    
    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "bronx manager"
        self.sub_title = "terminal interface"
        
        # Start periodic status updates
        self.status_timer = self.set_interval(3.0, self.update_status)
        
        # Start periodic log updates (every 2 seconds)
        self.log_timer = self.set_interval(2.0, self.refresh_logs)
        
        # Start periodic process updates (every 5 seconds)
        self.process_timer = self.set_interval(5.0, self.refresh_processes)
        
        # Initial status update
        self.call_later(self.update_status)
        
        # Initial log refresh
        self.call_later(self.refresh_logs)
        
        # Initial process refresh
        self.call_later(self.refresh_processes)
    
    async def update_status(self):
        """Update bot status"""
        status_widget = self.query_one("#status-widget", StatusWidget)
        await status_widget.update_status()
    
    async def refresh_logs(self):
        """Refresh log display"""
        log_viewer = self.query_one("#log-viewer", LogViewer)
        old_size = log_viewer.last_log_size
        await log_viewer.refresh_logs()
        
        # Only show update message if logs actually changed
        if log_viewer.last_log_size != old_size:
            timestamp = datetime.now().strftime("%H:%M:%S")
            footer_status = self.query_one("#footer-status", Static)
            footer_status.update(f"[{timestamp}] logs updated")
            # Clear this status after 2 seconds
            self.set_timer(2.0, lambda: footer_status.update(f"[{timestamp}] ready | logs live"))
    
    def action_refresh(self) -> None:
        """Refresh all data"""
        self.update_footer_status("refreshing...")
        self.call_later(self.update_status)
        self.call_later(self.refresh_logs)
        self.call_later(lambda: self.update_footer_status("refreshed!"))
    
    def action_toggle_status(self) -> None:
        """Toggle status display"""
        status_widget = self.query_one("#status-widget")
        status_widget.display = not status_widget.display
    
    def action_toggle_logs(self) -> None:
        """Toggle log display"""
        log_viewer = self.query_one("#log-viewer")
        log_viewer.display = not log_viewer.display
    
    def show_confirmation(self, message: str, script: str) -> None:
        """Show confirmation dialog"""
        self.push_screen(ConfirmationScreen(message, script))
    
    def run_script(self, script_name: str, message: str) -> None:
        """Run a script asynchronously"""
        self.update_footer_status(message)
        self.call_later(self._execute_script, script_name)
    
    def stop_tray_application(self) -> None:
        """Stop the tray application"""
        self.update_footer_status("Stopping tray application...")
        self.call_later(self._stop_tray_async)
    
    async def _stop_tray_async(self) -> None:
        """Stop tray application asynchronously"""
        try:
            script_output = self.query_one("#script-output", ScriptOutput)
            script_output.clear_output()
            script_output.add_output("Stopping tray application...")
            script_output.add_output("=" * 50)
            
            # Check if tray is running
            check_process = await asyncio.create_subprocess_exec(
                "pgrep", "-f", "bronxbot_tray.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await check_process.wait()
            
            if check_process.returncode != 0:
                script_output.add_output("Tray application is not running")
                self.update_footer_status("Tray not running")
                return
            
            # Stop the tray application
            stop_process = await asyncio.create_subprocess_exec(
                "pkill", "-f", "bronxbot_tray.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await stop_process.wait()
            
            if stop_process.returncode == 0:
                script_output.add_output("SUCCESS: Tray application stopped")
                self.update_footer_status("Tray stopped")
            else:
                script_output.add_output("WARNING: Tray may still be running")
                self.update_footer_status("Tray stop uncertain")
                
        except Exception as e:
            script_output = self.query_one("#script-output", ScriptOutput)
            script_output.add_output(f"ERROR: Failed to stop tray: {e}")
            self.update_footer_status("Tray stop failed")
    
    async def _execute_script(self, script_name: str) -> None:
        """Execute script and handle output"""
        try:
            script_path = self.scripts_dir / script_name
            
            if not script_path.exists():
                self.update_footer_status(f"Script not found: {script_name}")
                return
            
            # Get script output widget
            script_output = self.query_one("#script-output", ScriptOutput)
            script_output.clear_output()
            script_output.add_output(f"Running {script_name}...")
            script_output.add_output("=" * 50)
            
            # Special handling for tray script (GUI application)
            if script_name == "start_tray.sh":
                await self._execute_tray_script(script_path, script_output)
                return
            
            # Run regular script with real-time output
            process = await asyncio.create_subprocess_exec(
                "bash", str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # Combine stderr with stdout
                cwd=str(Path.cwd())
            )
            
            # Read output line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_text = line.decode().rstrip()
                if line_text:
                    script_output.add_output(line_text)
            
            await process.wait()
            
            if process.returncode == 0:
                script_output.add_output("=" * 50)
                script_output.add_output(f"SUCCESS: {script_name} completed")
                self.update_footer_status(f"SUCCESS: {script_name} completed")
                # Refresh status after operation
                await asyncio.sleep(1)
                await self.update_status()
                await self.refresh_logs()
            else:
                script_output.add_output("=" * 50)
                script_output.add_output(f"ERROR: {script_name} failed with code {process.returncode}")
                self.update_footer_status(f"ERROR: {script_name} failed")
                
        except Exception as e:
            script_output = self.query_one("#script-output", ScriptOutput)
            script_output.add_output(f"EXCEPTION: Error running {script_name}: {e}")
            self.update_footer_status(f"ERROR: {script_name} exception")
    
    async def _execute_tray_script(self, script_path: Path, script_output) -> None:
        """Execute tray script in background without blocking"""
        try:
            # Check if tray is already running
            check_process = await asyncio.create_subprocess_exec(
                "pgrep", "-f", "bronxbot_tray.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await check_process.wait()
            
            if check_process.returncode == 0:
                script_output.add_output("Tray application is already running")
                script_output.add_output("Use 'pkill -f bronxbot_tray.py' to stop it first")
                self.update_footer_status("Tray already running")
                return
            
            # Start tray in background using nohup
            script_output.add_output("Starting tray application in background...")
            
            # Use nohup to run the tray script detached from this process
            process = await asyncio.create_subprocess_exec(
                "nohup", "bash", str(script_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=str(Path.cwd())
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Check if it started successfully
            check_process = await asyncio.create_subprocess_exec(
                "pgrep", "-f", "bronxbot_tray.py",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await check_process.wait()
            
            if check_process.returncode == 0:
                script_output.add_output("SUCCESS: Tray application started in background")
                script_output.add_output("Check your system tray for the BronxBot icon")
                script_output.add_output("To stop: pkill -f bronxbot_tray.py")
                self.update_footer_status("Tray started successfully")
            else:
                script_output.add_output("WARNING: Tray may not have started properly")
                script_output.add_output("Check if PyQt5 is installed and X11/Wayland is available")
                self.update_footer_status("Tray start uncertain")
                
        except Exception as e:
            script_output.add_output(f"ERROR: Failed to start tray: {e}")
            self.update_footer_status("Tray start failed")
    
    def update_footer_status(self, message: str) -> None:
        """Update footer status message"""
        footer_status = self.query_one("#footer-status", Static)
        timestamp = datetime.now().strftime("%H:%M:%S")
        footer_status.update(f"[{timestamp}] {message}")
        
        # Auto-clear status after 5 seconds
        self.set_timer(5.0, lambda: footer_status.update("ready"))
    
    def on_unmount(self) -> None:
        """Cleanup when app closes"""
        if self.status_timer:
            self.status_timer.stop()
        if self.log_timer:
            self.log_timer.stop()
        if self.process_timer:
            self.process_timer.stop()
    
    async def refresh_processes(self):
        """Refresh process display"""
        process_manager = self.query_one("#process-manager", ProcessManager)
        await process_manager.refresh_processes()


def main():
    """main entry point"""
    # Check if we're in the right directory
    if not Path("bronxbot.py").exists():
        print("error: please run this from the bronxbot directory")
        return 1
    
    # Check if scripts directory exists
    if not Path("scripts").exists():
        print("error: scripts directory not found. please run setup first.")
        return 1
    
    # Run the app
    app = BronxManager()
    app.run()
    return 0


if __name__ == "__main__":
    exit(main())
