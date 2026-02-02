"""
Self-Discovering Arbitrage Detector

Scans ALL markets for arbitrage opportunities:
1. YES + NO < $1.00 opportunities (riskless profit)
2. Resolved markets with winning shares < $1.00
3. Works with just Polymarket API (no external dependencies)
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class ArbitrageOpportunity:
    """Represents an arbitrage opportunity."""
    
    def __init__(self, market_id: str, market_question: str, opportunity_type: str,
                 yes_price: float, no_price: float, edge_cents: float, 
                 optimal_size_usd: float, rationale: str):
        self.market_id = market_id
        self.market_question = market_question
        self.opportunity_type = opportunity_type  # 'yes_no_arb' or 'resolved_arb'
        self.yes_price = yes_price
        self.no_price = no_price
        self.edge_cents = edge_cents
        self.optimal_size_usd = optimal_size_usd
        self.rationale = rationale
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            'market_id': self.market_id,
            'market_question': self.market_question,
            'opportunity_type': self.opportunity_type,
            'yes_price': self.yes_price,
            'no_price': self.no_price,
            'edge_cents': self.edge_cents,
            'optimal_size_usd': self.optimal_size_usd,
            'rationale': self.rationale,
            'timestamp': self.timestamp.isoformat()
        }


class ArbitrageDetector:
    """
    NEVER STOPS LOOKING FOR ARBITRAGE
    
    Self-discovering arbitrage detection that:
    - Scans ALL markets for YES + NO < $1.00 opportunities
    - Scans resolved markets for winning shares < $1.00
    - Works with just Polymarket API (no external dependencies)
    - Auto-calculates optimal position sizes based on available balance
    """
    
    def __init__(self):
        self.min_edge_cents = Config.ARB_MIN_EDGE_CENTS
        self.scan_resolved = Config.ARB_SCAN_RESOLVED
        self.opportunities_found_today = 0
        self.last_scan_time = None
    
    def scan_markets(self, markets: List[Dict], available_balance: float = None) -> List[ArbitrageOpportunity]:
        """
        Scan all markets for arbitrage opportunities.
        
        Args:
            markets: List of market data from Polymarket
            available_balance: Optional balance for position sizing
        
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        for market in markets:
            # Check YES + NO arbitrage
            yes_no_opp = self._check_yes_no_arbitrage(market, available_balance)
            if yes_no_opp:
                opportunities.append(yes_no_opp)
            
            # Check resolved market arbitrage
            if self.scan_resolved:
                resolved_opp = self._check_resolved_arbitrage(market, available_balance)
                if resolved_opp:
                    opportunities.append(resolved_opp)
        
        self.opportunities_found_today += len(opportunities)
        self.last_scan_time = datetime.now()
        
        if opportunities:
            print(f"🎯 Arbitrage: Found {len(opportunities)} opportunities (Total today: {self.opportunities_found_today})")
        
        return opportunities
    
    def _check_yes_no_arbitrage(self, market: Dict, available_balance: Optional[float]) -> Optional[ArbitrageOpportunity]:
        """
        Check if YES + NO prices sum to less than $1.00.
        This is a riskless arbitrage - buy both, guaranteed profit.
        """
        try:
            # Get YES and NO prices
            yes_price = self._get_price(market, 'YES')
            no_price = self._get_price(market, 'NO')
            
            if yes_price is None or no_price is None:
                return None
            
            # Calculate edge
            total_cost = yes_price + no_price
            edge_cents = (1.0 - total_cost) * 100
            
            # Check if edge exceeds minimum
            if edge_cents < self.min_edge_cents:
                return None
            
            # Calculate optimal position size
            optimal_size = self._calculate_optimal_size(edge_cents, available_balance)
            
            market_id = market.get('id', market.get('condition_id', ''))
            market_question = market.get('question', market.get('title', 'Unknown'))
            
            rationale = (
                f"YES+NO=${total_cost:.3f} < $1.00. "
                f"Buy both sides for ${total_cost:.3f}, redeem for $1.00. "
                f"Guaranteed profit: {edge_cents:.1f}¢ per dollar invested."
            )
            
            print(f"🎯 Arbitrage: Found YES+NO=${total_cost:.3f} opportunity ({edge_cents:.1f}¢ edge)")
            
            return ArbitrageOpportunity(
                market_id=market_id,
                market_question=market_question,
                opportunity_type='yes_no_arb',
                yes_price=yes_price,
                no_price=no_price,
                edge_cents=edge_cents,
                optimal_size_usd=optimal_size,
                rationale=rationale
            )
            
        except Exception as e:
            # Silently skip on error - don't crash scanner
            return None
    
    def _check_resolved_arbitrage(self, market: Dict, available_balance: Optional[float]) -> Optional[ArbitrageOpportunity]:
        """
        Check if market is resolved with winning shares trading < $1.00.
        """
        try:
            # Check if market is resolved
            is_resolved = market.get('resolved', False) or market.get('closed', False)
            if not is_resolved:
                return None
            
            # Get winning outcome
            winning_outcome = market.get('winning_outcome')
            if not winning_outcome:
                return None
            
            # Get current price of winning outcome
            winning_price = self._get_price(market, winning_outcome)
            if winning_price is None or winning_price >= 0.99:
                return None
            
            # Calculate edge
            edge_cents = (1.0 - winning_price) * 100
            
            if edge_cents < self.min_edge_cents:
                return None
            
            # Calculate optimal position size
            optimal_size = self._calculate_optimal_size(edge_cents, available_balance)
            
            market_id = market.get('id', market.get('condition_id', ''))
            market_question = market.get('question', market.get('title', 'Unknown'))
            
            rationale = (
                f"Market resolved, {winning_outcome} won. "
                f"Winning shares trading at ${winning_price:.3f}. "
                f"Buy now, redeem for $1.00. "
                f"Guaranteed profit: {edge_cents:.1f}¢ per share."
            )
            
            print(f"🎯 Arbitrage: Found resolved market with {winning_outcome}=${winning_price:.3f} ({edge_cents:.1f}¢ edge)")
            
            return ArbitrageOpportunity(
                market_id=market_id,
                market_question=market_question,
                opportunity_type='resolved_arb',
                yes_price=winning_price if winning_outcome == 'YES' else 1.0,
                no_price=winning_price if winning_outcome == 'NO' else 1.0,
                edge_cents=edge_cents,
                optimal_size_usd=optimal_size,
                rationale=rationale
            )
            
        except Exception as e:
            # Silently skip on error
            return None
    
    def _get_price(self, market: Dict, outcome: str) -> Optional[float]:
        """Extract price for given outcome from market data."""
        try:
            # Try multiple possible data structures
            if 'current_price' in market:
                price = market['current_price']
                if isinstance(price, dict):
                    return price.get(outcome.lower(), price.get(outcome.upper()))
                return price
            
            if 'tokens' in market:
                for token in market['tokens']:
                    if token.get('outcome', '').upper() == outcome.upper():
                        return float(token.get('price', 0))
            
            if 'outcomes' in market:
                outcomes = market['outcomes']
                if isinstance(outcomes, dict):
                    return outcomes.get(outcome.lower(), outcomes.get(outcome.upper()))
            
            # Direct price keys
            if outcome.upper() == 'YES':
                return market.get('yes_price', market.get('price'))
            elif outcome.upper() == 'NO':
                return market.get('no_price', 1.0 - market.get('price', 0.5))
            
            return None
            
        except Exception:
            return None
    
    def _calculate_optimal_size(self, edge_cents: float, available_balance: Optional[float]) -> float:
        """
        Calculate optimal position size based on edge and available balance.
        Uses Kelly Criterion with conservative scaling.
        """
        if available_balance is None or available_balance <= 0:
            # Default to max position size from config
            return Config.MAX_POSITION_USD
        
        # For arbitrage, we can be aggressive since it's risk-free
        # Use 25% of available balance or max position, whichever is smaller
        kelly_fraction = 0.25
        optimal_size = available_balance * kelly_fraction
        
        # Cap at max position size
        return min(optimal_size, Config.MAX_POSITION_USD)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get arbitrage detector statistics."""
        return {
            'opportunities_found_today': self.opportunities_found_today,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'min_edge_cents': self.min_edge_cents,
            'scan_resolved': self.scan_resolved
        }
