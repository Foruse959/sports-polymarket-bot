"""
Aggressive Trader

Transforms trading from conservative to aggressive for exponential growth:
- Position sizes compound (% of equity, not fixed $)
- Kelly Criterion optimal sizing
- Pyramiding into winning positions (up to 3 add-ons)
- Auto-compounding when equity grows
- Wider stops and delayed trailing stops to let winners run
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from config_aggressive import AggressiveConfig
from data.database import Database
from risk.risk_manager import RiskManager
from core.kelly_criterion import optimal_position_size


class AggressiveTrader:
    """
    Aggressive paper trading engine with compounding and pyramiding.
    
    Key Features:
    - Position size = % of current equity (compounds automatically!)
    - Kelly Criterion for optimal bet sizing
    - Pyramid into winners (add up to 3x)
    - Delayed trailing stop (only after 20% profit)
    - Wider stops and targets
    """
    
    def __init__(self, starting_balance: Optional[float] = None):
        self.balance = starting_balance or Config.STARTING_BALANCE
        self.initial_balance = self.balance
        self.db = Database()
        self.risk_manager = RiskManager()
        self.positions = {}  # trade_id -> position
        self.pyramid_levels = {}  # trade_id -> list of pyramid entries
        
        # Compounding tracking
        self.last_compound_equity = self.balance
        self.compound_multiplier = 1.0
        
        print(f"⚡ Aggressive Trader initialized with ${self.balance:,.2f}")
        AggressiveConfig.print_status()
    
    def execute_trade(self, signal: Dict) -> Optional[Dict]:
        """
        Execute an aggressive paper trade from a signal.
        
        Args:
            signal: TradeSignal dict with entry details
            
        Returns:
            Trade dict if executed, None if rejected
        """
        # Check with risk manager (but with aggressive limits)
        can_trade, reason = self._can_trade_aggressive(signal)
        
        if not can_trade:
            print(f"⚠️ Trade rejected: {reason}")
            return None
        
        # Calculate aggressive position size
        size = self._calculate_aggressive_size(signal)
        
        # Check balance
        if size > self.balance:
            print(f"⚠️ Insufficient balance: ${self.balance:.2f} < ${size:.2f}")
            size = self.balance * 0.9  # Use 90% of remaining
        
        # Apply minimum
        if size < AggressiveConfig.MIN_POSITION_USD:
            print(f"⚠️ Position size ${size:.2f} below minimum ${AggressiveConfig.MIN_POSITION_USD}")
            return None
        
        # Simulate slippage
        slippage_percent = 0.001 + (size / 1000) * 0.004
        entry_price = signal.get('entry_price', 0.5)
        
        if signal.get('signal_type') == 'BUY':
            entry_price *= (1 + slippage_percent)
        else:
            entry_price *= (1 - slippage_percent)
        
        # Create trade
        trade_id = str(uuid.uuid4())[:8]
        
        # Calculate aggressive targets
        target_price, stop_loss_price = self._calculate_aggressive_targets(
            entry_price,
            signal.get('signal_type', 'BUY')
        )
        
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
            'target_price': target_price,
            'stop_loss_price': stop_loss_price,
            'size_usd': size,
            'confidence': signal.get('confidence', 0.5),
            'rationale': signal.get('rationale', ''),
            'entry_time': datetime.now().isoformat(),
            'status': 'open',
            'unrealized_pnl': 0,
            'high_water_mark': entry_price,
            'trailing_stop_activated': False,
            'pyramid_level': 0,
            'parent_trade_id': None,
            'metadata': signal.get('metadata', {})
        }
        
        # Deduct from balance
        self.balance -= size
        
        # Store position
        self.positions[trade_id] = trade
        self.pyramid_levels[trade_id] = []
        
        # Save to database
        self.db.save_trade(trade)
        self.db.save_position(trade)
        
        # Notify risk manager
        self.risk_manager.record_trade_opened(trade)
        
        print(f"✅ Aggressive trade opened: {trade['strategy']} {trade['direction']} @ ${entry_price:.4f}")
        print(f"   Size: ${size:.2f} ({size/self.get_equity()*100:.1f}% of equity)")
        print(f"   Target: ${target_price:.4f} ({AggressiveConfig.TAKE_PROFIT_PERCENT}%)")
        print(f"   Stop: ${stop_loss_price:.4f} ({AggressiveConfig.STOP_LOSS_PERCENT}%)")
        
        return trade
    
    def _can_trade_aggressive(self, signal: Dict) -> Tuple[bool, str]:
        """Check if can trade with aggressive limits."""
        # Max open positions
        if len(self.positions) >= AggressiveConfig.MAX_OPEN_POSITIONS:
            return False, f"Max positions ({AggressiveConfig.MAX_OPEN_POSITIONS}) reached"
        
        # Max positions per event
        event_positions = [p for p in self.positions.values() 
                          if p.get('market_id') == signal.get('market_id')]
        if len(event_positions) >= AggressiveConfig.MAX_POSITIONS_PER_EVENT:
            return False, f"Max positions per event ({AggressiveConfig.MAX_POSITIONS_PER_EVENT}) reached"
        
        return True, ""
    
    def _calculate_aggressive_size(self, signal: Dict) -> float:
        """Calculate aggressive position size with compounding and Kelly."""
        equity = self.get_equity()
        
        # Check auto-compounding
        if AggressiveConfig.AUTO_COMPOUND:
            if equity >= self.last_compound_equity * AggressiveConfig.COMPOUND_THRESHOLD:
                self.compound_multiplier *= AggressiveConfig.COMPOUND_MULTIPLIER
                self.last_compound_equity = equity
                print(f"📈 Compounding activated! Multiplier now {self.compound_multiplier:.2f}x")
        
        # Base size from equity percentage
        base_size_percent = AggressiveConfig.POSITION_SIZE_PERCENT / 100
        base_size_percent *= self.compound_multiplier
        
        # Apply Kelly Criterion if enabled
        if AggressiveConfig.USE_KELLY_SIZING:
            size = optimal_position_size(
                confidence=signal.get('confidence', 0.5),
                market_price=signal.get('entry_price', 0.5),
                bankroll=equity,
                base_size_percent=base_size_percent,
                use_kelly=True,
                kelly_fraction=AggressiveConfig.KELLY_FRACTION,
                max_position_percent=AggressiveConfig.MAX_POSITION_PERCENT / 100
            )
        else:
            # Simple percentage sizing
            size = equity * base_size_percent * signal.get('confidence', 0.5)
        
        # Cap at max position
        max_size = equity * (AggressiveConfig.MAX_POSITION_PERCENT / 100)
        size = min(size, max_size)
        
        return size
    
    def _calculate_aggressive_targets(self, entry_price: float, direction: str) -> Tuple[float, float]:
        """Calculate aggressive targets with wider stops."""
        if direction == 'BUY':
            target = entry_price * (1 + AggressiveConfig.TAKE_PROFIT_PERCENT / 100)
            stop = entry_price * (1 - AggressiveConfig.STOP_LOSS_PERCENT / 100)
        else:
            target = entry_price * (1 - AggressiveConfig.TAKE_PROFIT_PERCENT / 100)
            stop = entry_price * (1 + AggressiveConfig.STOP_LOSS_PERCENT / 100)
        
        return target, stop
    
    def update_positions(self, current_prices: Dict[str, float]) -> List[Dict]:
        """
        Update all positions with current prices and check for pyramiding opportunities.
        
        Args:
            current_prices: market_id -> current_price mapping
            
        Returns:
            List of positions that were closed
        """
        closed_trades = []
        positions_to_close = []
        positions_to_pyramid = []
        
        for trade_id, position in list(self.positions.items()):
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
            
            # Update high water mark
            if position['direction'] == 'BUY':
                if current_price > position['high_water_mark']:
                    position['high_water_mark'] = current_price
            else:
                if current_price < position['high_water_mark']:
                    position['high_water_mark'] = current_price
            
            # Check for pyramiding opportunity (only on parent trades)
            if (AggressiveConfig.PYRAMID_ENABLED and 
                position.get('pyramid_level', 0) == 0 and
                position.get('parent_trade_id') is None):
                
                pyramid_count = len(self.pyramid_levels.get(trade_id, []))
                if pyramid_count < AggressiveConfig.MAX_PYRAMID_LEVELS:
                    if pnl_percent >= AggressiveConfig.PYRAMID_TRIGGER_PROFIT:
                        # Check if we haven't pyramided at this level recently
                        last_pyramid_profit = self.pyramid_levels[trade_id][-1] if self.pyramid_levels[trade_id] else 0
                        if pnl_percent >= last_pyramid_profit + AggressiveConfig.PYRAMID_TRIGGER_PROFIT:
                            positions_to_pyramid.append((trade_id, position, pnl_percent))
            
            # Check exit conditions
            exit_reason = self._check_aggressive_exit(position)
            
            if exit_reason:
                positions_to_close.append((trade_id, exit_reason))
            else:
                # Update in database
                self.db.update_position_price(trade_id, current_price, position['unrealized_pnl'])
        
        # Execute pyramiding
        for trade_id, position, pnl_percent in positions_to_pyramid:
            self._add_pyramid_position(trade_id, position, pnl_percent)
        
        # Close positions that need closing
        for trade_id, reason in positions_to_close:
            closed_trade = self.close_trade(trade_id, reason)
            if closed_trade:
                closed_trades.append(closed_trade)
        
        return closed_trades
    
    def _add_pyramid_position(self, parent_trade_id: str, parent_position: Dict, current_pnl_percent: float):
        """Add a pyramid position to a winning trade."""
        # Calculate pyramid size (% of original position)
        pyramid_size = parent_position['size_usd'] * (AggressiveConfig.PYRAMID_SIZE_PERCENT / 100)
        
        # Check balance
        if pyramid_size > self.balance:
            print(f"⚠️ Insufficient balance for pyramid: ${self.balance:.2f} < ${pyramid_size:.2f}")
            return
        
        # Create pyramid trade
        trade_id = str(uuid.uuid4())[:8]
        current_price = parent_position['current_price']
        
        target_price, stop_loss_price = self._calculate_aggressive_targets(
            current_price,
            parent_position['direction']
        )
        
        pyramid_level = len(self.pyramid_levels[parent_trade_id]) + 1
        
        trade = {
            'id': trade_id,
            'trade_id': trade_id,
            'market_id': parent_position['market_id'],
            'market_question': parent_position['market_question'],
            'sport': parent_position['sport'],
            'strategy': parent_position['strategy'] + f' (Pyramid {pyramid_level})',
            'direction': parent_position['direction'],
            'entry_price': current_price,
            'current_price': current_price,
            'target_price': target_price,
            'stop_loss_price': stop_loss_price,
            'size_usd': pyramid_size,
            'confidence': parent_position['confidence'],
            'rationale': f"Pyramiding into winner at +{current_pnl_percent:.1f}%",
            'entry_time': datetime.now().isoformat(),
            'status': 'open',
            'unrealized_pnl': 0,
            'high_water_mark': current_price,
            'trailing_stop_activated': False,
            'pyramid_level': pyramid_level,
            'parent_trade_id': parent_trade_id,
            'metadata': parent_position.get('metadata', {})
        }
        
        # Deduct from balance
        self.balance -= pyramid_size
        
        # Store position
        self.positions[trade_id] = trade
        self.pyramid_levels[parent_trade_id].append(current_pnl_percent)
        
        # Save to database
        self.db.save_trade(trade)
        self.db.save_position(trade)
        
        print(f"📈 Pyramid {pyramid_level} added to {parent_trade_id[:6]}...")
        print(f"   Size: ${pyramid_size:.2f} @ ${current_price:.4f}")
        print(f"   Total position: ${parent_position['size_usd'] + pyramid_size:.2f}")
    
    def _check_aggressive_exit(self, position: Dict) -> Optional[str]:
        """Check exit conditions with aggressive parameters."""
        current_price = position['current_price']
        entry_price = position['entry_price']
        direction = position['direction']
        entry_time = datetime.fromisoformat(position['entry_time'])
        
        # Calculate profit/loss percent
        if direction == 'BUY':
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
        
        # Take profit (aggressive 50% target)
        if pnl_percent >= AggressiveConfig.TAKE_PROFIT_PERCENT:
            return f"Take profit hit (+{pnl_percent:.1f}%)"
        
        # Stop loss (wider 15% stop)
        if pnl_percent <= -AggressiveConfig.STOP_LOSS_PERCENT:
            return f"Stop loss hit ({pnl_percent:.1f}%)"
        
        # Aggressive trailing stop (only activates after 20% profit!)
        if pnl_percent >= AggressiveConfig.TRAILING_STOP_ACTIVATION:
            position['trailing_stop_activated'] = True
        
        if position.get('trailing_stop_activated', False):
            hwm = position['high_water_mark']
            
            if direction == 'BUY':
                drawdown = ((hwm - current_price) / hwm) * 100
            else:
                drawdown = ((current_price - hwm) / hwm) * 100
            
            if drawdown >= AggressiveConfig.TRAILING_STOP_PERCENT:
                return f"Trailing stop hit ({drawdown:.1f}% from high, was +{pnl_percent:.1f}%)"
        
        # Max hold time (4 hours instead of 1)
        elapsed_minutes = (datetime.now() - entry_time).seconds / 60
        if elapsed_minutes >= AggressiveConfig.MAX_HOLD_MINUTES:
            return f"Max hold time ({AggressiveConfig.MAX_HOLD_MINUTES} min)"
        
        return None
    
    def close_trade(self, trade_id: str, reason: str) -> Optional[Dict]:
        """Close a trade and any associated pyramid positions."""
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
        
        # Close any pyramid positions if this is a parent
        if position.get('pyramid_level', 0) == 0 and position.get('parent_trade_id') is None:
            pyramid_positions = [
                (pid, p) for pid, p in list(self.positions.items())
                if p.get('parent_trade_id') == trade_id
            ]
            for pid, _ in pyramid_positions:
                self.close_trade(pid, f"Parent closed: {reason}")
        
        result_emoji = "🟢" if pnl > 0 else "🔴"
        print(f"{result_emoji} Trade closed: {position['strategy']}")
        print(f"   P&L: ${pnl:+.2f} ({closed_trade['pnl_percent']:+.1f}%)")
        print(f"   Reason: {reason}")
        print(f"   Balance: ${self.balance:.2f} | Equity: ${self.get_equity():.2f}")
        
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
                'return_percent': 0,
                'compound_multiplier': self.compound_multiplier
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
            'open_positions': len(self.positions),
            'compound_multiplier': self.compound_multiplier
        }
    
    def get_status_summary(self) -> str:
        """Get human-readable status summary."""
        stats = self.get_performance_stats()
        
        lines = [
            "⚡ AGGRESSIVE TRADING STATUS",
            f"Balance: ${stats['balance']:.2f}",
            f"Equity: ${stats['equity']:.2f}",
            f"Return: {stats['return_percent']:+.1f}%",
            f"Compound: {stats['compound_multiplier']:.2f}x",
            "",
            f"Trades: {stats['total_trades']} ({stats['wins']}W/{stats['losses']}L)",
            f"Win Rate: {stats['win_rate']:.0%}",
            f"Total P&L: ${stats['total_pnl']:+.2f}",
            f"Open Positions: {stats['open_positions']}"
        ]
        
        return "\n".join(lines)
