"""
Favorite Flip Strategy

The exact strategy mentioned from Twitter/X:
"When Polymarket reevaluates odds for favorite, bot buys underdog"

Logic:
1. Track price history for each market
2. Identify the favorite (higher probability outcome)
3. Detect when favorite drops significantly (5%+ from recent high)
4. Buy the underdog at discounted price
5. Higher confidence for larger drops

This captures overreactions where the favorite drops too much,
making the underdog temporarily undervalued.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config_aggressive import AggressiveConfig


class PriceHistory:
    """Track price history for a market."""
    
    def __init__(self, market_id: str):
        self.market_id = market_id
        self.prices = []  # List of (timestamp, price) tuples
        self.high_water_mark = 0.0
        self.hwm_timestamp = None
    
    def add_price(self, price: float, timestamp: datetime = None):
        """Add a price observation."""
        timestamp = timestamp or datetime.now()
        
        self.prices.append((timestamp, price))
        
        # Update high water mark
        if price > self.high_water_mark:
            self.high_water_mark = price
            self.hwm_timestamp = timestamp
        
        # Keep only recent history (lookback period)
        cutoff = datetime.now() - timedelta(minutes=AggressiveConfig.FAVORITE_FLIP_LOOKBACK_MINUTES)
        self.prices = [(t, p) for t, p in self.prices if t > cutoff]
    
    def get_recent_high(self, minutes: int = None) -> Optional[float]:
        """Get highest price in recent period."""
        if not self.prices:
            return None
        
        if minutes is None:
            minutes = AggressiveConfig.FAVORITE_FLIP_LOOKBACK_MINUTES
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent = [p for t, p in self.prices if t > cutoff]
        
        return max(recent) if recent else None
    
    def get_drop_from_high(self, current_price: float) -> float:
        """Calculate drop from recent high as percentage."""
        recent_high = self.get_recent_high()
        
        if not recent_high or recent_high == 0:
            return 0.0
        
        drop_percent = ((recent_high - current_price) / recent_high) * 100
        
        return max(0, drop_percent)  # Only positive drops


class FavoriteFlipStrategy:
    """
    Favorite Flip Strategy
    
    Detects when favorite drops significantly and buys underdog.
    """
    
    def __init__(self):
        self.name = "favorite_flip"
        self.price_histories = {}  # market_id -> {outcome_id -> PriceHistory}
        
        self.min_drop_percent = AggressiveConfig.FAVORITE_FLIP_MIN_DROP_PERCENT
        self.lookback_minutes = AggressiveConfig.FAVORITE_FLIP_LOOKBACK_MINUTES
        
        # Stats
        self.signals_generated = 0
        self.markets_tracked = 0
        
        print(f"📉 Favorite Flip Strategy initialized")
        print(f"   Min drop: {self.min_drop_percent}%")
        print(f"   Lookback: {self.lookback_minutes} min")
    
        def update_prices(self, markets: List[Dict]):
        """Update price history for all markets."""
        for market in markets:
            try:
                market_id = market.get('id', market.get('condition_id', ''))
                
                # Get current price - handle different market structures
                price = None
                
                # Try direct price field first
                if 'current_price' in market:
                    price = market['current_price']
                elif 'price' in market:
                    price = market['price']
                
                # Try outcomes array
                elif 'outcomes' in market:
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        # FIX: Handle both dict and string outcomes
                        if isinstance(outcome, dict):
                            outcome_price = outcome.get('price', 0)
                            if outcome_price:
                                price = outcome_price
                                break
                        elif isinstance(outcome, str):
                            # Outcome is just a string name - skip
                            continue
                
                # Try tokens array
                elif 'tokens' in market:
                    tokens = market.get('tokens', [])
                    if tokens and isinstance(tokens[0], dict):
                        price = tokens[0].get('price', 0)
                
                # Fallback to outcomePrices
                if price is None and 'outcomePrices' in market:
                    prices = market.get('outcomePrices', [])
                    if prices:
                        try:
                            price = float(prices[0]) if prices[0] else 0
                        except:
                            price = 0
                
                if price and market_id:
                    self._record_price(market_id, float(price))
                    
            except Exception as e:
                # Skip this market on error, don't crash
                continue
    
    def scan_for_signals(self, markets: List[Dict]) -> List[Dict]:
        """
        Scan markets for favorite flip opportunities.
        
        Args:
            markets: List of current market states
        
        Returns:
            List of trading signals
        """
        signals = []
        
        for market in markets:
            market_id = market.get('id') or market.get('market_id')
            
            if not market_id or market_id not in self.price_histories:
                continue
            
            # Detect favorite flip
            signal = self._check_favorite_flip(market)
            
            if signal:
                signals.append(signal)
                self.signals_generated += 1
        
        return signals
    
    def _check_favorite_flip(self, market: Dict) -> Optional[Dict]:
        """
        Check if market has favorite flip opportunity.
        
        Returns signal dict if opportunity found, None otherwise.
        """
        market_id = market.get('id') or market.get('market_id')
        outcomes = market.get('outcomes', [])
        
        if len(outcomes) != 2:
            # Only works for binary markets
            return None
        
        # Identify favorite and underdog by current price
        outcome_a, outcome_b = outcomes[0], outcomes[1]
        
        price_a = outcome_a.get('price', outcome_a.get('last_price', 0.5))
        price_b = outcome_b.get('price', outcome_b.get('last_price', 0.5))
        
        if price_a > price_b:
            favorite = outcome_a
            underdog = outcome_b
            favorite_price = price_a
            underdog_price = price_b
        else:
            favorite = outcome_b
            underdog = outcome_a
            favorite_price = price_b
            underdog_price = price_a
        
        # Get favorite's price history
        favorite_id = favorite.get('id') or favorite.get('token_id', 'unknown')
        
        if favorite_id not in self.price_histories[market_id]:
            return None
        
        favorite_history = self.price_histories[market_id][favorite_id]
        
        # Calculate drop from recent high
        drop_percent = favorite_history.get_drop_from_high(favorite_price)
        
        if drop_percent < self.min_drop_percent:
            # Not enough drop
            return None
        
        # Calculate confidence (higher for larger drops)
        # 5% drop = 0.6 confidence
        # 10% drop = 0.8 confidence
        # 15%+ drop = 0.9 confidence
        confidence = min(0.9, 0.6 + (drop_percent - self.min_drop_percent) / 20)
        
        # Create signal to buy underdog
        underdog_id = underdog.get('id') or underdog.get('token_id', 'unknown')
        
        signal = {
            'strategy': self.name,
            'market_id': market_id,
            'market_question': market.get('question', market.get('market_question', 'Unknown')),
            'sport': market.get('sport', 'unknown'),
            'signal_type': 'BUY',
            'entry_price': underdog_price,
            'target_price': underdog_price * 1.3,  # 30% profit target
            'stop_loss_price': underdog_price * 0.85,  # 15% stop
            'confidence': confidence,
            'rationale': f"Favorite flip: Favorite dropped {drop_percent:.1f}% from recent high, buying underdog at {underdog_price:.3f}",
            'metadata': {
                'favorite_outcome': favorite.get('name', 'Unknown'),
                'underdog_outcome': underdog.get('name', 'Unknown'),
                'favorite_drop_percent': drop_percent,
                'favorite_current': favorite_price,
                'favorite_recent_high': favorite_history.high_water_mark,
                'underdog_id': underdog_id
            }
        }
        
        print(f"📉 Favorite Flip signal: {market.get('question', 'Unknown')[:50]}...")
        print(f"   Favorite dropped {drop_percent:.1f}% → Buying underdog @ {underdog_price:.3f}")
        print(f"   Confidence: {confidence:.1%}")
        
        return signal
    
    def get_stats(self) -> Dict:
        """Get strategy statistics."""
        return {
            'name': self.name,
            'enabled': AggressiveConfig.FAVORITE_FLIP_ENABLED,
            'signals_generated': self.signals_generated,
            'markets_tracked': self.markets_tracked,
            'min_drop_percent': self.min_drop_percent,
            'lookback_minutes': self.lookback_minutes
        }
