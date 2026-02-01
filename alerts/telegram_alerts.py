"""
Telegram Alerts

Strategy-specific alerts with entry/exit notifications,
P&L tracking, and risk warnings.
"""

import requests
from datetime import datetime
from typing import Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class TelegramAlerts:
    """
    Telegram notification system for sports trading bot.
    
    Alert Types:
    - Strategy signals (entry opportunities)
    - Trade executions (entry/exit)
    - Risk warnings
    - Performance summaries
    """
    
    def __init__(self):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            print("✅ Telegram alerts enabled")
        else:
            print("⚪ Telegram not configured - alerts disabled")
    
    def send(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send message to Telegram.
        
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"⚠️ Telegram error: {e}")
            return False
    
    def alert_signal(self, signal: Dict) -> bool:
        """
        Send alert for a trading signal.
        
        Args:
            signal: TradeSignal dict from strategy
        """
        if not Config.ALERT_ON_SIGNAL:
            return False
        
        strategy = signal.get('strategy', 'Unknown')
        direction = signal.get('signal_type', 'BUY')
        sport = signal.get('sport', 'unknown').upper()
        question = signal.get('market_question', 'Unknown market')
        confidence = signal.get('confidence', 0) * 100
        entry_price = signal.get('entry_price', 0)
        target = signal.get('target_price', 0)
        stop = signal.get('stop_loss_price', 0)
        rationale = signal.get('rationale', '')
        
        # Calculate expected profit
        if direction == 'BUY':
            expected_profit = ((target - entry_price) / entry_price) * 100
        else:
            expected_profit = ((entry_price - target) / entry_price) * 100
        
        # Direction emoji
        dir_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Sport emoji
        sport_emoji = {
            'FOOTBALL': '⚽',
            'NBA': '🏀',
            'CRICKET': '🏏',
            'TENNIS': '🎾',
            'UFC': '🥊'
        }.get(sport, '🎯')
        
        message = f"""
{dir_emoji} <b>{strategy.upper()} SIGNAL</b>

{sport_emoji} <b>{sport}</b>
📊 {question[:80]}{'...' if len(question) > 80 else ''}

🔥 <b>ACTION:</b> {direction} @ <code>${entry_price:.4f}</code>
🎯 <b>Target:</b> ${target:.4f} (+{expected_profit:.1f}%)
🛑 <b>Stop:</b> ${stop:.4f}

💪 <b>Confidence:</b> {confidence:.0f}%
📐 <b>Strategy:</b> {rationale}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self.send(message.strip())
    
    def alert_trade_opened(self, trade: Dict) -> bool:
        """Send alert when trade is executed."""
        if not Config.ALERT_ON_ENTRY:
            return False
        
        strategy = trade.get('strategy', 'Unknown')
        direction = trade.get('direction', 'BUY')
        sport = trade.get('sport', 'unknown').upper()
        question = trade.get('market_question', 'Unknown')
        size = trade.get('size_usd', 0)
        entry_price = trade.get('entry_price', 0)
        confidence = trade.get('confidence', 0) * 100
        
        message = f"""
✅ <b>TRADE OPENED</b>

📈 <b>{strategy}</b> | {sport}
📊 {question[:60]}...

💰 <b>Size:</b> ${size:.2f}
📍 <b>Entry:</b> ${entry_price:.4f}
💪 <b>Confidence:</b> {confidence:.0f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self.send(message.strip())
    
    def alert_trade_closed(self, trade: Dict) -> bool:
        """Send alert when trade is closed."""
        if not Config.ALERT_ON_EXIT:
            return False
        
        strategy = trade.get('strategy', 'Unknown')
        pnl = trade.get('pnl', 0)
        pnl_percent = trade.get('pnl_percent', 0)
        exit_reason = trade.get('exit_reason', 'Unknown')
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        
        # Calculate hold time
        try:
            entry_time = datetime.fromisoformat(trade.get('entry_time', ''))
            exit_time = datetime.fromisoformat(trade.get('exit_time', ''))
            hold_minutes = (exit_time - entry_time).seconds // 60
        except:
            hold_minutes = 0
        
        # Result emoji
        result_emoji = "🟢" if pnl > 0 else "🔴"
        result_text = "WIN" if pnl > 0 else "LOSS"
        
        message = f"""
{result_emoji} <b>TRADE CLOSED - {result_text}</b>

📈 <b>{strategy}</b>
📊 <b>P&L:</b> ${pnl:+.2f} ({pnl_percent:+.1f}%)

📍 Entry: ${entry_price:.4f}
📍 Exit: ${exit_price:.4f}
⏱️ Hold: {hold_minutes} minutes

📐 <b>Reason:</b> {exit_reason}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        return self.send(message.strip())
    
    def alert_risk_warning(self, warning_type: str, details: Dict) -> bool:
        """Send risk warning alert."""
        
        if warning_type == 'kill_switch':
            message = f"""
🚨 <b>KILL SWITCH ACTIVATED</b>

Daily loss limit reached!
Loss: ${abs(details.get('daily_pnl', 0)):.2f}
Limit: ${details.get('limit', 100):.2f}

Trading suspended until reset.
"""
        
        elif warning_type == 'loss_streak':
            message = f"""
⚠️ <b>LOSS STREAK WARNING</b>

Consecutive losses: {details.get('streak', 0)}
Trading paused for 1 hour.

Last loss: ${abs(details.get('last_pnl', 0)):.2f}
"""
        
        elif warning_type == 'low_balance':
            message = f"""
⚠️ <b>LOW BALANCE WARNING</b>

Balance: ${details.get('balance', 0):.2f}
Minimum recommended: $100

Consider reducing position sizes.
"""
        
        else:
            message = f"""
⚠️ <b>RISK WARNING</b>

{warning_type}: {details}
"""
        
        return self.send(message.strip())
    
    def alert_summary(self, stats: Dict) -> bool:
        """Send periodic performance summary."""
        
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        win_rate = stats.get('win_rate', 0) * 100
        total_pnl = stats.get('total_pnl', 0)
        balance = stats.get('balance', 0)
        equity = stats.get('equity', 0)
        return_pct = stats.get('return_percent', 0)
        open_positions = stats.get('open_positions', 0)
        
        # Trend emoji
        trend_emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
        
        message = f"""
📊 <b>PERFORMANCE SUMMARY</b>

💰 <b>Balance:</b> ${balance:.2f}
📈 <b>Equity:</b> ${equity:.2f}
{trend_emoji} <b>Return:</b> {return_pct:+.1f}%

📋 <b>Trades:</b> {total_trades} ({wins}W / {losses}L)
🎯 <b>Win Rate:</b> {win_rate:.0f}%
💵 <b>Total P&L:</b> ${total_pnl:+.2f}

📂 <b>Open Positions:</b> {open_positions}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        return self.send(message.strip())
    
    def alert_bot_status(self, status: str, details: Optional[Dict] = None) -> bool:
        """Send bot status update."""
        
        if status == 'started':
            enabled_strategies = Config.get_enabled_strategies()
            
            message = f"""
🤖 <b>SPORTS BOT STARTED</b>

📊 Mode: {'PAPER' if Config.is_paper_mode() else 'LIVE'} TRADING
💰 Balance: ${Config.STARTING_BALANCE:,.2f}

🎯 <b>Enabled Strategies:</b>
{chr(10).join(f"  • {s.replace('_', ' ').title()}" for s in enabled_strategies)}

🛡️ <b>Risk Limits:</b>
  • Max position: ${Config.MAX_POSITION_USD}
  • Max daily loss: ${Config.MAX_DAILY_LOSS_USD}
  • Max positions: {Config.MAX_OPEN_POSITIONS}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        elif status == 'stopped':
            message = f"""
🛑 <b>BOT STOPPED</b>

Reason: {details.get('reason', 'Manual shutdown') if details else 'Manual shutdown'}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        elif status == 'error':
            message = f"""
❌ <b>BOT ERROR</b>

Error: {details.get('error', 'Unknown') if details else 'Unknown'}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        else:
            message = f"ℹ️ Bot status: {status}"
        
        return self.send(message.strip())
    
    def test_connection(self) -> bool:
        """Test Telegram connection."""
        return self.send("✅ Sports Polymarket Bot connected!")
