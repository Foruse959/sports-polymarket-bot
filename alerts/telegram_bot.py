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
        """Handle /info command - search for match info using AI."""
        if not query:
            return "❌ Please provide a search query.\nExample: /info Barcelona vs Manchester"
        
        print(f"🔍 /info query: {query}")
        
        # Try to find matching markets from Polymarket
        matching_markets = self._search_markets(query)
        
        if not matching_markets:
            return f"❌ No markets found matching: <b>{query}</b>\n\nTry being more specific or check if there are active sports markets."
        
        # Build response with analysis
        response_parts = [f"<b>🏟️ Search Results for:</b> {query}\n"]
        
        for i, market in enumerate(matching_markets[:3], 1):
            market_info = self._analyze_market(market)
            response_parts.append(f"\n<b>{i}. {market.get('question', 'Unknown')[:60]}...</b>")
            response_parts.append(market_info)
        
        return "\n".join(response_parts)
    
    def _search_markets(self, query: str) -> List[Dict]:
        """Search for markets matching the query."""
        if not self.polymarket:
            return []
        
        try:
            # Get all sports markets
            markets = self.polymarket.get_sports_markets()
            
            if not markets:
                return []
            
            # Parse query for team names, sport, etc.
            query_lower = query.lower()
            query_words = set(query_lower.split())
            
            # Score each market by relevance
            scored_markets = []
            
            for market in markets:
                question = market.get('question', '').lower()
                description = market.get('description', '').lower()
                
                # Calculate relevance score
                score = 0
                
                # Check for exact phrases
                for word in query_words:
                    if len(word) > 2:  # Skip short words
                        if word in question:
                            score += 3
                        if word in description:
                            score += 1
                
                # Boost for team name matches
                teams = self._extract_teams(query)
                if teams:
                    for team in teams:
                        if team.lower() in question:
                            score += 5
                
                if score > 0:
                    market['relevance_score'] = score
                    scored_markets.append(market)
            
            # Sort by relevance
            scored_markets.sort(key=lambda m: m.get('relevance_score', 0), reverse=True)
            
            return scored_markets[:5]
            
        except Exception as e:
            print(f"⚠️ Market search error: {e}")
            return []
    
    def _extract_teams(self, query: str) -> List[str]:
        """Extract team names from query."""
        # Common patterns
        patterns = [
            r'(.+?)\s+(?:vs|v|versus)\s+(.+)',
            r'(.+?)\s+(?:against|plays?|@)\s+(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return [match.group(1).strip(), match.group(2).strip()]
        
        # Return single term if no pattern matched
        return [query.strip()] if query.strip() else []
    
    def _analyze_market(self, market: Dict) -> str:
        """Analyze a market and return formatted info."""
        current_price = market.get('current_price', market.get('outcomePrices', [0.5])[0] if isinstance(market.get('outcomePrices'), list) else 0.5)
        
        # Try to convert price
        try:
            if isinstance(current_price, str):
                current_price = float(current_price)
        except:
            current_price = 0.5
        
        info_lines = []
        
        # Current odds
        win_prob = current_price * 100
        info_lines.append(f"📊 <b>Win Probability:</b> {win_prob:.0f}%")
        
        # Determine edge based on price position
        if current_price > 0.75:
            edge = "⛔ No edge (heavy favorite)"
        elif current_price < 0.25:
            edge = "⚠️ High risk underdog (+potential value)"
        elif 0.45 <= current_price <= 0.55:
            edge = "⚖️ 50/50 toss-up"
        else:
            edge = "✅ Potential value"
        
        info_lines.append(f"📈 <b>Edge:</b> {edge}")
        
        # Get team stats if available
        question = market.get('question', '')
        teams = self._extract_teams(question)
        
        if teams and self.team_stats and len(teams) == 2:
            try:
                sport = market.get('sport', 'football')
                stats1 = self.team_stats.get_team_stats(teams[0], sport)
                stats2 = self.team_stats.get_team_stats(teams[1], sport)
                
                if stats1:
                    form1 = stats1.get('form', 'N/A')
                    info_lines.append(f"🔹 <b>{teams[0]}:</b> Form {form1}")
                
                if stats2:
                    form2 = stats2.get('form', 'N/A')
                    info_lines.append(f"🔹 <b>{teams[1]}:</b> Form {form2}")
            except:
                pass
        
        # AI analysis if available
        if self.ai_analyzer:
            try:
                ai_result = self.ai_analyzer.analyze_market(market)
                if ai_result and ai_result.get('confidence', 0) > 0.5:
                    prediction = ai_result.get('prediction', 'N/A')
                    ai_conf = ai_result.get('confidence', 0) * 100
                    info_lines.append(f"🤖 <b>AI:</b> {prediction} ({ai_conf:.0f}% conf)")
            except:
                pass
        
        # Trading recommendation
        if current_price < 0.30:
            rec = "🎯 <b>Trade:</b> Consider LONG (underdog value)"
        elif current_price > 0.80:
            rec = "🎯 <b>Trade:</b> Consider SHORT (fade favorite)"
        else:
            rec = "🎯 <b>Trade:</b> Monitor for entry"
        
        info_lines.append(rec)
        
        return "\n".join(info_lines)
    
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
