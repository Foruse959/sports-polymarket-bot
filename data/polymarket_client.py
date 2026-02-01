"""
Polymarket API Client

Fetches markets, orderbooks, and prices from Polymarket's APIs.
"""

import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import Config


class PolymarketClient:
    """Client for Polymarket Gamma and CLOB APIs."""
    
    def __init__(self):
        self.gamma_url = Config.POLYMARKET_GAMMA_URL
        self.clob_url = Config.POLYMARKET_CLOB_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Sports-Polymarket-Bot/1.0',
            'Accept': 'application/json'
        })
        
        # Sport keywords for filtering
        self.sport_keywords = {
            'football': ['soccer', 'premier league', 'champions league', 'la liga', 
                        'bundesliga', 'serie a', 'world cup', 'euro', 'fa cup',
                        'manchester', 'liverpool', 'arsenal', 'chelsea', 'barcelona',
                        'real madrid', 'bayern', 'psg', 'juventus', 'inter milan'],
            'nba': ['nba', 'basketball', 'lakers', 'celtics', 'warriors', 'nuggets',
                   'heat', 'bucks', 'suns', 'nets', 'knicks', '76ers', 'clippers',
                   'lebron', 'curry', 'durant', 'giannis', 'jokic', 'embiid'],
            'cricket': ['cricket', 'ipl', 't20', 'odi', 'test match', 'world cup cricket',
                       'rcb', 'csk', 'mi', 'kolkata', 'delhi capitals', 'punjab kings',
                       'kohli', 'rohit', 'dhoni', 'bumrah', 'ashes', 'bbl'],
            'tennis': ['tennis', 'wimbledon', 'us open', 'australian open', 
                      'french open', 'roland garros', 'atp', 'wta',
                      'djokovic', 'nadal', 'federer', 'alcaraz', 'sinner'],
            'ufc': ['ufc', 'mma', 'fight night', 'ppv', 'bellator', 'boxing',
                   'lightweight', 'heavyweight', 'welterweight'],
            'esports': ['esports', 'league of legends', 'dota', 'cs2', 'valorant',
                       'overwatch', 'call of duty', 'fortnite']
        }
        
        # Flatten for quick lookup
        self.all_sport_keywords = []
        for keywords in self.sport_keywords.values():
            self.all_sport_keywords.extend(keywords)
    
    def get_sports_markets(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get all active sports markets from Polymarket.
        
        Returns:
            List of sports market dictionaries
        """
        all_markets = self._fetch_all_markets(limit)
        sports_markets = self._filter_sports_markets(all_markets)
        
        # Enrich with sport category
        for market in sports_markets:
            market['sport'] = self._detect_sport(market.get('question', ''))
        
        print(f"📊 Found {len(sports_markets)} sports markets out of {len(all_markets)} total")
        return sports_markets
    
    def _fetch_all_markets(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Fetch all markets with pagination."""
        markets = []
        offset = 0
        batch_size = 100
        
        while len(markets) < limit:
            try:
                url = f"{self.gamma_url}/markets?limit={batch_size}&offset={offset}&closed=false"
                response = self.session.get(url, timeout=30)
                
                if response.status_code != 200:
                    print(f"⚠️ Gamma API returned {response.status_code}")
                    break
                
                data = response.json()
                if not data:
                    break
                
                markets.extend(data)
                
                if len(data) < batch_size:
                    break  # No more pages
                
                offset += batch_size
                
            except Exception as e:
                print(f"❌ Error fetching markets: {e}")
                break
        
        return markets[:limit]
    
    def _filter_sports_markets(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter markets to only include sports-related ones."""
        sports_markets = []
        
        for market in markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            
            # Check if market matches any sport keyword
            is_sports = any(
                keyword in question or keyword in description
                for keyword in self.all_sport_keywords
            )
            
            if is_sports:
                sports_markets.append(market)
        
        return sports_markets
    
    def _detect_sport(self, question: str) -> str:
        """Detect which sport a market belongs to."""
        question_lower = question.lower()
        
        for sport, keywords in self.sport_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                return sport
        
        return 'other'
    
    def get_market_price(self, market: Dict[str, Any]) -> float:
        """
        Parse price from market data with robust handling.
        
        Returns:
            Price between 0.0 and 1.0
        """
        try:
            # Try outcomePrices first (most common)
            if 'outcomePrices' in market and market['outcomePrices']:
                prices = market['outcomePrices']
                if prices:
                    price_str = str(prices[0]).strip('"')
                    return float(price_str)
            
            # Try tokens array
            if 'tokens' in market and market['tokens']:
                first_token = market['tokens'][0]
                if 'price' in first_token:
                    return float(first_token['price'])
            
            # Try best bid/ask
            if 'bestBid' in market:
                return float(market['bestBid'])
            if 'bestAsk' in market:
                return float(market['bestAsk'])
            
            # Try clobTokenIds and fetch from CLOB
            if 'clobTokenIds' in market and market['clobTokenIds']:
                # Could fetch live price from CLOB API here
                pass
            
        except (ValueError, TypeError, KeyError) as e:
            pass
        
        return 0.5  # Default fallback
    
    def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch orderbook for a specific token.
        
        Args:
            token_id: Polymarket token ID
            
        Returns:
            Orderbook dict with bids, asks, spread, etc.
        """
        try:
            url = f"{self.clob_url}/book?token_id={token_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Parse orderbook
            bids = [(float(b['price']), float(b['size'])) for b in data.get('bids', [])]
            asks = [(float(a['price']), float(a['size'])) for a in data.get('asks', [])]
            
            best_bid = bids[0][0] if bids else 0
            best_ask = asks[0][0] if asks else 1
            spread = best_ask - best_bid
            
            bid_liquidity = sum(p * s for p, s in bids[:5])
            ask_liquidity = sum(p * s for p, s in asks[:5])
            
            return {
                'token_id': token_id,
                'bids': bids,
                'asks': asks,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_percent': (spread / best_ask * 100) if best_ask > 0 else 0,
                'bid_liquidity': bid_liquidity,
                'ask_liquidity': ask_liquidity,
                'imbalance': (bid_liquidity - ask_liquidity) / (bid_liquidity + ask_liquidity) 
                            if (bid_liquidity + ask_liquidity) > 0 else 0,
                'mid_price': (best_bid + best_ask) / 2
            }
            
        except Exception as e:
            print(f"❌ Error fetching orderbook: {e}")
            return None
    
    def get_market_by_id(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific market by ID."""
        try:
            url = f"{self.gamma_url}/markets/{market_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            print(f"❌ Error fetching market {market_id}: {e}")
        
        return None
    
    def calculate_slippage(self, orderbook: Dict[str, Any], 
                           amount_usd: float, side: str) -> float:
        """
        Calculate expected slippage for a given order size.
        
        Args:
            orderbook: Orderbook data
            amount_usd: Order size in USD
            side: 'buy' or 'sell'
            
        Returns:
            Slippage percentage
        """
        levels = orderbook['asks'] if side == 'buy' else orderbook['bids']
        
        if not levels:
            return float('inf')
        
        remaining = amount_usd
        weighted_price = 0
        total_filled = 0
        
        for price, size in levels:
            level_value = price * size
            if remaining <= 0:
                break
            
            fill_amount = min(remaining, level_value)
            weighted_price += price * fill_amount
            total_filled += fill_amount
            remaining -= fill_amount
        
        if total_filled == 0:
            return float('inf')
        
        avg_fill_price = weighted_price / total_filled
        reference_price = levels[0][0]
        
        slippage = abs(avg_fill_price - reference_price) / reference_price * 100
        return slippage
    
    def get_live_markets_by_sport(self, sport: str) -> List[Dict[str, Any]]:
        """Get live markets for a specific sport."""
        all_sports = self.get_sports_markets()
        return [m for m in all_sports if m.get('sport') == sport]
