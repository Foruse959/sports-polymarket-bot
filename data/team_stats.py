"""
Team Statistics Provider

Fetches team statistics from free APIs:
- ESPN (no key required)
- Football-Data.org (free tier)

Used for Over/Under and BTTS predictions.
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from functools import lru_cache


class TeamStatsProvider:
    """
    Fetch team statistics for sports predictions.
    
    Prioritizes free data sources:
    1. ESPN API (always free, no key)
    2. Football-Data.org (free tier: 10 req/min)
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Sports-Polymarket-Bot/1.0'
        })
        
        # Football-Data.org API (optional)
        self.football_data_key = os.getenv('FOOTBALL_DATA_API_KEY', '')
        
        # Cache stats to avoid rate limits
        self._cache = {}
        self._cache_ttl = timedelta(hours=1)
        
        # ESPN endpoints
        self.espn_soccer_url = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
        self.espn_nba_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        self.espn_nfl_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        
        # Football-Data.org endpoints
        self.fd_base_url = "https://api.football-data.org/v4"
    
    def get_team_stats(self, team_name: str, sport: str = 'football') -> Optional[Dict]:
        """
        Get team statistics.
        
        Returns dict with:
        - avg_goals_scored: float
        - avg_goals_conceded: float
        - btts_rate: float (% of games where both teams scored)
        - clean_sheet_rate: float
        - home_avg_goals: float
        - away_avg_goals: float
        - recent_form: list of last 5 results
        """
        cache_key = f"{team_name}_{sport}"
        
        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                return cached['data']
        
        stats = None
        
        if sport == 'football':
            stats = self._get_football_stats(team_name)
        elif sport == 'nba':
            stats = self._get_nba_stats(team_name)
        elif sport == 'nfl':
            stats = self._get_nfl_stats(team_name)
        
        # Fallback to estimated stats if API fails
        if not stats:
            stats = self._estimate_stats(team_name, sport)
        
        # Cache result
        self._cache[cache_key] = {
            'data': stats,
            'timestamp': datetime.now()
        }
        
        return stats
    
    def _get_football_stats(self, team_name: str) -> Optional[Dict]:
        """Get football/soccer stats from Football-Data.org or ESPN."""
        
        # Try Football-Data.org first if key available
        if self.football_data_key:
            stats = self._fetch_football_data_stats(team_name)
            if stats:
                return stats
        
        # Fallback to ESPN
        return self._fetch_espn_soccer_stats(team_name)
    
    def _fetch_football_data_stats(self, team_name: str) -> Optional[Dict]:
        """Fetch from Football-Data.org API."""
        try:
            headers = {'X-Auth-Token': self.football_data_key}
            
            # Search in major leagues
            leagues = ['PL', 'BL1', 'SA', 'PD', 'FL1']  # Premier League, Bundesliga, etc.
            
            for league in leagues:
                url = f"{self.fd_base_url}/competitions/{league}/teams"
                resp = self.session.get(url, headers=headers, timeout=10)
                
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                teams = data.get('teams', [])
                
                # Find matching team
                team_lower = team_name.lower()
                for team in teams:
                    if team_lower in team.get('name', '').lower() or \
                       team_lower in team.get('shortName', '').lower():
                        # Get team's matches
                        return self._get_team_matches_fd(team['id'])
            
        except Exception as e:
            print(f"⚠️ Football-Data.org error: {e}")
        
        return None
    
    def _get_team_matches_fd(self, team_id: int) -> Optional[Dict]:
        """Get team match stats from Football-Data.org."""
        try:
            headers = {'X-Auth-Token': self.football_data_key}
            url = f"{self.fd_base_url}/teams/{team_id}/matches?status=FINISHED&limit=10"
            
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            matches = data.get('matches', [])
            
            if not matches:
                return None
            
            # Calculate stats
            goals_scored = []
            goals_conceded = []
            btts_count = 0
            clean_sheets = 0
            
            for match in matches:
                score = match.get('score', {}).get('fullTime', {})
                home_goals = score.get('home', 0) or 0
                away_goals = score.get('away', 0) or 0
                
                home_team = match.get('homeTeam', {}).get('id')
                is_home = home_team == team_id
                
                if is_home:
                    goals_scored.append(home_goals)
                    goals_conceded.append(away_goals)
                else:
                    goals_scored.append(away_goals)
                    goals_conceded.append(home_goals)
                
                # BTTS check
                if home_goals > 0 and away_goals > 0:
                    btts_count += 1
                
                # Clean sheet check
                if is_home and away_goals == 0:
                    clean_sheets += 1
                elif not is_home and home_goals == 0:
                    clean_sheets += 1
            
            n = len(matches)
            return {
                'avg_goals_scored': sum(goals_scored) / n if n > 0 else 1.5,
                'avg_goals_conceded': sum(goals_conceded) / n if n > 0 else 1.0,
                'btts_rate': btts_count / n if n > 0 else 0.5,
                'clean_sheet_rate': clean_sheets / n if n > 0 else 0.3,
                'recent_goals': goals_scored[-5:],
                'games_analyzed': n,
                'source': 'football-data.org'
            }
            
        except Exception as e:
            print(f"⚠️ Error getting team matches: {e}")
        
        return None
    
    def _fetch_espn_soccer_stats(self, team_name: str) -> Optional[Dict]:
        """Fetch soccer stats from ESPN."""
        try:
            # Try major leagues
            leagues = ['eng.1', 'esp.1', 'ger.1', 'ita.1', 'fra.1', 'usa.1']
            
            for league in leagues:
                url = self.espn_soccer_url.format(league=league)
                resp = self.session.get(url, timeout=10)
                
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                events = data.get('events', [])
                
                # Look for team in recent/upcoming matches
                team_lower = team_name.lower()
                for event in events:
                    competitors = event.get('competitions', [{}])[0].get('competitors', [])
                    for comp in competitors:
                        if team_lower in comp.get('team', {}).get('displayName', '').lower():
                            # Found team, now get their stats
                            stats = comp.get('statistics', [])
                            return self._parse_espn_stats(stats)
            
        except Exception as e:
            print(f"⚠️ ESPN API error: {e}")
        
        return None
    
    def _parse_espn_stats(self, stats: List) -> Optional[Dict]:
        """Parse ESPN statistics array."""
        if not stats:
            return None
        
        # ESPN stats structure varies, extract what we can
        parsed = {
            'avg_goals_scored': 1.5,
            'avg_goals_conceded': 1.0,
            'btts_rate': 0.5,
            'clean_sheet_rate': 0.25,
            'source': 'espn'
        }
        
        for stat in stats:
            name = stat.get('name', '').lower()
            value = stat.get('value', 0)
            
            if 'goals' in name and 'scored' in name:
                parsed['avg_goals_scored'] = float(value) / 10  # Normalize
            elif 'goals' in name and 'conceded' in name:
                parsed['avg_goals_conceded'] = float(value) / 10
        
        return parsed
    
    def _get_nba_stats(self, team_name: str) -> Optional[Dict]:
        """Get NBA team stats."""
        try:
            resp = self.session.get(self.espn_nba_url, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            events = data.get('events', [])
            
            team_lower = team_name.lower()
            for event in events:
                competitors = event.get('competitions', [{}])[0].get('competitors', [])
                for comp in competitors:
                    if team_lower in comp.get('team', {}).get('displayName', '').lower():
                        # Get team record for averages
                        record = comp.get('records', [{}])[0].get('summary', '0-0')
                        return {
                            'avg_points_scored': 112.0,  # NBA average
                            'avg_points_conceded': 110.0,
                            'record': record,
                            'source': 'espn_nba'
                        }
        except Exception as e:
            print(f"⚠️ ESPN NBA error: {e}")
        
        return None
    
    def _get_nfl_stats(self, team_name: str) -> Optional[Dict]:
        """Get NFL team stats."""
        try:
            resp = self.session.get(self.espn_nfl_url, timeout=10)
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            events = data.get('events', [])
            
            team_lower = team_name.lower()
            for event in events:
                competitors = event.get('competitions', [{}])[0].get('competitors', [])
                for comp in competitors:
                    if team_lower in comp.get('team', {}).get('displayName', '').lower():
                        return {
                            'avg_points_scored': 23.0,  # NFL average
                            'avg_points_conceded': 21.0,
                            'source': 'espn_nfl'
                        }
        except Exception as e:
            print(f"⚠️ ESPN NFL error: {e}")
        
        return None
    
    def _estimate_stats(self, team_name: str, sport: str) -> Dict:
        """
        Estimate stats when API fails.
        
        Uses sport-specific averages.
        """
        team_lower = team_name.lower()
        
        # Strong teams tend to score more
        is_strong_team = any(t in team_lower for t in [
            'city', 'real madrid', 'barcelona', 'bayern', 'liverpool',
            'arsenal', 'psg', 'inter', 'juventus', 'chelsea',
            'lakers', 'celtics', 'warriors', 'nuggets',
            'chiefs', '49ers', 'eagles', 'ravens'
        ])
        
        if sport == 'football':
            return {
                'avg_goals_scored': 2.0 if is_strong_team else 1.3,
                'avg_goals_conceded': 0.8 if is_strong_team else 1.4,
                'btts_rate': 0.55,
                'clean_sheet_rate': 0.35 if is_strong_team else 0.20,
                'source': 'estimated'
            }
        elif sport == 'nba':
            return {
                'avg_points_scored': 118.0 if is_strong_team else 110.0,
                'avg_points_conceded': 108.0 if is_strong_team else 115.0,
                'source': 'estimated'
            }
        elif sport == 'nfl':
            return {
                'avg_points_scored': 26.0 if is_strong_team else 20.0,
                'avg_points_conceded': 18.0 if is_strong_team else 24.0,
                'source': 'estimated'
            }
        
        return {
            'avg_goals_scored': 1.5,
            'avg_goals_conceded': 1.5,
            'btts_rate': 0.5,
            'source': 'estimated'
        }
    
    def predict_over_under(self, team1: str, team2: str, line: float, 
                           sport: str = 'football') -> Dict:
        """
        Predict if game will go over or under the line.
        
        Args:
            team1: First team name
            team2: Second team name
            line: Over/under line (e.g., 2.5 goals)
            sport: Sport type
            
        Returns:
            Dict with prediction, confidence, expected_total
        """
        stats1 = self.get_team_stats(team1, sport)
        stats2 = self.get_team_stats(team2, sport)
        
        if not stats1 or not stats2:
            return {'prediction': None, 'confidence': 0.0}
        
        # Calculate expected total
        if sport == 'football':
            # Team1 attack vs Team2 defense, and vice versa
            team1_expected = (stats1['avg_goals_scored'] + stats2['avg_goals_conceded']) / 2
            team2_expected = (stats2['avg_goals_scored'] + stats1['avg_goals_conceded']) / 2
        else:
            # NBA/NFL
            key = 'avg_points_scored' if 'avg_points_scored' in stats1 else 'avg_goals_scored'
            team1_expected = stats1.get(key, 1.5)
            team2_expected = stats2.get(key, 1.5)
        
        expected_total = team1_expected + team2_expected
        
        # Determine prediction
        diff = expected_total - line
        
        if diff > 0.5:
            prediction = 'over'
            confidence = min(0.7 + abs(diff) * 0.1, 0.85)
        elif diff < -0.5:
            prediction = 'under'
            confidence = min(0.7 + abs(diff) * 0.1, 0.85)
        else:
            # Too close to call
            prediction = 'over' if diff > 0 else 'under'
            confidence = 0.5 + abs(diff) * 0.2
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'expected_total': expected_total,
            'line': line,
            'team1_expected': team1_expected,
            'team2_expected': team2_expected,
            'source': stats1.get('source', 'unknown')
        }
    
    def predict_btts(self, team1: str, team2: str, sport: str = 'football') -> Dict:
        """
        Predict if both teams will score.
        
        Args:
            team1: First team name
            team2: Second team name
            sport: Sport type
            
        Returns:
            Dict with prediction, confidence
        """
        stats1 = self.get_team_stats(team1, sport)
        stats2 = self.get_team_stats(team2, sport)
        
        if not stats1 or not stats2:
            return {'prediction': None, 'confidence': 0.0}
        
        # Get BTTS rates
        btts1 = stats1.get('btts_rate', 0.5)
        btts2 = stats2.get('btts_rate', 0.5)
        
        # Get clean sheet rates
        cs1 = stats1.get('clean_sheet_rate', 0.25)
        cs2 = stats2.get('clean_sheet_rate', 0.25)
        
        # Calculate combined BTTS probability
        # Higher BTTS rate = more likely both score
        # Lower clean sheet rate = more likely concede
        btts_prob = (btts1 + btts2) / 2
        no_btts_prob = (cs1 + cs2) / 2
        
        # Adjust: if either team has high clean sheet rate, BTTS less likely
        if cs1 > 0.4 or cs2 > 0.4:
            btts_prob *= 0.7
        
        if btts_prob > 0.55:
            prediction = 'yes'
            confidence = min(0.5 + btts_prob * 0.3, 0.75)
        elif no_btts_prob > 0.35:
            prediction = 'no'
            confidence = min(0.5 + no_btts_prob * 0.4, 0.75)
        else:
            prediction = 'yes' if btts_prob > 0.5 else 'no'
            confidence = 0.5
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'btts_probability': btts_prob,
            'team1_btts_rate': btts1,
            'team2_btts_rate': btts2,
            'source': stats1.get('source', 'unknown')
        }
    
    def clear_cache(self):
        """Clear stats cache."""
        self._cache.clear()
