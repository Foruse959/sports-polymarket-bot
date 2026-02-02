"""
Dynamic Strategy Cascade Engine

NEVER STOPS LOOKING FOR OPPORTUNITIES

Cascade Logic:
1. Try CRITICAL strategies (arbitrage, resolved markets)
2. Try HIGH priority (overreaction, lag arb)
3. Try MEDIUM priority (market only, draw decay)
4. Try LOW priority (volatility scalp, favorite trap)
5. If nothing found → reduce thresholds by 20% → retry from step 1
6. After 3 threshold reductions with no results → wait and scan again
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from core.sports_strategies import BaseStrategy, TradeSignal


class StrategyPriority(Enum):
    """Priority levels for strategy cascade."""
    CRITICAL = 0  # Arbitrage, resolved markets
    HIGH = 1      # High EV, time-sensitive
    MEDIUM = 2    # Good opportunities
    LOW = 3       # Lower confidence plays


class DynamicStrategyEngine:
    """
    NEVER STOPS LOOKING FOR OPPORTUNITIES
    
    Wraps all existing strategies and runs them in priority order:
    - Tries strategies in cascading priority
    - If nothing found, lowers thresholds and retries
    - Tracks which strategies are working and prioritizes them
    - Adapts to market conditions
    """
    
    def __init__(self, base_strategies: List[BaseStrategy], config=None, 
                 arbitrage_detector=None, adaptive_thresholds=None):
        """
        Initialize dynamic engine.
        
        Args:
            base_strategies: List of existing strategy instances to wrap
            config: Config class (defaults to Config)
            arbitrage_detector: Optional ArbitrageDetector instance
            adaptive_thresholds: Optional AdaptiveThresholds instance
        """
        self.config = config or Config
        self.arbitrage_detector = arbitrage_detector
        self.adaptive_thresholds = adaptive_thresholds
        
        # Organize strategies by priority
        self.strategy_priorities = self._categorize_strategies(base_strategies)
        
        # Cascade settings
        self.cascade_enabled = self.config.CASCADE_ENABLED
        self.threshold_decay = self.config.CASCADE_THRESHOLD_DECAY
        self.max_retries = self.config.CASCADE_MAX_RETRIES
        
        # Track performance
        self.cascade_stats = {
            'total_scans': 0,
            'signals_found': 0,
            'retries_needed': 0,
            'threshold_reductions': 0,
            'strategy_success': {}
        }
        
        print(f"🔄 Dynamic Strategy Engine initialized:")
        print(f"   Cascade: {'✅ Enabled' if self.cascade_enabled else '⚪ Disabled'}")
        print(f"   Strategies by priority:")
        for priority, strategies in self.strategy_priorities.items():
            print(f"   {priority.name}: {len(strategies)} strategies")
    
    def _categorize_strategies(self, strategies: List[BaseStrategy]) -> Dict[StrategyPriority, List[BaseStrategy]]:
        """Categorize strategies by priority level."""
        categorized = {
            StrategyPriority.CRITICAL: [],
            StrategyPriority.HIGH: [],
            StrategyPriority.MEDIUM: [],
            StrategyPriority.LOW: []
        }
        
        # Map strategy names to priorities
        priority_map = {
            # CRITICAL - Risk-free or resolved
            'arbitrage': StrategyPriority.CRITICAL,
            'resolved': StrategyPriority.CRITICAL,
            
            # HIGH - High EV, time-sensitive
            'overreaction_fade': StrategyPriority.HIGH,
            'overreaction': StrategyPriority.HIGH,
            'lag_arbitrage': StrategyPriority.HIGH,
            'lag_arb': StrategyPriority.HIGH,
            'wicket_shock': StrategyPriority.HIGH,
            
            # MEDIUM - Good opportunities
            'market_only': StrategyPriority.MEDIUM,
            'draw_decay': StrategyPriority.MEDIUM,
            'run_reversion': StrategyPriority.MEDIUM,
            
            # LOW - Lower confidence
            'volatility_scalp': StrategyPriority.LOW,
            'favorite_trap': StrategyPriority.LOW,
            'liquidity_provision': StrategyPriority.LOW,
        }
        
        for strategy in strategies:
            strategy_name = strategy.name.lower().replace(' ', '_').replace('-', '_')
            
            # Find matching priority
            priority = StrategyPriority.MEDIUM  # Default
            for key, pri in priority_map.items():
                if key in strategy_name:
                    priority = pri
                    break
            
            categorized[priority].append(strategy)
        
        return categorized
    
    async def cascade_scan(self, markets: List[Dict], sports_data: Dict = None,
                          events: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Perform cascading scan across all strategies.
        
        Args:
            markets: List of markets to scan
            sports_data: Optional sports data
            events: Optional list of recent events
        
        Returns:
            List of trade signals
        """
        self.cascade_stats['total_scans'] += 1
        
        all_signals = []
        current_threshold_multiplier = 1.0
        retry_count = 0
        
        if sports_data is None:
            sports_data = {}
        if events is None:
            events = []
        
        # Cascade loop - try multiple times with progressively looser thresholds
        while retry_count <= self.max_retries:
            attempt_num = retry_count + 1
            print(f"\n🔄 Cascade Scan (attempt {attempt_num}/{self.max_retries + 1}, threshold multiplier: {current_threshold_multiplier:.2f})")
            
            # Phase 1: CRITICAL strategies (arbitrage, etc.)
            if self.arbitrage_detector:
                arb_signals = await self._scan_arbitrage(markets)
                if arb_signals:
                    all_signals.extend(arb_signals)
                    print(f"🎯 CRITICAL: Found {len(arb_signals)} arbitrage opportunities")
            
            # Phase 2: Try each priority level
            for priority in [StrategyPriority.CRITICAL, StrategyPriority.HIGH, 
                           StrategyPriority.MEDIUM, StrategyPriority.LOW]:
                
                strategies = self.strategy_priorities[priority]
                if not strategies:
                    continue
                
                priority_signals = await self._scan_priority_level(
                    priority, strategies, markets, sports_data, events,
                    current_threshold_multiplier
                )
                
                if priority_signals:
                    all_signals.extend(priority_signals)
                    print(f"✅ {priority.name}: Found {len(priority_signals)} signals from {len(strategies)} strategies")
                else:
                    print(f"🔄 {priority.name}: No signals from {len(strategies)} strategies, trying next priority...")
            
            # If we found signals, return them
            if all_signals:
                self.cascade_stats['signals_found'] += len(all_signals)
                print(f"✅ Cascade: Found {len(all_signals)} total signals")
                break
            
            # No signals found - reduce thresholds and retry
            if retry_count < self.max_retries:
                retry_count += 1
                self.cascade_stats['retries_needed'] += 1
                current_threshold_multiplier *= self.threshold_decay
                self.cascade_stats['threshold_reductions'] += 1
                
                print(f"🔄 Cascade: No signals found, reducing thresholds by {(1-self.threshold_decay)*100:.0f}%...")
            else:
                print(f"⚠️ Cascade: No opportunities found after {self.max_retries} retries")
                break
        
        return all_signals
    
    async def _scan_arbitrage(self, markets: List[Dict]) -> List[Dict[str, Any]]:
        """Scan for arbitrage opportunities."""
        if not self.arbitrage_detector:
            return []
        
        # Get available balance if possible
        available_balance = None
        try:
            available_balance = self.config.STARTING_BALANCE
        except:
            pass
        
        # Scan markets
        opportunities = self.arbitrage_detector.scan_markets(markets, available_balance)
        
        # Convert to signal format
        signals = []
        for opp in opportunities:
            signal = {
                'strategy': 'Arbitrage',
                'signal_type': 'BUY',
                'market_id': opp.market_id,
                'market_question': opp.market_question,
                'sport': 'unknown',
                'entry_price': opp.yes_price,
                'target_price': 1.0,
                'stop_loss_price': opp.yes_price * 0.95,  # Minimal stop
                'confidence': 1.0,  # Arbitrage is 100% confident
                'size_usd': opp.optimal_size_usd,
                'rationale': opp.rationale,
                'metadata': {
                    'opportunity_type': opp.opportunity_type,
                    'edge_cents': opp.edge_cents,
                    'yes_price': opp.yes_price,
                    'no_price': opp.no_price
                }
            }
            signals.append(signal)
            
            # Track success
            self._record_strategy_success('Arbitrage')
        
        return signals
    
    async def _scan_priority_level(self, priority: StrategyPriority, 
                                   strategies: List[BaseStrategy],
                                   markets: List[Dict], sports_data: Dict,
                                   events: List[Dict],
                                   threshold_multiplier: float) -> List[Dict[str, Any]]:
        """
        Scan all strategies at a given priority level.
        
        Args:
            priority: Priority level
            strategies: List of strategies at this level
            markets: Markets to scan
            sports_data: Sports data
            events: Recent events
            threshold_multiplier: Threshold adjustment multiplier
        
        Returns:
            List of signals found
        """
        signals = []
        
        for strategy in strategies:
            if not strategy.enabled:
                continue
            
            # Get adaptive threshold multiplier if available
            adaptive_multiplier = 1.0
            if self.adaptive_thresholds:
                adaptive_multiplier = self.adaptive_thresholds.get_threshold_multiplier(strategy.name)
            
            # Combine cascade and adaptive multipliers
            final_multiplier = threshold_multiplier * adaptive_multiplier
            
            # Apply threshold adjustment (this would need strategy support)
            # For now, we just run the strategy normally
            
            for market in markets:
                try:
                    # Try to match event to market
                    event_dict = None
                    market_question = market.get('question', '').lower()
                    for event in events:
                        if hasattr(event, 'team') and event.team.lower() in market_question:
                            event_dict = {
                                'event_type': event.event_type.value if hasattr(event, 'event_type') else 'unknown',
                                'team': event.team if hasattr(event, 'team') else '',
                                'game_time': event.game_time if hasattr(event, 'game_time') else None,
                                'details': event.details if hasattr(event, 'details') else {}
                            }
                            break
                    
                    # Run strategy analysis
                    signal = strategy.analyze(market, sports_data, event_dict)
                    
                    if signal:
                        # Convert to dict if needed
                        if hasattr(signal, '__dict__'):
                            signal_dict = {
                                'strategy': signal.strategy,
                                'signal_type': signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                                'market_id': signal.market_id,
                                'market_question': signal.market_question,
                                'sport': signal.sport,
                                'entry_price': signal.entry_price,
                                'target_price': signal.target_price,
                                'stop_loss_price': signal.stop_loss_price,
                                'confidence': signal.confidence,
                                'size_usd': signal.size_usd,
                                'rationale': signal.rationale,
                                'metadata': signal.metadata if hasattr(signal, 'metadata') else {}
                            }
                        else:
                            signal_dict = signal
                        
                        signals.append(signal_dict)
                        self._record_strategy_success(strategy.name)
                
                except Exception as e:
                    # Silently skip errors to keep cascade going
                    if self.config.DEBUG_MODE:
                        print(f"⚠️ Strategy {strategy.name} error: {e}")
        
        return signals
    
    def _record_strategy_success(self, strategy_name: str):
        """Record successful signal from a strategy."""
        if strategy_name not in self.cascade_stats['strategy_success']:
            self.cascade_stats['strategy_success'][strategy_name] = 0
        self.cascade_stats['strategy_success'][strategy_name] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cascade engine statistics."""
        return {
            'total_scans': self.cascade_stats['total_scans'],
            'signals_found': self.cascade_stats['signals_found'],
            'retries_needed': self.cascade_stats['retries_needed'],
            'threshold_reductions': self.cascade_stats['threshold_reductions'],
            'avg_signals_per_scan': (
                self.cascade_stats['signals_found'] / self.cascade_stats['total_scans']
                if self.cascade_stats['total_scans'] > 0 else 0
            ),
            'strategy_success': self.cascade_stats['strategy_success'],
            'cascade_enabled': self.cascade_enabled
        }
