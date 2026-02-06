"""
Pre-Game Value Strategy

Trades on sports markets BEFORE games start based on:
- Historical win rates vs market odds
- Team form (last 5 matches)
- Home/away advantages
"""

import os
import sys
from typing import Dict, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal, SignalType


class PreGameValueStrategy(BaseStrategy):
    """
    Pre-Game Value Strategy
    
    Finds value in markets before games start:
    - Home team underpriced (home advantage not fully priced)
    - Team form not reflected in odds
    - Historical head-to-head advantages
    """
    
    def __init__(self, team_stats_provider=None):
        super().__init__(
            name="Pre-Game Value",
            description="Find value in pre-game markets using historical data"
        )
        self.team_stats_provider = team_stats_provider
        self.min_edge = 0.05  # 5% edge required
        
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """Analyze pre-game market for value opportunities."""
        
        # Only trade pre-game markets
        if market.get('is_live', False):
            return None
        
        current_price = market.get('current_price', 0.5)
        question = market.get('question', '').lower()
        
        # Skip if already close to 50/50 (no clear value)
        if 0.45 <= current_price <= 0.55:
            return None
        
        # Try to extract team names from question
        teams = self._extract_teams(question)
        if not teams:
            return None
        
        team1, team2 = teams
        
        # Get historical success rates if available
        fair_value = self._estimate_fair_value(team1, team2, market)
        
        if fair_value is None:
            # Fallback: Use market sentiment heuristics
            fair_value = self._heuristic_fair_value(current_price, market)
        
        edge = fair_value - current_price
        
        # BUY if underpriced (edge positive)
        if edge >= self.min_edge:
            confidence = min(0.80, 0.55 + edge * 2)
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.BUY,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=current_price,
                target_price=fair_value,
                stop_loss_price=current_price * 0.85,
                confidence=confidence,
                size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.35),
                rationale=f"Pre-game value: {current_price*100:.0f}% → fair {fair_value*100:.0f}% (+{edge*100:.1f}% edge)",
                metadata={
                    'fair_value': fair_value,
                    'edge': edge,
                    'teams': teams
                }
            )
        
        # SELL if overpriced (edge negative, meaning current > fair)
        if edge <= -self.min_edge:
            confidence = min(0.80, 0.55 + abs(edge) * 2)
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.SELL,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=current_price,
                target_price=fair_value,
                stop_loss_price=min(0.98, current_price * 1.08),
                confidence=confidence,
                size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.35),
                rationale=f"Pre-game fade: {current_price*100:.0f}% → fair {fair_value*100:.0f}% ({edge*100:.1f}% overpriced)",
                metadata={
                    'fair_value': fair_value,
                    'edge': edge,
                    'teams': teams
                }
            )
        
        return None
    
    def _extract_teams(self, question: str) -> Optional[tuple]:
        """Extract team names from question."""
        # Common patterns: "Will X beat Y", "X vs Y", "X to win against Y"
        import re
        
        patterns = [
            r"will (.+?) (?:beat|defeat|win against) (.+?)[\?\.]",
            r"(.+?) vs\.? (.+?)[\?\.]",
            r"(.+?) to win (?:against|vs) (.+?)[\?\.]",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        
        return None
    
    def _estimate_fair_value(self, team1: str, team2: str, market: Dict) -> Optional[float]:
        """Estimate fair value using team stats."""
        if not self.team_stats_provider:
            return None
        
        try:
            sport = market.get('sport', 'football')
            
            stats1 = self.team_stats_provider.get_team_stats(team1, sport)
            stats2 = self.team_stats_provider.get_team_stats(team2, sport)
            
            if not stats1 or not stats2:
                return None
            
            # Calculate expected win rate based on form
            form1 = stats1.get('form', 0.5)
            form2 = stats2.get('form', 0.5)
            
            # Simple model: relative form comparison
            fair_value = form1 / (form1 + form2) if (form1 + form2) > 0 else 0.5
            
            # Adjust for home advantage (+5%)
            if 'home' in market.get('question', '').lower():
                fair_value += 0.05
            
            return min(0.95, max(0.05, fair_value))
            
        except Exception:
            return None
    
    def _heuristic_fair_value(self, current_price: float, market: Dict) -> float:
        """Estimate fair value using market heuristics."""
        # Regression to mean - extreme prices often overcorrect
        if current_price > 0.85:
            # High favorites are often overpriced
            return current_price - 0.08
        elif current_price < 0.15:
            # Extreme underdogs are often underpriced
            return current_price + 0.06
        else:
            # Mid-range: small pull toward 50%
            return current_price + (0.5 - current_price) * 0.15
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> tuple:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        entry_time = position.get('entry_time')
        
        # Check if game has started (should exit pre-game trades)
        if sports_data.get('game', {}).get('is_live', False):
            return True, "Game started - exiting pre-game position"
        
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        if profit_percent >= 10:
            return True, f"Pre-game take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -8:
            return True, f"Pre-game stop loss ({profit_percent:.1f}%)"
        
        return False, ""
