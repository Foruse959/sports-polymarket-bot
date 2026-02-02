"""
Auto-Discovering Whale Tracker

CRITICAL: Works with ZERO configured wallets!

If no wallets configured:
1. Monitor ALL trades on sports markets
2. Track wallets making trades > $500
3. Build performance profile for each wallet
4. Auto-promote wallets with >65% win rate to "whale" status
5. Start copying their trades

The bot DISCOVERS profitable wallets on its own!
"""

import sys
import os
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class WalletProfile:
    """Profile for a tracked wallet."""
    
    def __init__(self, address: str, source: str = 'discovered'):
        self.address = address
        self.source = source  # 'configured' or 'discovered'
        self.trades = []
        self.total_volume = 0.0
        self.wins = 0
        self.losses = 0
        self.pending = 0
        self.total_pnl = 0.0
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()
        self.is_whale = source == 'configured'  # Configured wallets start as whales
        self.promoted_at = datetime.now() if self.is_whale else None
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate."""
        total_completed = self.wins + self.losses
        if total_completed == 0:
            return 0.0
        return self.wins / total_completed
    
    @property
    def total_trades(self) -> int:
        """Total number of trades."""
        return len(self.trades)
    
    @property
    def avg_trade_size(self) -> float:
        """Average trade size in USD."""
        if not self.trades:
            return 0.0
        return self.total_volume / len(self.trades)
    
    def should_promote_to_whale(self, min_trades: int, min_win_rate: float, min_volume: float) -> bool:
        """Check if wallet should be promoted to whale status."""
        if self.is_whale:
            return False
        
        completed_trades = self.wins + self.losses
        if completed_trades < min_trades:
            return False
        
        if self.win_rate < min_win_rate:
            return False
        
        if self.total_volume < min_volume:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'address': self.address,
            'source': self.source,
            'is_whale': self.is_whale,
            'total_trades': self.total_trades,
            'total_volume': self.total_volume,
            'win_rate': self.win_rate,
            'wins': self.wins,
            'losses': self.losses,
            'pending': self.pending,
            'total_pnl': self.total_pnl,
            'avg_trade_size': self.avg_trade_size,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'promoted_at': self.promoted_at.isoformat() if self.promoted_at else None
        }


class WhaleTracker:
    """
    SELF-DISCOVERING WHALE TRACKER
    
    Works with ZERO configured wallets!
    
    If no wallets configured:
    1. Monitor ALL trades on sports markets
    2. Track wallets making trades > $500
    3. Build performance profile for each wallet
    4. Auto-promote wallets with >65% win rate to "whale" status
    5. Start copying their trades
    
    The bot DISCOVERS profitable wallets on its own!
    """
    
    def __init__(self):
        self.configured_wallets = set(Config.WHALE_WALLETS)  # From env (optional)
        self.wallet_profiles: Dict[str, WalletProfile] = {}
        
        # Initialize configured wallets
        for wallet in self.configured_wallets:
            self.wallet_profiles[wallet] = WalletProfile(wallet, source='configured')
        
        # Settings
        self.auto_discover = Config.WHALE_AUTO_DISCOVER
        self.min_trade_usd = Config.WHALE_MIN_TRADE_USD
        self.min_win_rate = Config.WHALE_MIN_WIN_RATE
        self.copy_delay_seconds = Config.WHALE_COPY_DELAY_SECONDS
        
        # Stats
        self.whales_discovered = 0
        self.total_wallets_tracked = len(self.configured_wallets)
        self.trades_observed = 0
        
        print(f"🐋 Whale Tracker initialized:")
        print(f"   Configured wallets: {len(self.configured_wallets)}")
        print(f"   Auto-discovery: {'✅ Enabled' if self.auto_discover else '⚪ Disabled'}")
        print(f"   Min trade size: ${self.min_trade_usd}")
        print(f"   Min win rate for promotion: {self.min_win_rate*100:.0f}%")
    
    def track_trade(self, wallet_address: str, market_id: str, side: str, 
                   size_usd: float, price: float, timestamp: datetime = None) -> bool:
        """
        Track a trade from any wallet.
        
        Args:
            wallet_address: Wallet that made the trade
            market_id: Market ID
            side: 'BUY' or 'SELL'
            size_usd: Trade size in USD
            price: Entry price
            timestamp: Trade timestamp
        
        Returns:
            True if this is a whale trade (should be copied)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.trades_observed += 1
        
        # Skip small trades if auto-discovery is enabled
        if self.auto_discover and size_usd < self.min_trade_usd:
            # Only track if wallet is already being tracked
            if wallet_address not in self.wallet_profiles:
                return False
        
        # Get or create wallet profile
        if wallet_address not in self.wallet_profiles:
            self.wallet_profiles[wallet_address] = WalletProfile(wallet_address, source='discovered')
            self.total_wallets_tracked += 1
        
        profile = self.wallet_profiles[wallet_address]
        
        # Record trade
        trade_data = {
            'market_id': market_id,
            'side': side,
            'size_usd': size_usd,
            'price': price,
            'timestamp': timestamp,
            'status': 'pending'
        }
        profile.trades.append(trade_data)
        profile.total_volume += size_usd
        profile.pending += 1
        profile.last_seen = timestamp
        
        # Check if should promote to whale
        if self.auto_discover and profile.should_promote_to_whale(
            min_trades=10,
            min_win_rate=self.min_win_rate,
            min_volume=self.min_trade_usd * 10
        ):
            profile.is_whale = True
            profile.promoted_at = datetime.now()
            self.whales_discovered += 1
            print(f"🐋 Whale Discovery: Wallet {wallet_address[:10]}... promoted to whale status!")
            print(f"   Win rate: {profile.win_rate*100:.1f}% | Trades: {profile.total_trades} | Volume: ${profile.total_volume:.0f}")
        
        # Return True if this wallet is a whale and trade should be copied
        return profile.is_whale
    
    def update_trade_outcome(self, wallet_address: str, market_id: str, pnl: float):
        """
        Update a trade's outcome.
        
        Args:
            wallet_address: Wallet address
            market_id: Market ID
            pnl: Profit/loss on the trade
        """
        if wallet_address not in self.wallet_profiles:
            return
        
        profile = self.wallet_profiles[wallet_address]
        
        # Find and update the trade
        for trade in profile.trades:
            if trade['market_id'] == market_id and trade['status'] == 'pending':
                trade['status'] = 'closed'
                trade['pnl'] = pnl
                
                # Update stats
                profile.pending -= 1
                profile.total_pnl += pnl
                
                if pnl > 0:
                    profile.wins += 1
                else:
                    profile.losses += 1
                
                break
    
    def get_whale_wallets(self) -> List[str]:
        """Get list of all whale wallet addresses."""
        return [addr for addr, profile in self.wallet_profiles.items() if profile.is_whale]
    
    def get_whale_profiles(self) -> List[Dict[str, Any]]:
        """Get profiles of all whale wallets."""
        return [
            profile.to_dict() 
            for profile in self.wallet_profiles.values() 
            if profile.is_whale
        ]
    
    def get_top_performers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing wallets by win rate (min 5 completed trades)."""
        candidates = [
            profile 
            for profile in self.wallet_profiles.values() 
            if (profile.wins + profile.losses) >= 5
        ]
        
        sorted_profiles = sorted(candidates, key=lambda p: p.win_rate, reverse=True)
        return [p.to_dict() for p in sorted_profiles[:limit]]
    
    def should_copy_trade(self, wallet_address: str) -> bool:
        """
        Check if trades from this wallet should be copied.
        
        Args:
            wallet_address: Wallet to check
        
        Returns:
            True if wallet is a whale and trades should be copied
        """
        if wallet_address not in self.wallet_profiles:
            return False
        
        profile = self.wallet_profiles[wallet_address]
        
        # Only copy if:
        # 1. Wallet is marked as whale
        # 2. Wallet is still active (traded in last 7 days)
        if not profile.is_whale:
            return False
        
        days_since_last_trade = (datetime.now() - profile.last_seen).days
        if days_since_last_trade > 7:
            return False
        
        # If discovered whale, check if performance has degraded
        if profile.source == 'discovered':
            # Demote if win rate drops below threshold
            if profile.win_rate < self.min_win_rate * 0.8:  # 20% buffer
                profile.is_whale = False
                print(f"⚠️ Whale demoted: {wallet_address[:10]}... (win rate dropped to {profile.win_rate*100:.1f}%)")
                return False
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get whale tracker statistics."""
        active_whales = len([w for w in self.get_whale_wallets() 
                            if self.should_copy_trade(w)])
        
        return {
            'configured_wallets': len(self.configured_wallets),
            'discovered_whales': self.whales_discovered,
            'active_whales': active_whales,
            'total_wallets_tracked': self.total_wallets_tracked,
            'trades_observed': self.trades_observed,
            'auto_discovery': self.auto_discover,
            'min_trade_usd': self.min_trade_usd,
            'min_win_rate': self.min_win_rate
        }
    
    def get_wallet_profile(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Get profile for a specific wallet."""
        if wallet_address not in self.wallet_profiles:
            return None
        return self.wallet_profiles[wallet_address].to_dict()
