"""
Momentum Strategy

Trades in the direction of sustained price movement.
Works WITHOUT live events - uses price history.
"""

import sys
import os
from typing import Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class MomentumStrategy(BaseStrategy):
    """
    Momentum-Based Trading Strategy.
    
    Trades in the direction of consistent price movement.
    Requires price history data (momentum_direction, momentum_strength).
    
    ALWAYS-ON: Works without live events!
    """
    
    def __init__(self):
        super().__init__()
        self.name = "momentum"
        self.min_strength = float(os.getenv('MOMENTUM_MIN_STRENGTH', '0.5'))
        self.min_moves = int(os.getenv('MOMENTUM_MIN_MOVES', '3'))
        
        # Stats
        self.signals_generated = 0
        self.last_signal_time = None
    
    def analyze(self, market: Dict, sports_data: Dict = None,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze market for momentum opportunities.
        
        Requires price history enrichment (momentum_direction, momentum_strength).
        """
        if not os.getenv('MOMENTUM_STRATEGY_ENABLED', 'true').lower() == 'true':
            return None
        
        # Get momentum data from enriched market
        momentum_direction = market.get('momentum_direction')
        momentum_strength = market.get('momentum_strength', 0)
        
        if not momentum_direction or momentum_direction == 'neutral':
            return None
        
        if momentum_strength < self.min_strength:
            return None
        
        current_price = market.get('current_price', 0.5)
        
        # Don't chase at extremes
        if current_price >= 0.90 or current_price <= 0.10:
            return None
        
        # Determine direction
        if momentum_direction == 'bullish':
            signal_type = SignalType.BUY_YES
            # Target: continue in momentum direction
            target = min(current_price + 0.08, 0.92)
            stop = max(current_price - 0.05, 0.05)
            rationale = f"Bullish momentum (strength: {momentum_strength:.2f})"
        else:  # bearish
            signal_type = SignalType.BUY_NO
            target = max(current_price - 0.08, 0.08)
            stop = min(current_price + 0.05, 0.95)
            rationale = f"Bearish momentum (strength: {momentum_strength:.2f})"
        
        # Confidence based on momentum strength
        confidence = 0.5 + (momentum_strength * 0.3)
        
        # Position size - conservative for momentum trades
        size = Config.MAX_POSITION_USD * 0.4 * momentum_strength
        
        self.signals_generated += 1
        self.last_signal_time = datetime.now()
        
        return TradeSignal(
            strategy=self.name,
            signal_type=signal_type,
            market_id=market.get('id', ''),
            market_question=market.get('question', '')[:100],
            sport=market.get('sport', 'unknown'),
            entry_price=current_price,
            target_price=target,
            stop_loss_price=stop,
            confidence=confidence,
            size_usd=size,
            rationale=rationale,
            metadata={
                'momentum_strength': momentum_strength,
                'momentum_direction': momentum_direction
            }
        )
    
    def get_stats(self) -> Dict:
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'enabled': os.getenv('MOMENTUM_STRATEGY_ENABLED', 'true').lower() == 'true'
        }
