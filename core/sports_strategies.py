"""
Sports Quant Trading Strategies

8 high-EV strategies for exploiting market inefficiencies in sports prediction markets.
These strategies trade in and out of positions - NOT hold-to-settlement betting.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class SignalType(Enum):
    """Trading signal types."""
    BUY = 'BUY'
    SELL = 'SELL'
    HOLD = 'HOLD'
    EXIT = 'EXIT'


@dataclass
class TradeSignal:
    """Represents a trading signal from a strategy."""
    strategy: str
    signal_type: SignalType
    market_id: str
    market_question: str
    sport: str
    entry_price: float
    target_price: float
    stop_loss_price: float
    confidence: float  # 0.0 to 1.0
    size_usd: float
    rationale: str
    metadata: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def expected_profit_percent(self) -> float:
        """Calculate expected profit percentage."""
        if self.signal_type == SignalType.BUY:
            return ((self.target_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - self.target_price) / self.entry_price) * 100
    
    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio."""
        if self.signal_type == SignalType.BUY:
            reward = self.target_price - self.entry_price
            risk = self.entry_price - self.stop_loss_price
        else:
            reward = self.entry_price - self.target_price
            risk = self.stop_loss_price - self.entry_price
        
        return reward / risk if risk > 0 else 0


class BaseStrategy(ABC):
    """Base class for all trading strategies."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.enabled = True
    
    @abstractmethod
    def analyze(self, market: Dict, sports_data: Dict, event: Optional[Dict] = None) -> Optional[TradeSignal]:
        """
        Analyze market for trading opportunity.
        
        Args:
            market: Polymarket market data
            sports_data: Live sports game data
            event: Optional recent sporting event (goal, wicket, etc.)
        
        Returns:
            TradeSignal if opportunity found, None otherwise
        """
        pass
    
    @abstractmethod
    def should_exit(self, position: Dict, current_price: float, 
                   sports_data: Dict) -> Tuple[bool, str]:
        """
        Check if position should be exited.
        
        Returns:
            (should_exit, reason)
        """
        pass
    
    def calculate_size(self, confidence: float, base_size: float) -> float:
        """Calculate position size based on confidence."""
        # Scale size with confidence, but cap at max
        size = base_size * confidence
        return min(size, Config.MAX_POSITION_USD)


class OverreactionFadeStrategy(BaseStrategy):
    """
    Strategy 1: Overreaction Fade
    
    When a goal/wicket/run causes a sharp price move (3-5%+),
    fade the move within 60 seconds as market overreacts.
    
    Edge: Recency bias causes emotional overpricing
    Sports: All
    Expected hold: 5-15 minutes
    """
    
    def __init__(self):
        super().__init__(
            name="Overreaction Fade",
            description="Fade sharp price moves after goals/wickets"
        )
        self.min_move_percent = 5.0  # Minimum move to trigger
        self.max_reaction_seconds = 60  # React within 60 seconds
        self.fade_percent = 0.5  # Expect 50% reversion
    
    def analyze(self, market: Dict, sports_data: Dict, 
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.OVERREACTION_FADE_ENABLED:
            return None
        
        if not event:
            return None
        
        # Check for recent price move
        current_price = market.get('current_price', 0.5)
        previous_price = market.get('previous_price', current_price)
        
        if previous_price == 0:
            return None
        
        price_change_percent = ((current_price - previous_price) / previous_price) * 100
        
        # Check if move is significant enough
        if abs(price_change_percent) < self.min_move_percent:
            return None
        
        # Determine fade direction
        if price_change_percent > 0:
            # Price spiked up, sell the spike
            signal_type = SignalType.SELL
            target_price = current_price - (abs(price_change_percent) * self.fade_percent / 100)
            stop_loss_price = current_price * 1.05  # 5% above for stop
        else:
            # Price crashed down, buy the dip  
            signal_type = SignalType.BUY
            target_price = current_price + (abs(price_change_percent) * self.fade_percent / 100)
            stop_loss_price = current_price * 0.95  # 5% below for stop
        
        confidence = min(0.8, abs(price_change_percent) / 10)  # Higher move = higher confidence
        
        return TradeSignal(
            strategy=self.name,
            signal_type=signal_type,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport=market.get('sport', 'unknown'),
            entry_price=current_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.5),
            rationale=f"Fading {abs(price_change_percent):.1f}% move after {event.get('event_type', 'event')}",
            metadata={
                'event_type': event.get('event_type'),
                'price_change': price_change_percent,
                'game_time': event.get('game_time')
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        entry_time = position.get('entry_time')
        
        # Time-based exit (max 15 minutes for fades)
        if entry_time:
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            elapsed = (datetime.now() - entry_time).seconds / 60
            if elapsed > 15:
                return True, "Max hold time reached (15 min)"
        
        # Profit target
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        if profit_percent >= 10:
            return True, f"Take profit hit (+{profit_percent:.1f}%)"
        
        if profit_percent <= -5:
            return True, f"Stop loss hit ({profit_percent:.1f}%)"
        
        return False, ""


class DrawDecayStrategy(BaseStrategy):
    """
    Strategy 2: Draw Probability Decay
    
    In football, draw probability naturally decays as time passes.
    Sell draw tokens near end of match, buy if shock event creates value.
    
    Edge: Time decay + panic after late goals
    Sports: Football (Soccer)
    Expected hold: 10-30 minutes
    """
    
    def __init__(self):
        super().__init__(
            name="Draw Decay",
            description="Trade draw probability decay in football"
        )
        self.start_decay_minute = Config.FOOTBALL_DRAW_DECAY_START_MINUTE
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.DRAW_DECAY_ENABLED:
            return None
        
        sport = market.get('sport', '')
        if sport != 'football':
            return None
        
        question = market.get('question', '').lower()
        if 'draw' not in question and 'tie' not in question:
            return None
        
        current_price = market.get('current_price', 0.5)
        game = sports_data.get('game', {})
        game_time = self._parse_game_time(game.get('game_time', '0'))
        score_diff = abs(game.get('home_score', 0) - game.get('away_score', 0))
        
        # Late game with tied score - draw is overpriced
        if game_time >= self.start_decay_minute and score_diff == 0:
            if current_price > 0.30:  # Draw at >30% with 20 min left
                return TradeSignal(
                    strategy=self.name,
                    signal_type=SignalType.SELL,
                    market_id=market.get('id', ''),
                    market_question=market.get('question', ''),
                    sport='football',
                    entry_price=current_price,
                    target_price=current_price * 0.7,
                    stop_loss_price=current_price * 1.15,
                    confidence=0.65,
                    size_usd=self.calculate_size(0.65, Config.MAX_POSITION_USD * 0.5),
                    rationale=f"Draw decay: Minute {game_time}, still 0-0, selling overpriced draw",
                    metadata={
                        'game_time': game_time,
                        'score': f"{game.get('home_score', 0)}-{game.get('away_score', 0)}"
                    }
                )
        
        # Late goal breaks draw - buy the crashed draw token as hedge value
        if event and event.get('event_type') == 'goal' and game_time >= 75:
            if current_price < 0.10:  # Draw crashed to <10%
                return TradeSignal(
                    strategy=self.name,
                    signal_type=SignalType.BUY,
                    market_id=market.get('id', ''),
                    market_question=market.get('question', ''),
                    sport='football',
                    entry_price=current_price,
                    target_price=current_price * 1.5,
                    stop_loss_price=current_price * 0.5,
                    confidence=0.55,
                    size_usd=self.calculate_size(0.55, Config.MAX_POSITION_USD * 0.3),
                    rationale=f"Buying crashed draw after late goal for hedge value",
                    metadata={
                        'game_time': game_time,
                        'trigger': 'late_goal'
                    }
                )
        
        return None
    
    def _parse_game_time(self, time_str: str) -> int:
        """Parse game time string to minutes."""
        try:
            return int(str(time_str).replace("'", "").replace("+", " ").split()[0])
        except:
            return 0
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'SELL')
        
        if direction == 'SELL':
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        else:
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        # Draw trades are higher risk, tighter exits
        if profit_percent >= 15:
            return True, f"Take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -8:
            return True, f"Stop loss ({profit_percent:.1f}%)"
        
        # Exit if game ends
        game = sports_data.get('game', {})
        if game.get('status', '') in ['FINAL', 'STATUS_FINAL']:
            return True, "Game ended"
        
        return False, ""


class RunReversionStrategy(BaseStrategy):
    """
    Strategy 3: NBA Run Reversion
    
    When a team goes on a 10+ point run, the market overreacts.
    Fade the run, expecting regression to the mean.
    
    Edge: Mean reversion in basketball scoring patterns
    Sports: NBA
    Expected hold: 5-10 minutes (1-2 quarters worth)
    """
    
    def __init__(self):
        super().__init__(
            name="Run Reversion",
            description="Fade NBA scoring runs expecting reversion"
        )
        self.min_run_points = Config.NBA_RUN_REVERSION_POINTS
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.RUN_REVERSION_ENABLED:
            return None
        
        sport = market.get('sport', '')
        if sport != 'nba':
            return None
        
        # Check for run event
        if not event or event.get('event_type') != 'run':
            return None
        
        run_points = event.get('details', {}).get('run_points', 0)
        if run_points < self.min_run_points:
            return None
        
        current_price = market.get('current_price', 0.5)
        running_team = event.get('team', '')
        
        # Fade the team that just went on a run
        question = market.get('question', '').lower()
        
        # If running team is in market question, sell (they're overpriced)
        if running_team.lower() in question:
            signal_type = SignalType.SELL
            target_price = current_price * 0.9
            stop_loss_price = current_price * 1.08
            rationale = f"Fading {running_team} after {run_points}-pt run"
        else:
            # Buy the opponent (they're underpriced due to panic)
            signal_type = SignalType.BUY
            target_price = current_price * 1.1
            stop_loss_price = current_price * 0.92
            rationale = f"Buying opponent after {running_team} {run_points}-pt run"
        
        confidence = min(0.75, 0.5 + (run_points - 10) * 0.05)
        
        return TradeSignal(
            strategy=self.name,
            signal_type=signal_type,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport='nba',
            entry_price=current_price,
            target_price=target_price,
            stop_loss_price=stop_loss_price,
            confidence=confidence,
            size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.5),
            rationale=rationale,
            metadata={
                'run_points': run_points,
                'running_team': running_team,
                'quarter': event.get('details', {}).get('quarter')
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        if profit_percent >= 8:
            return True, f"Take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -6:
            return True, f"Stop loss ({profit_percent:.1f}%)"
        
        return False, ""


class WicketShockStrategy(BaseStrategy):
    """
    Strategy 4: Cricket Wicket Shock
    
    Early wickets cause panic selling in cricket markets.
    Buy the dip on quality teams that can recover.
    
    Edge: Overreaction to early wickets
    Sports: Cricket (T20, ODI)
    Expected hold: 30-60 minutes (several overs)
    """
    
    def __init__(self):
        super().__init__(
            name="Wicket Shock",
            description="Buy dips after early wickets in cricket"
        )
        self.min_dip_percent = Config.CRICKET_WICKET_DIP_PERCENT * 100
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.WICKET_SHOCK_ENABLED:
            return None
        
        sport = market.get('sport', '')
        if sport != 'cricket':
            return None
        
        if not event or event.get('event_type') != 'wicket':
            return None
        
        current_price = market.get('current_price', 0.5)
        previous_price = market.get('previous_price', current_price)
        
        if previous_price == 0:
            return None
        
        dip_percent = ((previous_price - current_price) / previous_price) * 100
        
        # Check if dip is significant
        if dip_percent < self.min_dip_percent:
            return None
        
        # Early innings (first 10 overs) - best opportunity
        overs = sports_data.get('game', {}).get('overs', 0)
        if overs > 10:
            return None  # Only trade early wicket shocks
        
        wickets = event.get('details', {}).get('wickets_now', 0)
        
        # Don't buy if team is collapsing (3+ wickets quickly)
        if wickets >= 4:
            return None
        
        confidence = 0.6 + (dip_percent - 15) * 0.02
        confidence = min(0.8, max(0.5, confidence))
        
        return TradeSignal(
            strategy=self.name,
            signal_type=SignalType.BUY,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport='cricket',
            entry_price=current_price,
            target_price=current_price * 1.15,
            stop_loss_price=current_price * 0.88,
            confidence=confidence,
            size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.4),
            rationale=f"Buying {dip_percent:.1f}% dip after wicket (over {overs})",
            metadata={
                'dip_percent': dip_percent,
                'overs': overs,
                'wickets': wickets
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        if profit_percent >= 12:
            return True, f"Take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -10:
            return True, f"Stop loss ({profit_percent:.1f}%)"
        
        # Exit if too many wickets fall
        wickets = sports_data.get('game', {}).get('wickets', 0)
        if wickets >= 6:
            return True, "Team collapsing - exit risk"
        
        return False, ""


class FavoriteTrapStrategy(BaseStrategy):
    """
    Strategy 5: Late-Game Favorite Trap
    
    When a favorite reaches 90%+ late in the game, market is complacent.
    Sell the overpriced favorite - upsets happen more than priced.
    
    Edge: False certainty bias, fat tails
    Sports: All
    Expected hold: Until game ends or price corrects
    """
    
    def __init__(self):
        super().__init__(
            name="Favorite Trap",
            description="Sell overpriced late-game favorites"
        )
        self.min_favorite_price = 0.90  # >90% probability
        self.min_completion = 75  # >75% game complete
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.FAVORITE_TRAP_ENABLED:
            return None
        
        current_price = market.get('current_price', 0.5)
        completion = sports_data.get('game', {}).get('completion_percent', 0)
        
        # Check if favorite is overpriced late in game
        if current_price < self.min_favorite_price:
            return None
        if completion < self.min_completion:
            return None
        
        # The higher the price, the more confident we are in fade
        edge = current_price - 0.85  # How overpriced vs fair
        confidence = 0.5 + edge * 2  # Scale confidence with edge
        confidence = min(0.75, max(0.5, confidence))
        
        return TradeSignal(
            strategy=self.name,
            signal_type=SignalType.SELL,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport=market.get('sport', 'unknown'),
            entry_price=current_price,
            target_price=current_price * 0.95,  # 5% drop target
            stop_loss_price=min(0.99, current_price * 1.02),  # Tight stop
            confidence=confidence,
            size_usd=self.calculate_size(confidence, Config.MAX_POSITION_USD * 0.3),
            rationale=f"Selling {current_price*100:.0f}% favorite at {completion:.0f}% completion",
            metadata={
                'favorite_price': current_price,
                'completion': completion
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        
        profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        if profit_percent >= 5:
            return True, f"Take profit (+{profit_percent:.1f}%)"
        if profit_percent <= -3:
            return True, f"Stop loss ({profit_percent:.1f}%)"
        
        # Exit if game ends
        status = sports_data.get('game', {}).get('status', '')
        if 'FINAL' in status.upper():
            return True, "Game ended"
        
        return False, ""


class VolatilityScalpStrategy(BaseStrategy):
    """
    Strategy 6: Volatility Scalping
    
    During chaotic game moments (multiple quick events), volatility spikes.
    Buy low, sell high within the chaos window.
    
    Edge: Liquidity crunch during fast action
    Sports: All
    Expected hold: 1-5 minutes
    """
    
    def __init__(self):
        super().__init__(
            name="Volatility Scalp",
            description="Scalp during high-volatility moments"
        )
        self.min_spread_percent = 3.0  # Wide spread indicates volatility
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.VOLATILITY_SCALP_ENABLED:
            return None
        
        orderbook = market.get('orderbook', {})
        spread_percent = orderbook.get('spread_percent', 0)
        
        if spread_percent < self.min_spread_percent:
            return None
        
        # Wide spread = volatility opportunity
        best_bid = orderbook.get('best_bid', 0.45)
        best_ask = orderbook.get('best_ask', 0.55)
        mid_price = (best_bid + best_ask) / 2
        
        # Buy at bid, target the ask
        return TradeSignal(
            strategy=self.name,
            signal_type=SignalType.BUY,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport=market.get('sport', 'unknown'),
            entry_price=best_bid,
            target_price=best_ask * 0.95,  # Target near ask
            stop_loss_price=best_bid * 0.95,
            confidence=0.6,
            size_usd=self.calculate_size(0.6, Config.MAX_POSITION_USD * 0.3),
            rationale=f"Scalping {spread_percent:.1f}% spread volatility",
            metadata={
                'spread_percent': spread_percent,
                'best_bid': best_bid,
                'best_ask': best_ask
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        entry_time = position.get('entry_time')
        
        # Very short hold time for scalps
        if entry_time:
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            elapsed = (datetime.now() - entry_time).seconds / 60
            if elapsed > 5:
                return True, "Max scalp time (5 min)"
        
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        if profit_percent >= 3:
            return True, f"Scalp target hit (+{profit_percent:.1f}%)"
        if profit_percent <= -2:
            return True, f"Scalp stop hit ({profit_percent:.1f}%)"
        
        return False, ""


class LagArbitrageStrategy(BaseStrategy):
    """
    Strategy 7: Cross-Market Lag Arbitrage
    
    When a goal/event happens, some markets update faster than others.
    Exploit the lag between fast and slow price updates.
    
    Edge: Market microstructure inefficiency
    Sports: All
    Expected hold: 1-3 minutes
    """
    
    def __init__(self):
        super().__init__(
            name="Lag Arbitrage",
            description="Exploit delayed price updates between markets"
        )
        self.min_price_difference = 0.05  # 5% difference between related markets
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.LAG_ARBITRAGE_ENABLED:
            return None
        
        if not event:
            return None
        
        # Check for related markets with price differences
        related_markets = market.get('related_markets', [])
        current_price = market.get('current_price', 0.5)
        
        for related in related_markets:
            related_price = related.get('current_price', 0.5)
            
            # Check for exploitable lag
            if abs(current_price - related_price) >= self.min_price_difference:
                # Buy the cheaper, sell the expensive
                if current_price < related_price:
                    signal_type = SignalType.BUY
                    target_price = related_price
                else:
                    signal_type = SignalType.SELL
                    target_price = related_price
                
                return TradeSignal(
                    strategy=self.name,
                    signal_type=signal_type,
                    market_id=market.get('id', ''),
                    market_question=market.get('question', ''),
                    sport=market.get('sport', 'unknown'),
                    entry_price=current_price,
                    target_price=target_price,
                    stop_loss_price=current_price * (0.97 if signal_type == SignalType.BUY else 1.03),
                    confidence=0.7,
                    size_usd=self.calculate_size(0.7, Config.MAX_POSITION_USD * 0.4),
                    rationale=f"Lag arb: {abs(current_price - related_price)*100:.1f}% price difference",
                    metadata={
                        'related_market': related.get('id'),
                        'price_diff': current_price - related_price
                    }
                )
        
        return None
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_time = position.get('entry_time')
        
        # Very short hold for arb
        if entry_time:
            if isinstance(entry_time, str):
                entry_time = datetime.fromisoformat(entry_time)
            elapsed = (datetime.now() - entry_time).seconds / 60
            if elapsed > 3:
                return True, "Arb window closed (3 min)"
        
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        if profit_percent >= 4:
            return True, f"Arb profit captured (+{profit_percent:.1f}%)"
        if profit_percent <= -2:
            return True, f"Arb failed ({profit_percent:.1f}%)"
        
        return False, ""


class LiquidityProvisionStrategy(BaseStrategy):
    """
    Strategy 8: Liquidity Provision (Market Making)
    
    During panic selling, provide liquidity to capture spread.
    Advanced strategy - disabled by default.
    
    Edge: Spread capture during illiquid moments
    Sports: All
    Expected hold: Variable
    """
    
    def __init__(self):
        super().__init__(
            name="Liquidity Provision",
            description="Provide liquidity during panic for spread capture"
        )
        self.min_spread_percent = 5.0  # Very wide spreads only
        self.enabled = False  # Disabled by default
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        if not Config.LIQUIDITY_PROVISION_ENABLED:
            return None
        
        orderbook = market.get('orderbook', {})
        spread_percent = orderbook.get('spread_percent', 0)
        
        if spread_percent < self.min_spread_percent:
            return None
        
        # Provide liquidity at mid-price
        best_bid = orderbook.get('best_bid', 0.45)
        best_ask = orderbook.get('best_ask', 0.55)
        mid_price = (best_bid + best_ask) / 2
        
        return TradeSignal(
            strategy=self.name,
            signal_type=SignalType.BUY,
            market_id=market.get('id', ''),
            market_question=market.get('question', ''),
            sport=market.get('sport', 'unknown'),
            entry_price=mid_price,
            target_price=best_ask * 0.98,
            stop_loss_price=best_bid * 0.95,
            confidence=0.55,
            size_usd=self.calculate_size(0.55, Config.MAX_POSITION_USD * 0.2),
            rationale=f"Providing liquidity at {spread_percent:.1f}% spread",
            metadata={
                'spread_percent': spread_percent,
                'mid_price': mid_price
            }
        )
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        
        profit_percent = ((current_price - entry_price) / entry_price) * 100
        
        if profit_percent >= 2:
            return True, f"Spread captured (+{profit_percent:.1f}%)"
        if profit_percent <= -3:
            return True, f"MM stop hit ({profit_percent:.1f}%)"
        
        return False, ""


class MarketOnlyStrategy(BaseStrategy):
    """
    Strategy 9: Market-Only Trading (NO ESPN DATA NEEDED)
    
    Trades based purely on Polymarket data:
    - Buy underpriced events (low probability that seem fair)
    - Sell overpriced favorites
    - Trade wide spreads for quick scalps
    
    Edge: Works 24/7 without live sports data
    Sports: All
    Expected hold: Variable
    """
    
    def __init__(self):
        super().__init__(
            name="Market Only",
            description="Trade based on market data alone (no ESPN needed)"
        )
    
    def analyze(self, market: Dict, sports_data: Dict,
                event: Optional[Dict] = None) -> Optional[TradeSignal]:
        
        current_price = market.get('current_price', 0.5)
        question = market.get('question', '').lower()
        
        # Skip if price is exactly 0.5 (default/unknown)
        if current_price == 0.5:
            return None
        
        # Strategy 1: Extreme favorites (>75%) - SELL
        # Markets at 75%+ often have fat tail risk
        if current_price >= Config.MARKET_ONLY_FAVORITE_THRESHOLD:
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.SELL,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=current_price,
                target_price=current_price * 0.97,  # 3% drop
                stop_loss_price=min(0.99, current_price * 1.02),
                confidence=0.55 + (current_price - 0.75) * 2,  # Higher price = higher confidence
                size_usd=self.calculate_size(0.55, Config.MAX_POSITION_USD * 0.3),
                rationale=f"Selling favorite at {current_price*100:.0f}%",
                metadata={
                    'entry_price': current_price,
                    'strategy_type': 'extreme_favorite_fade'
                }
            )
        
        # Strategy 2: Underdogs (<25%) - BUY for asymmetric risk
        # Low probability events are often underpriced
        if current_price <= Config.MARKET_ONLY_UNDERDOG_THRESHOLD and current_price > 0.03:
            # Only if it's a "win" market (not weird derivatives)
            if 'win' in question or 'beat' in question or 'defeat' in question or market.get('sport'):
                return TradeSignal(
                    strategy=self.name,
                    signal_type=SignalType.BUY,
                    market_id=market.get('id', market.get('condition_id', '')),
                    market_question=market.get('question', ''),
                    sport=market.get('sport', 'unknown'),
                    entry_price=current_price,
                    target_price=current_price * 1.4,  # 40% gain target
                    stop_loss_price=current_price * 0.7,  # 30% stop
                    confidence=0.55,
                    size_usd=self.calculate_size(0.50, Config.MAX_POSITION_USD * 0.25),
                    rationale=f"Buying underdog at {current_price*100:.1f}% for asymmetric upside",
                    metadata={
                        'entry_price': current_price,
                        'strategy_type': 'underdog_value'
                    }
                )
        
        # Strategy 3: Mid-range volatility opportunity (40-60%)
        # 50/50 markets often have mispricing opportunities
        orderbook = market.get('orderbook', {})
        spread_percent = orderbook.get('spread_percent', 0)
        
        if spread_percent >= Config.SPREAD_SCALP_MIN_PERCENT and 0.35 <= current_price <= 0.65:
            best_bid = orderbook.get('best_bid', current_price * 0.97)
            best_ask = orderbook.get('best_ask', current_price * 1.03)
            
            return TradeSignal(
                strategy=self.name,
                signal_type=SignalType.BUY,
                market_id=market.get('id', market.get('condition_id', '')),
                market_question=market.get('question', ''),
                sport=market.get('sport', 'unknown'),
                entry_price=best_bid,  # Buy at bid
                target_price=best_ask * 0.97,  # Sell near ask
                stop_loss_price=best_bid * 0.95,
                confidence=0.55,
                size_usd=self.calculate_size(0.55, Config.MAX_POSITION_USD * 0.25),
                rationale=f"Wide spread scalp ({spread_percent:.1f}%) at 50/50 market",
                metadata={
                    'spread_percent': spread_percent,
                    'strategy_type': 'spread_scalp'
                }
            )
        
        return None
    
    def should_exit(self, position: Dict, current_price: float,
                   sports_data: Dict) -> Tuple[bool, str]:
        entry_price = position.get('entry_price', current_price)
        direction = position.get('direction', 'BUY')
        strategy_type = position.get('metadata', {}).get('strategy_type', '')
        
        if direction == 'BUY':
            profit_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_percent = ((entry_price - current_price) / entry_price) * 100
        
        # Different exit rules based on strategy type
        if strategy_type == 'extreme_favorite_fade':
            if profit_percent >= 3:
                return True, f"Favorite fade profit (+{profit_percent:.1f}%)"
            if profit_percent <= -2:
                return True, f"Favorite fade stop ({profit_percent:.1f}%)"
        elif strategy_type == 'underdog_value':
            if profit_percent >= 40:
                return True, f"Underdog value hit (+{profit_percent:.1f}%)"
            if profit_percent <= -35:
                return True, f"Underdog stop ({profit_percent:.1f}%)"
        else:  # spread_scalp
            if profit_percent >= 3:
                return True, f"Spread scalp profit (+{profit_percent:.1f}%)"
            if profit_percent <= -3:
                return True, f"Spread scalp stop ({profit_percent:.1f}%)"
        
        return False, ""


class SportsStrategyEngine:
    """
    Main engine that coordinates all trading strategies.
    """
    
    def __init__(self):
        self.strategies = [
            OverreactionFadeStrategy(),
            DrawDecayStrategy(),
            RunReversionStrategy(),
            WicketShockStrategy(),
            FavoriteTrapStrategy(),
            VolatilityScalpStrategy(),
            LagArbitrageStrategy(),
            LiquidityProvisionStrategy(),
            MarketOnlyStrategy(),  # NEW: Works without ESPN data!
        ]
        
        print(f"✅ Strategy Engine initialized with {len(self.strategies)} strategies")
        for s in self.strategies:
            status = "✅" if self._is_strategy_enabled(s) else "⚪"
            print(f"   {status} {s.name}")
    
    def _is_strategy_enabled(self, strategy: BaseStrategy) -> bool:
        """Check if strategy is enabled in config."""
        name_map = {
            'Overreaction Fade': Config.OVERREACTION_FADE_ENABLED,
            'Draw Decay': Config.DRAW_DECAY_ENABLED,
            'Run Reversion': Config.RUN_REVERSION_ENABLED,
            'Wicket Shock': Config.WICKET_SHOCK_ENABLED,
            'Favorite Trap': Config.FAVORITE_TRAP_ENABLED,
            'Volatility Scalp': Config.VOLATILITY_SCALP_ENABLED,
            'Lag Arbitrage': Config.LAG_ARBITRAGE_ENABLED,
            'Liquidity Provision': Config.LIQUIDITY_PROVISION_ENABLED,
            'Market Only': getattr(Config, 'MARKET_ONLY_ENABLED', True),  # Enabled by default!
        }
        return name_map.get(strategy.name, False)
    
    def analyze_market(self, market: Dict, sports_data: Dict,
                       event: Optional[Dict] = None) -> List[TradeSignal]:
        """
        Run all strategies on a market.
        
        Returns list of signals from all strategies that found opportunities.
        """
        signals = []
        
        for strategy in self.strategies:
            if not self._is_strategy_enabled(strategy):
                continue
            
            try:
                signal = strategy.analyze(market, sports_data, event)
                if signal:
                    signals.append(signal)
            except Exception as e:
                print(f"⚠️ Error in {strategy.name}: {e}")
        
        # Sort by confidence
        signals.sort(key=lambda s: s.confidence, reverse=True)
        
        return signals
    
    def check_exits(self, positions: List[Dict], current_prices: Dict,
                    sports_data: Dict) -> List[Tuple[str, str]]:
        """
        Check all open positions for exit conditions.
        
        Returns list of (trade_id, exit_reason) for positions that should exit.
        """
        exits = []
        
        for position in positions:
            trade_id = position.get('trade_id')
            strategy_name = position.get('strategy')
            market_id = position.get('market_id')
            
            current_price = current_prices.get(market_id, position.get('entry_price'))
            
            # Find the strategy
            strategy = next((s for s in self.strategies if s.name == strategy_name), None)
            if not strategy:
                continue
            
            should_exit, reason = strategy.should_exit(position, current_price, sports_data)
            
            if should_exit:
                exits.append((trade_id, reason))
        
        return exits
    
    def get_strategy_stats(self) -> List[Dict]:
        """Get statistics for all strategies."""
        return [{
            'name': s.name,
            'description': s.description,
            'enabled': self._is_strategy_enabled(s)
        } for s in self.strategies]
