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
            'cricket': [
                # Leagues & Tournaments
                'cricket', 'ipl', 't20', 'odi', 'test match', 'world cup cricket', 'asia cup',
                'big bash', 'bbl', 'cpl', 'psl', 'hundred', 'county championship',
                # IPL Teams
                'rcb', 'royal challengers', 'csk', 'chennai super kings', 'mi', 'mumbai indians',
                'kkr', 'kolkata knight riders', 'dc', 'delhi capitals', 'pbks', 'punjab kings',
                'rr', 'rajasthan royals', 'srh', 'sunrisers', 'gt', 'gujarat titans', 'lsg', 'lucknow',
                # National Teams
                'india cricket', 'australia cricket', 'england cricket', 'pakistan cricket',
                'south africa cricket', 'new zealand cricket', 'west indies', 'bangladesh cricket',
                'sri lanka cricket', 'afghanistan cricket',
                # Players
                'kohli', 'virat', 'rohit sharma', 'dhoni', 'bumrah', 'jadeja', 'hardik pandya',
                'smith', 'warner', 'cummins', 'starc', 'head', 'labuschagne',
                'root', 'stokes', 'bairstow', 'buttler', 'archer',
                'babar azam', 'shaheen', 'rizwan',
                # Match Types
                'innings', 'wicket', 'run chase', 'powerplay', 'death overs'
            ],
            'football': [
                # Major Leagues
                'soccer', 'football', 'premier league', 'epl', 'champions league', 'ucl',
                'la liga', 'bundesliga', 'serie a', 'ligue 1', 'eredivisie',
                'fa cup', 'carabao cup', 'europa league', 'conference league',
                'world cup', 'euro', 'copa america', 'nations league',
                'mls', 'liga mx',
                # Premier League Teams
                'manchester united', 'man utd', 'manchester city', 'man city', 'liverpool',
                'arsenal', 'chelsea', 'tottenham', 'spurs', 'newcastle', 'aston villa',
                'west ham', 'brighton', 'wolves', 'everton', 'nottingham forest',
                'crystal palace', 'fulham', 'bournemouth', 'brentford', 'burnley',
                'sheffield united', 'luton',
                # Top European Clubs
                'real madrid', 'barcelona', 'barca', 'atletico madrid', 'sevilla', 'valencia',
                'bayern munich', 'bayern', 'dortmund', 'bvb', 'leipzig', 'leverkusen',
                'juventus', 'juve', 'inter milan', 'ac milan', 'napoli', 'roma', 'lazio', 'atalanta',
                'psg', 'paris saint-germain', 'marseille', 'lyon', 'monaco',
                'ajax', 'psv', 'feyenoord', 'porto', 'benfica', 'sporting',
                # Players
                'haaland', 'mbappe', 'salah', 'de bruyne', 'saka', 'bellingham',
                'vinicius', 'rodri', 'kane', 'son', 'bruno fernandes', 'rashford'
            ],
            'nba': [
                # League
                'nba', 'basketball', 'nba playoffs', 'nba finals', 'all-star',
                # Teams
                'lakers', 'los angeles lakers', 'celtics', 'boston celtics',
                'warriors', 'golden state', 'nuggets', 'denver nuggets',
                'heat', 'miami heat', 'bucks', 'milwaukee bucks',
                'suns', 'phoenix suns', 'nets', 'brooklyn nets',
                'knicks', 'new york knicks', '76ers', 'philadelphia 76ers', 'sixers',
                'clippers', 'la clippers', 'bulls', 'chicago bulls',
                'mavericks', 'dallas mavericks', 'mavs', 'rockets', 'houston rockets',
                'thunder', 'oklahoma city', 'okc', 'timberwolves', 'minnesota',
                'grizzlies', 'memphis', 'pelicans', 'new orleans',
                'kings', 'sacramento', 'jazz', 'utah jazz',
                'spurs', 'san antonio', 'hawks', 'atlanta hawks',
                'cavaliers', 'cleveland', 'cavs', 'pistons', 'detroit',
                'pacers', 'indiana', 'magic', 'orlando', 'raptors', 'toronto',
                'hornets', 'charlotte', 'wizards', 'washington', 'trail blazers', 'portland',
                # Players
                'lebron', 'lebron james', 'curry', 'steph curry', 'stephen curry',
                'durant', 'kevin durant', 'kd', 'giannis', 'antetokounmpo',
                'jokic', 'nikola jokic', 'embiid', 'joel embiid',
                'tatum', 'jayson tatum', 'luka', 'luka doncic', 'doncic',
                'morant', 'ja morant', 'booker', 'devin booker',
                'anthony edwards', 'ant edwards', 'sga', 'shai',
                'kawhi', 'paul george', 'jimmy butler', 'bam adebayo',
                'donovan mitchell', 'brunson', 'jalen brunson'
            ],
            'nfl': [
                # League
                'nfl', 'football', 'super bowl', 'nfl playoffs', 'nfl draft',
                'monday night football', 'sunday night football', 'thursday night football',
                # Teams - AFC
                'chiefs', 'kansas city chiefs', 'bills', 'buffalo bills',
                'dolphins', 'miami dolphins', 'patriots', 'new england patriots',
                'ravens', 'baltimore ravens', 'bengals', 'cincinnati bengals',
                'browns', 'cleveland browns', 'steelers', 'pittsburgh steelers',
                'texans', 'houston texans', 'colts', 'indianapolis colts',
                'jaguars', 'jacksonville jaguars', 'titans', 'tennessee titans',
                'broncos', 'denver broncos', 'chargers', 'la chargers', 'los angeles chargers',
                'raiders', 'las vegas raiders', 'jets', 'new york jets',
                # Teams - NFC
                'eagles', 'philadelphia eagles', 'cowboys', 'dallas cowboys',
                'giants', 'new york giants', 'commanders', 'washington commanders',
                '49ers', 'san francisco 49ers', 'niners', 'seahawks', 'seattle seahawks',
                'rams', 'la rams', 'los angeles rams', 'cardinals', 'arizona cardinals',
                'bears', 'chicago bears', 'lions', 'detroit lions',
                'packers', 'green bay packers', 'vikings', 'minnesota vikings',
                'falcons', 'atlanta falcons', 'panthers', 'carolina panthers',
                'saints', 'new orleans saints', 'buccaneers', 'tampa bay buccaneers', 'bucs',
                # Players
                'mahomes', 'patrick mahomes', 'allen', 'josh allen',
                'burrow', 'joe burrow', 'lamar', 'lamar jackson',
                'hurts', 'jalen hurts', 'herbert', 'justin herbert',
                'prescott', 'dak prescott', 'rodgers', 'aaron rodgers',
                'kelce', 'travis kelce', 'hill', 'tyreek hill',
                'jefferson', 'justin jefferson', 'chase', 'jamarr chase',
                'henry', 'derrick henry', 'mccaffrey', 'christian mccaffrey'
            ],
            'tennis': [
                # Tournaments
                'tennis', 'wimbledon', 'us open', 'australian open', 'french open',
                'roland garros', 'atp', 'wta', 'atp finals', 'wta finals',
                'indian wells', 'miami open', 'madrid open', 'rome masters',
                'canadian open', 'cincinnati masters', 'shanghai masters',
                # Players - Men
                'djokovic', 'novak djokovic', 'nadal', 'rafael nadal', 'rafa',
                'federer', 'roger federer', 'alcaraz', 'carlos alcaraz',
                'sinner', 'jannik sinner', 'medvedev', 'daniil medvedev',
                'zverev', 'alexander zverev', 'rublev', 'andrey rublev',
                'tsitsipas', 'stefanos tsitsipas', 'ruud', 'casper ruud',
                'fritz', 'taylor fritz', 'tiafoe', 'frances tiafoe',
                # Players - Women
                'swiatek', 'iga swiatek', 'sabalenka', 'aryna sabalenka',
                'gauff', 'coco gauff', 'rybakina', 'elena rybakina',
                'pegula', 'jessica pegula', 'jabeur', 'ons jabeur',
                'osaka', 'naomi osaka', 'halep', 'simona halep'
            ],
            'ufc': [
                # League
                'ufc', 'mma', 'mixed martial arts', 'fight night', 'ppv',
                'ufc numbered', 'bellator', 'pfl', 'one championship',
                # Weight Classes
                'heavyweight', 'light heavyweight', 'middleweight', 'welterweight',
                'lightweight', 'featherweight', 'bantamweight', 'flyweight',
                'strawweight', "women's",
                # Fighters
                'jones', 'jon jones', 'adesanya', 'israel adesanya', 'izzy',
                'makhachev', 'islam makhachev', 'volkanovski', 'alexander volkanovski', 'volk',
                'o\'malley', 'sean o\'malley', 'chimaev', 'khamzat chimaev',
                'edwards', 'leon edwards', 'usman', 'kamaru usman',
                'poirier', 'dustin poirier', 'gaethje', 'justin gaethje',
                'pereira', 'alex pereira', 'topuria', 'ilia topuria',
                'strickland', 'sean strickland', 'aspinall', 'tom aspinall',
                'grasso', 'alexa grasso', 'shevchenko', 'valentina shevchenko'
            ],
            'mlb': [
                'mlb', 'baseball', 'world series', 'mlb playoffs',
                'yankees', 'dodgers', 'astros', 'braves', 'phillies',
                'padres', 'mets', 'red sox', 'cubs', 'cardinals',
                'ohtani', 'shohei ohtani', 'judge', 'aaron judge', 'trout', 'mike trout'
            ],
            'nhl': [
                'nhl', 'hockey', 'stanley cup', 'nhl playoffs',
                'oilers', 'panthers', 'bruins', 'rangers', 'avalanche',
                'maple leafs', 'leafs', 'canadiens', 'penguins', 'blackhawks',
                'mcdavid', 'connor mcdavid', 'crosby', 'sidney crosby', 'ovechkin'
            ],
            'golf': [
                'golf', 'pga', 'masters', 'us open golf', 'british open', 'pga championship',
                'ryder cup', 'liv golf',
                'scottie scheffler', 'rory mcilroy', 'jon rahm', 'brooks koepka'
            ]
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
    
    def get_all_sports_series(self) -> List[Dict]:
        """
        Fetch all sports leagues from Polymarket's /sports endpoint.
        Returns list of sports with series_id for filtering.
        
        GET https://gamma-api.polymarket.com/sports
        """
        try:
            url = f"{self.gamma_url}/sports"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"⚠️ /sports endpoint returned {response.status_code}")
                return []
            
            data = response.json()
            print(f"✅ Found {len(data)} sports series from /sports endpoint")
            return data
            
        except Exception as e:
            print(f"❌ Error fetching sports series: {e}")
            return []
    
    def get_events_by_series(self, series_id: str, include_upcoming: bool = True) -> List[Dict]:
        """
        Fetch all events for a specific sports league.
        
        GET https://gamma-api.polymarket.com/events?series_id={series_id}&active=true&closed=false
        """
        try:
            url = f"{self.gamma_url}/events?series_id={series_id}&active=true&closed=false"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data if data else []
            
        except Exception as e:
            print(f"❌ Error fetching events for series {series_id}: {e}")
            return []
    
    def get_markets_by_tag(self, tag_id: str) -> List[Dict]:
        """
        Fetch markets filtered by tag (game bets vs futures).
        
        GET https://gamma-api.polymarket.com/events?tag_id={tag_id}&active=true&closed=false
        """
        try:
            url = f"{self.gamma_url}/events?tag_id={tag_id}&active=true&closed=false"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data if data else []
            
        except Exception as e:
            print(f"❌ Error fetching markets by tag {tag_id}: {e}")
            return []
    
    def get_upcoming_markets(self, hours_ahead: int = 24) -> List[Dict]:
        """
        Fetch markets for games scheduled in the next X hours.
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate end time
            end_time = datetime.now() + timedelta(hours=hours_ahead)
            end_timestamp = int(end_time.timestamp())
            
            # Fetch events with end_date_min filter
            url = f"{self.gamma_url}/events?active=true&closed=false&end_date_max={end_timestamp}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return data if data else []
            
        except Exception as e:
            print(f"❌ Error fetching upcoming markets: {e}")
            return []
    
    def get_sports_markets_v2(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        NEW improved method that:
        1. First fetches all sports series from /sports
        2. For each priority sport, fetches events by series_id
        3. Includes both LIVE and UPCOMING markets
        4. Falls back to keyword filtering if API fails
        """
        from config import Config
        
        all_markets = []
        
        print(f"\n🔍 Fetching sports markets using improved v2 method...")
        
        # Try to use the /sports endpoint first
        try:
            sports_series = self.get_all_sports_series()
            
            if sports_series:
                # Get priority sports from config
                priority_sports = getattr(Config, 'PRIORITY_SPORTS', 
                                         ['cricket', 'football', 'nba', 'nfl', 'tennis', 'ufc'])
                
                print(f"🎯 Priority sports: {', '.join(priority_sports)}")
                
                # Fetch events for each sport series
                for series in sports_series:
                    series_name = series.get('name', '').lower()
                    series_id = series.get('id', '')
                    
                    # Check if this series matches any priority sport
                    matched_sport = None
                    for sport in priority_sports:
                        if sport in series_name or any(
                            keyword in series_name 
                            for keyword in self.sport_keywords.get(sport, [])[:5]  # Check first 5 keywords
                        ):
                            matched_sport = sport
                            break
                    
                    if matched_sport and series_id:
                        print(f"  📥 Fetching {matched_sport} events from series: {series.get('name', 'Unknown')}")
                        events = self.get_events_by_series(series_id)
                        
                        # Add sport tag to each event/market
                        for event in events:
                            event['sport'] = matched_sport
                            # Extract markets from event if nested
                            if 'markets' in event:
                                for market in event['markets']:
                                    market['sport'] = matched_sport
                                    market['is_live'] = event.get('active', False)
                                    all_markets.append(market)
                            else:
                                event['is_live'] = event.get('active', False)
                                all_markets.append(event)
                
                print(f"✅ Fetched {len(all_markets)} markets from /sports endpoint")
        
        except Exception as e:
            print(f"⚠️ /sports endpoint method failed: {e}")
            print("⚠️ Falling back to traditional keyword filtering...")
        
        # Fallback: Use traditional keyword filtering if /sports method didn't work well
        if len(all_markets) < 10:
            print(f"⚠️ Only found {len(all_markets)} markets via /sports, using fallback...")
            fallback_markets = self.get_sports_markets(limit=limit)
            
            # Merge with existing, avoid duplicates
            existing_ids = {m.get('id') for m in all_markets}
            for market in fallback_markets:
                if market.get('id') not in existing_ids:
                    all_markets.append(market)
        
        # Include upcoming markets if configured
        try:
            if getattr(Config, 'INCLUDE_UPCOMING_MARKETS', True):
                hours_ahead = getattr(Config, 'UPCOMING_HOURS_AHEAD', 24)
                upcoming = self.get_upcoming_markets(hours_ahead=hours_ahead)
                
                # Add to all_markets, avoiding duplicates
                existing_ids = {m.get('id') for m in all_markets}
                for market in upcoming:
                    if market.get('id') not in existing_ids:
                        # Detect sport for upcoming markets
                        market['sport'] = self._detect_sport(market.get('question', ''))
                        market['is_live'] = False
                        all_markets.append(market)
                
                print(f"✅ Added {len([m for m in all_markets if not m.get('is_live')])} upcoming markets")
        except Exception as e:
            print(f"⚠️ Error fetching upcoming markets: {e}")
        
        # Limit to requested size
        all_markets = all_markets[:limit]
        
        # Print summary by sport
        print(f"\n📊 Total markets found: {len(all_markets)}")
        print(f"🏏 Cricket markets: {len([m for m in all_markets if m.get('sport') == 'cricket'])}")
        print(f"⚽ Football markets: {len([m for m in all_markets if m.get('sport') == 'football'])}")
        print(f"🏀 NBA markets: {len([m for m in all_markets if m.get('sport') == 'nba'])}")
        print(f"🏈 NFL markets: {len([m for m in all_markets if m.get('sport') == 'nfl'])}")
        print(f"🎾 Tennis markets: {len([m for m in all_markets if m.get('sport') == 'tennis'])}")
        print(f"🥊 UFC markets: {len([m for m in all_markets if m.get('sport') == 'ufc'])}")
        print(f"📅 Upcoming markets: {len([m for m in all_markets if not m.get('is_live')])}")
        print(f"🔴 Live markets: {len([m for m in all_markets if m.get('is_live')])}")
        
        return all_markets
