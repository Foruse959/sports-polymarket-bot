"""
Paper Trader

Simulates trade execution without real money.
Tracks positions, P&L, and performance metrics.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from data.database import Database
from risk.risk_manager import RiskManager


class PaperTrader:
    """
    Paper trading engine for simulating trades.
    
    Features:
    - Simulated order execution with slippage
    - Position tracking with P&L
    - Automatic exit condition checking
    - Integration with risk manager
    """
    
    def __init__(self, starting_balance: Optional[float] = None):
        self.balance = starting_balance or Config.STARTING_BALANCE
        self.initial_balance = self.balance
        self.db = Database()
        self.risk_manager = RiskManager()
        self.positions = {}  # trade_id -> position
        
        print(f"✅ Paper Trader initialized with ${self.balance:,.2f}")
    
    def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """
        Execute a paper trade from a signal.
        
        Args:
            signal: TradeSignal dict with entry details
            
        Returns:
            Trade dict if executed, None if rejected
        """
        # Check with risk manager
        can_trade, reason = self.risk_manager.can_trade(signal, list(self.positions.values()))
        
        if not can_trade:
            print(f"⚠️ Trade rejected: {reason}")
            return None
        
        # Calculate size with risk adjustment
        size = self.risk_manager.calculate_position_size(
            signal.get('size_usd', Config.MAX_POSITION_USD),
            signal.get('confidence', 0.5)
        )
        
        # Check balance
        if size > self.balance:
            print(f"⚠️ Insufficient balance: ${self.balance:.2f} < ${size:.2f}")
            size = self.balance * 0.9  # Use 90% of remaining
        
        # Simulate slippage (0.1% - 0.5% based on size)
        slippage_percent = 0.001 + (size / 1000) * 0.004
        entry_price = signal.get('entry_price', 0.5)
        
        if signal.get('signal_type') == 'BUY':
            entry_price *= (1 + slippage_percent)
        else:
            entry_price *= (1 - slippage_percent)
        
        # Create trade
        trade_id = str(uuid.uuid4())[:8]
        
        trade = {
            'id': trade_id,
            'trade_id': trade_id,
            'market_id': signal.get('market_id', ''),
            'market_question': signal.get('market_question', ''),
            'sport': signal.get('sport', 'unknown'),
            'strategy': signal.get('strategy', 'unknown'),
            'direction': signal.get('signal_type', 'BUY'),
            'entry_price': entry_price,
            'current_price': entry_price,
            'target_price': signal.get('target_price', entry_price * 1.1),
            'stop_loss_price': signal.get('stop_loss_price', entry_price * 0.9),
            'size_usd': size,
            'confidence': signal.get('confidence', 0.5),
            'rationale': signal.get('rationale', ''),
            'entry_time': datetime.now().isoformat(),
            'status': 'open',
            'unrealized_pnl': 0,
            'high_water_mark': entry_price,
            'metadata': signal.get('metadata', {})
        }
        
        # Deduct from balance
        self.balance -= size
        
        # Store position
        self.positions[trade_id] = trade
        
        # Save to database
        self.db.save_trade(trade)
        self.db.save_position(trade)
        
        # Notify risk manager
        self.risk_manager.record_trade_opened(trade)
        
        print(f"✅ Paper trade opened: {trade['strategy']} {trade['direction']} @ ${entry_price:.4f}")
        print(f"   Size: ${size:.2f} | Target: ${trade['target_price']:.4f} | Stop: ${trade['stop_loss_price']:.4f}")
        
        return trade
    
    def update_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Update all positions with current prices.
        
        Args:
            current_prices: market_id -> current_price mapping
            
        Returns:
            List of positions that were closed
        """
        closed_trades = []
        positions_to_close = []
        
        for trade_id, position in self.positions.items():
            market_id = position['market_id']
            current_price = current_prices.get(market_id, position['current_price'])
            
            # Update position
            position['current_price'] = current_price
            
            # Calculate unrealized P&L
            if position['direction'] == 'BUY':
                pnl_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
            else:
                pnl_percent = ((position['entry_price'] - current_price) / position['entry_price']) * 100
            
            position['unrealized_pnl'] = position['size_usd'] * (pnl_percent / 100)
            
            # Update high water mark for trailing stop
            if position['direction'] == 'BUY':
                if current_price > position['high_water_mark']:
                    position['high_water_mark'] = current_price
            else:
                if current_price < position['high_water_mark']:
                    position['high_water_mark'] = current_price
            
            # Check exit conditions
            exit_reason = self._check_exit_conditions(position)
            
            if exit_reason:
                positions_to_close.append((trade_id, exit_reason))
            else:
                # Update in database
                self.db.update_position_price(trade_id, current_price, position['unrealized_pnl'])
        
        # Close positions that need closing
        for trade_id, reason in positions_to_close:
            closed_trade = self.close_trade(trade_id, reason)
            if closed_trade:
                closed_trades.append(closed_trade)
        
        return closed_trades
    
    def _check_exit_conditions(self, position: Dict) -> Optional[str]:
        """
        Check if position should be exited.
        
        Returns:
            Exit reason if should exit, None otherwise
        """
        current_price = position['current_price']
        entry_price = position['entry_price']
        direction = position['direction']
        entry_time = datetime.fromisoformat(position['entry_time'])
        
        # Calculate profit/loss percent
        if direction == 'BUY':
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
        
        # Take profit
        if pnl_percent >= Config.TAKE_PROFIT_PERCENT:
            return f"Take profit hit (+{pnl_percent:.1f}%)"
        
        # Stop loss
        if pnl_percent <= -Config.STOP_LOSS_PERCENT:
            return f"Stop loss hit ({pnl_percent:.1f}%)"
        
        # Trailing stop
        if Config.TRAILING_STOP_ENABLED:
            hwm = position['high_water_mark']
            
            if direction == 'BUY':
                drawdown = ((hwm - current_price) / hwm) * 100
            else:
                drawdown = ((current_price - hwm) / hwm) * 100
            
            # Only trigger trailing stop if we were profitable
            if direction == 'BUY' and hwm > entry_price:
                if drawdown >= Config.TRAILING_STOP_PERCENT:
                    return f"Trailing stop hit ({drawdown:.1f}% from high)"
            elif direction == 'SELL' and hwm < entry_price:
                if drawdown >= Config.TRAILING_STOP_PERCENT:
                    return f"Trailing stop hit ({drawdown:.1f}% from low)"
        
        # Max hold time
        elapsed_minutes = (datetime.now() - entry_time).seconds / 60
        if elapsed_minutes >= Config.MAX_HOLD_MINUTES:
            return f"Max hold time ({Config.MAX_HOLD_MINUTES} min)"
        
        return None
    
    def close_trade(self, trade_id: str, reason: str) -> Optional[Dict]:
        """
        Close a paper trade.
        
        Args:
            trade_id: ID of trade to close
            reason: Reason for closing
            
        Returns:
            Closed trade dict with P&L
        """
        if trade_id not in self.positions:
            print(f"⚠️ Trade {trade_id} not found")
            return None
        
        position = self.positions[trade_id]
        exit_price = position['current_price']
        
        # Calculate P&L
        if position['direction'] == 'BUY':
            pnl = position['size_usd'] * ((exit_price - position['entry_price']) / position['entry_price'])
        else:
            pnl = position['size_usd'] * ((position['entry_price'] - exit_price) / position['entry_price'])
        
        # Update balance
        self.balance += position['size_usd'] + pnl
        
        # Create closed trade record
        closed_trade = {
            **position,
            'exit_price': exit_price,
            'exit_time': datetime.now().isoformat(),
            'exit_reason': reason,
            'pnl': pnl,
            'pnl_percent': (pnl / position['size_usd']) * 100,
            'status': 'closed'
        }
        
        # Update database
        self.db.close_trade(trade_id, exit_price, pnl, reason)
        
        # Notify risk manager
        self.risk_manager.record_trade_closed(position, pnl)
        
        # Update strategy stats
        self.db.update_strategy_stats(
            position['strategy'],
            win=pnl > 0,
            pnl=pnl
        )
        
        # Remove from active positions
        del self.positions[trade_id]
        
        result_emoji = "🟢" if pnl > 0 else "🔴"
        print(f"{result_emoji} Trade closed: {position['strategy']}")
        print(f"   P&L: ${pnl:+.2f} ({closed_trade['pnl_percent']:+.1f}%)")
        print(f"   Reason: {reason}")
        print(f"   Balance: ${self.balance:.2f}")
        
        return closed_trade
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        return list(self.positions.values())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L across all positions."""
        return sum(p.get('unrealized_pnl', 0) for p in self.positions.values())
    
    def get_equity(self) -> float:
        """Get total equity (balance + unrealized P&L)."""
        return self.balance + self.get_total_unrealized_pnl()
    
    def get_performance_stats(self) -> Dict:
        """Get overall performance statistics."""
        trade_history = self.db.get_trade_history(limit=100)
        
        if not trade_history:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'balance': self.balance,
                'equity': self.get_equity(),
                'return_percent': 0
            }
        
        wins = [t for t in trade_history if t.get('pnl', 0) > 0]
        losses = [t for t in trade_history if t.get('pnl', 0) < 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trade_history)
        gross_profit = sum(t.get('pnl', 0) for t in wins)
        gross_loss = abs(sum(t.get('pnl', 0) for t in losses))
        
        return {
            'total_trades': len(trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trade_history) if trade_history else 0,
            'total_pnl': total_pnl,
            'avg_win': gross_profit / len(wins) if wins else 0,
            'avg_loss': gross_loss / len(losses) if losses else 0,
            'profit_factor': gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            'balance': self.balance,
            'equity': self.get_equity(),
            'return_percent': ((self.balance - self.initial_balance) / self.initial_balance) * 100,
            'open_positions': len(self.positions)
        }
    
    def get_status_summary(self) -> str:
        """Get human-readable status summary."""
        stats = self.get_performance_stats()
        
        lines = [
            "💰 PAPER TRADING STATUS",
            f"Balance: ${stats['balance']:.2f}",
            f"Equity: ${stats['equity']:.2f}",
            f"Return: {stats['return_percent']:+.1f}%",
            "",
            f"Trades: {stats['total_trades']} ({stats['wins']}W/{stats['losses']}L)",
            f"Win Rate: {stats['win_rate']:.0%}",
            f"Total P&L: ${stats['total_pnl']:+.2f}",
            f"Open Positions: {stats['open_positions']}"
        ]
        
        return "\n".join(lines)
