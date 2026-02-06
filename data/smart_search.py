"""
Smart Search for Polymarket Sports Markets

Provides intelligent search with:
- Proper Polymarket API integration
- Fuzzy keyword matching
- Interactive suggestions (1, 2, 3...)
- Session tracking for user selections
"""

import os
import sys
import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class SmartSearch:
    """
    Smart search for Polymarket markets with interactive suggestions.
    """
    
    # Extended team aliases for matching
    TEAM_ALIASES = {
        # Football (Soccer) - Major Teams
        'barcelona': ['barca', 'barça', 'fcb', 'blaugrana'],
        'real madrid': ['real', 'madrid', 'los blancos', 'rmcf', 'madridistas'],
        'manchester united': ['man utd', 'man u', 'united', 'mufc', 'red devils', 'manu'],
        'manchester city': ['man city', 'city', 'mcfc', 'citizens'],
        'liverpool': ['pool', 'lfc', 'reds', 'anfield'],
        'chelsea': ['cfc', 'blues', 'stamford bridge'],
        'arsenal': ['gunners', 'afc', 'gooners', 'ars'],
        'tottenham': ['spurs', 'thfc', 'tottenham hotspur', 'lilywhites'],
        'bayern munich': ['bayern', 'fcb munich', 'bavaria', 'bavarians'],
        'paris saint-germain': ['psg', 'paris', 'les parisiens'],
        'juventus': ['juve', 'old lady', 'bianconeri'],
        'inter milan': ['inter', 'internazionale', 'nerazzurri'],
        'ac milan': ['milan', 'rossoneri', 'diavoli'],
        'atletico madrid': ['atletico', 'atleti', 'colchoneros'],
        'borussia dortmund': ['dortmund', 'bvb', 'die borussen'],
        'ajax': ['ajax amsterdam', 'godenzonen'],
        'benfica': ['slb', 'encarnado'],
        'porto': ['fcp', 'portistas'],
        
        # NBA Teams
        'los angeles lakers': ['lakers', 'lal', 'lake show', 'la lakers'],
        'boston celtics': ['celtics', 'celts', 'bos', 'c\'s'],
        'golden state warriors': ['warriors', 'gsw', 'dubs', 'golden state'],
        'brooklyn nets': ['nets', 'bkn', 'brooklyn'],
        'miami heat': ['heat', 'mia', 'heatles'],
        'chicago bulls': ['bulls', 'chi', 'chicago'],
        'new york knicks': ['knicks', 'nyk', 'ny knicks'],
        'los angeles clippers': ['clippers', 'lac', 'clips'],
        'phoenix suns': ['suns', 'phx', 'phoenix'],
        'milwaukee bucks': ['bucks', 'mil', 'milwaukee'],
        'denver nuggets': ['nuggets', 'den', 'denver'],
        'philadelphia 76ers': ['76ers', 'sixers', 'phi', 'philly'],
        'dallas mavericks': ['mavs', 'mavericks', 'dal', 'dallas'],
        
        # NFL Teams
        'kansas city chiefs': ['chiefs', 'kc', 'kansas city'],
        'new england patriots': ['patriots', 'pats', 'ne', 'new england'],
        'dallas cowboys': ['cowboys', 'dal', 'dallas', 'americas team'],
        'san francisco 49ers': ['49ers', 'niners', 'sf', 'san francisco'],
        'buffalo bills': ['bills', 'buf', 'buffalo'],
        'philadelphia eagles': ['eagles', 'phi', 'philly', 'birds'],
        'baltimore ravens': ['ravens', 'bal', 'baltimore'],
        'cincinnati bengals': ['bengals', 'cin', 'cincy'],
        
        # Cricket Teams
        'mumbai indians': ['mi', 'mumbai', 'paltan'],
        'chennai super kings': ['csk', 'chennai', 'yellove'],
        'royal challengers bangalore': ['rcb', 'bangalore', 'challengers'],
        'kolkata knight riders': ['kkr', 'kolkata', 'knights'],
        'delhi capitals': ['dc', 'delhi', 'capitals'],
        'rajasthan royals': ['rr', 'rajasthan', 'royals'],
        'sunrisers hyderabad': ['srh', 'sunrisers', 'hyderabad'],
        'punjab kings': ['pbks', 'punjab', 'kings xi'],
        'gujarat titans': ['gt', 'gujarat', 'titans'],
        'lucknow super giants': ['lsg', 'lucknow', 'super giants'],
    }
    
    def __init__(self, polymarket_client=None):
        self.polymarket = polymarket_client
        
        # Session storage for pending selections
        # chat_id -> {query, suggestions, timestamp}
        self._pending_selections = {}
        
        # Cache for recent searches
        self._search_cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        print("🔍 SmartSearch initialized")
    
    def search(self, query: str, chat_id: str = None) -> Dict:
        """
        Search for markets matching the query.
        
        Returns:
            {
                'found': bool,
                'exact_match': bool,
                'market': dict or None,
                'suggestions': list,
                'message': str (formatted for display)
            }
        """
        result = {
            'found': False,
            'exact_match': False,
            'market': None,
            'suggestions': [],
            'message': '',
            'query': query,
        }
        
        # Check if this is a number selection from pending suggestions
        if chat_id and query.strip().isdigit():
            selection = self._handle_number_selection(chat_id, int(query.strip()))
            if selection:
                return selection
        
        # Normalize the query
        normalized = self._normalize_query(query)
        
        # Get all sports markets from Polymarket
        markets = self._get_markets()
        
        if not markets:
            result['message'] = "⚠️ Could not fetch markets from Polymarket. Try again later."
            return result
        
        # Score and rank markets
        scored_markets = self._score_markets(markets, normalized)
        
        if not scored_markets:
            # No matches - try fuzzy search
            fuzzy_matches = self._fuzzy_search(markets, normalized)
            
            if fuzzy_matches:
                result['suggestions'] = fuzzy_matches[:5]
                result['message'] = self._format_suggestions(query, fuzzy_matches[:5])
                
                # Store for later selection
                if chat_id:
                    self._store_pending(chat_id, query, fuzzy_matches[:5])
            else:
                result['message'] = self._format_no_results(query)
            
            return result
        
        # Check if top match is high confidence
        top_market = scored_markets[0]
        
        if top_market['match_score'] >= 20:
            # High confidence match
            result['found'] = True
            result['exact_match'] = True
            result['market'] = top_market
            result['message'] = "✅ Found exact match!"
        else:
            # Multiple possible matches - show suggestions
            result['found'] = True
            result['suggestions'] = scored_markets[:5]
            result['market'] = top_market  # Default to best match
            result['message'] = self._format_suggestions(query, scored_markets[:5])
            
            if chat_id:
                self._store_pending(chat_id, query, scored_markets[:5])
        
        return result
    
    def _normalize_query(self, query: str) -> Dict:
        """Normalize and parse the query."""
        query_lower = query.lower().strip()
        
        # Apply team alias corrections
        corrected = query_lower
        for canonical, aliases in self.TEAM_ALIASES.items():
            for alias in aliases:
                # Match whole words
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, corrected):
                    corrected = re.sub(pattern, canonical, corrected)
        
        # Extract team names
        teams = self._extract_teams(corrected)
        
        # Detect sport
        sport = self._detect_sport(corrected)
        
        # Extract keywords
        keywords = [w for w in corrected.split() if len(w) > 2]
        
        return {
            'original': query,
            'corrected': corrected,
            'teams': teams,
            'sport': sport,
            'keywords': keywords,
        }
    
    def _extract_teams(self, query: str) -> List[str]:
        """Extract team names from query."""
        patterns = [
            r'(.+?)\s+(?:vs?\.?|versus|against)\s+(.+?)(?:\s|$)',
            r'(.+?)\s+(?:plays?|@|at)\s+(.+?)(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                team1 = re.sub(r'\s+(match|game|today|tomorrow|win)$', '', match.group(1).strip())
                team2 = re.sub(r'\s+(match|game|today|tomorrow|win)$', '', match.group(2).strip())
                return [team1, team2]
        
        # Try to find known team names
        found = []
        for canonical in self.TEAM_ALIASES.keys():
            if canonical in query:
                found.append(canonical)
        
        return found[:2] if found else [query.strip()]
    
    def _detect_sport(self, query: str) -> str:
        """Detect sport from query."""
        sport_keywords = {
            'football': ['football', 'soccer', 'premier league', 'la liga', 'ucl', 'champions league'],
            'nba': ['nba', 'basketball', 'lakers', 'celtics', 'warriors'],
            'nfl': ['nfl', 'super bowl', 'chiefs', 'eagles', 'cowboys'],
            'cricket': ['cricket', 'ipl', 't20', 'odi', 'test match', 'csk', 'mi', 'rcb'],
        }
        
        for sport, keywords in sport_keywords.items():
            if any(kw in query for kw in keywords):
                return sport
        
        return 'unknown'
    
    def _get_markets(self) -> List[Dict]:
        """Fetch markets from Polymarket."""
        if not self.polymarket:
            return []
        
        # Check cache
        cache_key = 'all_sports_markets'
        if cache_key in self._search_cache:
            cached = self._search_cache[cache_key]
            if datetime.now() - cached['timestamp'] < timedelta(seconds=self._cache_ttl):
                return cached['data']
        
        try:
            markets = self.polymarket.get_sports_markets(limit=500)
            
            # Cache the results
            self._search_cache[cache_key] = {
                'data': markets,
                'timestamp': datetime.now()
            }
            
            return markets
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []
    
    def _score_markets(self, markets: List[Dict], normalized: Dict) -> List[Dict]:
        """Score markets based on query match."""
        scored = []
        
        teams = [t.lower() for t in normalized.get('teams', [])]
        keywords = normalized.get('keywords', [])
        sport = normalized.get('sport', '')
        
        for market in markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            full_text = question + ' ' + description
            
            score = 0
            
            # Team name matching (highest priority)
            teams_found = 0
            for team in teams:
                if team in full_text:
                    score += 15
                    teams_found += 1
                else:
                    # Check aliases too
                    for canonical, aliases in self.TEAM_ALIASES.items():
                        if team == canonical or team in aliases:
                            if canonical in full_text or any(a in full_text for a in aliases):
                                score += 12
                                teams_found += 1
                                break
            
            # Bonus for matching both teams
            if teams_found >= 2:
                score += 10
            
            # Keyword matching
            for keyword in keywords:
                if keyword in full_text:
                    score += 3
            
            # Sport matching
            if sport and sport != 'unknown':
                market_sport = market.get('sport', '').lower()
                if sport == market_sport:
                    score += 5
            
            if score > 0:
                market['match_score'] = score
                scored.append(market)
        
        # Sort by score
        scored.sort(key=lambda m: m.get('match_score', 0), reverse=True)
        
        return scored
    
    def _fuzzy_search(self, markets: List[Dict], normalized: Dict) -> List[Dict]:
        """Fuzzy search when exact match fails."""
        query_text = normalized.get('corrected', '')
        results = []
        
        for market in markets:
            question = market.get('question', '')
            
            # Calculate similarity
            similarity = SequenceMatcher(None, query_text.lower(), question.lower()).ratio()
            
            # Also check for partial word matches
            query_words = set(query_text.lower().split())
            question_words = set(question.lower().split())
            word_overlap = len(query_words & question_words)
            
            combined_score = (similarity * 50) + (word_overlap * 10)
            
            if combined_score > 15:
                market['fuzzy_score'] = combined_score
                results.append(market)
        
        results.sort(key=lambda m: m.get('fuzzy_score', 0), reverse=True)
        
        return results[:10]
    
    def _format_suggestions(self, query: str, suggestions: List[Dict]) -> str:
        """Format suggestions for display."""
        lines = [
            f"<b>🔍 Search: </b><i>{query}</i>",
            "",
            "<b>Did you mean one of these?</b>",
            "<i>Reply with the number to select:</i>",
            ""
        ]
        
        for i, market in enumerate(suggestions[:5], 1):
            question = market.get('question', 'Unknown')[:60]
            price = self._get_price(market)
            score = market.get('match_score', market.get('fuzzy_score', 0))
            
            # Star rating based on match confidence
            if score >= 20:
                stars = "⭐⭐⭐"
            elif score >= 10:
                stars = "⭐⭐"
            else:
                stars = "⭐"
            
            lines.append(f"<b>{i}.</b> {question}...")
            lines.append(f"    📊 {price*100:.0f}% | {stars}")
            lines.append("")
        
        lines.append("<b>💡 Example:</b> Reply <b>1</b> to select the first option")
        
        return "\n".join(lines)
    
    def _format_no_results(self, query: str) -> str:
        """Format message when no results found."""
        lines = [
            f"<b>❌ No markets found for:</b> <i>{query}</i>",
            "",
            "<b>💡 Suggestions:</b>",
            "• Try full team names (e.g., 'Barcelona vs Real Madrid')",
            "• Check spelling",
            "• Markets may not exist for this match yet",
            "",
            "<b>🔥 Tip:</b> Try searching for:",
            "• /info Lakers vs Celtics",
            "• /info Manchester United",
            "• /info Champions League",
        ]
        
        return "\n".join(lines)
    
    def _get_price(self, market: Dict) -> float:
        """Extract price from market."""
        price = market.get('current_price')
        if not price:
            prices = market.get('outcomePrices', [])
            if prices:
                try:
                    price = float(prices[0])
                except:
                    price = 0.5
            else:
                price = 0.5
        try:
            return float(price)
        except:
            return 0.5
    
    def _store_pending(self, chat_id: str, query: str, suggestions: List[Dict]):
        """Store pending selections for a user."""
        self._pending_selections[str(chat_id)] = {
            'query': query,
            'suggestions': suggestions,
            'timestamp': datetime.now(),
        }
    
    def _handle_number_selection(self, chat_id: str, number: int) -> Optional[Dict]:
        """Handle when user replies with a number."""
        chat_id = str(chat_id)
        
        if chat_id not in self._pending_selections:
            return None
        
        pending = self._pending_selections[chat_id]
        
        # Check if expired (10 minutes)
        if datetime.now() - pending['timestamp'] > timedelta(minutes=10):
            del self._pending_selections[chat_id]
            return None
        
        suggestions = pending['suggestions']
        
        if number < 1 or number > len(suggestions):
            return None
        
        # Get selected market
        selected = suggestions[number - 1]
        
        # Clear pending
        del self._pending_selections[chat_id]
        
        return {
            'found': True,
            'exact_match': True,
            'market': selected,
            'suggestions': [],
            'message': f"✅ Selected: {selected.get('question', 'Unknown')[:60]}...",
            'query': pending['query'],
        }
    
    def has_pending_selection(self, chat_id: str) -> bool:
        """Check if user has pending selection."""
        chat_id = str(chat_id)
        if chat_id in self._pending_selections:
            pending = self._pending_selections[chat_id]
            if datetime.now() - pending['timestamp'] < timedelta(minutes=10):
                return True
        return False


# Singleton
_smart_search = None

def get_smart_search(polymarket_client=None) -> SmartSearch:
    """Get or create SmartSearch instance."""
    global _smart_search
    if _smart_search is None:
        _smart_search = SmartSearch(polymarket_client)
    elif polymarket_client:
        _smart_search.polymarket = polymarket_client
    return _smart_search
