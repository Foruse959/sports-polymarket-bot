"""
Price History Tracker

Tracks price changes between scans to enable:
- Previous price detection for OverreactionFade
- Momentum calculation
- Velocity and acceleration metrics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass


@dataclass
class PricePoint:
    """Single price observation."""
    price: float
    timestamp: datetime
    volume: float = 0


class PriceHistory:
    """
    Tracks price history for all markets.
    
    Features:
    - Stores last N price points per market
    - Calculates previous_price, velocity, momentum
    - Thread-safe with simple dict operations
    """
    
    def __init__(self, max_history: int = 20, max_age_minutes: int = 60):
        """
        Initialize price history tracker.
        
        Args:
            max_history: Maximum price points to store per market
            max_age_minutes: Drop prices older than this
        """
        self.max_history = max_history
        self.max_age = timedelta(minutes=max_age_minutes)
        
        # market_id -> deque of PricePoint
        self._history: Dict[str, deque] = {}
        
        # Stats
        self.total_updates = 0
        self.markets_tracked = 0
    
    def update(self, market_id: str, price: float, volume: float = 0) -> None:
        """
        Record a new price observation for a market.
        
        Args:
            market_id: Polymarket market ID
            price: Current price (0-1)
            volume: Optional volume
        """
        if market_id not in self._history:
            self._history[market_id] = deque(maxlen=self.max_history)
            self.markets_tracked += 1
        
        point = PricePoint(
            price=price,
            timestamp=datetime.now(),
            volume=volume
        )
        self._history[market_id].append(point)
        self.total_updates += 1
        
        # Clean old entries
        self._clean_old(market_id)
    
    def _clean_old(self, market_id: str) -> None:
        """Remove price points older than max_age."""
        if market_id not in self._history:
            return
            
        cutoff = datetime.now() - self.max_age
        history = self._history[market_id]
        
        # Remove from front while too old
        while history and history[0].timestamp < cutoff:
            history.popleft()
    
    def get_previous_price(self, market_id: str) -> Optional[float]:
        """
        Get the previous price for a market (before current).
        
        Returns None if no previous price available.
        """
        if market_id not in self._history:
            return None
            
        history = self._history[market_id]
        if len(history) < 2:
            return None
            
        return history[-2].price
    
    def get_price_change(self, market_id: str) -> Optional[float]:
        """
        Get price change since last observation.
        
        Returns: Change in price points (e.g., 0.05 = 5% change)
        """
        if market_id not in self._history:
            return None
            
        history = self._history[market_id]
        if len(history) < 2:
            return None
            
        return history[-1].price - history[-2].price
    
    def get_velocity(self, market_id: str, periods: int = 3) -> Optional[float]:
        """
        Get price velocity (average change per period).
        
        Args:
            market_id: Market to check
            periods: Number of periods to calculate over
            
        Returns: Average price change per period
        """
        if market_id not in self._history:
            return None
            
        history = list(self._history[market_id])
        if len(history) < periods + 1:
            return None
        
        # Get last N changes
        changes = []
        for i in range(-1, -periods - 1, -1):
            if abs(i) < len(history):
                changes.append(history[i].price - history[i-1].price)
        
        if not changes:
            return None
            
        return sum(changes) / len(changes)
    
    def get_momentum(self, market_id: str, periods: int = 5) -> Optional[Tuple[str, float]]:
        """
        Get momentum direction and strength.
        
        Returns:
            ('bullish', strength) - consistent upward movement
            ('bearish', strength) - consistent downward movement
            ('neutral', strength) - no clear direction
            None if not enough data
        """
        if market_id not in self._history:
            return None
            
        history = list(self._history[market_id])
        if len(history) < periods + 1:
            return None
        
        # Count direction of changes
        up_moves = 0
        down_moves = 0
        total_change = 0
        
        for i in range(-1, -min(periods + 1, len(history)), -1):
            if abs(i) >= len(history):
                break
            change = history[i].price - history[i-1].price
            total_change += abs(change)
            if change > 0.001:  # Small threshold to ignore noise
                up_moves += 1
            elif change < -0.001:
                down_moves += 1
        
        total_moves = up_moves + down_moves
        if total_moves == 0:
            return ('neutral', 0.0)
        
        # Calculate direction and strength
        if up_moves > down_moves * 1.5:
            return ('bullish', up_moves / periods)
        elif down_moves > up_moves * 1.5:
            return ('bearish', down_moves / periods)
        else:
            return ('neutral', abs(up_moves - down_moves) / periods)
    
    def get_range(self, market_id: str, periods: int = 10) -> Optional[Tuple[float, float]]:
        """
        Get price range (min, max) over last N periods.
        """
        if market_id not in self._history:
            return None
            
        history = list(self._history[market_id])
        if len(history) < 2:
            return None
        
        recent = [p.price for p in history[-periods:]]
        return (min(recent), max(recent))
    
    def is_at_extreme(self, market_id: str, periods: int = 10) -> Optional[str]:
        """
        Check if current price is at recent extreme.
        
        Returns: 'high', 'low', or None
        """
        range_data = self.get_range(market_id, periods)
        if not range_data:
            return None
            
        history = self._history[market_id]
        if not history:
            return None
            
        current = history[-1].price
        low, high = range_data
        
        # Within 1% of extreme
        if abs(current - high) < 0.01:
            return 'high'
        elif abs(current - low) < 0.01:
            return 'low'
        return None
    
    def enrich_market(self, market: Dict) -> Dict:
        """
        Add price history data to market dict.
        
        Adds:
        - previous_price
        - price_change
        - price_velocity
        - momentum_direction
        - momentum_strength
        """
        market_id = market.get('id', '')
        
        if market_id:
            market['previous_price'] = self.get_previous_price(market_id)
            market['price_change'] = self.get_price_change(market_id)
            market['price_velocity'] = self.get_velocity(market_id)
            
            momentum = self.get_momentum(market_id)
            if momentum:
                market['momentum_direction'] = momentum[0]
                market['momentum_strength'] = momentum[1]
            
            market['price_extreme'] = self.is_at_extreme(market_id)
        
        return market
    
    def enrich_markets(self, markets: List[Dict]) -> List[Dict]:
        """Enrich all markets with price history data."""
        return [self.enrich_market(m) for m in markets]
    
    def get_stats(self) -> Dict:
        """Get tracker statistics."""
        return {
            'markets_tracked': self.markets_tracked,
            'total_updates': self.total_updates,
            'avg_history_length': sum(len(h) for h in self._history.values()) / max(1, len(self._history))
        }
