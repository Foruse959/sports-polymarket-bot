"""
Whale Copy Executor

Automatically copies whale trades with ML validation.

Flow:
1. BlockchainMonitor detects whale trade
2. WhaleTracker validates wallet profitability
3. ML model predicts if we should copy
4. Execute with smart sizing (Kelly + ML confidence)
5. Feed results back to ML for learning

Features:
- Real-time whale trade detection
- ML-validated copying (only copy high-confidence trades)
- Smart position sizing based on ML confidence
- Automatic learning from results
- Configurable copy delay (avoid front-running detection)
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from config_aggressive import AggressiveConfig
from core.whale_tracker import WhaleTracker
from core.blockchain_monitor import create_monitor
from core.ml_whale_learner import WhaleBehaviorModel


class WhaleCopyExecutor:
    """
    Automated whale trade copying with ML validation.
    
    Integrates:
    - BlockchainMonitor: Detects whale trades
    - WhaleTracker: Validates whale profitability
    - ML Model: Predicts copy success
    - Trader: Executes copy trades
    """
    
    def __init__(self, trader):
        """
        Initialize whale copy executor.
        
        Args:
            trader: Trading engine (PaperTrader or AggressiveTrader)
        """
        self.trader = trader
        
        # Initialize components
        self.whale_tracker = WhaleTracker() if Config.WHALE_TRACKING_ENABLED else None
        self.blockchain_monitor = create_monitor() if AggressiveConfig.BLOCKCHAIN_MONITOR_ENABLED else None
        self.ml_model = WhaleBehaviorModel() if AggressiveConfig.ML_ENABLED else None
        
        # State
        self.copy_trades = {}  # trade_id -> copy trade info
        self.pending_outcomes = []  # List of trades waiting for outcome
        
        # Stats
        self.trades_detected = 0
        self.trades_copied = 0
        self.trades_rejected_whale = 0
        self.trades_rejected_ml = 0
        self.trades_rejected_risk = 0
        
        # Copy settings
        self.copy_delay = Config.WHALE_COPY_DELAY_SECONDS
        self.copy_size_multiplier = AggressiveConfig.WHALE_COPY_SIZE_MULTIPLIER
        self.max_position_percent = AggressiveConfig.WHALE_COPY_MAX_POSITION_PERCENT
        
        print(f"🐋 Whale Copy Executor initialized")
        print(f"   Whale tracking: {'✅' if self.whale_tracker else '⚪'}")
        print(f"   Blockchain monitor: {'✅' if self.blockchain_monitor else '⚪'}")
        print(f"   ML validation: {'✅' if self.ml_model else '⚪'}")
        print(f"   Copy delay: {self.copy_delay}s")
        print(f"   Size multiplier: {self.copy_size_multiplier:.1%}")
    
    def start_monitoring(self):
        """Start background monitoring for whale trades."""
        if not self.blockchain_monitor:
            print("⚠️ Blockchain monitor not available")
            return
        
        # Register callback
        self.blockchain_monitor.register_callback(self._on_whale_trade_detected)
        
        # Start monitoring
        self.blockchain_monitor.start_monitoring()
        
        print("✅ Whale copy monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        if self.blockchain_monitor:
            self.blockchain_monitor.stop_monitoring()
        print("✅ Whale copy monitoring stopped")
    
    def _on_whale_trade_detected(self, whale_trade: Dict):
        """
        Callback when whale trade detected by blockchain monitor.
        
        Args:
            whale_trade: Whale trade info from blockchain
        """
        self.trades_detected += 1
        
        wallet_address = whale_trade['wallet_address']
        
        print(f"\n🐋 Whale trade detected from {wallet_address[:10]}...")
        print(f"   Size: ${whale_trade['size_usd']:.0f}")
        
        # Step 1: Validate with WhaleTracker
        if self.whale_tracker:
            should_copy_whale = self.whale_tracker.should_copy_trade(wallet_address)
            
            if not should_copy_whale:
                print(f"   ⚠️ Wallet not validated by WhaleTracker")
                self.trades_rejected_whale += 1
                return
            
            print(f"   ✅ Wallet validated by WhaleTracker")
        
        # Step 2: Get market data for ML features
        market_data = self._get_market_data(whale_trade)
        
        # Step 3: ML validation
        if self.ml_model:
            should_copy_ml, ml_confidence = self.ml_model.predict_should_copy(
                whale_trade,
                market_data
            )
            
            if not should_copy_ml:
                print(f"   ⚠️ ML model rejected (confidence: {ml_confidence:.1%})")
                self.trades_rejected_ml += 1
                
                # Still record for learning
                self.ml_model.add_training_sample(
                    whale_trade,
                    market_data,
                    copied=False,
                    outcome=None
                )
                return
            
            print(f"   ✅ ML model approved (confidence: {ml_confidence:.1%})")
        else:
            ml_confidence = 0.7  # Default confidence if no ML
        
        # Step 4: Apply copy delay (avoid front-running detection)
        if self.copy_delay > 0:
            print(f"   ⏱️ Waiting {self.copy_delay}s (copy delay)...")
            time.sleep(self.copy_delay)
        
        # Step 5: Execute copy trade
        copy_trade = self._execute_copy_trade(whale_trade, market_data, ml_confidence)
        
        if copy_trade:
            # Record for ML learning
            if self.ml_model:
                self.ml_model.add_training_sample(
                    whale_trade,
                    market_data,
                    copied=True,
                    outcome=None  # Will update when trade closes
                )
            
            # Track for outcome learning
            self.pending_outcomes.append({
                'copy_trade_id': copy_trade['trade_id'],
                'whale_trade': whale_trade,
                'market_data': market_data,
                'ml_confidence': ml_confidence
            })
    
    def _get_market_data(self, whale_trade: Dict) -> Dict:
        """
        Get market data for ML feature extraction.
        
        In production, this would query:
        - Polymarket API for current price, liquidity
        - Historical data for momentum calculations
        - Odds aggregator for consensus
        
        For now, returns mock data.
        """
        # TODO: Integrate with real data sources
        return {
            'price_momentum_1h': 0.0,
            'price_momentum_24h': 0.0,
            'volume_ratio': 1.0,
            'time_to_event_hours': 24.0,
            'liquidity': 1000.0,
            'spread': 0.02,
            'whale_sentiment': 0.0,
            'odds_vs_consensus': 0.0
        }
    
    def _execute_copy_trade(
        self,
        whale_trade: Dict,
        market_data: Dict,
        ml_confidence: float
    ) -> Optional[Dict]:
        """
        Execute a copy trade.
        
        Args:
            whale_trade: Original whale trade
            market_data: Market context
            ml_confidence: ML model confidence
        
        Returns:
            Copy trade dict if executed, None if rejected
        """
        # Calculate copy size
        whale_size = whale_trade['size_usd']
        copy_size = whale_size * self.copy_size_multiplier
        
        # Adjust by ML confidence
        copy_size *= ml_confidence
        
        # Cap at max position size
        equity = self.trader.get_equity()
        max_size = equity * (self.max_position_percent / 100)
        copy_size = min(copy_size, max_size)
        
        # Create signal for trader
        signal = {
            'market_id': whale_trade.get('market_id', 'unknown'),
            'market_question': f"Whale Copy: {whale_trade.get('market_id', 'unknown')[:20]}...",
            'sport': 'whale_copy',
            'strategy': 'whale_copy',
            'signal_type': whale_trade.get('side', 'BUY'),
            'entry_price': whale_trade.get('price', 0.5),
            'size_usd': copy_size,
            'confidence': ml_confidence,
            'rationale': f"Copying whale {whale_trade['wallet_address'][:10]}... (${whale_size:.0f})",
            'metadata': {
                'whale_address': whale_trade['wallet_address'],
                'whale_size': whale_size,
                'ml_confidence': ml_confidence,
                'copy_type': 'whale_copy'
            }
        }
        
        # Execute trade
        try:
            copy_trade = self.trader.execute_trade(signal)
            
            if copy_trade:
                self.trades_copied += 1
                self.copy_trades[copy_trade['trade_id']] = {
                    'copy_trade': copy_trade,
                    'whale_trade': whale_trade,
                    'ml_confidence': ml_confidence
                }
                
                print(f"   ✅ Copy trade executed: ${copy_size:.2f}")
                return copy_trade
            else:
                self.trades_rejected_risk += 1
                print(f"   ⚠️ Copy trade rejected by trader")
                return None
        
        except Exception as e:
            print(f"   ⚠️ Error executing copy trade: {e}")
            return None
    
    def update_outcomes(self, closed_trades: List[Dict]):
        """
        Update ML model with trade outcomes.
        
        Called by main bot when trades close.
        
        Args:
            closed_trades: List of recently closed trades
        """
        if not self.ml_model:
            return
        
        for closed_trade in closed_trades:
            # Check if this is a whale copy trade
            trade_id = closed_trade['trade_id']
            
            if trade_id not in self.copy_trades:
                continue
            
            # Get the corresponding pending outcome
            pending = None
            for i, p in enumerate(self.pending_outcomes):
                if p['copy_trade_id'] == trade_id:
                    pending = self.pending_outcomes.pop(i)
                    break
            
            if not pending:
                continue
            
            # Determine outcome
            outcome = closed_trade['pnl'] > 0
            
            # Update ML model (will retrain if enough samples)
            # Note: We already called add_training_sample when we copied,
            # but now we update with the outcome
            # For simplicity, we'll just add a new sample with outcome
            self.ml_model.add_training_sample(
                pending['whale_trade'],
                pending['market_data'],
                copied=True,
                outcome=outcome
            )
            
            print(f"🤖 ML model updated with {'WIN' if outcome else 'LOSS'} from whale copy")
    
    def get_stats(self) -> Dict:
        """Get whale copy executor statistics."""
        stats = {
            'trades_detected': self.trades_detected,
            'trades_copied': self.trades_copied,
            'trades_rejected_whale': self.trades_rejected_whale,
            'trades_rejected_ml': self.trades_rejected_ml,
            'trades_rejected_risk': self.trades_rejected_risk,
            'copy_success_rate': 0,
            'pending_outcomes': len(self.pending_outcomes)
        }
        
        if self.trades_copied > 0:
            # Calculate success rate from completed trades
            completed = [
                t for t in self.copy_trades.values()
                if t['copy_trade'].get('status') == 'closed'
            ]
            if completed:
                wins = sum(1 for t in completed if t['copy_trade'].get('pnl', 0) > 0)
                stats['copy_success_rate'] = wins / len(completed)
        
        # Add component stats
        if self.whale_tracker:
            stats['whale_tracker'] = self.whale_tracker.get_stats()
        
        if self.blockchain_monitor:
            stats['blockchain_monitor'] = self.blockchain_monitor.get_stats()
        
        if self.ml_model:
            stats['ml_model'] = self.ml_model.get_stats()
        
        return stats
    
    def get_status_summary(self) -> str:
        """Get human-readable status summary."""
        stats = self.get_stats()
        
        lines = [
            "🐋 WHALE COPY EXECUTOR STATUS",
            f"Trades detected: {stats['trades_detected']}",
            f"Trades copied: {stats['trades_copied']}",
            f"Success rate: {stats['copy_success_rate']:.0%}",
            "",
            f"Rejected by whale tracker: {stats['trades_rejected_whale']}",
            f"Rejected by ML: {stats['trades_rejected_ml']}",
            f"Rejected by risk: {stats['trades_rejected_risk']}",
            "",
            f"Pending outcomes: {stats['pending_outcomes']}"
        ]
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Test mode
    from trading.paper_trader import PaperTrader
    
    print("Testing Whale Copy Executor...")
    
    trader = PaperTrader(starting_balance=1000)
    executor = WhaleCopyExecutor(trader)
    
    # Simulate whale trade
    test_trade = {
        'wallet_address': '0x1234567890abcdef',
        'market_id': 'test_market',
        'side': 'BUY',
        'size_usd': 1000,
        'price': 0.45,
        'timestamp': datetime.now()
    }
    
    print("\nSimulating whale trade detection...")
    executor._on_whale_trade_detected(test_trade)
    
    print(f"\nStats:\n{executor.get_status_summary()}")
