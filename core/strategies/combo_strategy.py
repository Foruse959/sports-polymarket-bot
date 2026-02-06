"""
Combo Strategy

Trades with higher confidence when multiple strategies agree.
This strategy generates signals when 2+ other strategies would agree on a trade.
"""

import os
import sys
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class ComboStrategy(BaseStrategy):
    """
    Combo Strategy - Trade when multiple signals align.
    
    When 2+ strategies agree on a trade direction:
    - Higher confidence
    - Larger position size
    - Better win rate expected
    """
    
    def __init__(self):
        super().__init__(
            name="Combo Signal",
            description="Higher confidence trades when multiple strategies agree"
        )
        self.min_signals = 2  # Minimum agreeing strategies
        
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """Analyze market for combo signal opportunity."""
        
        # Get individual signals from market metadata
        signals = market.get('strategy_signals', [])
        
        if len(signals) < self.min_signals:
            return None
        
        # Count buy vs sell signals
        buy_signals = [s for s in signals if s.get('direction') == 'BUY']
        sell_signals = [s for s in signals if s.get('direction') == 'SELL']
        
        current_price = market.get('current_price', 0.5)
        
        # Generate combo signal if strong agreement
        if len(buy_signals) >= self.min_signals:
            avg_confidence = sum(s.get('confidence', 0.5) for s in buy_signals) / len(buy_signals)
            combo_confidence = min(0.90, avg_confidence + 0.1 * (len(buy_signals) - 1))
            
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.BUY,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=current_price,
                target_price=current_price * 1.15,
                stop_loss_price=current_price * 0.93,
                confidence=combo_confidence,
                size_usd=self.calculate_size(combo_confidence, Config.MAX_POSITION_USD * 0.6),
                rationale=f"COMBO BUY: {len(buy_signals)} strategies agree ({', '.join(s.get('strategy', '?') for s in buy_signals[:3])})",
                metadata={
                    'combo_count': len(buy_signals),
                    'strategies': [s.get('strategy') for s in buy_signals],
                    'avg_confidence': avg_confidence
                }
            )
        
        if len(sell_signals) >= self.min_signals:
            avg_confidence = sum(s.get('confidence', 0.5) for s in sell_signals) / len(sell_signals)
            combo_confidence = min(0.90, avg_confidence + 0.1 * (len(sell_signals) - 1))
            
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.SELL,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=current_price,
                target_price=current_price * 0.85,
                stop_loss_price=current_price * 1.07,
                confidence=combo_confidence,
                size_usd=self.calculate_size(combo_confidence, Config.MAX_POSITION_USD * 0.6),
                rationale=f"COMBO SELL: {len(sell_signals)} strategies agree ({', '.join(s.get('strategy', '?') for s in sell_signals[:3])})",
                metadata={
                    'combo_count': len(sell_signals),
                    'strategies': [s.get('strategy') for s in sell_signals],
                    'avg_confidence': avg_confidence
                }
            )
        
        return None
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> tuple:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        # Combo trades have higher targets (they're higher confidence)
        if profit_percent >= 12:
            return True, f"Combo take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -6:
            return True, f"Combo stop loss ({profit_percent:.1f}%)"
        
        return False, ""
