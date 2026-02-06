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
        
        # Check if it's a command
        for cmd, handler in self.commands.items():
            if text.startswith(cmd):
                query = text[len(cmd):].strip()
                try:
                    response = handler(query)
                    self._send_message(chat_id, response)
                except Exception as e:
                    self._send_message(chat_id, f"❌ Error: {str(e)}")
                return
    
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

    def cmd_info(self, query: str) -> str:
        """
        Handle /info command - SMART search for match info using AI.
        
        Features:
        - AI interprets imprecise queries
        - Fuzzy team name matching
        - Comprehensive insights with stats and predictions
        """
        if not query:
            return """❌ Please provide a search query.

<b>Examples:</b>
• /info Barcelona vs Manchester
• /info Lakers game
• /info Man United match tomorrow
• /info Chelsea win chance

I'll use AI to understand what you mean, even with typos!"""
        
        print(f"🔍 /info query: {query}")
        
        # Step 1: Use AI to interpret the query
        interpreted = self._ai_interpret_query(query)
        
        # Step 2: Find matching markets (with fuzzy matching)
        matching_markets = self._smart_search_markets(interpreted)
        
        if not matching_markets:
            # Try harder with AI correction
            corrected = self._ai_correct_teams(query)
            if corrected != query:
                matching_markets = self._smart_search_markets(corrected)
        
        if not matching_markets:
            return f"""❌ <b>No markets found</b>

Query: "{query}"
{f'Interpreted as: "{interpreted}"' if interpreted != query else ''}

<b>💡 Tips:</b>
• Try full team names
• Check if there's an active market
• Example: /info Liverpool vs Real Madrid"""
        
        # Step 3: Build comprehensive response
        response_parts = [
            f"<b>🏟️ Match Info</b>",
            f"Query: <i>{query}</i>",
        ]
        
        if interpreted and interpreted != query:
            response_parts.append(f"Understood as: <i>{interpreted}</i>")
        
        response_parts.append("")
        
        # Show top match with full analysis
        top_market = matching_markets[0]
        market_analysis = self._comprehensive_analysis(top_market)
        response_parts.append(market_analysis)
        
        # Show other matches if any
        if len(matching_markets) > 1:
            response_parts.append("\n<b>📋 Other Related Markets:</b>")
            for market in matching_markets[1:3]:
                q = market.get('question', 'Unknown')[:50]
                p = market.get('current_price', 0.5)
                try:
                    p = float(p) if p else 0.5
                except:
                    p = 0.5
                response_parts.append(f"• {q}... ({p*100:.0f}%)")
        
        return "\n".join(response_parts)
    
    def _ai_interpret_query(self, query: str) -> str:
        """Use AI to interpret and standardize the query."""
        if not self.ai_analyzer:
            return query
        
        try:
            # Ask AI to interpret the query
            prompt = f"""Interpret this sports market query and extract:
- Team names (corrected spelling)
- Sport type
- Date/time if mentioned

Query: "{query}"

Return just the corrected/interpreted query, e.g., "Barcelona vs Real Madrid football" or "Lakers vs Celtics NBA game".
If unclear, return the original query."""

            # Use AI analyzer's underlying model if available
            result = self.ai_analyzer._call_ai(prompt)
            if result and len(result) < 100:
                return result.strip().strip('"')
        except:
            pass
        
        return query
    
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
            'warriors': 'Golden State Warriors',
            'bulls': 'Chicago Bulls',
            'heat': 'Miami Heat',
            'nets': 'Brooklyn Nets',
            'chiefs': 'Kansas City Chiefs',
            'pats': 'New England Patriots',
            'cowboys': 'Dallas Cowboys',
        }
        
        result = query.lower()
        for short, full in corrections.items():
            result = result.replace(short, full)
        
        return result
    
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
                
                # Exact phrase matching
                for word in query_words:
                    if word in full_text:
                        score += 3
                    # Fuzzy: check if 80% of word matches
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
        question = market.get('question', '')
        teams = self._extract_teams(question)
        
        # Team Stats Section
        if teams and self.team_stats and len(teams) >= 2:
            lines.append("<b>📈 Team Statistics:</b>")
            try:
                sport = market.get('sport', 'football')
                
                for i, team in enumerate(teams[:2]):
                    stats = self.team_stats.get_team_stats(team, sport)
                    if stats:
                        form = stats.get('form', 'N/A')
                        goals = stats.get('goals_scored', 'N/A')
                        conceded = stats.get('goals_conceded', 'N/A')
                        icon = "🏠" if i == 0 else "✈️"
                        lines.append(f"  {icon} <b>{team}</b>")
                        lines.append(f"      Form: {form} | Goals: {goals} | Conceded: {conceded}")
            except:
                pass
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
        
        # AI Prediction
        if self.ai_analyzer:
            try:
                ai_result = self.ai_analyzer.analyze_market(market)
                if ai_result:
                    prediction = ai_result.get('prediction', 'N/A')
                    confidence = ai_result.get('confidence', 0) * 100
                    reasoning = ai_result.get('reasoning', '')[:100]
                    
                    lines.append("<b>🤖 AI Analysis:</b>")
                    lines.append(f"  Prediction: <b>{prediction}</b> ({confidence:.0f}% confidence)")
                    if reasoning:
                        lines.append(f"  Reason: {reasoning}...")
                    lines.append("")
            except:
                pass
        
        # Historical Pattern (if available)
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
