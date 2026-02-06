"""
Advanced Match Info Provider

Provides comprehensive match insights using multiple FREE data sources:
- ESPN API (free) for match schedules, team info, head-to-head
- Football-Data.org (free tier) for football stats
- Polymarket for market data
- AI analysis for predictions

This module is designed to ALWAYS provide useful info, even without
an exact market match.
"""

import os
import sys
import requests
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class AdvancedMatchInfo:
    """
    Advanced match information provider.
    
    Uses multiple free data sources to provide comprehensive insights.
    """
    
    # ESPN API endpoints (FREE!)
    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
    
    # Football-Data.org (FREE tier: 10 req/min)
    FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
    
    # Common team name variations for matching
    TEAM_ALIASES = {
        # Football (Soccer)
        'barcelona': ['barca', 'barça', 'fc barcelona', 'fcb'],
        'real madrid': ['real', 'madrid', 'los blancos', 'rmcf'],
        'manchester united': ['man utd', 'man u', 'united', 'mufc', 'red devils'],
        'manchester city': ['man city', 'city', 'mcfc', 'citizens'],
        'liverpool': ['pool', 'lfc', 'reds'],
        'chelsea': ['cfc', 'blues'],
        'arsenal': ['gunners', 'afc', 'gooners'],
        'tottenham': ['spurs', 'thfc', 'tottenham hotspur'],
        'bayern munich': ['bayern', 'fcb', 'bavaria'],
        'paris saint-germain': ['psg', 'paris'],
        'juventus': ['juve', 'old lady'],
        'inter milan': ['inter', 'internazionale'],
        'ac milan': ['milan', 'rossoneri'],
        'atletico madrid': ['atletico', 'atleti'],
        'borussia dortmund': ['dortmund', 'bvb'],
        
        # NBA
        'los angeles lakers': ['lakers', 'lal', 'lake show'],
        'boston celtics': ['celtics', 'celts', 'bos'],
        'golden state warriors': ['warriors', 'gsw', 'dubs'],
        'brooklyn nets': ['nets', 'bkn'],
        'miami heat': ['heat', 'mia'],
        'chicago bulls': ['bulls', 'chi'],
        'new york knicks': ['knicks', 'nyk'],
        'los angeles clippers': ['clippers', 'lac'],
        'phoenix suns': ['suns', 'phx'],
        'milwaukee bucks': ['bucks', 'mil'],
        
        # NFL
        'kansas city chiefs': ['chiefs', 'kc'],
        'new england patriots': ['patriots', 'pats', 'ne'],
        'dallas cowboys': ['cowboys', 'dallas'],
        'san francisco 49ers': ['49ers', 'niners', 'sf'],
        'buffalo bills': ['bills', 'buf'],
        'philadelphia eagles': ['eagles', 'philly'],
    }
    
    # Sport detection keywords
    SPORT_KEYWORDS = {
        'football': ['football', 'soccer', 'premier league', 'la liga', 'bundesliga', 'serie a', 'champions league', 'ucl', 'epl'],
        'nba': ['nba', 'basketball', 'lakers', 'celtics', 'warriors'],
        'nfl': ['nfl', 'american football', 'superbowl', 'chiefs', 'cowboys'],
        'cricket': ['cricket', 'ipl', 't20', 'odi', 'test match', 'ashes'],
        'tennis': ['tennis', 'wimbledon', 'us open', 'french open', 'australian open'],
        'mma': ['ufc', 'mma', 'fight', 'boxing'],
    }
    
    def __init__(self, polymarket_client=None, ai_analyzer=None, team_stats_provider=None):
        self.polymarket = polymarket_client
        self.ai_analyzer = ai_analyzer
        self.team_stats = team_stats_provider
        self.football_api_key = os.getenv('FOOTBALL_DATA_API_KEY', '')
        
        # Cache for recent queries
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        print("📊 Advanced Match Info Provider initialized")
    
    def get_match_info(self, query: str) -> Dict:
        """
        Get comprehensive match information for a query.
        
        Returns insights even if no exact market is found.
        """
        result = {
            'query': query,
            'interpreted': query,
            'market_found': False,
            'market': None,
            'teams': [],
            'sport': 'unknown',
            'match_data': None,
            'head_to_head': None,
            'team_stats': {},
            'prediction': None,
            'insights': [],
            'trading_recommendation': None,
        }
        
        # Step 1: Parse and normalize the query
        parsed = self._parse_query(query)
        result['interpreted'] = parsed['normalized']
        result['teams'] = parsed['teams']
        result['sport'] = parsed['sport']
        
        # Step 2: Search for matching Polymarket market
        if self.polymarket:
            market = self._find_best_market(parsed)
            if market:
                result['market_found'] = True
                result['market'] = market
        
        # Step 3: Get match data from ESPN (FREE!)
        match_data = self._get_espn_match_data(parsed)
        if match_data:
            result['match_data'] = match_data
        
        # Step 4: Get head-to-head history
        if len(parsed['teams']) >= 2:
            h2h = self._get_head_to_head(parsed['teams'][0], parsed['teams'][1], parsed['sport'])
            result['head_to_head'] = h2h
        
        # Step 5: Get team statistics
        for team in parsed['teams'][:2]:
            stats = self._get_team_stats(team, parsed['sport'])
            if stats:
                result['team_stats'][team] = stats
        
        # Step 6: Generate prediction
        prediction = self._generate_prediction(result)
        result['prediction'] = prediction
        
        # Step 7: Generate insights
        insights = self._generate_insights(result)
        result['insights'] = insights
        
        # Step 8: Trading recommendation
        recommendation = self._generate_trading_recommendation(result)
        result['trading_recommendation'] = recommendation
        
        return result
    
    def _parse_query(self, query: str) -> Dict:
        """Parse and normalize the query."""
        query_lower = query.lower().strip()
        
        # Detect sport
        sport = 'football'  # Default
        for sport_name, keywords in self.SPORT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                sport = sport_name
                break
        
        # Extract teams
        teams = self._extract_teams(query_lower)
        
        # Normalize team names
        normalized_teams = []
        for team in teams:
            normalized = self._normalize_team_name(team)
            normalized_teams.append(normalized)
        
        # Build normalized query
        if len(normalized_teams) >= 2:
            normalized = f"{normalized_teams[0]} vs {normalized_teams[1]}"
        elif normalized_teams:
            normalized = normalized_teams[0]
        else:
            normalized = query
        
        return {
            'original': query,
            'normalized': normalized,
            'teams': normalized_teams,
            'sport': sport,
        }
    
    def _extract_teams(self, query: str) -> List[str]:
        """Extract team names from query."""
        # Try common patterns
        patterns = [
            r'(.+?)\s+(?:vs?\.?|versus|against)\s+(.+?)(?:\s+(?:match|game|today|tomorrow))?$',
            r'(.+?)\s+(?:plays?|@|at)\s+(.+?)(?:\s+(?:match|game|today|tomorrow))?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                # Clean up trailing words
                team2 = re.sub(r'\s+(match|game|today|tomorrow|win|chance)$', '', team2, flags=re.IGNORECASE)
                return [team1, team2]
        
        # Try to find known team names
        found_teams = []
        for canonical, aliases in self.TEAM_ALIASES.items():
            all_names = [canonical] + aliases
            for name in all_names:
                if name in query:
                    found_teams.append(canonical)
                    break
        
        if found_teams:
            return found_teams[:2]
        
        # Last resort: return query as single team
        clean = re.sub(r'\s+(match|game|today|tomorrow|win|chance)$', '', query, flags=re.IGNORECASE)
        return [clean] if clean else []
    
    def _normalize_team_name(self, team: str) -> str:
        """Normalize team name to canonical form."""
        team_lower = team.lower().strip()
        
        # Check aliases
        for canonical, aliases in self.TEAM_ALIASES.items():
            if team_lower == canonical or team_lower in aliases:
                return canonical.title()
        
        # Use fuzzy matching for close matches
        best_match = None
        best_score = 0.6  # Minimum threshold
        
        for canonical, aliases in self.TEAM_ALIASES.items():
            all_names = [canonical] + aliases
            for name in all_names:
                score = SequenceMatcher(None, team_lower, name).ratio()
                if score > best_score:
                    best_score = score
                    best_match = canonical.title()
        
        return best_match if best_match else team.title()
    
    def _find_best_market(self, parsed: Dict) -> Optional[Dict]:
        """Find the best matching Polymarket market."""
        try:
            markets = self.polymarket.get_sports_markets()
            if not markets:
                return None
            
            scored = []
            teams = [t.lower() for t in parsed['teams']]
            
            for market in markets:
                question = market.get('question', '').lower()
                score = 0
                
                # Team name matching (high priority)
                for team in teams:
                    if team in question:
                        score += 20
                    # Partial match
                    elif any(word in question for word in team.split() if len(word) > 3):
                        score += 10
                
                # Sport matching
                if parsed['sport'] in question or parsed['sport'] in market.get('description', '').lower():
                    score += 5
                
                if score > 0:
                    market['match_score'] = score
                    scored.append(market)
            
            if scored:
                scored.sort(key=lambda m: m.get('match_score', 0), reverse=True)
                return scored[0]
            
            return None
            
        except Exception as e:
            print(f"Market search error: {e}")
            return None
    
    def _get_espn_match_data(self, parsed: Dict) -> Optional[Dict]:
        """Fetch match data from ESPN (FREE API)."""
        try:
            sport = parsed['sport']
            
            # ESPN sport endpoints
            sport_endpoints = {
                'football': '/soccer/eng.1/scoreboard',  # Premier League
                'nba': '/basketball/nba/scoreboard',
                'nfl': '/football/nfl/scoreboard',
            }
            
            endpoint = sport_endpoints.get(sport)
            if not endpoint:
                return None
            
            url = f"{self.ESPN_BASE}{endpoint}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            events = data.get('events', [])
            
            # Find matching event
            teams = [t.lower() for t in parsed['teams']]
            
            for event in events:
                name = event.get('name', '').lower()
                short_name = event.get('shortName', '').lower()
                
                match_count = sum(1 for team in teams if team in name or team in short_name)
                
                if match_count >= 1:
                    # Extract useful info
                    competitions = event.get('competitions', [{}])
                    if competitions:
                        comp = competitions[0]
                        competitors = comp.get('competitors', [])
                        
                        return {
                            'name': event.get('name'),
                            'date': event.get('date'),
                            'status': event.get('status', {}).get('type', {}).get('description'),
                            'venue': comp.get('venue', {}).get('fullName'),
                            'competitors': [
                                {
                                    'name': c.get('team', {}).get('displayName'),
                                    'score': c.get('score'),
                                    'home': c.get('homeAway') == 'home',
                                    'winner': c.get('winner', False),
                                }
                                for c in competitors
                            ]
                        }
            
            return None
            
        except Exception as e:
            print(f"ESPN API error: {e}")
            return None
    
    def _get_head_to_head(self, team1: str, team2: str, sport: str) -> Optional[Dict]:
        """Get head-to-head history between two teams."""
        try:
            if sport == 'football' and self.football_api_key:
                # Try Football-Data.org
                return self._get_football_h2h(team1, team2)
            
            # Fallback: use cached/heuristic data
            return self._get_cached_h2h(team1, team2)
            
        except Exception as e:
            print(f"H2H error: {e}")
            return None
    
    def _get_football_h2h(self, team1: str, team2: str) -> Optional[Dict]:
        """Get H2H from Football-Data.org (requires API key)."""
        if not self.football_api_key:
            return None
        
        # This would require team ID lookup - simplified version
        return {
            'source': 'football-data.org',
            'available': False,
            'note': 'Full H2H requires team ID mapping'
        }
    
    def _get_cached_h2h(self, team1: str, team2: str) -> Dict:
        """Return heuristic H2H data for common matchups."""
        # Well-known rivalries with estimated stats
        rivalries = {
            ('barcelona', 'real madrid'): {'team1_wins': 96, 'draws': 52, 'team2_wins': 100, 'total': 248},
            ('manchester united', 'liverpool'): {'team1_wins': 81, 'draws': 58, 'team2_wins': 68, 'total': 207},
            ('arsenal', 'tottenham'): {'team1_wins': 84, 'draws': 53, 'team2_wins': 63, 'total': 200},
            ('los angeles lakers', 'boston celtics'): {'team1_wins': 162, 'draws': 0, 'team2_wins': 200, 'total': 362},
            ('manchester city', 'manchester united'): {'team1_wins': 57, 'draws': 52, 'team2_wins': 78, 'total': 187},
        }
        
        key1 = (team1.lower(), team2.lower())
        key2 = (team2.lower(), team1.lower())
        
        if key1 in rivalries:
            data = rivalries[key1]
            return {
                'team1': team1,
                'team2': team2,
                'team1_wins': data['team1_wins'],
                'team2_wins': data['team2_wins'],
                'draws': data['draws'],
                'total_matches': data['total'],
                'source': 'historical_data'
            }
        elif key2 in rivalries:
            data = rivalries[key2]
            return {
                'team1': team1,
                'team2': team2,
                'team1_wins': data['team2_wins'],
                'team2_wins': data['team1_wins'],
                'draws': data['draws'],
                'total_matches': data['total'],
                'source': 'historical_data'
            }
        
        return None
    
    def _get_team_stats(self, team: str, sport: str) -> Optional[Dict]:
        """Get team statistics."""
        if self.team_stats:
            try:
                return self.team_stats.get_team_stats(team, sport)
            except:
                pass
        
        # Fallback: fetch from ESPN team stats
        return self._get_espn_team_stats(team, sport)
    
    def _get_espn_team_stats(self, team: str, sport: str) -> Optional[Dict]:
        """Fetch team stats from ESPN."""
        # Simplified - would need team ID lookup
        return None
    
    def _generate_prediction(self, data: Dict) -> Dict:
        """Generate prediction using all available data."""
        prediction = {
            'winner': None,
            'confidence': 0.5,
            'reasoning': [],
        }
        
        teams = data['teams']
        if len(teams) < 2:
            return prediction
        
        team1, team2 = teams[0], teams[1]
        score1, score2 = 0, 0
        reasons = []
        
        # Factor 1: Market price (if available)
        if data['market']:
            price = self._get_market_price(data['market'])
            if price > 0.5:
                score1 += (price - 0.5) * 40
                reasons.append(f"Market favors {team1} ({price*100:.0f}%)")
            else:
                score2 += (0.5 - price) * 40
                reasons.append(f"Market favors {team2} ({(1-price)*100:.0f}%)")
        
        # Factor 2: Head-to-head
        h2h = data.get('head_to_head')
        if h2h and h2h.get('total_matches', 0) > 0:
            t1_wins = h2h.get('team1_wins', 0)
            t2_wins = h2h.get('team2_wins', 0)
            total = h2h.get('total_matches', 1)
            
            if t1_wins > t2_wins:
                score1 += 10 * (t1_wins / total)
                reasons.append(f"H2H: {team1} {t1_wins}-{t2_wins} {team2}")
            else:
                score2 += 10 * (t2_wins / total)
                reasons.append(f"H2H: {team2} {t2_wins}-{t1_wins} {team1}")
        
        # Factor 3: Team form
        for team in [team1, team2]:
            stats = data['team_stats'].get(team)
            if stats:
                form = stats.get('form', '')
                if isinstance(form, str):
                    wins = form.count('W')
                    losses = form.count('L')
                    form_score = (wins - losses) * 2
                    if team == team1:
                        score1 += form_score
                    else:
                        score2 += form_score
                    reasons.append(f"{team} form: {form}")
        
        # Factor 4: Home advantage (if match data available)
        match_data = data.get('match_data')
        if match_data:
            for comp in match_data.get('competitors', []):
                if comp.get('home'):
                    if team1.lower() in comp.get('name', '').lower():
                        score1 += 5
                        reasons.append(f"{team1} playing at home")
                    elif team2.lower() in comp.get('name', '').lower():
                        score2 += 5
                        reasons.append(f"{team2} playing at home")
        
        # Determine winner
        total = abs(score1) + abs(score2) + 1
        if score1 > score2:
            prediction['winner'] = team1
            prediction['confidence'] = 0.5 + (score1 / total) * 0.4
        elif score2 > score1:
            prediction['winner'] = team2
            prediction['confidence'] = 0.5 + (score2 / total) * 0.4
        else:
            prediction['winner'] = 'Toss-up'
            prediction['confidence'] = 0.5
        
        prediction['reasoning'] = reasons
        
        # AI enhancement
        if self.ai_analyzer and data['market']:
            try:
                ai_result = self.ai_analyzer.analyze_market(data['market'])
                if ai_result and ai_result.get('prediction'):
                    prediction['ai_prediction'] = ai_result
            except:
                pass
        
        return prediction
    
    def _get_market_price(self, market: Dict) -> float:
        """Extract price from market."""
        price = market.get('current_price')
        if not price:
            prices = market.get('outcomePrices', [])
            if prices:
                try:
                    price = float(prices[0])
                except:
                    price = 0.5
        try:
            return float(price)
        except:
            return 0.5
    
    def _generate_insights(self, data: Dict) -> List[str]:
        """Generate actionable insights."""
        insights = []
        
        teams = data['teams']
        if len(teams) >= 2:
            team1, team2 = teams[0], teams[1]
            
            # Head-to-head insight
            h2h = data.get('head_to_head')
            if h2h:
                t1w = h2h.get('team1_wins', 0)
                t2w = h2h.get('team2_wins', 0)
                draws = h2h.get('draws', 0)
                total = h2h.get('total_matches', 0)
                
                if total > 0:
                    t1_pct = (t1w / total) * 100
                    t2_pct = (t2w / total) * 100
                    
                    if t1_pct > t2_pct + 10:
                        insights.append(f"📊 {team1} dominates: {t1_pct:.0f}% win rate in {total} matches")
                    elif t2_pct > t1_pct + 10:
                        insights.append(f"📊 {team2} dominates: {t2_pct:.0f}% win rate in {total} matches")
                    else:
                        insights.append(f"⚖️ Even rivalry: {team1} {t1w}-{draws}-{t2w} {team2}")
            
            # Form insight
            for team in [team1, team2]:
                stats = data['team_stats'].get(team)
                if stats:
                    form = stats.get('form', '')
                    if isinstance(form, str) and len(form) >= 3:
                        recent = form[:3]
                        if recent.count('W') == 3:
                            insights.append(f"🔥 {team} on fire: WWW in last 3!")
                        elif recent.count('L') == 3:
                            insights.append(f"❄️ {team} struggling: LLL in last 3")
            
            # Market insight
            if data['market']:
                price = self._get_market_price(data['market'])
                if price >= 0.80:
                    insights.append(f"⚠️ Heavy favorite ({price*100:.0f}%) - upset risk underpriced")
                elif price <= 0.20:
                    insights.append(f"🎯 Deep underdog ({price*100:.0f}%) - asymmetric reward")
        
        # Match status
        match_data = data.get('match_data')
        if match_data:
            status = match_data.get('status', '')
            if 'live' in status.lower() or 'in progress' in status.lower():
                insights.append("🔴 LIVE MATCH - prices may be volatile")
            elif 'scheduled' in status.lower() or 'pre' in status.lower():
                insights.append("📅 Upcoming match - good time for pre-game positions")
        
        return insights
    
    def _generate_trading_recommendation(self, data: Dict) -> Dict:
        """Generate trading recommendation."""
        rec = {
            'action': 'WAIT',
            'side': None,
            'size': 'SMALL',
            'reasoning': '',
        }
        
        if not data['market']:
            rec['reasoning'] = 'No market found - monitor for market creation'
            return rec
        
        price = self._get_market_price(data['market'])
        prediction = data.get('prediction', {})
        confidence = prediction.get('confidence', 0.5)
        
        # Decision logic
        if confidence >= 0.65:
            if price < 0.40:
                rec['action'] = 'BUY'
                rec['side'] = 'YES' if prediction.get('winner') == data['teams'][0] else 'NO'
                rec['size'] = 'NORMAL' if confidence >= 0.70 else 'SMALL'
                rec['reasoning'] = f"Strong edge detected ({confidence*100:.0f}% confidence)"
            elif price > 0.75:
                rec['action'] = 'CONSIDER FADE'
                rec['side'] = 'NO'
                rec['size'] = 'SMALL'
                rec['reasoning'] = 'Favorite overpriced - consider fade'
        elif 0.45 <= price <= 0.55:
            rec['action'] = 'WAIT'
            rec['reasoning'] = '50/50 market - need more edge'
        else:
            rec['action'] = 'MONITOR'
            rec['reasoning'] = f'Moderate confidence ({confidence*100:.0f}%) - wait for better entry'
        
        return rec


def format_match_info_telegram(data: Dict) -> str:
    """Format match info for Telegram message."""
    lines = []
    
    # Header
    if data.get('market_found'):
        lines.append(f"<b>🏟️ Match Found!</b>")
    else:
        lines.append(f"<b>🔍 Match Analysis</b>")
    
    lines.append(f"Query: <i>{data.get('query')}</i>")
    
    if data.get('interpreted') != data.get('query'):
        lines.append(f"Understood as: <i>{data.get('interpreted')}</i>")
    
    lines.append("")
    
    # Teams
    teams = data.get('teams', [])
    if len(teams) >= 2:
        lines.append(f"<b>⚔️ {teams[0]} vs {teams[1]}</b>")
        lines.append("")
    
    # Match data (from ESPN)
    match_data = data.get('match_data')
    if match_data:
        lines.append("<b>📅 Match Info:</b>")
        if match_data.get('date'):
            date_str = match_data['date'][:10] if len(match_data.get('date', '')) > 10 else match_data.get('date')
            lines.append(f"  Date: {date_str}")
        if match_data.get('venue'):
            lines.append(f"  Venue: {match_data['venue']}")
        if match_data.get('status'):
            lines.append(f"  Status: {match_data['status']}")
        lines.append("")
    
    # Market probability
    if data.get('market'):
        price = data['market'].get('current_price', 0.5)
        try:
            price = float(price)
        except:
            price = 0.5
        
        bar_filled = int(price * 10)
        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
        lines.append(f"<b>📊 Market Probability:</b>")
        lines.append(f"  {bar} {price*100:.0f}%")
        lines.append("")
    
    # Head-to-head
    h2h = data.get('head_to_head')
    if h2h and h2h.get('total_matches', 0) > 0:
        lines.append("<b>📜 Head-to-Head History:</b>")
        lines.append(f"  {h2h.get('team1', 'Team 1')}: {h2h.get('team1_wins', 0)} wins")
        lines.append(f"  {h2h.get('team2', 'Team 2')}: {h2h.get('team2_wins', 0)} wins")
        lines.append(f"  Draws: {h2h.get('draws', 0)}")
        lines.append(f"  Total Matches: {h2h.get('total_matches', 0)}")
        lines.append("")
    
    # Team stats
    if data.get('team_stats'):
        lines.append("<b>📈 Team Form:</b>")
        for team, stats in data['team_stats'].items():
            if stats:
                form = stats.get('form', 'N/A')
                lines.append(f"  {team}: {form}")
        lines.append("")
    
    # Prediction
    prediction = data.get('prediction', {})
    if prediction.get('winner'):
        lines.append("<b>🤖 Prediction:</b>")
        winner = prediction.get('winner')
        conf = prediction.get('confidence', 0.5) * 100
        lines.append(f"  Winner: <b>{winner}</b> ({conf:.0f}% confidence)")
        
        if prediction.get('reasoning'):
            lines.append("  Factors:")
            for reason in prediction['reasoning'][:3]:
                lines.append(f"    • {reason}")
        lines.append("")
    
    # Insights
    insights = data.get('insights', [])
    if insights:
        lines.append("<b>💡 Key Insights:</b>")
        for insight in insights[:4]:
            lines.append(f"  {insight}")
        lines.append("")
    
    # Trading Recommendation
    rec = data.get('trading_recommendation', {})
    if rec:
        lines.append("<b>🎯 Trading Recommendation:</b>")
        action = rec.get('action', 'WAIT')
        
        if action == 'BUY':
            lines.append(f"  ✅ <b>{action}</b> {rec.get('side', '')} ({rec.get('size', 'SMALL')} size)")
        elif action == 'CONSIDER FADE':
            lines.append(f"  ⚠️ <b>{action}</b> ({rec.get('size', 'SMALL')} size)")
        else:
            lines.append(f"  ⏳ <b>{action}</b>")
        
        if rec.get('reasoning'):
            lines.append(f"  Reason: {rec['reasoning']}")
    
    return "\n".join(lines)
