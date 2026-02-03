"""
Multi-Sportsbook Odds Aggregator

Compares Polymarket prices to traditional sportsbooks:
- DraftKings, FanDuel, BetMGM, Pinnacle
- Uses The Odds API (free tier: 500 requests/month)
- Calculates "true" probability by removing vig
- Finds edge vs consensus odds
- Returns list of arbitrage opportunities

Falls back to mock data if API key not configured.
"""

import sys
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class OddsComparison:
    """Represents a comparison between Polymarket and sportsbooks."""
    
    def __init__(self, market_id: str, event_name: str, outcome: str,
                 polymarket_price: float, consensus_price: float, 
                 true_probability: float, edge_percent: float,
                 sportsbook_prices: Dict[str, float], sport: str):
        self.market_id = market_id
        self.event_name = event_name
        self.outcome = outcome
        self.polymarket_price = polymarket_price
        self.consensus_price = consensus_price
        self.true_probability = true_probability
        self.edge_percent = edge_percent
        self.sportsbook_prices = sportsbook_prices
        self.sport = sport
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            'market_id': self.market_id,
            'event_name': self.event_name,
            'outcome': self.outcome,
            'polymarket_price': self.polymarket_price,
            'consensus_price': self.consensus_price,
            'true_probability': self.true_probability,
            'edge_percent': self.edge_percent,
            'sportsbook_prices': self.sportsbook_prices,
            'sport': self.sport,
            'timestamp': self.timestamp.isoformat()
        }


class MultiSourceOddsAggregator:
    """
    CROSS-MARKET ODDS COMPARISON
    
    Compares Polymarket prices to traditional sportsbooks:
    - DraftKings, FanDuel, BetMGM, Pinnacle
    - Uses The Odds API (free tier: 500 requests/month)
    - Calculates "true" probability by removing vig
    - Finds edge vs consensus odds
    
    Falls back to mock data if API key not configured.
    """
    
    ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
    
    # Supported sports mapping
    SPORT_MAPPING = {
        'nba': 'basketball_nba',
        'nfl': 'americanfootball_nfl',
        'mlb': 'baseball_mlb',
        'nhl': 'icehockey_nhl',
        'football': 'soccer_epl',  # Default to Premier League
        'soccer': 'soccer_epl',
        'tennis': 'tennis_atp',
        'ufc': 'mma_mixed_martial_arts',
        'cricket': 'cricket_ipl'
    }
    
    # Major sportsbooks to compare
    TARGET_BOOKMAKERS = [
        'draftkings', 'fanduel', 'betmgm', 'pinnacle',
        'williamhill', 'bovada', 'pointsbet'
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize odds aggregator.
        
        Args:
            api_key: The Odds API key (optional, falls back to mock data)
        """
        self.api_key = api_key or Config.ODDS_API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Sports-Polymarket-Bot/1.0'
        })
        
        # Cache to avoid repeated API calls
        self.odds_cache = {}
        self.cache_duration = timedelta(minutes=5)
        
        # Stats tracking
        self.stats = {
            'api_calls': 0,
            'api_errors': 0,
            'cache_hits': 0,
            'comparisons_made': 0,
            'edges_found': 0,
            'mock_mode_uses': 0
        }
        
        self.use_mock = not bool(self.api_key)
        if self.use_mock:
            print("⚠️ The Odds API key not configured - using mock data")
        else:
            print(f"✅ The Odds API configured (free tier: 500 req/month)")
    
    def compare_markets(self, polymarket_markets: List[Dict], 
                       min_edge_percent: float = 3.0) -> List[OddsComparison]:
        """
        Compare Polymarket markets to sportsbook odds.
        
        Args:
            polymarket_markets: List of Polymarket market data
            min_edge_percent: Minimum edge to consider (default 3%)
        
        Returns:
            List of OddsComparison objects showing edges
        """
        comparisons = []
        
        for market in polymarket_markets:
            try:
                comparison = self._compare_single_market(market)
                if comparison and comparison.edge_percent >= min_edge_percent:
                    comparisons.append(comparison)
                    self.stats['edges_found'] += 1
            except Exception as e:
                if Config.DEBUG_MODE:
                    print(f"⚠️ Error comparing market {market.get('question', 'unknown')}: {e}")
                continue
        
        self.stats['comparisons_made'] += len(polymarket_markets)
        
        if comparisons:
            print(f"📊 Odds Aggregator: Found {len(comparisons)} edges vs sportsbooks")
        
        return sorted(comparisons, key=lambda x: x.edge_percent, reverse=True)
    
    def _compare_single_market(self, market: Dict) -> Optional[OddsComparison]:
        """Compare a single Polymarket market to sportsbook odds."""
        # Extract market info
        market_id = market.get('condition_id') or market.get('id', '')
        question = market.get('question', '')
        sport = self._identify_sport(question, market)
        
        if not sport:
            return None
        
        # Get Polymarket price
        tokens = market.get('tokens', [])
        if not tokens:
            return None
        
        # Assume first token is YES
        polymarket_price = float(tokens[0].get('price', 0))
        if polymarket_price <= 0 or polymarket_price >= 1:
            return None
        
        # Get sportsbook odds
        sportsbook_odds = self._get_sportsbook_odds(sport, question)
        if not sportsbook_odds:
            return None
        
        # Calculate consensus and true probability
        consensus_price, true_prob = self._calculate_consensus(sportsbook_odds)
        
        # Calculate edge
        edge_percent = ((true_prob / polymarket_price) - 1) * 100
        
        # Determine outcome (team/player name)
        outcome = self._extract_outcome(question)
        
        return OddsComparison(
            market_id=market_id,
            event_name=question,
            outcome=outcome,
            polymarket_price=polymarket_price,
            consensus_price=consensus_price,
            true_probability=true_prob,
            edge_percent=edge_percent,
            sportsbook_prices=sportsbook_odds,
            sport=sport
        )
    
    def _get_sportsbook_odds(self, sport: str, event_name: str) -> Dict[str, float]:
        """
        Get odds from multiple sportsbooks.
        
        Returns dict of {bookmaker: probability}
        """
        # Check cache first
        cache_key = f"{sport}:{event_name}"
        if cache_key in self.odds_cache:
            cached_data, cached_time = self.odds_cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                self.stats['cache_hits'] += 1
                return cached_data
        
        if self.use_mock:
            return self._get_mock_odds(sport)
        
        try:
            # Get sport key for The Odds API
            sport_key = self.SPORT_MAPPING.get(sport.lower(), 'basketball_nba')
            
            # Call The Odds API
            url = f"{self.ODDS_API_BASE_URL}/sports/{sport_key}/odds/"
            params = {
                'apiKey': self.api_key,
                'regions': 'us',
                'markets': 'h2h',  # Head-to-head (moneyline)
                'oddsFormat': 'decimal'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            self.stats['api_calls'] += 1
            
            if response.status_code != 200:
                raise Exception(f"API returned {response.status_code}")
            
            data = response.json()
            odds = self._parse_odds_response(data, event_name)
            
            # Cache the result
            self.odds_cache[cache_key] = (odds, datetime.now())
            
            return odds
            
        except Exception as e:
            self.stats['api_errors'] += 1
            if Config.DEBUG_MODE:
                print(f"⚠️ Error fetching odds for {sport}: {e}")
            return self._get_mock_odds(sport)
    
    def _parse_odds_response(self, data: List[Dict], event_name: str) -> Dict[str, float]:
        """Parse The Odds API response to extract probabilities."""
        odds_by_bookmaker = {}
        
        # Find matching event
        for event in data:
            # Simple matching by name similarity
            if not self._events_match(event.get('home_team', ''), event_name) and \
               not self._events_match(event.get('away_team', ''), event_name):
                continue
            
            # Extract odds from bookmakers
            for bookmaker in event.get('bookmakers', []):
                book_key = bookmaker.get('key', '')
                if book_key not in self.TARGET_BOOKMAKERS:
                    continue
                
                # Get first market (h2h)
                markets = bookmaker.get('markets', [])
                if not markets:
                    continue
                
                outcomes = markets[0].get('outcomes', [])
                if not outcomes:
                    continue
                
                # Convert decimal odds to probability
                # Use first outcome (typically home team)
                decimal_odds = float(outcomes[0].get('price', 0))
                if decimal_odds > 0:
                    implied_prob = 1.0 / decimal_odds
                    odds_by_bookmaker[book_key] = implied_prob
        
        return odds_by_bookmaker
    
    def _events_match(self, team: str, question: str) -> bool:
        """Check if team name appears in question."""
        team_lower = team.lower()
        question_lower = question.lower()
        return team_lower in question_lower or any(
            word in question_lower for word in team_lower.split()
        )
    
    def _calculate_consensus(self, sportsbook_odds: Dict[str, float]) -> tuple:
        """
        Calculate consensus probability and vig-free true probability.
        
        Returns:
            (consensus_price, true_probability)
        """
        if not sportsbook_odds:
            return (0.5, 0.5)
        
        # Simple average for consensus
        probabilities = list(sportsbook_odds.values())
        consensus = sum(probabilities) / len(probabilities)
        
        # Remove vig (sportsbooks typically have 5-10% vig)
        # Estimate: true_prob = implied_prob * 0.95
        true_prob = consensus * 0.95
        
        # Clamp between 0.01 and 0.99
        true_prob = max(0.01, min(0.99, true_prob))
        
        return (consensus, true_prob)
    
    def _identify_sport(self, question: str, market: Dict) -> Optional[str]:
        """Identify sport from market question or tags."""
        question_lower = question.lower()
        
        # Check common sport keywords
        sport_keywords = {
            'nba': ['nba', 'lakers', 'celtics', 'warriors', 'nets', 'basketball'],
            'nfl': ['nfl', 'super bowl', 'chiefs', 'patriots', 'cowboys', 'football'],
            'mlb': ['mlb', 'yankees', 'dodgers', 'red sox', 'baseball'],
            'nhl': ['nhl', 'stanley cup', 'bruins', 'maple leafs', 'hockey'],
            'football': ['premier league', 'champions league', 'manchester', 'liverpool', 'arsenal'],
            'tennis': ['wimbledon', 'us open', 'french open', 'australian open', 'nadal', 'djokovic'],
            'ufc': ['ufc', 'mma', 'fight night', 'conor mcgregor'],
            'cricket': ['cricket', 'ipl', 't20', 'test match', 'india cricket']
        }
        
        for sport, keywords in sport_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                return sport
        
        return None
    
    def _extract_outcome(self, question: str) -> str:
        """Extract the outcome/team name from question."""
        # Try to extract team or player name
        # This is simplified - could be enhanced with NLP
        if ' win' in question.lower():
            return question.split(' win')[0].strip()
        if ' to win' in question.lower():
            return question.split(' to win')[0].strip()
        return question[:50]  # First 50 chars as fallback
    
    def _get_mock_odds(self, sport: str) -> Dict[str, float]:
        """Generate mock sportsbook odds for testing."""
        self.stats['mock_mode_uses'] += 1
        
        # Generate realistic-looking odds with slight variations
        base_prob = 0.50 + (hash(sport) % 20 - 10) / 100  # 0.40 to 0.60
        
        mock_odds = {
            'draftkings': base_prob + 0.02,
            'fanduel': base_prob - 0.01,
            'betmgm': base_prob + 0.01,
            'pinnacle': base_prob  # Pinnacle as sharp book
        }
        
        return mock_odds
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            **self.stats,
            'using_mock_data': self.use_mock,
            'cache_size': len(self.odds_cache)
        }
    
    def clear_cache(self):
        """Clear odds cache."""
        self.odds_cache.clear()


def main():
    """Test the odds aggregator."""
    print("=" * 60)
    print("🎲 MULTI-SPORTSBOOK ODDS AGGREGATOR TEST")
    print("=" * 60)
    
    aggregator = MultiSourceOddsAggregator()
    
    # Create mock Polymarket markets
    mock_markets = [
        {
            'condition_id': 'test_nba_1',
            'question': 'Lakers to win vs Celtics',
            'tokens': [{'price': 0.45}]
        },
        {
            'condition_id': 'test_nfl_1',
            'question': 'Chiefs to win Super Bowl',
            'tokens': [{'price': 0.30}]
        }
    ]
    
    # Compare markets
    comparisons = aggregator.compare_markets(mock_markets, min_edge_percent=1.0)
    
    print(f"\n📊 Found {len(comparisons)} comparisons:")
    for comp in comparisons:
        print(f"\n   {comp.event_name}")
        print(f"   Polymarket: {comp.polymarket_price:.3f}")
        print(f"   Consensus: {comp.consensus_price:.3f}")
        print(f"   True Prob: {comp.true_probability:.3f}")
        print(f"   Edge: {comp.edge_percent:.2f}%")
    
    print(f"\n📈 Stats: {aggregator.get_stats()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
