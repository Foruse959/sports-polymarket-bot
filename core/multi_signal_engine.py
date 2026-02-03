"""
Multi-Signal Execution Engine

Takes MULTIPLE trades simultaneously:
- Captures all opportunities meeting MIN_SIGNAL_CONFIDENCE criteria
- Groups signals by correlation to manage exposure
- Limits to MAX_SIGNALS_PER_SCAN trades per scan
- Integrates with existing strategy engine

Instead of taking only the best signal, this captures ALL qualified opportunities.
"""

import sys
import os
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from core.sports_strategies import TradeSignal


@dataclass
class SignalGroup:
    """Group of correlated signals."""
    group_id: str
    correlation_key: str
    signals: List[TradeSignal]
    total_exposure_usd: float
    avg_confidence: float


class MultiSignalEngine:
    """
    CAPTURES MULTIPLE OPPORTUNITIES SIMULTANEOUSLY
    
    Instead of taking only the best signal, this engine:
    - Takes ALL signals meeting MIN_SIGNAL_CONFIDENCE
    - Groups signals by correlation (same event, same sport)
    - Manages aggregate exposure across correlated positions
    - Limits total signals per scan to MAX_SIGNALS_PER_SCAN
    - Prioritizes uncorrelated opportunities for diversification
    
    Example: If 5 strategies all trigger on different events,
    this will execute all 5 trades instead of just the best one.
    """
    
    def __init__(self, config=None):
        """
        Initialize multi-signal engine.
        
        Args:
            config: Config class (defaults to Config)
        """
        self.config = config or Config
        
        # Multi-signal parameters
        self.min_signal_confidence = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.6'))
        self.max_signals_per_scan = int(os.getenv('MAX_SIGNALS_PER_SCAN', '5'))
        self.max_correlated_exposure_usd = float(os.getenv('MAX_CORRELATED_EXPOSURE_USD', '100'))
        self.diversification_bonus = float(os.getenv('DIVERSIFICATION_BONUS', '0.1'))
        
        # Correlation tracking
        self.event_exposure = defaultdict(float)  # event_id -> total exposure
        self.sport_exposure = defaultdict(float)  # sport -> total exposure
        
        # Stats tracking
        self.stats = {
            'total_scans': 0,
            'signals_evaluated': 0,
            'signals_executed': 0,
            'signals_rejected_confidence': 0,
            'signals_rejected_correlation': 0,
            'signals_rejected_limits': 0,
            'avg_signals_per_scan': 0.0,
            'max_signals_in_scan': 0
        }
        
        print(f"🎯 Multi-Signal Engine initialized:")
        print(f"   Min confidence: {self.min_signal_confidence:.1%}")
        print(f"   Max signals/scan: {self.max_signals_per_scan}")
        print(f"   Max correlated exposure: ${self.max_correlated_exposure_usd}")
    
    def select_signals(self, all_signals: List[TradeSignal], 
                      current_positions: List[Dict] = None) -> List[TradeSignal]:
        """
        Select multiple signals to execute simultaneously.
        
        Args:
            all_signals: All signals from strategies
            current_positions: List of current open positions
        
        Returns:
            List of signals to execute (may be multiple)
        """
        self.stats['total_scans'] += 1
        self.stats['signals_evaluated'] += len(all_signals)
        
        if not all_signals:
            return []
        
        # Update exposure tracking from current positions
        self._update_exposure(current_positions or [])
        
        # Filter by minimum confidence
        qualified_signals = self._filter_by_confidence(all_signals)
        
        if not qualified_signals:
            return []
        
        # Group signals by correlation
        signal_groups = self._group_by_correlation(qualified_signals)
        
        # Select signals respecting correlation limits
        selected_signals = self._select_diversified_signals(signal_groups)
        
        # Limit to max signals per scan
        if len(selected_signals) > self.max_signals_per_scan:
            selected_signals = selected_signals[:self.max_signals_per_scan]
            self.stats['signals_rejected_limits'] += (len(qualified_signals) - len(selected_signals))
        
        # Update stats
        self.stats['signals_executed'] += len(selected_signals)
        if len(selected_signals) > self.stats['max_signals_in_scan']:
            self.stats['max_signals_in_scan'] = len(selected_signals)
        
        # Recalculate average
        if self.stats['total_scans'] > 0:
            self.stats['avg_signals_per_scan'] = (
                self.stats['signals_executed'] / self.stats['total_scans']
            )
        
        if selected_signals:
            print(f"🎯 Multi-Signal: Selected {len(selected_signals)} signals from {len(all_signals)} candidates")
            self._print_signal_summary(selected_signals)
        
        return selected_signals
    
    def _filter_by_confidence(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """Filter signals by minimum confidence threshold."""
        qualified = []
        
        for signal in signals:
            confidence = getattr(signal, 'confidence', 0.5)
            
            if confidence >= self.min_signal_confidence:
                qualified.append(signal)
            else:
                self.stats['signals_rejected_confidence'] += 1
        
        return qualified
    
    def _group_by_correlation(self, signals: List[TradeSignal]) -> List[SignalGroup]:
        """
        Group signals by correlation.
        
        Signals are correlated if they are:
        - Same event (same condition_id)
        - Same sport at same time
        """
        groups_dict = defaultdict(list)
        
        for signal in signals:
            # Create correlation key
            correlation_key = self._get_correlation_key(signal)
            groups_dict[correlation_key].append(signal)
        
        # Convert to SignalGroup objects
        signal_groups = []
        for corr_key, group_signals in groups_dict.items():
            total_exposure = sum(getattr(s, 'size_usd', 50) for s in group_signals)
            avg_confidence = sum(getattr(s, 'confidence', 0.5) for s in group_signals) / len(group_signals)
            
            signal_groups.append(SignalGroup(
                group_id=f"group_{len(signal_groups)}",
                correlation_key=corr_key,
                signals=group_signals,
                total_exposure_usd=total_exposure,
                avg_confidence=avg_confidence
            ))
        
        return signal_groups
    
    def _get_correlation_key(self, signal: TradeSignal) -> str:
        """
        Generate correlation key for a signal.
        
        Signals with same correlation key are considered correlated.
        """
        # Same event = highly correlated
        market_id = getattr(signal, 'market_id', '')
        condition_id = getattr(signal, 'condition_id', '')
        
        if market_id:
            return f"event:{market_id}"
        if condition_id:
            return f"event:{condition_id}"
        
        # Fallback: sport + strategy
        sport = getattr(signal, 'sport', 'unknown')
        strategy = getattr(signal, 'strategy', 'unknown')
        return f"sport:{sport}:{strategy}"
    
    def _select_diversified_signals(self, signal_groups: List[SignalGroup]) -> List[TradeSignal]:
        """
        Select signals prioritizing diversification.
        
        Strategy:
        1. Take one signal from each uncorrelated group
        2. Prioritize by confidence within groups
        3. Respect correlation exposure limits
        """
        selected_signals = []
        
        # Sort groups by average confidence (descending)
        sorted_groups = sorted(signal_groups, key=lambda g: g.avg_confidence, reverse=True)
        
        for group in sorted_groups:
            # Check if we can add signals from this group
            existing_exposure = self._get_group_exposure(group)
            
            # Take best signal from group if within limits
            best_signal = max(group.signals, key=lambda s: getattr(s, 'confidence', 0.5))
            signal_size = getattr(best_signal, 'size_usd', 50)
            
            if existing_exposure + signal_size <= self.max_correlated_exposure_usd:
                selected_signals.append(best_signal)
                
                # Apply diversification bonus to uncorrelated signals
                if len(selected_signals) > 1:
                    if hasattr(best_signal, 'confidence'):
                        best_signal.confidence = min(1.0, best_signal.confidence * (1 + self.diversification_bonus))
            else:
                self.stats['signals_rejected_correlation'] += 1
        
        return selected_signals
    
    def _get_group_exposure(self, group: SignalGroup) -> float:
        """Get current exposure for a signal group."""
        # Extract event ID or sport from correlation key
        if group.correlation_key.startswith('event:'):
            event_id = group.correlation_key.split(':', 1)[1]
            return self.event_exposure.get(event_id, 0.0)
        elif group.correlation_key.startswith('sport:'):
            sport = group.correlation_key.split(':', 1)[1].split(':', 1)[0]
            return self.sport_exposure.get(sport, 0.0)
        
        return 0.0
    
    def _update_exposure(self, current_positions: List[Dict]):
        """Update exposure tracking from current positions."""
        # Reset exposure
        self.event_exposure.clear()
        self.sport_exposure.clear()
        
        for position in current_positions:
            # Track event exposure
            event_id = position.get('market_id') or position.get('condition_id', '')
            if event_id:
                self.event_exposure[event_id] += position.get('size_usd', 0)
            
            # Track sport exposure
            sport = position.get('sport', 'unknown')
            if sport:
                self.sport_exposure[sport] += position.get('size_usd', 0)
    
    def _print_signal_summary(self, signals: List[TradeSignal]):
        """Print summary of selected signals."""
        print(f"\n   Selected Signals:")
        for i, signal in enumerate(signals, 1):
            confidence = getattr(signal, 'confidence', 0.5)
            strategy = getattr(signal, 'strategy', 'unknown')
            market_id = getattr(signal, 'market_id', 'unknown')
            direction = getattr(signal, 'direction', 'unknown')
            
            print(f"   {i}. {strategy} - {direction} - conf: {confidence:.1%} - {market_id[:20]}...")
    
    def get_exposure_summary(self) -> Dict[str, Any]:
        """Get current exposure summary."""
        return {
            'event_exposures': dict(self.event_exposure),
            'sport_exposures': dict(self.sport_exposure),
            'total_events': len(self.event_exposure),
            'total_sports': len(self.sport_exposure)
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return dict(self.stats)
    
    def reset_stats(self):
        """Reset statistics."""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0


def main():
    """Test the multi-signal engine."""
    print("=" * 60)
    print("🎯 MULTI-SIGNAL EXECUTION ENGINE TEST")
    print("=" * 60)
    
    engine = MultiSignalEngine()
    
    # Create mock signals
    class MockSignal:
        def __init__(self, market_id, strategy, confidence, sport='nba'):
            self.market_id = market_id
            self.strategy = strategy
            self.confidence = confidence
            self.sport = sport
            self.direction = 'long'
            self.size_usd = 50
    
    mock_signals = [
        MockSignal('market_1', 'overreaction_fade', 0.75, 'nba'),
        MockSignal('market_2', 'draw_decay', 0.80, 'football'),
        MockSignal('market_3', 'run_reversion', 0.65, 'nba'),
        MockSignal('market_1', 'favorite_trap', 0.70, 'nba'),  # Correlated with first
        MockSignal('market_4', 'wicket_shock', 0.85, 'cricket'),
        MockSignal('market_5', 'volatility_scalp', 0.55, 'tennis'),  # Below threshold
    ]
    
    # Select signals
    selected = engine.select_signals(mock_signals)
    
    print(f"\n✅ Selected {len(selected)} signals from {len(mock_signals)} candidates")
    print(f"\n📊 Exposure Summary: {engine.get_exposure_summary()}")
    print(f"\n📈 Stats: {engine.get_stats()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
