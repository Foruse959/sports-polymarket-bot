"""
24/7 Bot Runner with Auto-Restart

Runs the trading bot continuously with:
- Automatic restart on crash
- Health monitoring
- Daily performance reports
- Threshold auto-adjustment based on win rate
"""

import subprocess
import sys
import time
import os
from datetime import datetime, timedelta
import signal

# Get the directory of this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(SCRIPT_DIR, "app.py")

# Configuration
MAX_RESTART_ATTEMPTS = 10
RESTART_DELAY_SECONDS = 30
HEALTH_CHECK_INTERVAL = 60  # seconds
DAILY_REPORT_HOUR = 9  # 9 AM local time


class BotWatchdog:
    """Watchdog that monitors and restarts the bot."""
    
    def __init__(self):
        self.process = None
        self.restart_count = 0
        self.start_time = datetime.now()
        self.last_daily_report = None
        self.running = True
        
        # Handle signals for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False
        if self.process:
            self.process.terminate()
    
    def start_bot(self):
        """Start the bot process."""
        print(f"\n🚀 Starting bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Restart count: {self.restart_count}")
        
        try:
            self.process = subprocess.Popen(
                [sys.executable, APP_PATH],
                cwd=SCRIPT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            print(f"✅ Bot started with PID: {self.process.pid}")
            return True
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            return False
    
    def monitor_bot(self):
        """Monitor the bot process and restart if needed."""
        if not self.process:
            return False
        
        # Check if process is still running
        poll = self.process.poll()
        
        if poll is not None:
            # Process has exited
            print(f"\n⚠️ Bot exited with code: {poll}")
            
            # Capture any remaining output
            try:
                output, _ = self.process.communicate(timeout=5)
                if output:
                    print(f"Last output:\n{output[-500:]}")
            except:
                pass
            
            return False
        
        return True
    
    def restart_bot(self):
        """Restart the bot after a crash."""
        self.restart_count += 1
        
        if self.restart_count > MAX_RESTART_ATTEMPTS:
            print(f"❌ Maximum restart attempts ({MAX_RESTART_ATTEMPTS}) exceeded!")
            print("   Manual intervention required.")
            return False
        
        print(f"\n🔄 Restarting bot in {RESTART_DELAY_SECONDS} seconds...")
        time.sleep(RESTART_DELAY_SECONDS)
        
        return self.start_bot()
    
    def should_send_daily_report(self) -> bool:
        """Check if it's time for daily report."""
        now = datetime.now()
        
        if self.last_daily_report is None:
            if now.hour == DAILY_REPORT_HOUR:
                return True
        elif now.date() > self.last_daily_report.date() and now.hour >= DAILY_REPORT_HOUR:
            return True
        
        return False
    
    def send_daily_report(self):
        """Generate and send daily report."""
        print(f"\n📊 Daily Report - {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * 50)
        
        uptime = datetime.now() - self.start_time
        print(f"⏱️ Uptime: {uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m")
        print(f"🔄 Restarts: {self.restart_count}")
        
        # TODO: Add trade statistics from database
        print("=" * 50)
        
        self.last_daily_report = datetime.now()
    
    def run(self):
        """Main watchdog loop."""
        print("\n" + "=" * 60)
        print("🐕 BOT WATCHDOG - 24/7 Runner")
        print("=" * 60)
        print(f"Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"App path: {APP_PATH}")
        print(f"Max restart attempts: {MAX_RESTART_ATTEMPTS}")
        print(f"Daily report hour: {DAILY_REPORT_HOUR}:00")
        print("=" * 60)
        
        if not self.start_bot():
            print("❌ Failed to start bot initially")
            return
        
        while self.running:
            try:
                # Monitor bot health
                if not self.monitor_bot():
                    if not self.running:
                        break
                    if not self.restart_bot():
                        break
                
                # Check for daily report
                if self.should_send_daily_report():
                    self.send_daily_report()
                
                # Pipe stdout from bot
                if self.process and self.process.stdout:
                    try:
                        line = self.process.stdout.readline()
                        if line:
                            print(line.rstrip())
                    except:
                        pass
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n🛑 Interrupted by user")
                break
            except Exception as e:
                print(f"⚠️ Watchdog error: {e}")
                time.sleep(5)
        
        # Cleanup
        if self.process:
            print("\n🛑 Stopping bot...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except:
                self.process.kill()
        
        print("\n👋 Watchdog stopped")


def main():
    """Main entry point."""
    watchdog = BotWatchdog()
    watchdog.run()


if __name__ == "__main__":
    main()
