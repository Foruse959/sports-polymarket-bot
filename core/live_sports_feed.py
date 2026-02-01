"""
Live Sports Data Feed

Real-time sports data with event detection for trading signals.
Uses ESPN API (free, no key required) and optional premium APIs.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from config import Config


class EventType(Enum):
    """Types of sporting events that trigger trading signals."""
    GOAL = 'goal'
    WICKET = 'wicket'
    RUN = 'run'
    FOUL = 'foul'
    RED_CARD = 'red_card'
    TIMEOUT = 'timeout'
    SUBSTITUTION = 'substitution'
    INJURY = 'injury'
    QUARTER_END = 'quarter_end'
    HALF_TIME = 'half_time'
    SET_END = 'set_end'
    OVER_COMPLETE = 'over_complete'


@dataclass
class SportEvent:
    """Represents a detected sporting event."""
    event_type: EventType
    sport: str
    game_id: str
    team: str
    player: Optional[str]
    timestamp: datetime
    game_time: str  # e.g., "78'" for football, "Q4 2:30" for NBA
    details: Dict[str, Any]


class LiveSportsFeed:
    """
    Unified live sports data feed with event detection.
    
    Supports:
    - Football (Soccer) via ESPN
    - NBA Basketball via ESPN
    - Cricket via ESPN / optional Cricbuzz
    - Tennis via ESPN
    """
    
    ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Sports-Bot/1.0'
        })
        
        # Cache for rate limiting
        self.cache = {}
        self.cache_ttl = 30  # 30 second cache
        
        # Previous state for event detection
        self.previous_state = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self.cache:
            return False
        cached_time = self.cache[key].get('timestamp', datetime.min)
        return (datetime.now() - cached_time).seconds < self.cache_ttl
    
    def _get_cached_or_fetch(self, url: str, cache_key: str) -> Optional[Dict]:
        """Get from cache or fetch from URL."""
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].get('data')
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.cache[cache_key] = {
                    'data': data,
                    'timestamp': datetime.now()
                }
                return data
        except Exception as e:
            print(f"⚠️ Error fetching {cache_key}: {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # FOOTBALL (SOCCER)
    # ═══════════════════════════════════════════════════════════════
    
    def get_live_football(self) -> List[Dict[str, Any]]:
        """
        Get live football/soccer matches from ESPN.
        
        Returns list of live games with:
        - Teams, scores, game time
        - Status (in_progress, halftime, etc.)
        - Competition info
        """
        url = f"{self.ESPN_BASE_URL}/soccer/scoreboard"
        data = self._get_cached_or_fetch(url, 'football_live')
        
        if not data:
            return []
        
        games = []
        
        for league in data.get('leagues', []):
            for event in league.get('events', []):
                competition = event.get('competitions', [{}])[0]
                competitors = competition.get('competitors', [])
                
                if len(competitors) < 2:
                    continue
                
                status = event.get('status', {})
                
                # Only include live games
                if status.get('type', {}).get('name') != 'STATUS_IN_PROGRESS':
                    if status.get('type', {}).get('name') != 'STATUS_HALFTIME':
                        continue
                
                home = next((c for c in competitors if c.get('homeAway') == 'home'), competitors[0])
                away = next((c for c in competitors if c.get('homeAway') == 'away'), competitors[1])
                
                game = {
                    'game_id': event.get('id'),
                    'sport': 'football',
                    'league': league.get('name', 'Unknown'),
                    'home_team': home.get('team', {}).get('name', 'Unknown'),
                    'away_team': away.get('team', {}).get('name', 'Unknown'),
                    'home_score': int(home.get('score', 0)),
                    'away_score': int(away.get('score', 0)),
                    'game_time': status.get('displayClock', '0\''),
                    'period': status.get('period', 1),
                    'status': status.get('type', {}).get('name', 'UNKNOWN'),
                    'is_halftime': status.get('type', {}).get('name') == 'STATUS_HALFTIME',
                    'completion_percent': self._get_football_completion(status)
                }
                games.append(game)
        
        return games
    
    def _get_football_completion(self, status: Dict) -> float:
        """Calculate game completion percentage for football."""
        try:
            clock = status.get('displayClock', "0'")
            minute = int(clock.replace("'", "").replace("+", "").split()[0])
            
            # Standard 90 minutes + injury time
            return min(100, (minute / 90) * 100)
        except:
            return 50
    
    def detect_football_events(self, games: List[Dict]) -> List[SportEvent]:
        """
        Detect football events by comparing current state to previous.
        
        Detects:
        - Goals scored
        - Red cards
        - Half time
        """
        events = []
        
        for game in games:
            game_id = game['game_id']
            prev = self.previous_state.get(f"football_{game_id}", {})
            
            # Detect goals
            home_score = game['home_score']
            away_score = game['away_score']
            prev_home = prev.get('home_score', home_score)
            prev_away = prev.get('away_score', away_score)
            
            if home_score > prev_home:
                events.append(SportEvent(
                    event_type=EventType.GOAL,
                    sport='football',
                    game_id=game_id,
                    team=game['home_team'],
                    player=None,
                    timestamp=datetime.now(),
                    game_time=game['game_time'],
                    details={
                        'score': f"{home_score}-{away_score}",
                        'scorer': 'home',
                        'opponent': game['away_team']
                    }
                ))
            
            if away_score > prev_away:
                events.append(SportEvent(
                    event_type=EventType.GOAL,
                    sport='football',
                    game_id=game_id,
                    team=game['away_team'],
                    player=None,
                    timestamp=datetime.now(),
                    game_time=game['game_time'],
                    details={
                        'score': f"{home_score}-{away_score}",
                        'scorer': 'away',
                        'opponent': game['home_team']
                    }
                ))
            
            # Detect halftime
            if game.get('is_halftime') and not prev.get('is_halftime', False):
                events.append(SportEvent(
                    event_type=EventType.HALF_TIME,
                    sport='football',
                    game_id=game_id,
                    team='',
                    player=None,
                    timestamp=datetime.now(),
                    game_time="HT",
                    details={'score': f"{home_score}-{away_score}"}
                ))
            
            # Update previous state
            self.previous_state[f"football_{game_id}"] = game
        
        return events
    
    # ═══════════════════════════════════════════════════════════════
    # NBA BASKETBALL
    # ═══════════════════════════════════════════════════════════════
    
    def get_live_nba(self) -> List[Dict[str, Any]]:
        """
        Get live NBA games from ESPN.
        
        Returns list of live games with:
        - Teams, scores, quarter, time remaining
        - Recent scoring runs
        """
        url = f"{self.ESPN_BASE_URL}/basketball/nba/scoreboard"
        data = self._get_cached_or_fetch(url, 'nba_live')
        
        if not data:
            return []
        
        games = []
        
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) < 2:
                continue
            
            status = event.get('status', {})
            
            # Only include live games
            if status.get('type', {}).get('name') != 'STATUS_IN_PROGRESS':
                continue
            
            home = next((c for c in competitors if c.get('homeAway') == 'home'), competitors[0])
            away = next((c for c in competitors if c.get('homeAway') == 'away'), competitors[1])
            
            home_score = int(home.get('score', 0))
            away_score = int(away.get('score', 0))
            
            game = {
                'game_id': event.get('id'),
                'sport': 'nba',
                'home_team': home.get('team', {}).get('name', 'Unknown'),
                'away_team': away.get('team', {}).get('name', 'Unknown'),
                'home_score': home_score,
                'away_score': away_score,
                'quarter': status.get('period', 1),
                'time_remaining': status.get('displayClock', '12:00'),
                'lead': abs(home_score - away_score),
                'leader': 'home' if home_score > away_score else 'away' if away_score > home_score else 'tie',
                'completion_percent': self._get_nba_completion(status)
            }
            games.append(game)
        
        return games
    
    def _get_nba_completion(self, status: Dict) -> float:
        """Calculate game completion for NBA."""
        try:
            quarter = status.get('period', 1)
            clock = status.get('displayClock', '12:00')
            
            # Parse time remaining in quarter
            parts = clock.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1]) if len(parts) > 1 else 0
            time_remaining = minutes + seconds / 60
            
            # Each quarter is 12 minutes, 4 quarters total
            completed_quarters = (quarter - 1) * 12
            current_quarter_elapsed = 12 - time_remaining
            total_elapsed = completed_quarters + current_quarter_elapsed
            
            return (total_elapsed / 48) * 100
        except:
            return 50
    
    def detect_nba_events(self, games: List[Dict]) -> List[SportEvent]:
        """
        Detect NBA events.
        
        Detects:
        - Scoring runs (10+ points)
        - Quarter ends
        - Large lead changes
        """
        events = []
        
        for game in games:
            game_id = game['game_id']
            prev = self.previous_state.get(f"nba_{game_id}", {})
            
            # Detect scoring run (10+ points in last check)
            home_change = game['home_score'] - prev.get('home_score', game['home_score'])
            away_change = game['away_score'] - prev.get('away_score', game['away_score'])
            
            # If one team scored 10+ without opponent scoring much
            if home_change >= 10 and away_change <= 2:
                events.append(SportEvent(
                    event_type=EventType.RUN,
                    sport='nba',
                    game_id=game_id,
                    team=game['home_team'],
                    player=None,
                    timestamp=datetime.now(),
                    game_time=f"Q{game['quarter']} {game['time_remaining']}",
                    details={
                        'run_points': home_change,
                        'opponent_points': away_change,
                        'current_lead': game['lead']
                    }
                ))
            
            if away_change >= 10 and home_change <= 2:
                events.append(SportEvent(
                    event_type=EventType.RUN,
                    sport='nba',
                    game_id=game_id,
                    team=game['away_team'],
                    player=None,
                    timestamp=datetime.now(),
                    game_time=f"Q{game['quarter']} {game['time_remaining']}",
                    details={
                        'run_points': away_change,
                        'opponent_points': home_change,
                        'current_lead': game['lead']
                    }
                ))
            
            # Detect quarter end
            if game['quarter'] > prev.get('quarter', game['quarter']):
                events.append(SportEvent(
                    event_type=EventType.QUARTER_END,
                    sport='nba',
                    game_id=game_id,
                    team='',
                    player=None,
                    timestamp=datetime.now(),
                    game_time=f"End Q{prev.get('quarter', game['quarter'] - 1)}",
                    details={
                        'home_score': game['home_score'],
                        'away_score': game['away_score']
                    }
                ))
            
            self.previous_state[f"nba_{game_id}"] = game
        
        return events
    
    # ═══════════════════════════════════════════════════════════════
    # CRICKET
    # ═══════════════════════════════════════════════════════════════
    
    def get_live_cricket(self) -> List[Dict[str, Any]]:
        """
        Get live cricket matches.
        
        Returns list of live games with:
        - Teams, scores, overs, wickets
        - Run rate, required rate
        """
        url = f"{self.ESPN_BASE_URL}/cricket/scoreboard"
        data = self._get_cached_or_fetch(url, 'cricket_live')
        
        if not data:
            return []
        
        games = []
        
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) < 2:
                continue
            
            status = event.get('status', {})
            
            # Only include live games
            if status.get('type', {}).get('name') != 'STATUS_IN_PROGRESS':
                continue
            
            team1 = competitors[0]
            team2 = competitors[1]
            
            game = {
                'game_id': event.get('id'),
                'sport': 'cricket',
                'format': self._detect_cricket_format(event),
                'team1_name': team1.get('team', {}).get('name', 'Unknown'),
                'team2_name': team2.get('team', {}).get('name', 'Unknown'),
                'batting_team': self._get_batting_team(competition),
                'current_score': self._parse_cricket_score(team1, team2),
                'overs': status.get('period', 0),
                'wickets': self._get_wickets(team1, team2),
                'status_text': status.get('type', {}).get('detail', ''),
                'completion_percent': self._get_cricket_completion(event)
            }
            games.append(game)
        
        return games
    
    def _detect_cricket_format(self, event: Dict) -> str:
        """Detect T20, ODI, or Test format."""
        name = event.get('name', '').lower()
        if 't20' in name or 'ipl' in name or 'bbl' in name:
            return 'T20'
        elif 'odi' in name or 'one day' in name:
            return 'ODI'
        elif 'test' in name:
            return 'Test'
        return 'T20'  # Default to T20
    
    def _get_batting_team(self, competition: Dict) -> str:
        """Get currently batting team."""
        # This would need match details API for accuracy
        return ''
    
    def _parse_cricket_score(self, team1: Dict, team2: Dict) -> Dict:
        """Parse cricket scores."""
        return {
            'team1': team1.get('score', '0/0'),
            'team2': team2.get('score', '0/0')
        }
    
    def _get_wickets(self, team1: Dict, team2: Dict) -> int:
        """Get current wickets fallen."""
        try:
            # Parse from score string like "156/4"
            scores = [team1.get('score', '0/0'), team2.get('score', '0/0')]
            for score in scores:
                if '/' in str(score):
                    wickets = int(str(score).split('/')[1].split()[0])
                    return wickets
        except:
            pass
        return 0
    
    def _get_cricket_completion(self, event: Dict) -> float:
        """Calculate completion percentage for cricket."""
        format_type = self._detect_cricket_format(event)
        status = event.get('status', {})
        overs = status.get('period', 0)
        
        max_overs = {'T20': 40, 'ODI': 100, 'Test': 450}  # Both innings
        max_over = max_overs.get(format_type, 40)
        
        return min(100, (overs / max_over) * 100)
    
    def detect_cricket_events(self, games: List[Dict]) -> List[SportEvent]:
        """
        Detect cricket events.
        
        Detects:
        - Wickets fallen
        - Over completions
        - Big overs (10+ runs)
        """
        events = []
        
        for game in games:
            game_id = game['game_id']
            prev = self.previous_state.get(f"cricket_{game_id}", {})
            
            # Detect wicket
            current_wickets = game.get('wickets', 0)
            prev_wickets = prev.get('wickets', current_wickets)
            
            if current_wickets > prev_wickets:
                events.append(SportEvent(
                    event_type=EventType.WICKET,
                    sport='cricket',
                    game_id=game_id,
                    team=game.get('batting_team', 'Unknown'),
                    player=None,
                    timestamp=datetime.now(),
                    game_time=f"Over {game['overs']}",
                    details={
                        'wickets_now': current_wickets,
                        'wickets_fallen': current_wickets - prev_wickets
                    }
                ))
            
            self.previous_state[f"cricket_{game_id}"] = game
        
        return events
    
    # ═══════════════════════════════════════════════════════════════
    # TENNIS
    # ═══════════════════════════════════════════════════════════════
    
    def get_live_tennis(self) -> List[Dict[str, Any]]:
        """Get live tennis matches."""
        url = f"{self.ESPN_BASE_URL}/tennis/scoreboard"
        data = self._get_cached_or_fetch(url, 'tennis_live')
        
        if not data:
            return []
        
        games = []
        
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) < 2:
                continue
            
            status = event.get('status', {})
            
            if status.get('type', {}).get('name') != 'STATUS_IN_PROGRESS':
                continue
            
            player1 = competitors[0]
            player2 = competitors[1]
            
            game = {
                'game_id': event.get('id'),
                'sport': 'tennis',
                'player1': player1.get('athlete', {}).get('displayName', 'Unknown'),
                'player2': player2.get('athlete', {}).get('displayName', 'Unknown'),
                'sets': self._parse_tennis_sets(player1, player2),
                'current_set': status.get('period', 1),
                'status_text': status.get('type', {}).get('detail', '')
            }
            games.append(game)
        
        return games
    
    def _parse_tennis_sets(self, p1: Dict, p2: Dict) -> Dict:
        """Parse tennis set scores."""
        return {
            'player1': p1.get('score', '0'),
            'player2': p2.get('score', '0')
        }
    
    # ═══════════════════════════════════════════════════════════════
    # UNIFIED INTERFACE
    # ═══════════════════════════════════════════════════════════════
    
    def get_all_live_games(self) -> Dict[str, List[Dict]]:
        """Get all live games across all sports."""
        return {
            'football': self.get_live_football(),
            'nba': self.get_live_nba(),
            'cricket': self.get_live_cricket(),
            'tennis': self.get_live_tennis()
        }
    
    def detect_all_events(self) -> List[SportEvent]:
        """Detect events across all live sports."""
        events = []
        
        football_games = self.get_live_football()
        events.extend(self.detect_football_events(football_games))
        
        nba_games = self.get_live_nba()
        events.extend(self.detect_nba_events(nba_games))
        
        cricket_games = self.get_live_cricket()
        events.extend(self.detect_cricket_events(cricket_games))
        
        return events
    
    def find_late_game_opportunities(self, min_completion: float = 75) -> List[Dict]:
        """
        Find games that are nearly complete with clear leaders.
        Prime candidates for late-game trading strategies.
        """
        opportunities = []
        all_games = self.get_all_live_games()
        
        for sport, games in all_games.items():
            for game in games:
                completion = game.get('completion_percent', 0)
                
                if completion >= min_completion:
                    opportunities.append({
                        **game,
                        'opportunity_type': 'late_game',
                        'completion': completion
                    })
        
        return opportunities
    
    # ═══════════════════════════════════════════════════════════════
    # DYNAMIC MARKET-DRIVEN ESPN SEARCH
    # ═══════════════════════════════════════════════════════════════
    
    def extract_teams_from_market(self, market: Dict) -> List[str]:
        """
        Extract team/player names from a Polymarket market question.
        
        Examples:
        - "Will Manchester United win vs Chelsea?" → ["Manchester United", "Chelsea"]
        - "Lakers vs Celtics - Who wins?" → ["Lakers", "Celtics"]
        """
        question = market.get('question', '') or market.get('title', '')
        teams = []
        
        # Common patterns
        import re
        
        # Pattern: "Team A vs Team B" or "Team A v Team B"
        vs_pattern = r'([A-Z][a-zA-Z\s]+?)\s+(?:vs\.?|v\.?|versus)\s+([A-Z][a-zA-Z\s]+?)(?:\s*[-\?]|$)'
        match = re.search(vs_pattern, question)
        if match:
            teams.extend([match.group(1).strip(), match.group(2).strip()])
        
        # Pattern: "Will [Team] win/beat..."
        will_pattern = r'Will\s+(?:the\s+)?([A-Z][a-zA-Z\s]+?)\s+(?:win|beat|defeat)'
        match = re.search(will_pattern, question)
        if match:
            teams.append(match.group(1).strip())
        
        # Known team names lookup
        known_teams = [
            # NFL
            'Chiefs', 'Eagles', 'Cowboys', 'Patriots', '49ers', 'Bills',
            # NBA  
            'Lakers', 'Celtics', 'Warriors', 'Nets', 'Heat', 'Bucks', 'Suns',
            # Football/Soccer
            'Manchester United', 'Manchester City', 'Liverpool', 'Chelsea', 'Arsenal',
            'Real Madrid', 'Barcelona', 'Bayern Munich', 'PSG', 'Juventus',
            # Cricket
            'India', 'Australia', 'England', 'Pakistan', 'South Africa',
            'Mumbai Indians', 'Chennai Super Kings', 'RCB', 'KKR',
        ]
        
        for team in known_teams:
            if team.lower() in question.lower() and team not in teams:
                teams.append(team)
        
        return teams[:2]  # Max 2 teams per market
    
    def search_espn_for_team(self, team_name: str, sport: str = 'football') -> Optional[Dict]:
        """
        Search ESPN for a specific team's current/upcoming game.
        
        This is more targeted than fetching all live games.
        """
        sport_endpoints = {
            'football': 'soccer',
            'nba': 'basketball/nba',
            'nfl': 'football/nfl',
            'cricket': 'cricket',
            'tennis': 'tennis'
        }
        
        endpoint = sport_endpoints.get(sport, 'soccer')
        url = f"{self.ESPN_BASE_URL}/{endpoint}/scoreboard"
        
        data = self._get_cached_or_fetch(url, f'{sport}_search_{team_name}')
        
        if not data:
            return None
        
        # Search for the team in events
        team_lower = team_name.lower()
        
        for event in data.get('events', []):
            for comp in event.get('competitions', []):
                for competitor in comp.get('competitors', []):
                    team_info = competitor.get('team', {})
                    name = team_info.get('name', '').lower()
                    display_name = team_info.get('displayName', '').lower()
                    short_name = team_info.get('shortDisplayName', '').lower()
                    
                    if team_lower in name or team_lower in display_name or team_lower in short_name:
                        # Found the team - return game info
                        status = event.get('status', {})
                        competitors = comp.get('competitors', [])
                        
                        return {
                            'game_id': event.get('id'),
                            'found_team': team_name,
                            'sport': sport,
                            'is_live': status.get('type', {}).get('name') == 'STATUS_IN_PROGRESS',
                            'status': status.get('type', {}).get('description', 'Unknown'),
                            'home_team': competitors[0].get('team', {}).get('name') if competitors else 'Unknown',
                            'away_team': competitors[1].get('team', {}).get('name') if len(competitors) > 1 else 'Unknown',
                            'home_score': int(competitors[0].get('score', 0)) if competitors else 0,
                            'away_score': int(competitors[1].get('score', 0)) if len(competitors) > 1 else 0,
                            'game_time': status.get('displayClock', ''),
                            'period': status.get('period', 0),
                            'completion_percent': self._estimate_completion(status, sport)
                        }
        
        return None
    
    def _estimate_completion(self, status: Dict, sport: str) -> float:
        """Estimate game completion percentage."""
        period = status.get('period', 1)
        
        if sport == 'football':
            clock = status.get('displayClock', "0'")
            try:
                minute = int(clock.replace("'", "").split()[0])
                return min(100, (minute / 90) * 100)
            except:
                return 50
        elif sport == 'nba':
            # 4 quarters
            return min(100, (period / 4) * 100)
        elif sport == 'nfl':
            # 4 quarters
            return min(100, (period / 4) * 100)
        
        return 50
    
    def get_game_data_for_markets(self, markets: List[Dict]) -> Dict[str, Dict]:
        """
        Given a list of Polymarket markets, find relevant ESPN game data.
        
        Returns dict mapping market_id -> game_data
        """
        market_games = {}
        
        for market in markets:
            market_id = market.get('id', '')
            sport = market.get('sport', 'football')
            
            # Extract teams from market question
            teams = self.extract_teams_from_market(market)
            
            if not teams:
                continue
            
            # Search for each team
            for team in teams:
                game_data = self.search_espn_for_team(team, sport)
                
                if game_data:
                    game_data['market_teams'] = teams
                    market_games[market_id] = game_data
                    break  # Found game, no need to search other team
        
        return market_games
    
    def get_live_game_for_market(self, market: Dict) -> Optional[Dict]:
        """
        Get live game data specifically for a Polymarket market.
        
        This is the main entry point for market-driven data fetching.
        """
        sport = market.get('sport', 'football')
        teams = self.extract_teams_from_market(market)
        
        for team in teams:
            game = self.search_espn_for_team(team, sport)
            if game and game.get('is_live'):
                return game
        
        return None

