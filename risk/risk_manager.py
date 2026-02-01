"""
Risk Manager

Comprehensive risk controls including exposure caps, kill switches,
and position limits to protect capital.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class RiskManager:
    """
    Risk management system with multiple protection layers.
    
    Controls:
    - Position size limits
    - Daily loss limits (kill switch)
    - Open position limits
    - Trade frequency limits
    - Loss streak detection
    - Correlation/concentration limits
    """
    
    def __init__(self):
        self.daily_pnl = 0.0
        self.hourly_trades = 0
        self.last_hour_reset = datetime.now()
        self.loss_streak = 0
        self.pause_until = None
        self.positions_by_event = {}  # event_id -> count
        self.trade_history = []  # Recent trades for analysis
        
        print("✅ Risk Manager initialized")
        print(f"   • Max position: ${Config.MAX_POSITION_USD}")
        print(f"   • Max daily loss: ${Config.MAX_DAILY_LOSS_USD}")
        print(f"   • Max open positions: {Config.MAX_OPEN_POSITIONS}")
    
    def can_trade(self, signal: Dict, current_positions: List[Dict]) -> Tuple[bool, str]:
        """
        Check if a trade is allowed under current risk constraints.
        
        Args:
            signal: Trade signal from strategy
            current_positions: List of current open positions
            
        Returns:
            (can_trade, rejection_reason)
        """
        # Check kill switch
        if self._is_killed():
            return False, f"Kill switch active: Daily loss ${abs(self.daily_pnl):.2f} exceeds limit"
        
        # Check pause (loss streak)
        if self._is_paused():
            remaining = (self.pause_until - datetime.now()).seconds // 60
            return False, f"Paused for {remaining} more minutes due to loss streak"
        
        # Check position count
        if len(current_positions) >= Config.MAX_OPEN_POSITIONS:
            return False, f"Max positions ({Config.MAX_OPEN_POSITIONS}) reached"
        
        # Check hourly trade limit
        if not self._check_hourly_limit():
            return False, f"Hourly trade limit ({Config.MAX_HOURLY_TRADES}) reached"
        
        # Check event concentration
        event_id = signal.get('metadata', {}).get('game_id', signal.get('market_id'))
        if event_id and not self._check_event_concentration(event_id):
            return False, f"Max positions per event ({Config.MAX_POSITIONS_PER_EVENT}) reached"
        
        # Check position size
        size = signal.get('size_usd', 0)
        if size > Config.MAX_POSITION_USD:
            return False, f"Position size ${size:.2f} exceeds max ${Config.MAX_POSITION_USD}"
        
        # Check if signal confidence is high enough
        confidence = signal.get('confidence', 0)
        if confidence < 0.5:
            return False, f"Confidence {confidence:.0%} below minimum 50%"
        
        return True, "Trade approved"
    
    def _is_killed(self) -> bool:
        """Check if kill switch is active due to daily loss limit."""
        return self.daily_pnl <= -Config.MAX_DAILY_LOSS_USD
    
    def _is_paused(self) -> bool:
        """Check if trading is paused due to loss streak."""
        if self.pause_until is None:
            return False
        return datetime.now() < self.pause_until
    
    def _check_hourly_limit(self) -> bool:
        """Check if hourly trade limit is reached, reset if hour passed."""
        now = datetime.now()
        
        if (now - self.last_hour_reset).seconds >= 3600:
            self.hourly_trades = 0
            self.last_hour_reset = now
        
        return self.hourly_trades < Config.MAX_HOURLY_TRADES
    
    def _check_event_concentration(self, event_id: str) -> bool:
        """Check if too many positions on same event."""
        current_count = self.positions_by_event.get(event_id, 0)
        return current_count < Config.MAX_POSITIONS_PER_EVENT
    
    def record_trade_opened(self, trade: Dict):
        """Record a new trade opening."""
        self.hourly_trades += 1
        
        event_id = trade.get('metadata', {}).get('game_id', trade.get('market_id'))
        if event_id:
            self.positions_by_event[event_id] = self.positions_by_event.get(event_id, 0) + 1
    
    def record_trade_closed(self, trade: Dict, pnl: float):
        """Record a trade closing and update risk metrics."""
        # Update daily P&L
        self.daily_pnl += pnl
        
        # Update event concentration
        event_id = trade.get('metadata', {}).get('game_id', trade.get('market_id'))
        if event_id and event_id in self.positions_by_event:
            self.positions_by_event[event_id] = max(0, self.positions_by_event[event_id] - 1)
        
        # Track win/loss streak
        if pnl < 0:
            self.loss_streak += 1
            
            # Pause if loss streak limit reached
            if self.loss_streak >= Config.LOSS_STREAK_PAUSE_LIMIT:
                self.pause_until = datetime.now() + timedelta(hours=1)
                print(f"⚠️ Loss streak of {self.loss_streak} - pausing for 1 hour")
        else:
            self.loss_streak = 0
        
        # Add to history
        self.trade_history.append({
            'pnl': pnl,
            'timestamp': datetime.now().isoformat(),
            'strategy': trade.get('strategy')
        })
        
        # Keep only last 100 trades
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
    
    def reset_daily(self):
        """Reset daily metrics (call at midnight)."""
        self.daily_pnl = 0.0
        self.hourly_trades = 0
        print("🔄 Daily risk metrics reset")
    
    def get_status(self) -> Dict:
        """Get current risk status."""
        return {
            'daily_pnl': self.daily_pnl,
            'daily_loss_limit': Config.MAX_DAILY_LOSS_USD,
            'daily_pnl_percent': (self.daily_pnl / Config.MAX_DAILY_LOSS_USD) * 100 if Config.MAX_DAILY_LOSS_USD > 0 else 0,
            'kill_switch_active': self._is_killed(),
            'is_paused': self._is_paused(),
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'loss_streak': self.loss_streak,
            'hourly_trades': self.hourly_trades,
            'hourly_limit': Config.MAX_HOURLY_TRADES,
            'positions_by_event': dict(self.positions_by_event)
        }
    
    def calculate_position_size(self, base_size: float, confidence: float) -> float:
        """
        Calculate risk-adjusted position size.
        
        Reduces size when:
        - On a loss streak
        - Near daily loss limit
        - Low confidence signal
        """
        size = base_size
        
        # Reduce for loss streak (down to 50%)
        streak_multiplier = max(0.5, 1 - (self.loss_streak * 0.1))
        size *= streak_multiplier
        
        # Reduce when near daily limit
        if self.daily_pnl < 0:
            loss_percent = abs(self.daily_pnl) / Config.MAX_DAILY_LOSS_USD
            limit_multiplier = max(0.3, 1 - loss_percent)
            size *= limit_multiplier
        
        # Scale with confidence
        size *= confidence
        
        # Cap at max
        size = min(size, Config.MAX_POSITION_USD)
        
        return max(1.0, size)  # Minimum $1
    
    def get_risk_report(self) -> str:
        """Generate human-readable risk report."""
        status = self.get_status()
        
        report = ["📊 RISK STATUS"]
        report.append(f"Daily P&L: ${status['daily_pnl']:.2f} / ${status['daily_loss_limit']:.2f}")
        
        if status['kill_switch_active']:
            report.append("🛑 KILL SWITCH ACTIVE")
        elif status['is_paused']:
            report.append(f"⏸️ Trading paused until {status['pause_until']}")
        else:
            report.append("✅ Trading active")
        
        report.append(f"Loss streak: {status['loss_streak']}")
        report.append(f"Hourly trades: {status['hourly_trades']}/{status['hourly_limit']}")
        
        return "\n".join(report)
