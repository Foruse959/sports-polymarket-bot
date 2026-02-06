"""
BTTS Strategy (Both Teams To Score)

Trades on BTTS markets using team scoring/conceding history.
Primarily for football/soccer markets.
"""

import os
import re
from typing import Dict, Optional
from datetime import datetime

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class BTTSStrategy(BaseStrategy):
    """
    Both Teams To Score Strategy.
    
    Uses team scoring and clean sheet history to predict BTTS.
    
    ALWAYS-ON: Works with any BTTS market!
    """
    
    def __init__(self, team_stats_provider=None):
        """
        Initialize strategy.
        
        Args:
            team_stats_provider: TeamStatsProvider instance
        """
        super().__init__()
        self.name = "btts"
        self.team_stats = team_stats_provider
        
        # Minimum confidence to trade
        self.min_confidence = float(os.getenv('BTTS_MIN_CONFIDENCE', '0.55'))
        
        # Stats
        self.signals_generated = 0
        self.last_signal_time = None
        
        # Team name extraction patterns
        self.vs_pattern = re.compile(r'(.+?)\s+(?:vs?\.?|versus|at|@)\s+(.+?)(?:\s*[-:,\?]|$)', re.IGNORECASE)
    
    def analyze(self, market: Dict, sports_data: Dict = None,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze BTTS market for trading opportunity.
        """
        if not os.getenv('BTTS_STRATEGY_ENABLED', 'true').lower() == 'true':
            return None
        
        # Check if this is a BTTS market
        market_type = market.get('market_type', '')
        if market_type != 'btts':
            return None
        
        # Extract team names from question
        question = market.get('question', '')
        teams = self._extract_teams(question)
        
        if not teams:
            return None
        
        team1, team2 = teams
        sport = market.get('sport', 'football')
        current_price = market.get('current_price', 0.5)
        
        # Get prediction from team stats
        if self.team_stats:
            prediction = self.team_stats.predict_btts(team1, team2, sport)
        else:
            # Fallback: use simple heuristics
            prediction = self._simple_btts_prediction()
        
        if not prediction or not prediction.get('prediction'):
            return None
        
        confidence = prediction.get('confidence', 0.5)
        
        if confidence < self.min_confidence:
            return None
        
        # Determine signal
        predicted = prediction['prediction']  # 'yes' or 'no'
        
        if predicted == 'yes':
            signal_type = SignalType.BUY_YES
            rationale = f"BTTS likely ({prediction.get('btts_probability', 0.5)*100:.0f}% prob)"
        else:
            signal_type = SignalType.BUY_NO
            rationale = f"BTTS unlikely (clean sheet expected)"
        
        # Calculate targets
        if signal_type == SignalType.BUY_YES:
            target = min(current_price + 0.10, 0.88)
            stop = max(current_price - 0.07, 0.10)
        else:
            target = max(current_price - 0.10, 0.12)
            stop = min(current_price + 0.07, 0.90)
        
        # Position size based on confidence
        size = Config.MAX_POSITION_USD * 0.4 * (confidence / 0.65)
        
        self.signals_generated += 1
        self.last_signal_time = datetime.now()
        
        return TradeSignal(
            strategy=self.name,
            signal_type=signal_type,
            market_id=market.get('id', ''),
            market_question=question[:100],
            sport=sport,
            entry_price=current_price,
            target_price=target,
            stop_loss_price=stop,
            confidence=confidence,
            size_usd=size,
            rationale=rationale,
            metadata={
                'predicted': predicted,
                'btts_probability': prediction.get('btts_probability'),
                'team1': team1,
                'team2': team2,
                'team1_btts_rate': prediction.get('team1_btts_rate'),
                'team2_btts_rate': prediction.get('team2_btts_rate'),
                'source': prediction.get('source', 'unknown')
            }
        )
    
    def _extract_teams(self, question: str) -> Optional[tuple]:
        """Extract team names from question text."""
        # Try regex pattern first
        match = self.vs_pattern.search(question)
        if match:
            return (match.group(1).strip(), match.group(2).strip())
        
        # Fallback: split on common separators
        for sep in [' vs ', ' v ', ' vs. ', ' versus ', ' at ', ' @ ']:
            if sep in question.lower():
                parts = question.lower().split(sep, 1)
                if len(parts) == 2:
                    return (parts[0].strip(), parts[1].split('?')[0].strip())
        
        return None
    
    def _simple_btts_prediction(self) -> Dict:
        """Simple heuristic when stats provider not available."""
        # BTTS hits roughly 50-55% of the time in top leagues
        return {
            'prediction': 'yes',
            'confidence': 0.52,
            'btts_probability': 0.52,
            'source': 'heuristic'
        }
    
    def should_exit(self, position: Dict, current_price: float,
                    sports_data: Dict = None) -> tuple:
        """Check if position should be exited."""
        entry_price = position.get('entry_price', current_price)
        signal_type = position.get('signal_type', 'BUY_YES')
        
        # Calculate P&L
        if signal_type == 'BUY_YES':
            pnl_percent = (current_price - entry_price) / entry_price * 100
        else:
            pnl_percent = (entry_price - current_price) / entry_price * 100
        
        # Take profit at 10%
        if pnl_percent >= 10:
            return (True, "BTTS take profit")
        
        # Stop loss at 7%
        if pnl_percent <= -7:
            return (True, "BTTS stop loss")
        
        return (False, "")
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'enabled': os.getenv('BTTS_STRATEGY_ENABLED', 'true').lower() == 'true'
        }
