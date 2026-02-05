"""
AI Value Edge Strategy

Uses AI analysis to detect mispriced markets.
Works WITHOUT live events - always looking for opportunities.
"""

import sys
import os
from typing import Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class AIValueEdgeStrategy(BaseStrategy):
    """
    AI-Powered Value Detection Strategy.
    
    Uses AI analyzer to find mispriced markets based on:
    - Fair value estimation
    - Momentum signals
    - Probability analysis
    
    ALWAYS-ON: Works without live events!
    """
    
    def __init__(self, ai_analyzer=None):
        """
        Initialize strategy.
        
        Args:
            ai_analyzer: AIAnalyzer instance (optional - will create if needed)
        """
        super().__init__()
        self.name = "ai_value_edge"
        self.ai_analyzer = ai_analyzer
        self.min_confidence = float(os.getenv('AI_MIN_TRADE_CONFIDENCE', '0.6'))
        self.min_edge = float(os.getenv('AI_MIN_EDGE_PERCENT', '3')) / 100  # 3%
        
        # Stats
        self.signals_generated = 0
        self.last_signal_time = None
    
    def analyze(self, market: Dict, sports_data: Dict = None,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze market for AI-detected value.
        
        Doesn't require events or sports data - uses AI analysis.
        """
        if not os.getenv('AI_VALUE_EDGE_ENABLED', 'true').lower() == 'true':
            return None
        
        if not self.ai_analyzer:
            return None
        
        # Get AI analysis
        analysis = self.ai_analyzer.analyze_market(market)
        
        if not analysis:
            return None
        
        # Check if edge detected with sufficient confidence
        if not analysis.edge_detected:
            return None
            
        if analysis.confidence < self.min_confidence:
            return None
        
        # Check edge size
        current_price = market.get('current_price', 0.5)
        fair_value = analysis.fair_value_estimate or 0.5
        edge = abs(fair_value - current_price)
        
        if edge < self.min_edge:
            return None
        
        # Determine signal type
        if analysis.suggested_direction == 'buy_yes':
            signal_type = SignalType.BUY_YES
            target = min(current_price + edge * 0.7, 0.95)
            stop = max(current_price - edge * 0.5, 0.05)
        elif analysis.suggested_direction == 'buy_no':
            signal_type = SignalType.BUY_NO
            # For NO, we want price to go down
            target = max(current_price - edge * 0.7, 0.05)
            stop = min(current_price + edge * 0.5, 0.95)
        else:
            return None
        
        # Calculate position size (more confident = larger size)
        base_size = Config.MAX_POSITION_USD * 0.5
        confidence_multiplier = 0.5 + (analysis.confidence * 0.5)
        size = base_size * confidence_multiplier
        
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
            confidence=analysis.confidence,
            size_usd=size,
            rationale=f"AI Edge: {analysis.rationale} (via {analysis.provider.value})",
            metadata={
                'ai_provider': analysis.provider.value,
                'fair_value': fair_value,
                'edge_percent': edge * 100
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                    sports_data: Dict = None) -> tuple:
        """
        Check if position should be exited.
        
        Returns:
            (should_exit, reason)
        """
        entry_price = position.get('entry_price', current_price)
        signal_type = position.get('signal_type', 'BUY_YES')
        
        # Calculate P&L
        if signal_type == 'BUY_YES':
            pnl_percent = (current_price - entry_price) / entry_price * 100
        else:
            pnl_percent = (entry_price - current_price) / entry_price * 100
        
        # Take profit at 15%
        if pnl_percent >= 15:
            return (True, "AI Value Edge take profit")
        
        # Stop loss at 8%
        if pnl_percent <= -8:
            return (True, "AI Value Edge stop loss")
        
        return (False, "")
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'min_confidence': self.min_confidence,
            'enabled': os.getenv('AI_VALUE_EDGE_ENABLED', 'true').lower() == 'true'
        }
