"""
Market Type Detector

Classifies Polymarket sports markets into types:
- Winner: "Will X win?"
- Over/Under: "Over/under 2.5 goals"
- BTTS: "Both teams to score"
- Handicap: "Team A -1.5"
"""

from enum import Enum
from typing import Dict, Optional, Tuple
import re


class MarketType(Enum):
    """Market type classification."""
    WINNER = "winner"
    OVER_UNDER = "over_under"
    BTTS = "btts"
    HANDICAP = "handicap"
    PROP = "prop"
    OTHER = "other"


class MarketTypeDetector:
    """
    Detect market type from question text.
    
    Used to route markets to appropriate strategies.
    """
    
    def __init__(self):
        # Keywords for each market type
        self.over_under_keywords = [
            'over', 'under', 'total goals', 'total points', 'total score',
            'o/u', 'over/under', 'more than', 'less than', 'fewer than',
            'o0.5', 'o1.5', 'o2.5', 'o3.5', 'o4.5', 'o5.5',
            'u0.5', 'u1.5', 'u2.5', 'u3.5', 'u4.5', 'u5.5',
            'combined score', 'combined points', 'match total',
            'goals in', 'points in', 'at least', 'exceed',
            'over 100', 'over 150', 'over 200', 'over 250'  # NBA totals
        ]
        
        self.btts_keywords = [
            'both teams to score', 'btts', 'both teams score',
            'each team to score', 'both sides to score',
            'both teams scorers', 'ggs', 'goal goal',
            'both score', 'each team scores',
            'both teams will score', 'will both teams score'
        ]
        
        self.handicap_keywords = [
            'handicap', 'spread', 'point spread', 
            '-0.5', '-1.5', '-2.5', '-3.5', '-4.5',
            '+0.5', '+1.5', '+2.5', '+3.5', '+4.5',
            'asian handicap', 'ah', 'covers'
        ]
        
        self.prop_keywords = [
            'first goal', 'first scorer', 'anytime scorer',
            'hat trick', 'yellow card', 'red card',
            'corner', 'penalty', 'own goal',
            'clean sheet', 'shutout', 'assists',
            'mvp', 'player of', 'man of the match'
        ]
        
        # Patterns for extracting numbers from over/under
        self.over_under_pattern = re.compile(
            r'(?:over|under|o|u)\s*(\d+\.?\d*)',
            re.IGNORECASE
        )
    
    def detect(self, market: Dict) -> MarketType:
        """
        Detect market type from market data.
        
        Args:
            market: Market dict with 'question' and optionally 'description'
            
        Returns:
            MarketType enum value
        """
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        combined = f"{question} {description}"
        
        # Check BTTS first (more specific)
        if any(kw in combined for kw in self.btts_keywords):
            return MarketType.BTTS
        
        # Check Over/Under
        if any(kw in combined for kw in self.over_under_keywords):
            return MarketType.OVER_UNDER
        
        # Check Handicap
        if any(kw in combined for kw in self.handicap_keywords):
            return MarketType.HANDICAP
        
        # Check Props
        if any(kw in combined for kw in self.prop_keywords):
            return MarketType.PROP
        
        # Default to Winner (most common)
        return MarketType.WINNER
    
    def extract_line(self, market: Dict) -> Optional[float]:
        """
        Extract the line number from over/under markets.
        
        Args:
            market: Market dict
            
        Returns:
            Line number (e.g., 2.5 for "Over 2.5 goals") or None
        """
        question = market.get('question', '')
        description = market.get('description', '')
        combined = f"{question} {description}"
        
        match = self.over_under_pattern.search(combined)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        return None
    
    def extract_side(self, market: Dict) -> Optional[str]:
        """
        Extract whether market is "over" or "under".
        
        Returns:
            'over', 'under', or None
        """
        question = market.get('question', '').lower()
        
        # Check for explicit over/under
        if 'over' in question and 'under' not in question:
            return 'over'
        elif 'under' in question and 'over' not in question:
            return 'under'
        
        return None
    
    def get_market_info(self, market: Dict) -> Dict:
        """
        Get comprehensive market type information.
        
        Returns dict with:
        - market_type: MarketType enum
        - line: float (for over/under)
        - side: 'over' or 'under'
        """
        return {
            'market_type': self.detect(market),
            'line': self.extract_line(market),
            'side': self.extract_side(market)
        }
    
    def enrich_market(self, market: Dict) -> Dict:
        """Add market type info to market dict."""
        info = self.get_market_info(market)
        market['market_type'] = info['market_type'].value
        market['line'] = info['line']
        market['over_under_side'] = info['side']
        return market
    
    def enrich_markets(self, markets: list) -> list:
        """Add market type info to all markets."""
        return [self.enrich_market(m) for m in markets]
