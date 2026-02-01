"""
Enhanced Sports Data Sources

Free APIs and data enrichment for better trading signals:
- Match details and schedules
- Player stats and form
- Home/away advantages
- Historical head-to-head
- AI-powered analysis (Groq)
"""

import requests
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from config import Config


class EnhancedSportsData:
    """
    Multi-source sports data aggregator.
    
    Free APIs used:
    - TheSportsDB (free API)
    - Football-Data.org (10 req/min free)
    - BALLDONTLIE (NBA, free)
    - API-Football (100 req/day free) 
    """
    
    # Free API endpoints
    SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"  # Free tier
    FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
    BALLDONTLIE_BASE = "https://api.balldontlie.io/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Sports-Polymarket-Bot/1.0'
        })
        self.cache = {}
        self.cache_ttl = 300  # 5 minute cache
        
        # Optional API keys
        self.football_data_key = os.getenv('FOOTBALL_DATA_API_KEY', '')
        self.groq_api_key = os.getenv('GROQ_API_KEY', '')
    
    # ═══════════════════════════════════════════════════════════════
    # THESPORTSDB - FREE API (No key needed!)
    # ═══════════════════════════════════════════════════════════════
    
    def get_team_info(self, team_name: str) -> Optional[Dict]:
        """
        Get detailed team information from TheSportsDB.
        
        Returns: Stadium, home ground, country, founded year, etc.
        """
        try:
            url = f"{self.SPORTSDB_BASE}/searchteams.php?t={team_name}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                teams = data.get('teams', [])
                
                if teams:
                    team = teams[0]
                    return {
                        'id': team.get('idTeam'),
                        'name': team.get('strTeam'),
                        'alternate_names': team.get('strAlternate', '').split(','),
                        'stadium': team.get('strStadium'),
                        'stadium_capacity': team.get('intStadiumCapacity'),
                        'country': team.get('strCountry'),
                        'league': team.get('strLeague'),
                        'founded': team.get('intFormedYear'),
                        'description': team.get('strDescriptionEN', '')[:500],
                        'badge_url': team.get('strBadge'),
                        'home_advantage': self._estimate_home_advantage(team)
                    }
        except Exception as e:
            print(f"⚠️ TheSportsDB error: {e}")
        
        return None
    
    def _estimate_home_advantage(self, team: Dict) -> float:
        """
        Estimate home advantage based on stadium size and league.
        
        Returns: 0.0 to 0.2 (percentage boost for home team)
        """
        try:
            capacity = int(team.get('intStadiumCapacity', 0) or 0)
            
            # Larger stadiums = more home advantage (crowd factor)
            if capacity >= 70000:
                return 0.15  # 15% home boost
            elif capacity >= 50000:
                return 0.12
            elif capacity >= 30000:
                return 0.10
            elif capacity >= 15000:
                return 0.08
            else:
                return 0.05
        except:
            return 0.08  # Default
    
    def get_player_info(self, player_name: str) -> Optional[Dict]:
        """Get player details from TheSportsDB."""
        try:
            url = f"{self.SPORTSDB_BASE}/searchplayers.php?p={player_name}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get('player', [])
                
                if players:
                    player = players[0]
                    return {
                        'id': player.get('idPlayer'),
                        'name': player.get('strPlayer'),
                        'team': player.get('strTeam'),
                        'nationality': player.get('strNationality'),
                        'position': player.get('strPosition'),
                        'date_of_birth': player.get('dateBorn'),
                        'height': player.get('strHeight'),
                        'weight': player.get('strWeight'),
                        'description': player.get('strDescriptionEN', '')[:300]
                    }
        except Exception as e:
            print(f"⚠️ Player search error: {e}")
        
        return None
    
    def get_next_events_for_team(self, team_name: str) -> List[Dict]:
        """Get upcoming matches for a team."""
        try:
            # First find team ID
            team_info = self.get_team_info(team_name)
            if not team_info:
                return []
            
            team_id = team_info.get('id')
            url = f"{self.SPORTSDB_BASE}/eventsnext.php?id={team_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', []) or []
                
                return [{
                    'event_id': e.get('idEvent'),
                    'home_team': e.get('strHomeTeam'),
                    'away_team': e.get('strAwayTeam'),
                    'date': e.get('dateEvent'),
                    'time': e.get('strTime'),
                    'venue': e.get('strVenue'),
                    'league': e.get('strLeague'),
                    'season': e.get('strSeason')
                } for e in events[:5]]
        except Exception as e:
            print(f"⚠️ Next events error: {e}")
        
        return []
    
    def get_head_to_head(self, team1: str, team2: str, limit: int = 10) -> Dict:
        """Get historical head-to-head record between two teams."""
        try:
            # Search for events between teams
            team1_info = self.get_team_info(team1)
            if not team1_info:
                return {'matches': [], 'summary': {}}
            
            team_id = team1_info.get('id')
            url = f"{self.SPORTSDB_BASE}/eventslast.php?id={team_id}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('results', []) or []
                
                # Filter for matches against team2
                h2h_matches = []
                team2_lower = team2.lower()
                
                for e in events:
                    home = e.get('strHomeTeam', '').lower()
                    away = e.get('strAwayTeam', '').lower()
                    
                    if team2_lower in home or team2_lower in away:
                        h2h_matches.append({
                            'date': e.get('dateEvent'),
                            'home_team': e.get('strHomeTeam'),
                            'away_team': e.get('strAwayTeam'),
                            'home_score': e.get('intHomeScore'),
                            'away_score': e.get('intAwayScore'),
                            'venue': e.get('strVenue')
                        })
                
                # Calculate summary
                team1_wins = 0
                team2_wins = 0
                draws = 0
                
                for m in h2h_matches:
                    home_score = int(m['home_score'] or 0)
                    away_score = int(m['away_score'] or 0)
                    
                    if home_score > away_score:
                        if team1.lower() in m['home_team'].lower():
                            team1_wins += 1
                        else:
                            team2_wins += 1
                    elif away_score > home_score:
                        if team1.lower() in m['away_team'].lower():
                            team1_wins += 1
                        else:
                            team2_wins += 1
                    else:
                        draws += 1
                
                return {
                    'matches': h2h_matches[:limit],
                    'summary': {
                        'total': len(h2h_matches),
                        f'{team1}_wins': team1_wins,
                        f'{team2}_wins': team2_wins,
                        'draws': draws
                    }
                }
        except Exception as e:
            print(f"⚠️ H2H error: {e}")
        
        return {'matches': [], 'summary': {}}
    
    # ═══════════════════════════════════════════════════════════════
    # BALLDONTLIE - FREE NBA API
    # ═══════════════════════════════════════════════════════════════
    
    def get_nba_player_stats(self, player_name: str) -> Optional[Dict]:
        """Get NBA player season stats."""
        try:
            # Search player
            url = f"{self.BALLDONTLIE_BASE}/players?search={player_name}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                players = data.get('data', [])
                
                if players:
                    player = players[0]
                    player_id = player.get('id')
                    
                    # Get season averages
                    stats_url = f"{self.BALLDONTLIE_BASE}/season_averages?player_ids[]={player_id}"
                    stats_response = self.session.get(stats_url, timeout=10)
                    
                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        averages = stats_data.get('data', [{}])[0] if stats_data.get('data') else {}
                        
                        return {
                            'id': player_id,
                            'name': f"{player.get('first_name')} {player.get('last_name')}",
                            'team': player.get('team', {}).get('full_name'),
                            'position': player.get('position'),
                            'stats': {
                                'games_played': averages.get('games_played', 0),
                                'ppg': averages.get('pts', 0),  # Points per game
                                'rpg': averages.get('reb', 0),  # Rebounds
                                'apg': averages.get('ast', 0),  # Assists
                                'fg_pct': averages.get('fg_pct', 0) * 100,
                                'three_pct': averages.get('fg3_pct', 0) * 100,
                                'ft_pct': averages.get('ft_pct', 0) * 100
                            }
                        }
        except Exception as e:
            print(f"⚠️ NBA stats error: {e}")
        
        return None
    
    def get_nba_team_standings(self) -> List[Dict]:
        """Get current NBA standings."""
        try:
            url = f"{self.BALLDONTLIE_BASE}/standings"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json().get('data', [])
        except Exception as e:
            print(f"⚠️ NBA standings error: {e}")
        
        return []
    
    # ═══════════════════════════════════════════════════════════════
    # GROQ AI - FREE LLM FOR ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    
    def analyze_with_ai(self, market_data: Dict, sports_data: Dict) -> Optional[Dict]:
        """
        Use Groq AI to analyze market opportunity.
        
        Groq is FREE and very fast (LPU inference).
        Get key at: https://console.groq.com
        """
        if not self.groq_api_key:
            return None
        
        try:
            prompt = f"""Analyze this sports betting market for trading opportunity:

Market: {market_data.get('question', 'Unknown')}
Current Price: {market_data.get('current_price', 0.5) * 100:.1f}%
Sport: {market_data.get('sport', 'Unknown')}

Sports Context:
{sports_data}

Based on this data, provide:
1. A brief assessment (2-3 sentences max)
2. Confidence score (0.0 to 1.0)
3. Recommendation: BUY, SELL, or HOLD
4. Key factor influencing your decision

Respond in JSON format only:
{{"assessment": "...", "confidence": 0.X, "recommendation": "...", "key_factor": "..."}}"""

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",  # Fast and capable
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 200
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parse JSON response
                import json
                try:
                    return json.loads(content)
                except:
                    # Try to extract from markdown code block
                    if '```json' in content:
                        json_str = content.split('```json')[1].split('```')[0]
                        return json.loads(json_str)
                    return {'assessment': content, 'confidence': 0.5, 'recommendation': 'HOLD'}
            
        except Exception as e:
            print(f"⚠️ Groq AI error: {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # ENRICHMENT HELPER
    # ═══════════════════════════════════════════════════════════════
    
    def enrich_market(self, market: Dict) -> Dict:
        """
        Enrich a market with additional data from all sources.
        
        Adds: team info, player stats, home advantage, AI analysis
        """
        question = market.get('question', '')
        sport = market.get('sport', 'unknown')
        
        enriched = dict(market)
        enriched['enrichment'] = {}
        
        # Extract team names (simple approach)
        import re
        vs_match = re.search(r'([A-Z][a-zA-Z\s]+?)\s+(?:vs\.?|v\.?)\s+([A-Z][a-zA-Z\s]+)', question)
        
        if vs_match:
            team1, team2 = vs_match.group(1).strip(), vs_match.group(2).strip()
            
            # Get team info
            team1_info = self.get_team_info(team1)
            team2_info = self.get_team_info(team2)
            
            if team1_info:
                enriched['enrichment']['home_team'] = team1_info
            if team2_info:
                enriched['enrichment']['away_team'] = team2_info
            
            # Get head to head
            h2h = self.get_head_to_head(team1, team2)
            enriched['enrichment']['head_to_head'] = h2h.get('summary', {})
            
            # Home advantage factor
            if team1_info and team2_info:
                home_adv = team1_info.get('home_advantage', 0.08)
                enriched['enrichment']['home_advantage'] = home_adv
        
        # AI analysis (if Groq key available)
        if self.groq_api_key:
            ai_analysis = self.analyze_with_ai(market, enriched.get('enrichment', {}))
            if ai_analysis:
                enriched['enrichment']['ai_analysis'] = ai_analysis
        
        return enriched


# Convenience function
def create_enhanced_data():
    """Create an enhanced data client."""
    return EnhancedSportsData()


# Example usage
if __name__ == '__main__':
    client = EnhancedSportsData()
    
    # Test team info
    print("\n=== Team Info ===")
    team = client.get_team_info("Liverpool")
    if team:
        print(f"Team: {team['name']}")
        print(f"Stadium: {team['stadium']} ({team['stadium_capacity']} capacity)")
        print(f"Home advantage: {team['home_advantage']*100:.0f}%")
    
    # Test head to head
    print("\n=== Head to Head ===")
    h2h = client.get_head_to_head("Liverpool", "Manchester United")
    print(f"H2H Summary: {h2h['summary']}")
