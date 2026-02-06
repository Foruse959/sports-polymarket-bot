"""
Contrarian Strategy

Fades extreme price movements - bets against the crowd.
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


class ContrarianStrategy(BaseStrategy):
    """
    Contrarian (Mean Reversion) Strategy.
    
    Fades extreme price moves with the expectation of reversion.
    Uses price history data (price_change, price_extreme).
    
    ALWAYS-ON: Works without live events!
    """
    
    def __init__(self):
        super().__init__(
            name="Contrarian",
            description="Fades extreme price movements - bets against the crowd"
        )
        # Minimum price change to trigger (5%)
        self.min_move = float(os.getenv('CONTRARIAN_MIN_MOVE', '0.05'))
        
        # Stats
        self.signals_generated = 0
        self.last_signal_time = None
    
    def analyze(self, market: Dict, sports_data: Dict = None,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze market for contrarian opportunities.
        
        Looks for:
        1. Large recent price moves to fade
        2. Prices at recent extremes
        """
        if not os.getenv('CONTRARIAN_STRATEGY_ENABLED', 'true').lower() == 'true':
            return None
        
        current_price = market.get('current_price', 0.5)
        price_change = market.get('price_change', 0)
        price_extreme = market.get('price_extreme')
        
        signal_type = None
        rationale = None
        confidence = 0.55
        
        # Strategy 1: Fade large moves
        if abs(price_change or 0) >= self.min_move:
            if price_change > 0 and current_price < 0.85:
                # Price jumped up - fade it
                signal_type = SignalType.BUY_NO
                rationale = f"Fading +{price_change*100:.1f}% spike"
                confidence = 0.55 + min(abs(price_change) * 2, 0.15)
            elif price_change < 0 and current_price > 0.15:
                # Price dropped - fade it
                signal_type = SignalType.BUY_YES
                rationale = f"Fading {price_change*100:.1f}% drop"
                confidence = 0.55 + min(abs(price_change) * 2, 0.15)
        
        # Strategy 2: Fade extremes
        elif price_extreme:
            if price_extreme == 'high' and current_price < 0.88:
                signal_type = SignalType.BUY_NO
                rationale = "Price at recent high - expecting pullback"
                confidence = 0.52
            elif price_extreme == 'low' and current_price > 0.12:
                signal_type = SignalType.BUY_YES
                rationale = "Price at recent low - expecting bounce"
                confidence = 0.52
        
        if not signal_type:
            return None
        
        # Contrarian targets: expect 50% reversion
        if signal_type == SignalType.BUY_YES:
            reversion = abs(price_change or 0.03) * 0.5
            target = min(current_price + reversion, 0.88)
            stop = max(current_price - reversion * 0.6, 0.05)
        else:
            reversion = abs(price_change or 0.03) * 0.5
            target = max(current_price - reversion, 0.12)
            stop = min(current_price + reversion * 0.6, 0.95)
        
        # Smaller position size - contrarian is risky
        size = Config.MAX_POSITION_USD * 0.35
        
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
                'price_change': price_change,
                'price_extreme': price_extreme
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                    sports_data: Dict = None) -> tuple:
        """Check if position should be exited."""
        entry_price = position.get('entry_price', current_price)
        signal_type = position.get('signal_type', 'BUY_YES')
        
        if signal_type == 'BUY_YES':
            pnl_percent = (current_price - entry_price) / entry_price * 100
        else:
            pnl_percent = (entry_price - current_price) / entry_price * 100
        
        # Contrarian: take quick profits, tight stops
        if pnl_percent >= 10:
            return (True, "Contrarian take profit")
        if pnl_percent <= -7:
            return (True, "Contrarian stop loss")
        
        return (False, "")
    
    def get_stats(self) -> Dict:
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'enabled': os.getenv('CONTRARIAN_STRATEGY_ENABLED', 'true').lower() == 'true'
        }
