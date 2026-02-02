"""
Adaptive Threshold System

Auto-tunes strategy thresholds based on performance:
- Winning strategies → loosen thresholds (take more trades)
- Losing strategies → tighten thresholds (be selective)
- New strategies → start with default, learn over time

Also implements EMERGENCY MODE:
- If no trades for 6+ hours → progressively loosen ALL thresholds
- Ensures bot always finds SOMETHING to trade
"""

import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class StrategyPerformance:
    """Track performance for a single strategy."""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.threshold_multiplier = 1.0  # 1.0 = default thresholds
        self.last_adjusted = datetime.now()
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return self.wins / total
    
    @property
    def avg_pnl(self) -> float:
        """Calculate average P&L per trade."""
        if not self.trades:
            return 0.0
        return self.total_pnl / len(self.trades)
    
    def add_trade(self, pnl: float, timestamp: datetime = None):
        """Record a completed trade."""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.trades.append({'pnl': pnl, 'timestamp': timestamp})
        self.total_pnl += pnl
        
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
    
    def get_recent_performance(self, lookback_trades: int) -> Dict[str, float]:
        """Get performance over recent N trades."""
        if not self.trades:
            return {'win_rate': 0.0, 'avg_pnl': 0.0, 'total_trades': 0}
        
        recent_trades = self.trades[-lookback_trades:]
        wins = sum(1 for t in recent_trades if t['pnl'] > 0)
        total_pnl = sum(t['pnl'] for t in recent_trades)
        
        return {
            'win_rate': wins / len(recent_trades) if recent_trades else 0.0,
            'avg_pnl': total_pnl / len(recent_trades) if recent_trades else 0.0,
            'total_trades': len(recent_trades)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'strategy_name': self.strategy_name,
            'total_trades': len(self.trades),
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'avg_pnl': self.avg_pnl,
            'threshold_multiplier': self.threshold_multiplier,
            'last_adjusted': self.last_adjusted.isoformat()
        }


class AdaptiveThresholds:
    """
    LEARNS AND ADAPTS
    
    - Tracks win/loss for each strategy
    - Winning strategies → loosen thresholds (take more trades)
    - Losing strategies → tighten thresholds (be selective)
    - New strategies → start with default, learn over time
    
    Also implements EMERGENCY MODE:
    - If no trades for 6+ hours → progressively loosen ALL thresholds
    - Ensures bot always finds SOMETHING to trade
    """
    
    def __init__(self):
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.lookback_trades = Config.ADAPTIVE_LOOKBACK_TRADES
        self.emergency_hours = Config.ADAPTIVE_EMERGENCY_HOURS
        
        self.last_trade_time = datetime.now()
        self.emergency_mode = False
        self.emergency_multiplier = 1.0
        
        self.adjustment_log = []
        
        print(f"📊 Adaptive Thresholds initialized:")
        print(f"   Lookback window: {self.lookback_trades} trades")
        print(f"   Emergency mode after: {self.emergency_hours} hours no trades")
    
    def record_trade(self, strategy_name: str, pnl: float, timestamp: datetime = None):
        """
        Record a completed trade for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            pnl: Profit/loss of the trade
            timestamp: Trade completion time
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Get or create strategy performance tracker
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = StrategyPerformance(strategy_name)
        
        perf = self.strategy_performance[strategy_name]
        perf.add_trade(pnl, timestamp)
        
        # Update last trade time
        self.last_trade_time = timestamp
        
        # Exit emergency mode if we got a trade
        if self.emergency_mode:
            self.emergency_mode = False
            self.emergency_multiplier = 1.0
            print(f"✅ Emergency Mode: Disabled (trade executed)")
        
        # Check if we should adjust thresholds for this strategy
        self._maybe_adjust_strategy(strategy_name)
    
    def get_threshold_multiplier(self, strategy_name: str) -> float:
        """
        Get the threshold multiplier for a strategy.
        
        A multiplier < 1.0 means looser thresholds (more trades).
        A multiplier > 1.0 means tighter thresholds (fewer trades).
        
        Args:
            strategy_name: Name of the strategy
        
        Returns:
            Threshold multiplier to apply
        """
        # Check for emergency mode
        self._check_emergency_mode()
        
        # Get strategy-specific multiplier
        if strategy_name not in self.strategy_performance:
            strategy_multiplier = 1.0  # Default for new strategies
        else:
            strategy_multiplier = self.strategy_performance[strategy_name].threshold_multiplier
        
        # Combine with emergency multiplier
        final_multiplier = strategy_multiplier * self.emergency_multiplier
        
        return final_multiplier
    
    def _check_emergency_mode(self):
        """
        Check if we should enter emergency mode.
        
        Emergency mode progressively loosens thresholds when no trades are executed:
        - Activates after ADAPTIVE_EMERGENCY_HOURS without trades
        - Reduces threshold multiplier by 5% per hour (makes thresholds looser)
        - Floor of 0.5 (50% of normal thresholds) reached after 10 hours
        - This ensures bot finds opportunities even in slow markets
        """
        hours_since_trade = (datetime.now() - self.last_trade_time).total_seconds() / 3600
        
        if hours_since_trade >= self.emergency_hours:
            if not self.emergency_mode:
                self.emergency_mode = True
                print(f"🚨 Emergency Mode: ACTIVATED (no trades for {hours_since_trade:.1f}h)")
            
            # Progressive loosening: 5% per hour after threshold, floor at 50%
            hours_over = hours_since_trade - self.emergency_hours
            self.emergency_multiplier = max(0.5, 1.0 - (0.05 * hours_over))
            
            if self.emergency_multiplier < 0.8:
                print(f"🚨 Emergency Mode: Loosening all thresholds by {(1-self.emergency_multiplier)*100:.0f}%")
    
    def _maybe_adjust_strategy(self, strategy_name: str):
        """
        Check if strategy thresholds should be adjusted based on performance.
        Only adjusts after minimum number of trades.
        """
        perf = self.strategy_performance[strategy_name]
        
        # Need minimum trades before adjusting
        if len(perf.trades) < 10:
            return
        
        # Don't adjust too frequently (wait at least 5 trades)
        trades_since_adjustment = len([t for t in perf.trades 
                                       if t['timestamp'] > perf.last_adjusted])
        if trades_since_adjustment < 5:
            return
        
        # Get recent performance
        recent = perf.get_recent_performance(self.lookback_trades)
        win_rate = recent['win_rate']
        avg_pnl = recent['avg_pnl']
        
        # Determine adjustment
        old_multiplier = perf.threshold_multiplier
        
        # Good performance → loosen thresholds (lower multiplier)
        if win_rate >= 0.70 and avg_pnl > 0:
            perf.threshold_multiplier = max(0.6, perf.threshold_multiplier * 0.9)
            action = "loosening"
        
        # Decent performance → slight loosening
        elif win_rate >= 0.60 and avg_pnl > 0:
            perf.threshold_multiplier = max(0.8, perf.threshold_multiplier * 0.95)
            action = "slightly loosening"
        
        # Poor performance → tighten thresholds (higher multiplier)
        elif win_rate < 0.45 or avg_pnl < -1.0:
            perf.threshold_multiplier = min(1.5, perf.threshold_multiplier * 1.1)
            action = "tightening"
        
        # Mediocre performance → slight tightening
        elif win_rate < 0.55:
            perf.threshold_multiplier = min(1.2, perf.threshold_multiplier * 1.05)
            action = "slightly tightening"
        
        else:
            # No adjustment needed
            return
        
        # Log adjustment
        perf.last_adjusted = datetime.now()
        
        adjustment = {
            'timestamp': datetime.now().isoformat(),
            'strategy': strategy_name,
            'action': action,
            'old_multiplier': old_multiplier,
            'new_multiplier': perf.threshold_multiplier,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'trades_analyzed': recent['total_trades']
        }
        self.adjustment_log.append(adjustment)
        
        print(f"📊 Adaptive: {action} '{strategy_name}' thresholds "
              f"(win rate: {win_rate*100:.0f}%, multiplier: {old_multiplier:.2f} → {perf.threshold_multiplier:.2f})")
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics for all strategies."""
        return {
            strategy_name: perf.to_dict()
            for strategy_name, perf in self.strategy_performance.items()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adaptive system statistics."""
        hours_since_trade = (datetime.now() - self.last_trade_time).total_seconds() / 3600
        
        return {
            'emergency_mode': self.emergency_mode,
            'emergency_multiplier': self.emergency_multiplier,
            'hours_since_trade': hours_since_trade,
            'strategies_tracked': len(self.strategy_performance),
            'total_adjustments': len(self.adjustment_log),
            'recent_adjustments': self.adjustment_log[-5:] if self.adjustment_log else []
        }
    
    def get_adjustment_log(self, limit: int = 50) -> list:
        """Get recent threshold adjustments."""
        return self.adjustment_log[-limit:] if self.adjustment_log else []
