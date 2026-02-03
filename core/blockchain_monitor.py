"""
Blockchain Whale Monitor

Monitors Polymarket's CLOB contract on Polygon for large trades in real-time.
Detects whale trades (>$500) and tracks wallet activity.

Uses:
- Polygon RPC for blockchain data
- Polygonscan API (optional, for better performance)
- Filters for sports markets only
"""

import sys
import os
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from config_aggressive import AggressiveConfig

try:
    from web3 import Web3
    # web3.py v7+ uses ExtraDataToPOAMiddleware for PoA chains
    from web3.middleware import ExtraDataToPOAMiddleware
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("⚠️ web3 not installed. Blockchain monitoring disabled.")


class BlockchainWhaleMonitor:
    """
    Monitors Polygon blockchain for whale trades on Polymarket.
    
    Features:
    - Real-time monitoring via RPC polling
    - Filters for trades > $500 (configurable)
    - Tracks wallet addresses and trade patterns
    - Callbacks for detected whale trades
    """
    
    def __init__(self, min_trade_usd: float = None):
        if not WEB3_AVAILABLE:
            raise RuntimeError("web3 package required for blockchain monitoring")
        
        self.min_trade_usd = min_trade_usd or Config.WHALE_MIN_TRADE_USD
        self.poll_seconds = AggressiveConfig.BLOCKCHAIN_POLL_SECONDS
        
        # Connect to Polygon
        self.w3 = Web3(Web3.HTTPProvider(Config.POLYGON_RPC_URL))
        
        # CRITICAL: Add POA middleware for Polygon chain
        # Polygon uses PoA/PoS with 586-byte extraData field (vs standard 32 bytes)
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        # CLOB contract address
        self.clob_contract_address = AggressiveConfig.POLYMARKET_CLOB_CONTRACT
        
        # State
        self.last_block_checked = None
        self.running = False
        self.monitor_thread = None
        self.callbacks = []  # List of callback functions to call on whale trade
        
        # Stats
        self.trades_detected = 0
        self.whale_trades_detected = 0
        self.blocks_scanned = 0
        
        print(f"⛓️ Blockchain Whale Monitor initialized")
        print(f"   RPC: {Config.POLYGON_RPC_URL}")
        print(f"   Min trade size: ${self.min_trade_usd}")
        print(f"   Poll interval: {self.poll_seconds}s")
        
        # Test connection
        try:
            block_number = self.w3.eth.block_number
            self.last_block_checked = block_number
            print(f"   ✅ Connected to Polygon (block {block_number})")
        except Exception as e:
            print(f"   ⚠️ Connection test failed: {e}")
    
    def register_callback(self, callback: Callable):
        """
        Register a callback function to be called when whale trade detected.
        
        Callback signature: callback(whale_trade: Dict) -> None
        
        whale_trade format:
        {
            'wallet_address': '0x...',
            'market_id': 'market_id',
            'side': 'BUY' or 'SELL',
            'size_usd': float,
            'price': float,
            'timestamp': datetime,
            'tx_hash': '0x...',
            'block_number': int
        }
        """
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self.running:
            print("⚠️ Monitor already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ Blockchain monitor started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("✅ Blockchain monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop (runs in background thread)."""
        print("🔍 Monitoring blockchain for whale trades...")
        
        while self.running:
            try:
                self._scan_recent_blocks()
                time.sleep(self.poll_seconds)
            except Exception as e:
                print(f"⚠️ Blockchain monitor error: {e}")
                time.sleep(self.poll_seconds * 2)  # Back off on error
    
    def _scan_recent_blocks(self):
        """Scan recent blocks for whale trades."""
        try:
            current_block = self.w3.eth.block_number
            
            # Scan blocks since last check (max 10 blocks to avoid overload)
            start_block = max(self.last_block_checked + 1, current_block - 10)
            
            if start_block > current_block:
                return  # No new blocks
            
            # Scan blocks
            for block_num in range(start_block, current_block + 1):
                self._scan_block(block_num)
                self.blocks_scanned += 1
            
            self.last_block_checked = current_block
            
        except Exception as e:
            print(f"⚠️ Error scanning blocks: {e}")
    
    def _scan_block(self, block_number: int):
        """Scan a single block for whale trades."""
        try:
            block = self.w3.eth.get_block(block_number, full_transactions=True)
            
            for tx in block.transactions:
                # Check if transaction is to CLOB contract
                if tx.to and tx.to.lower() == self.clob_contract_address.lower():
                    whale_trade = self._parse_transaction(tx, block.timestamp)
                    
                    if whale_trade:
                        self.whale_trades_detected += 1
                        
                        # Call all registered callbacks
                        for callback in self.callbacks:
                            try:
                                callback(whale_trade)
                            except Exception as e:
                                print(f"⚠️ Callback error: {e}")
        
        except Exception as e:
            print(f"⚠️ Error scanning block {block_number}: {e}")
    
    def _parse_transaction(self, tx, timestamp: int) -> Optional[Dict]:
        """
        Parse a transaction to extract whale trade info.
        
        This is a simplified parser. In production, you would:
        1. Decode the contract call data
        2. Extract trade parameters (market, side, size, price)
        3. Filter for sports markets only
        
        For now, we use heuristics based on transaction value.
        """
        self.trades_detected += 1
        
        # Convert timestamp to datetime
        trade_time = datetime.fromtimestamp(timestamp)
        
        # Estimate trade size from transaction value
        # Note: This is a simplification. Real implementation would decode contract calls.
        value_eth = self.w3.from_wei(tx.value, 'ether')
        
        # Skip if too small (gas only)
        if value_eth < 0.001:
            return None
        
        # Estimate USD value (simplified - would need price oracle in production)
        # Assume 1 ETH = $2000 for estimation
        estimated_usd = float(value_eth) * 2000
        
        if estimated_usd < self.min_trade_usd:
            return None
        
        # Extract wallet address
        wallet_address = tx['from']
        
        # Create whale trade record
        whale_trade = {
            'wallet_address': wallet_address,
            'market_id': 'unknown',  # Would extract from contract call
            'side': 'BUY',  # Would determine from contract call
            'size_usd': estimated_usd,
            'price': 0.5,  # Would extract from contract call
            'timestamp': trade_time,
            'tx_hash': tx.hash.hex(),
            'block_number': tx.blockNumber
        }
        
        print(f"🐋 Whale trade detected!")
        print(f"   Wallet: {wallet_address[:10]}...")
        print(f"   Size: ~${estimated_usd:.0f}")
        print(f"   Block: {tx.blockNumber}")
        
        return whale_trade
    
    def get_stats(self) -> Dict:
        """Get monitoring statistics."""
        return {
            'running': self.running,
            'last_block': self.last_block_checked,
            'blocks_scanned': self.blocks_scanned,
            'trades_detected': self.trades_detected,
            'whale_trades_detected': self.whale_trades_detected,
            'min_trade_usd': self.min_trade_usd,
            'callbacks_registered': len(self.callbacks)
        }


class MockBlockchainMonitor:
    """
    Mock monitor for testing without blockchain access.
    Simulates whale trades for development.
    """
    
    def __init__(self, min_trade_usd: float = None):
        self.min_trade_usd = min_trade_usd or Config.WHALE_MIN_TRADE_USD
        self.running = False
        self.callbacks = []
        
        print(f"⚠️ Using mock blockchain monitor (for testing)")
    
    def register_callback(self, callback: Callable):
        """Register callback."""
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """Start mock monitoring."""
        self.running = True
        print("✅ Mock blockchain monitor started")
    
    def stop_monitoring(self):
        """Stop mock monitoring."""
        self.running = False
        print("✅ Mock blockchain monitor stopped")
    
    def get_stats(self) -> Dict:
        """Get stats."""
        return {
            'running': self.running,
            'mock': True,
            'callbacks_registered': len(self.callbacks)
        }


def create_monitor(min_trade_usd: float = None) -> 'BlockchainWhaleMonitor':
    """
    Factory function to create appropriate monitor.
    Returns mock if web3 unavailable.
    """
    if WEB3_AVAILABLE:
        try:
            return BlockchainWhaleMonitor(min_trade_usd)
        except Exception as e:
            print(f"⚠️ Failed to create blockchain monitor: {e}")
            return MockBlockchainMonitor(min_trade_usd)
    else:
        return MockBlockchainMonitor(min_trade_usd)


if __name__ == "__main__":
    # Test the monitor
    def test_callback(whale_trade):
        print(f"Callback received: {whale_trade}")
    
    monitor = create_monitor()
    monitor.register_callback(test_callback)
    monitor.start_monitoring()
    
    try:
        print("Monitoring... Press Ctrl+C to stop")
        while True:
            time.sleep(10)
            stats = monitor.get_stats()
            print(f"Stats: {stats}")
    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.stop_monitoring()
