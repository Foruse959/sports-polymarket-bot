"""
Telegram Bot Handler

Interactive Telegram bot with commands for match info queries.
Supports /info command to search for match info using AI analysis.
"""

import os
import sys
import requests
import threading
import time
import re
from typing import Dict, Optional, List
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class TelegramBot:
    """
    Interactive Telegram Bot with commands.
    
    Commands:
    - /info <query> - Search for match info (e.g., "/info Barcelona vs Manchester")
    - /status - Get bot status
    - /balance - Get current balance
    - /positions - Get open positions
    """
    
    def __init__(self, polymarket_client=None, ai_analyzer=None, team_stats_provider=None, db=None):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        
        self.polymarket = polymarket_client
        self.ai_analyzer = ai_analyzer
        self.team_stats = team_stats_provider
        self.db = db
        
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None
        self.last_update_id = 0
        self.running = False
        
        # Command handlers
        self.commands = {
            '/info': self.cmd_info,
            '/status': self.cmd_status,
            '/balance': self.cmd_balance,
            '/positions': self.cmd_positions,
            '/help': self.cmd_help,
        }
        
        if self.token:
            print("🤖 Telegram Bot initialized")
    
    def start(self):
        """Start polling for messages in background thread."""
        if not self.token:
            print("⚠️ Telegram Bot: No token configured")
            return
        
        self.running = True
        thread = threading.Thread(target=self._poll_updates, daemon=True)
        thread.start()
        print("🤖 Telegram Bot: Started polling for commands")
    
    def stop(self):
        """Stop the bot."""
        self.running = False
    
    def _poll_updates(self):
        """Poll for updates from Telegram."""
        while self.running:
            try:
                updates = self._get_updates()
                
                for update in updates:
                    self._handle_update(update)
                    self.last_update_id = update.get('update_id', 0) + 1
                
                time.sleep(1)  # Poll every second
                
            except Exception as e:
                print(f"⚠️ Telegram poll error: {e}")
                time.sleep(5)
    
    def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram."""
        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={
                    'offset': self.last_update_id,
                    'timeout': 30,
                    'allowed_updates': ['message']
                },
                timeout=35
            )
            data = response.json()
            return data.get('result', [])
        except:
            return []
    
    def _handle_update(self, update: Dict):
        """Handle an incoming update."""
        message = update.get('message', {})
        text = message.get('text', '')
        chat_id = message.get('chat', {}).get('id')
        
        if not text or not chat_id:
            return
        
        # Check if user is selecting from suggestions (plain number)
        if text.strip().isdigit():
            response = self._handle_number_selection(chat_id, text.strip())
            if response:
                self._send_message(chat_id, response)
                return
        
        # Check if it's a command
        for cmd, handler in self.commands.items():
            if text.startswith(cmd):
                query = text[len(cmd):].strip()
                try:
                    # Pass chat_id for session tracking
                    if cmd == '/info':
                        response = handler(query, chat_id)
                    else:
                        response = handler(query)
                    self._send_message(chat_id, response)
                except Exception as e:
                    self._send_message(chat_id, f"❌ Error: {str(e)}")
                return
    
    def _handle_number_selection(self, chat_id: int, number_str: str) -> Optional[str]:
        """Handle when user replies with a number to select from suggestions."""
        try:
            from data.smart_search import get_smart_search
            search = get_smart_search(self.polymarket)
            
            result = search.search(number_str, str(chat_id))
            
            if result.get('found') and result.get('market'):
                # User selected a market - show full analysis
                return self._full_market_analysis(result['market'])
            
            return None
        except:
            return None
    
    def _send_message(self, chat_id: int, text: str):
        """Send message to chat."""
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'HTML'
                },
                timeout=10
            )
        except Exception as e:
            print(f"⚠️ Telegram send error: {e}")
    
    def cmd_help(self, query: str = "") -> str:
        """Handle /help command."""
        return """<b>🤖 Sports Polymarket Bot Commands</b>

/info <query> - Search for match info
  Example: /info Barcelona vs Manchester

/status - Get bot status
/balance - Get current balance  
/positions - Get open positions
/help - Show this message

<b>💡 Search Examples:</b>
• /info Lakers vs Celtics today
• /info Manchester United match
• /info Liverpool win chance"""

    def cmd_info(self, query: str, chat_id: int = None) -> str:
        """
        Handle /info command - SMART search with interactive suggestions.
        
        Features:
        - Searches Polymarket for matching markets
        - Shows numbered suggestions if multiple matches
        - User can reply with number to select
        - Falls back to general info if no market found
        """
        if not query:
            return """❌ Please provide a search query.

<b>Examples:</b>
• /info Barcelona vs Real Madrid
• /info Lakers vs Celtics
• /info Man United match
• /info barca vs real (nicknames work!)

I understand nicknames and typos! Try any team name."""
        
        print(f"🔍 /info query: {query}")
        
        try:
            # Use SmartSearch for interactive suggestions
            from data.smart_search import get_smart_search
            
            search = get_smart_search(self.polymarket)
            result = search.search(query, str(chat_id) if chat_id else None)
            
            if result.get('exact_match') and result.get('market'):
                # High confidence match - show full analysis
                return self._full_market_analysis(result['market'])
            elif result.get('suggestions'):
                # Multiple matches - show numbered suggestions
                return result['message']
            elif result.get('found') and result.get('market'):
                # Low confidence match but still show analysis
                return self._full_market_analysis(result['market'])
            else:
                # No market found - provide general info
                return self._provide_general_info(query)
                
        except Exception as e:
            print(f"⚠️ Smart search error: {e}")
            # Fallback to basic search
            return self._basic_info_search(query)
    
    def _full_market_analysis(self, market: Dict) -> str:
        """Generate full analysis for a selected market."""
        lines = []
        
        question = market.get('question', 'Unknown Market')
        lines.append(f"<b>✅ Match Found!</b>")
        lines.append(f"<b>📊 {question[:75]}{'...' if len(question) > 75 else ''}</b>")
        lines.append("")
        
        # Current probability
        current_price = self._get_price(market)
        win_prob = current_price * 100
        
        # Probability bar
        bar_filled = int(win_prob / 10)
        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
        lines.append(f"<b>📈 Win Probability:</b> {bar} {win_prob:.0f}%")
        lines.append("")
        
        # Extract and show teams
        teams = self._extract_teams(question)
        if len(teams) >= 2:
            lines.append(f"<b>⚔️ {teams[0].title()} vs {teams[1].title()}</b>")
            
            # Head-to-head
            h2h = self._get_rivalry_history(teams[0].lower(), teams[1].lower())
            if h2h:
                lines.append(f"📜 H2H: {teams[0].title()} {h2h['team1_wins']} | Draws {h2h['draws']} | {teams[1].title()} {h2h['team2_wins']}")
            lines.append("")
        
        # Edge Analysis
        lines.append("<b>📉 Edge Analysis:</b>")
        if current_price >= 0.85:
            lines.append("  ⚠️ <b>Heavy Favorite</b> - Limited upside, upset risk")
            action = "Consider FADE (sell)"
        elif current_price <= 0.15:
            lines.append("  🎯 <b>Deep Underdog</b> - High risk, asymmetric reward")
            action = "Small position LONG"
        elif current_price >= 0.70:
            lines.append("  📊 <b>Moderate Favorite</b>")
            action = "Wait for better entry"
        elif current_price <= 0.30:
            lines.append("  ⚡ <b>Underdog Value</b> - Potential mispricing")
            action = "Consider LONG"
        else:
            lines.append("  ⚖️ <b>Coin Flip</b> - Market unsure")
            action = "Need more edge"
        lines.append("")
        
        # Trading Recommendation
        lines.append("<b>🎯 Recommendation:</b>")
        lines.append(f"  {action}")
        
        if current_price < 0.30 or current_price > 0.80:
            lines.append("  💰 Size: Small (2-3% of bankroll)")
        else:
            lines.append("  💰 Size: Normal (5% of bankroll)")
        
        # Market ID for reference
        market_id = market.get('id', market.get('conditionId', 'N/A'))
        if market_id and market_id != 'N/A':
            lines.append(f"\n<i>Market ID: {str(market_id)[:20]}...</i>")
        
        return "\n".join(lines)
    
    def _basic_info_search(self, query: str) -> str:
        """Fallback basic search when advanced system fails."""
        # Normalize query
        corrected = self._ai_correct_teams(query)
        
        # Search markets
        matching_markets = self._smart_search_markets(corrected)
        
        if not matching_markets:
            # Still provide useful info even without market
            return self._provide_general_info(query)
        
        # Build response
        top_market = matching_markets[0]
        return self._comprehensive_analysis(top_market)
    
    def _provide_general_info(self, query: str) -> str:
        """Provide general info when no market found."""
        # Extract teams from query
        teams = self._extract_teams(query)
        
        lines = [
            "<b>🔍 Match Analysis</b>",
            f"Query: <i>{query}</i>",
            ""
        ]
        
        if len(teams) >= 2:
            lines.append(f"<b>⚔️ {teams[0].title()} vs {teams[1].title()}</b>")
            lines.append("")
            
            # Check for known rivalries and provide historical data
            h2h = self._get_rivalry_history(teams[0].lower(), teams[1].lower())
            if h2h:
                lines.append("<b>📜 Historical Head-to-Head:</b>")
                lines.append(f"  {teams[0].title()}: {h2h['team1_wins']} wins")
                lines.append(f"  {teams[1].title()}: {h2h['team2_wins']} wins")  
                lines.append(f"  Draws: {h2h['draws']}")
                lines.append(f"  Total: {h2h['total']} matches")
                lines.append("")
            
            # Provide general betting insight
            lines.append("<b>💡 General Insights:</b>")
            lines.append("  • No active Polymarket found for this match")
            lines.append("  • Check back closer to match time")
            lines.append("  • Markets typically open 24-48h before")
            lines.append("")
            lines.append("<b>📊 What to watch:</b>")
            lines.append("  • Team form (recent 5 games)")
            lines.append("  • Home/away advantage")
            lines.append("  • Key player injuries")
            lines.append("  • Recent head-to-head results")
        else:
            lines.append(f"Could not identify teams from: {query}")
            lines.append("")
            lines.append("<b>💡 Try:</b>")
            lines.append("  • /info Barcelona vs Real Madrid")
            lines.append("  • /info Lakers vs Celtics")
            lines.append("  • /info Chelsea match")
        
        return "\n".join(lines)
    
    def _get_rivalry_history(self, team1: str, team2: str) -> Optional[Dict]:
        """Get historical data for known rivalries."""
        rivalries = {
            ('barcelona', 'real madrid'): {'team1_wins': 96, 'draws': 52, 'team2_wins': 100, 'total': 248},
            ('manchester united', 'liverpool'): {'team1_wins': 81, 'draws': 58, 'team2_wins': 68, 'total': 207},
            ('arsenal', 'tottenham'): {'team1_wins': 84, 'draws': 53, 'team2_wins': 63, 'total': 200},
            ('los angeles lakers', 'boston celtics'): {'team1_wins': 162, 'draws': 0, 'team2_wins': 200, 'total': 362},
            ('manchester city', 'manchester united'): {'team1_wins': 57, 'draws': 52, 'team2_wins': 78, 'total': 187},
            ('chelsea', 'arsenal'): {'team1_wins': 67, 'draws': 60, 'team2_wins': 76, 'total': 203},
            ('bayern munich', 'borussia dortmund'): {'team1_wins': 63, 'draws': 28, 'team2_wins': 34, 'total': 125},
            ('inter milan', 'ac milan'): {'team1_wins': 78, 'draws': 58, 'team2_wins': 82, 'total': 218},
            ('juventus', 'inter milan'): {'team1_wins': 86, 'draws': 63, 'team2_wins': 51, 'total': 200},
            ('real madrid', 'atletico madrid'): {'team1_wins': 115, 'draws': 56, 'team2_wins': 54, 'total': 225},
        }
        
        key1 = (team1, team2)
        key2 = (team2, team1)
        
        if key1 in rivalries:
            return rivalries[key1]
        elif key2 in rivalries:
            r = rivalries[key2]
            return {'team1_wins': r['team2_wins'], 'team2_wins': r['team1_wins'], 'draws': r['draws'], 'total': r['total']}
        
        return None
    
    def _ai_correct_teams(self, query: str) -> str:
        """Use AI to correct team name spellings."""
        # Common team name corrections
        corrections = {
            'barca': 'Barcelona',
            'barça': 'Barcelona',
            'man utd': 'Manchester United',
            'man united': 'Manchester United',
            'man u': 'Manchester United',
            'man city': 'Manchester City',
            'spurs': 'Tottenham',
            'gunners': 'Arsenal',
            'reds': 'Liverpool',
            'bayern': 'Bayern Munich',
            'real': 'Real Madrid',
            'psg': 'Paris Saint-Germain',
            'juve': 'Juventus',
            'inter': 'Inter Milan',
            'lakers': 'Los Angeles Lakers',
            'celts': 'Boston Celtics',
            'celtics': 'Boston Celtics',
            'warriors': 'Golden State Warriors',
            'bulls': 'Chicago Bulls',
            'heat': 'Miami Heat',
            'nets': 'Brooklyn Nets',
            'chiefs': 'Kansas City Chiefs',
            'pats': 'New England Patriots',
            'cowboys': 'Dallas Cowboys',
            'dortmund': 'Borussia Dortmund',
            'bvb': 'Borussia Dortmund',
            'atletico': 'Atletico Madrid',
            'atleti': 'Atletico Madrid',
            'milan': 'AC Milan',
        }
        
        result = query.lower()
        for short, full in corrections.items():
            # Match whole words only
            import re
            result = re.sub(r'\b' + re.escape(short) + r'\b', full, result, flags=re.IGNORECASE)
        
        return result
    
    def _extract_teams(self, query: str) -> List[str]:
        """Extract team names from query."""
        import re
        
        # Common patterns
        patterns = [
            r'(.+?)\s+(?:vs|v|versus|against)\s+(.+?)(?:\s+(?:match|game|today|tomorrow))?$',
            r'(.+?)\s+(?:plays?|@|at)\s+(.+?)(?:\s+(?:match|game|today|tomorrow))?$',
        ]
        
        query_clean = query.lower().strip()
        
        for pattern in patterns:
            match = re.search(pattern, query_clean, re.IGNORECASE)
            if match:
                team1 = match.group(1).strip()
                team2 = match.group(2).strip()
                # Clean up trailing words
                team2 = re.sub(r'\s+(match|game|today|tomorrow|win|chance)$', '', team2, flags=re.IGNORECASE)
                return [team1, team2]
        
        # Single team query
        clean = re.sub(r'\s+(match|game|today|tomorrow|win|chance)$', '', query_clean, flags=re.IGNORECASE)
        return [clean] if clean else []
    
    def _smart_search_markets(self, query: str) -> List[Dict]:
        """Smart search with fuzzy matching."""
        if not self.polymarket:
            return []
        
        try:
            markets = self.polymarket.get_sports_markets()
            if not markets:
                return []
            
            query_lower = query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]
            
            scored_markets = []
            
            for market in markets:
                question = market.get('question', '').lower()
                description = market.get('description', '').lower()
                full_text = question + " " + description
                
                score = 0
                
                # Word matching
                for word in query_words:
                    if word in full_text:
                        score += 3
                    elif any(word in w or w in word for w in full_text.split()):
                        score += 1
                
                # Team name matching
                teams = self._extract_teams(query)
                for team in teams:
                    team_lower = team.lower()
                    if team_lower in question:
                        score += 10
                    elif any(t in team_lower or team_lower in t for t in question.split()):
                        score += 5
                
                if score > 0:
                    market['relevance_score'] = score
                    scored_markets.append(market)
            
            scored_markets.sort(key=lambda m: m.get('relevance_score', 0), reverse=True)
            return scored_markets[:5]
            
        except Exception as e:
            print(f"⚠️ Smart search error: {e}")
            return []
    
    def _comprehensive_analysis(self, market: Dict) -> str:
        """Generate comprehensive analysis with all available insights."""
        lines = []
        
        question = market.get('question', 'Unknown Market')
        lines.append(f"<b>📊 {question[:80]}{'...' if len(question) > 80 else ''}</b>\n")
        
        # Current probability
        current_price = self._get_price(market)
        win_prob = current_price * 100
        
        # Probability bar visualization
        bar_filled = int(win_prob / 10)
        bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
        lines.append(f"<b>Win Probability:</b> {bar} {win_prob:.0f}%\n")
        
        # Extract teams
        teams = self._extract_teams(question)
        
        # Head-to-head if we have two teams
        if len(teams) >= 2:
            h2h = self._get_rivalry_history(teams[0].lower(), teams[1].lower())
            if h2h:
                lines.append("<b>📜 Head-to-Head:</b>")
                lines.append(f"  {teams[0].title()}: {h2h['team1_wins']} | Draws: {h2h['draws']} | {teams[1].title()}: {h2h['team2_wins']}")
                lines.append("")
        
        # Edge Analysis
        lines.append("<b>📉 Edge Analysis:</b>")
        
        if current_price >= 0.85:
            edge_verdict = "⚠️ <b>Heavy Favorite</b> - Limited upside, upset risk"
            trade_side = "Consider FADE (sell)"
        elif current_price <= 0.15:
            edge_verdict = "🎯 <b>Deep Underdog</b> - High risk, asymmetric reward"
            trade_side = "Small position LONG"
        elif current_price >= 0.70:
            edge_verdict = "📊 <b>Moderate Favorite</b> - Some value if correct"
            trade_side = "Wait for better entry or fade"
        elif current_price <= 0.30:
            edge_verdict = "⚡ <b>Underdog Value</b> - Potential mispricing"
            trade_side = "Consider LONG if fundamentals support"
        else:
            edge_verdict = "⚖️ <b>Coin Flip</b> - Market unsure"
            trade_side = "Need more edge to trade"
        
        lines.append(f"  {edge_verdict}")
        lines.append("")
        
        # Quick stats
        lines.append("<b>📚 Quick Stats:</b>")
        if current_price > 0.65:
            lines.append("  • Favorites at this level win ~70% of the time")
            lines.append("  • But upset risk is often underpriced")
        elif current_price < 0.35:
            lines.append("  • Underdogs at this level upset ~20-30% of the time")
            lines.append("  • Potential for 3x-5x if correct")
        else:
            lines.append("  • Toss-up markets are often the best value")
            lines.append("  • Look for news or form advantage")
        lines.append("")
        
        # Trading Recommendation
        lines.append("<b>🎯 Trading Recommendation:</b>")
        lines.append(f"  {trade_side}")
        
        # Position sizing hint
        if current_price < 0.30 or current_price > 0.80:
            lines.append("  💰 Sizing: Small (2-3% of bankroll)")
        else:
            lines.append("  💰 Sizing: Normal (5% of bankroll)")
        
        return "\n".join(lines)
    
    def _get_price(self, market: Dict) -> float:
        """Get current price from market data."""
        current_price = market.get('current_price')
        
        if not current_price:
            prices = market.get('outcomePrices', [])
            if prices and len(prices) > 0:
                try:
                    current_price = float(prices[0])
                except:
                    current_price = 0.5
            else:
                current_price = 0.5
        
        try:
            return float(current_price)
        except:
            return 0.5
    
    def cmd_status(self, query: str = "") -> str:
        """Handle /status command."""
        return f"""<b>🤖 Bot Status</b>

⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 Mode: {Config.TRADING_MODE}
💰 Max Position: ${Config.MAX_POSITION_USD}

✅ Bot is running!"""

    def cmd_balance(self, query: str = "") -> str:
        """Handle /balance command."""
        if self.db:
            try:
                balance = self.db.get_balance()
                return f"""<b>💰 Balance</b>

Current: ${balance:,.2f}
Mode: {Config.TRADING_MODE}"""
            except:
                pass
        
        return f"<b>💰 Balance</b>\n\nStarting: ${Config.STARTING_BALANCE:,.2f}\nMode: {Config.TRADING_MODE}"

    def cmd_positions(self, query: str = "") -> str:
        """Handle /positions command."""
        if self.db:
            try:
                positions = self.db.get_open_positions()
                if not positions:
                    return "📭 No open positions"
                
                lines = ["<b>📊 Open Positions</b>\n"]
                for pos in positions[:5]:
                    market = pos.get('market_question', 'Unknown')[:40]
                    entry = pos.get('entry_price', 0) * 100
                    size = pos.get('size_usd', 0)
                    lines.append(f"• {market}...\n  Entry: {entry:.0f}%, Size: ${size:.0f}")
                
                return "\n".join(lines)
            except:
                pass
        
        return "📭 No positions loaded"


# Singleton instance
_telegram_bot = None

def get_telegram_bot(**kwargs) -> TelegramBot:
    """Get or create Telegram bot instance."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot(**kwargs)
    return _telegram_bot
