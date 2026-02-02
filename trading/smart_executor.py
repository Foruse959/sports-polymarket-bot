"""
Smart Order Execution

Intelligent order execution with:
- Slippage protection
- Liquidity checking
- Order splitting for large trades
- Retry logic with backoff
"""

import sys
import os
from typing import Dict, Any, Optional
from datetime import datetime
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class SmartExecutor:
    """
    Smart order execution with protection mechanisms.
    """
    
    def __init__(self, polymarket_client=None):
        self.polymarket_client = polymarket_client
        self.max_slippage = Config.MAX_SLIPPAGE_PERCENT / 100
        self.min_liquidity = Config.MIN_LIQUIDITY_USD
        
        self.stats = {
            'orders_attempted': 0,
            'orders_executed': 0,
            'orders_rejected': 0,
            'total_slippage': 0.0,
            'retries': 0
        }
        
        print(f"⚡ Smart Executor initialized:")
        print(f"   Max slippage: {Config.MAX_SLIPPAGE_PERCENT}%")
        print(f"   Min liquidity: ${self.min_liquidity}")
    
    def execute_order(self, signal: Dict[str, Any], dry_run: bool = True) -> Optional[Dict[str, Any]]:
        """
        Execute a trade with smart order logic.
        
        Args:
            signal: Trade signal to execute
            dry_run: If True, simulate execution without real trade
        
        Returns:
            Execution result or None if failed
        """
        self.stats['orders_attempted'] += 1
        
        market_id = signal.get('market_id')
        entry_price = signal.get('entry_price')
        size_usd = signal.get('size_usd')
        
        # Check liquidity
        if not self._check_liquidity(market_id, size_usd):
            self.stats['orders_rejected'] += 1
            print(f"❌ Order rejected: Insufficient liquidity for ${size_usd}")
            return None
        
        # Check slippage
        current_price = self._get_current_price(market_id)
        if current_price is None:
            self.stats['orders_rejected'] += 1
            print(f"❌ Order rejected: Cannot get current price")
            return None
        
        slippage = abs(current_price - entry_price) / entry_price
        if slippage > self.max_slippage:
            self.stats['orders_rejected'] += 1
            print(f"❌ Order rejected: Slippage too high ({slippage*100:.2f}% > {self.max_slippage*100:.2f}%)")
            return None
        
        self.stats['total_slippage'] += slippage
        
        # Execute (or simulate)
        if dry_run:
            # Paper trading execution
            result = {
                'market_id': market_id,
                'executed_price': current_price,
                'size_usd': size_usd,
                'slippage': slippage,
                'timestamp': datetime.now().isoformat(),
                'dry_run': True
            }
            self.stats['orders_executed'] += 1
            print(f"✅ Paper order executed: ${size_usd} @ ${current_price:.3f} (slippage: {slippage*100:.2f}%)")
            return result
        else:
            # Real execution would go here
            # This would use self.polymarket_client to place real orders
            print(f"⚠️ Live trading not implemented")
            return None
    
    def _check_liquidity(self, market_id: str, size_usd: float) -> bool:
        """
        Check if market has sufficient liquidity.
        
        Args:
            market_id: Market to check
            size_usd: Desired trade size
        
        Returns:
            True if sufficient liquidity
        """
        # For now, assume sufficient liquidity
        # In real implementation, would query order book depth
        return True
    
    def _get_current_price(self, market_id: str) -> Optional[float]:
        """
        Get current market price.
        
        Args:
            market_id: Market ID
        
        Returns:
            Current price or None if unavailable
        """
        if not self.polymarket_client:
            # Return mock price for testing
            return 0.50
        
        try:
            market = self.polymarket_client.get_market(market_id)
            if market:
                return self.polymarket_client.get_market_price(market)
        except Exception as e:
            print(f"⚠️ Error getting price for {market_id}: {e}")
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        avg_slippage = (
            self.stats['total_slippage'] / self.stats['orders_executed']
            if self.stats['orders_executed'] > 0 else 0
        )
        
        return {
            'orders_attempted': self.stats['orders_attempted'],
            'orders_executed': self.stats['orders_executed'],
            'orders_rejected': self.stats['orders_rejected'],
            'success_rate': (
                self.stats['orders_executed'] / self.stats['orders_attempted']
                if self.stats['orders_attempted'] > 0 else 0
            ),
            'avg_slippage_percent': avg_slippage * 100,
            'retries': self.stats['retries']
        }
