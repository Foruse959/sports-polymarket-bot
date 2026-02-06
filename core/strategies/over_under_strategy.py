"""
Over/Under Strategy

Trades on over/under goal/point markets using team statistics.
Works for football (goals), NBA (points), NFL (points).
"""

import os
import re
from typing import Dict, Optional
from datetime import datetime

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class OverUnderStrategy(BaseStrategy):
    """
    Over/Under Market Strategy.
    
    Uses team scoring history to predict if game will go over or under.
    
    ALWAYS-ON: Works with any over/under market!
    """
    
    def __init__(self, team_stats_provider=None):
        """
        Initialize strategy.
        
        Args:
            team_stats_provider: TeamStatsProvider instance
        """
        super().__init__(
            name="Over/Under",
            description="Trades on over/under goal/point markets using team statistics"
        )
        self.team_stats = team_stats_provider
        
        # Minimum confidence to trade
        self.min_confidence = float(os.getenv('OVER_UNDER_MIN_CONFIDENCE', '0.55'))
        
        # Minimum edge (expected vs line)
        self.min_edge = float(os.getenv('OVER_UNDER_MIN_EDGE', '0.5'))
        
        # Stats
        self.signals_generated = 0
        self.last_signal_time = None
        
        # Team name extraction patterns
        self.vs_pattern = re.compile(r'(.+?)\s+(?:vs?\.?|versus|at|@)\s+(.+?)(?:\s*[-:,\?]|$)', re.IGNORECASE)
        
        # Team name extraction patterns
        self.vs_pattern = re.compile(r'(.+?)\s+(?:vs?\.?|versus|at|@)\s+(.+?)(?:\s*[-:,\?]|$)', re.IGNORECASE)
    
    def analyze(self, market: Dict, sports_data: Dict = None,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze over/under market for trading opportunity.
        """
        if not os.getenv('OVER_UNDER_STRATEGY_ENABLED', 'true').lower() == 'true':
            return None
        
        # Check if this is an over/under market
        market_type = market.get('market_type', '')
        if market_type != 'over_under':
            return None
        
        # Get the line
        line = market.get('line')
        if not line:
            return None
        
        # Get the side (over or under)
        side = market.get('over_under_side')
        
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
            prediction = self.team_stats.predict_over_under(team1, team2, line, sport)
        else:
            # Fallback: use simple heuristics
            prediction = self._simple_over_under_prediction(line, sport)
        
        if not prediction or not prediction.get('prediction'):
            return None
        
        confidence = prediction.get('confidence', 0.5)
        
        if confidence < self.min_confidence:
            return None
        
        # Check edge
        expected_total = prediction.get('expected_total', line)
        edge = abs(expected_total - line)
        
        if edge < self.min_edge:
            return None
        
        # Determine signal based on market side and prediction
        predicted_side = prediction['prediction']  # 'over' or 'under'
        
        # If market is for "over" and we predict over -> BUY YES
        # If market is for "over" and we predict under -> BUY NO
        # Similar logic for "under" markets
        if side == 'over':
            if predicted_side == 'over':
                signal_type = SignalType.BUY_YES
                rationale = f"Predicting Over {line} (expected: {expected_total:.2f})"
            else:
                signal_type = SignalType.BUY_NO
                rationale = f"Predicting Under {line} (expected: {expected_total:.2f})"
        elif side == 'under':
            if predicted_side == 'under':
                signal_type = SignalType.BUY_YES
                rationale = f"Predicting Under {line} (expected: {expected_total:.2f})"
            else:
                signal_type = SignalType.BUY_NO
                rationale = f"Predicting Over {line} (expected: {expected_total:.2f})"
        else:
            # Unknown side, assume market is "will it go over?"
            if predicted_side == 'over':
                signal_type = SignalType.BUY_YES
            else:
                signal_type = SignalType.BUY_NO
            rationale = f"Predicting {predicted_side} {line} (expected: {expected_total:.2f})"
        
        # Calculate targets
        if signal_type == SignalType.BUY_YES:
            target = min(current_price + 0.12, 0.90)
            stop = max(current_price - 0.08, 0.08)
        else:
            target = max(current_price - 0.12, 0.10)
            stop = min(current_price + 0.08, 0.92)
        
        # Position size based on confidence
        size = Config.MAX_POSITION_USD * 0.4 * (confidence / 0.7)
        
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
                'line': line,
                'expected_total': expected_total,
                'predicted_side': predicted_side,
                'team1': team1,
                'team2': team2,
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
    
    def _simple_over_under_prediction(self, line: float, sport: str) -> Dict:
        """Simple heuristic when stats provider not available."""
        # Sport-specific averages
        averages = {
            'football': 2.7,  # Goals per game
            'nba': 225,       # Points per game
            'nfl': 46,        # Points per game
            'cricket': 320    # Runs per game (T20)
        }
        
        avg = averages.get(sport, 2.5)
        
        # Compare line to average
        if sport in ['nba', 'nfl']:
            diff = (avg - line) / 10  # Normalize
        else:
            diff = avg - line
        
        if diff > 0.3:
            return {
                'prediction': 'over',
                'confidence': 0.55 + min(abs(diff) * 0.1, 0.15),
                'expected_total': avg,
                'source': 'heuristic'
            }
        elif diff < -0.3:
            return {
                'prediction': 'under',
                'confidence': 0.55 + min(abs(diff) * 0.1, 0.15),
                'expected_total': avg,
                'source': 'heuristic'
            }
        
        return {
            'prediction': 'over' if diff > 0 else 'under',
            'confidence': 0.50,
            'expected_total': avg,
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
        
        # Take profit at 12%
        if pnl_percent >= 12:
            return (True, "Over/Under take profit")
        
        # Stop loss at 8%
        if pnl_percent <= -8:
            return (True, "Over/Under stop loss")
        
        return (False, "")
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'signals_generated': self.signals_generated,
            'last_signal': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'enabled': os.getenv('OVER_UNDER_STRATEGY_ENABLED', 'true').lower() == 'true'
        }
