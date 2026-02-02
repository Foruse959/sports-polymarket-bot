"""
Sports Polymarket Quant Trading Bot

Main Flask application with dashboard, scanner, and trading engine.
"""

import os
import sys
import threading
import time
import asyncio
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS

# Ensure we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from data.database import Database
from data.polymarket_client import PolymarketClient
from core.live_sports_feed import LiveSportsFeed
from core.sports_strategies import SportsStrategyEngine
from trading.paper_trader import PaperTrader
from alerts.telegram_alerts import TelegramAlerts

# NEW: Import dynamic components
from core.dynamic_engine import DynamicStrategyEngine
from core.arbitrage_detector import ArbitrageDetector
from core.whale_tracker import WhaleTracker
from core.adaptive_thresholds import AdaptiveThresholds
from data.multi_source import DataAggregator
from trading.smart_executor import SmartExecutor


# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global instances
db = Database()
polymarket = PolymarketClient()
sports_feed = LiveSportsFeed()
strategy_engine = SportsStrategyEngine()
paper_trader = PaperTrader()
alerts = TelegramAlerts()

# NEW: Initialize dynamic components with graceful degradation
try:
    print("\n🚀 Initializing dynamic autonomous systems...")
    
    # Initialize components
    arbitrage_detector = ArbitrageDetector() if Config.ARB_ENABLED else None
    whale_tracker = WhaleTracker() if Config.WHALE_TRACKING_ENABLED else None
    adaptive_thresholds = AdaptiveThresholds() if Config.ADAPTIVE_ENABLED else None
    data_aggregator = DataAggregator()
    smart_executor = SmartExecutor(polymarket_client=polymarket)
    
    # Initialize dynamic engine (wraps existing strategies)
    if Config.CASCADE_ENABLED:
        dynamic_engine = DynamicStrategyEngine(
            base_strategies=strategy_engine.strategies,
            config=Config,
            arbitrage_detector=arbitrage_detector,
            adaptive_thresholds=adaptive_thresholds
        )
        print("✅ Dynamic Strategy Engine: Enabled")
    else:
        dynamic_engine = None
        print("⚪ Dynamic Strategy Engine: Disabled (using basic engine)")
    
    print("✅ All dynamic systems initialized successfully\n")
    
except Exception as e:
    print(f"⚠️ Dynamic engine initialization failed: {e}")
    print("⚠️ Falling back to basic engine")
    dynamic_engine = None
    arbitrage_detector = None
    whale_tracker = None
    adaptive_thresholds = None
    data_aggregator = None
    smart_executor = None

# State
bot_running = False
last_scan_time = None
scan_count = 0
signals_found = 0


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD HTML
# ═══════════════════════════════════════════════════════════════════════════

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sports Polymarket Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
        }
        h1 { font-size: 1.8em; }
        .badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .badge-paper { background: #f39c12; color: #000; }
        .badge-live { background: #e74c3c; }
        .badge-running { background: #27ae60; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.08);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .stat-card .icon { font-size: 2em; margin-bottom: 10px; }
        .stat-card .value { font-size: 1.8em; font-weight: bold; color: #3498db; }
        .stat-card .label { color: #888; font-size: 0.9em; margin-top: 5px; }
        
        .section {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .section h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .strategies-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 10px;
        }
        .strategy-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
        }
        .strategy-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .strategy-dot.on { background: #2ecc71; }
        .strategy-dot.off { background: #555; }
        
        .positions-list { margin-top: 10px; }
        .position-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .position-info { flex: 1; }
        .position-pnl { font-weight: bold; font-size: 1.2em; }
        .position-pnl.positive { color: #2ecc71; }
        .position-pnl.negative { color: #e74c3c; }
        
        .trades-list { max-height: 300px; overflow-y: auto; }
        .trade-item {
            display: flex;
            justify-content: space-between;
            padding: 12px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .trade-win { border-left: 3px solid #2ecc71; }
        .trade-loss { border-left: 3px solid #e74c3c; }
        
        .no-data {
            text-align: center;
            color: #666;
            padding: 30px;
        }
        
        .risk-status {
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
        }
        .risk-ok { background: rgba(46,204,113,0.2); border: 1px solid #2ecc71; }
        .risk-warning { background: rgba(243,156,18,0.2); border: 1px solid #f39c12; }
        .risk-danger { background: rgba(231,76,60,0.2); border: 1px solid #e74c3c; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 Sports Polymarket Bot</h1>
            <div>
                <span id="mode-badge" class="badge badge-paper">📝 PAPER</span>
                <span id="status-badge" class="badge badge-running">🟢 Running</span>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">💰</div>
                <div class="value" id="balance">$0</div>
                <div class="label">Balance</div>
            </div>
            <div class="stat-card">
                <div class="icon">📈</div>
                <div class="value" id="equity">$0</div>
                <div class="label">Equity</div>
            </div>
            <div class="stat-card">
                <div class="icon">💵</div>
                <div class="value" id="pnl">$0</div>
                <div class="label">Total P&L</div>
            </div>
            <div class="stat-card">
                <div class="icon">🎯</div>
                <div class="value" id="win-rate">0%</div>
                <div class="label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="icon">📊</div>
                <div class="value" id="trades">0</div>
                <div class="label">Total Trades</div>
            </div>
            <div class="stat-card">
                <div class="icon">📂</div>
                <div class="value" id="positions">0</div>
                <div class="label">Open Positions</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🎯 Active Strategies</h2>
            <div class="strategies-grid" id="strategies"></div>
        </div>
        
        <div class="section">
            <h2>📂 Open Positions</h2>
            <div class="positions-list" id="positions-list">
                <div class="no-data">No open positions</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📜 Recent Trades</h2>
            <div class="trades-list" id="trades-list">
                <div class="no-data">No trades yet</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🛡️ Risk Status</h2>
            <div id="risk-status" class="risk-status risk-ok">
                Loading risk status...
            </div>
        </div>
        
        <div class="section">
            <h2>🤖 Dynamic Autonomous Systems</h2>
            <div id="dynamic-stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px">
                <div style="background:rgba(255,255,255,0.03);padding:15px;border-radius:8px">
                    <div style="font-size:1.5em;margin-bottom:5px">🔄</div>
                    <div style="font-size:1.2em;font-weight:bold" id="cascade-signals">-</div>
                    <div style="color:#888;font-size:0.85em">Cascade Signals</div>
                </div>
                <div style="background:rgba(255,255,255,0.03);padding:15px;border-radius:8px">
                    <div style="font-size:1.5em;margin-bottom:5px">🎯</div>
                    <div style="font-size:1.2em;font-weight:bold" id="arb-opportunities">-</div>
                    <div style="color:#888;font-size:0.85em">Arb Opportunities</div>
                </div>
                <div style="background:rgba(255,255,255,0.03);padding:15px;border-radius:8px">
                    <div style="font-size:1.5em;margin-bottom:5px">🐋</div>
                    <div style="font-size:1.2em;font-weight:bold" id="whale-count">-</div>
                    <div style="color:#888;font-size:0.85em">Active Whales</div>
                </div>
                <div style="background:rgba(255,255,255,0.03);padding:15px;border-radius:8px">
                    <div style="font-size:1.5em;margin-bottom:5px">📊</div>
                    <div style="font-size:1.2em;font-weight:bold" id="adaptive-mode">-</div>
                    <div style="color:#888;font-size:0.85em">Adaptive Mode</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function fetchData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Update stats
                document.getElementById('balance').textContent = '$' + data.balance.toFixed(2);
                document.getElementById('equity').textContent = '$' + data.equity.toFixed(2);
                document.getElementById('pnl').textContent = (data.total_pnl >= 0 ? '+$' : '-$') + Math.abs(data.total_pnl).toFixed(2);
                document.getElementById('pnl').style.color = data.total_pnl >= 0 ? '#2ecc71' : '#e74c3c';
                document.getElementById('win-rate').textContent = (data.win_rate * 100).toFixed(0) + '%';
                document.getElementById('trades').textContent = data.total_trades;
                document.getElementById('positions').textContent = data.open_positions;
                
                // Update mode badge
                const modeBadge = document.getElementById('mode-badge');
                modeBadge.textContent = data.is_paper ? '📝 PAPER' : '💸 LIVE';
                modeBadge.className = 'badge ' + (data.is_paper ? 'badge-paper' : 'badge-live');
                
                // Update strategies
                const strategiesHtml = data.strategies.map(s => `
                    <div class="strategy-item">
                        <div class="strategy-dot ${s.enabled ? 'on' : 'off'}"></div>
                        <span>${s.name}</span>
                    </div>
                `).join('');
                document.getElementById('strategies').innerHTML = strategiesHtml;
                
                // Update positions
                if (data.positions.length > 0) {
                    const positionsHtml = data.positions.map(p => {
                        const isPositive = p.unrealized_pnl >= 0;
                        return `
                            <div class="position-item">
                                <div class="position-info">
                                    <strong>${p.strategy}</strong> | ${p.sport.toUpperCase()}
                                    <div style="color:#888;font-size:0.85em">${p.market_question.substring(0, 50)}...</div>
                                </div>
                                <div class="position-pnl ${isPositive ? 'positive' : 'negative'}">
                                    ${isPositive ? '+' : ''}$${p.unrealized_pnl.toFixed(2)}
                                </div>
                            </div>
                        `;
                    }).join('');
                    document.getElementById('positions-list').innerHTML = positionsHtml;
                } else {
                    document.getElementById('positions-list').innerHTML = '<div class="no-data">No open positions</div>';
                }
                
                // Update trades
                if (data.recent_trades.length > 0) {
                    const tradesHtml = data.recent_trades.map(t => {
                        const isWin = t.pnl > 0;
                        return `
                            <div class="trade-item ${isWin ? 'trade-win' : 'trade-loss'}">
                                <div>
                                    <strong>${t.strategy}</strong>
                                    <div style="color:#888;font-size:0.85em">${t.exit_reason}</div>
                                </div>
                                <div style="font-weight:bold;color:${isWin ? '#2ecc71' : '#e74c3c'}">
                                    ${isWin ? '+' : ''}$${t.pnl.toFixed(2)}
                                </div>
                            </div>
                        `;
                    }).join('');
                    document.getElementById('trades-list').innerHTML = tradesHtml;
                }
                
                // Update risk status
                const risk = data.risk;
                const riskHtml = `
                    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px">
                        <div>Daily P&L: <strong>${risk.daily_pnl >= 0 ? '+' : ''}$${risk.daily_pnl.toFixed(2)}</strong> / $${risk.daily_loss_limit}</div>
                        <div>Loss Streak: <strong>${risk.loss_streak}</strong></div>
                        <div>Hourly Trades: <strong>${risk.hourly_trades}/${risk.hourly_limit}</strong></div>
                    </div>
                    ${risk.kill_switch_active ? '<div style="margin-top:10px;color:#e74c3c">⚠️ KILL SWITCH ACTIVE</div>' : ''}
                    ${risk.is_paused ? '<div style="margin-top:10px;color:#f39c12">⏸️ Trading paused</div>' : ''}
                `;
                const riskDiv = document.getElementById('risk-status');
                riskDiv.innerHTML = riskHtml;
                riskDiv.className = 'risk-status ' + (risk.kill_switch_active ? 'risk-danger' : risk.loss_streak > 2 ? 'risk-warning' : 'risk-ok');
                
                // Fetch and update dynamic stats
                fetchDynamicStats();
                
            } catch (e) {
                console.error('Error fetching data:', e);
            }
        }
        
        async function fetchDynamicStats() {
            try {
                const res = await fetch('/api/dynamic_stats');
                const data = await res.json();
                
                // Update cascade stats
                if (data.cascade) {
                    document.getElementById('cascade-signals').textContent = data.cascade.signals_found || 0;
                }
                
                // Update arbitrage stats
                if (data.arbitrage) {
                    document.getElementById('arb-opportunities').textContent = data.arbitrage.opportunities_found_today || 0;
                }
                
                // Update whale tracker stats
                if (data.whale_tracker) {
                    document.getElementById('whale-count').textContent = data.whale_tracker.active_whales || 0;
                }
                
                // Update adaptive mode
                if (data.adaptive) {
                    const mode = data.adaptive.emergency_mode ? '🚨 Emergency' : '✅ Normal';
                    document.getElementById('adaptive-mode').textContent = mode;
                }
                
            } catch (e) {
                console.error('Error fetching dynamic stats:', e);
            }
        }
        
        // Initial fetch and then every 5 seconds
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
'''


# ═══════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    """Serve the dashboard."""
    return DASHBOARD_HTML


@app.route('/api/status')
def api_status():
    """Get bot status for dashboard."""
    stats = paper_trader.get_performance_stats()
    risk_status = paper_trader.risk_manager.get_status()
    positions = paper_trader.get_positions()
    trades = db.get_trade_history(limit=10)
    strategies = strategy_engine.get_strategy_stats()
    
    return jsonify({
        'is_paper': Config.is_paper_mode(),
        'balance': stats.get('balance', 0),
        'equity': stats.get('equity', 0),
        'total_pnl': stats.get('total_pnl', 0),
        'win_rate': stats.get('win_rate', 0),
        'total_trades': stats.get('total_trades', 0),
        'open_positions': len(positions),
        'positions': positions,
        'recent_trades': trades,
        'strategies': strategies,
        'risk': risk_status,
        'last_scan': last_scan_time.isoformat() if last_scan_time else None,
        'scan_count': scan_count,
        'signals_found': signals_found
    })


@app.route('/api/positions')
def api_positions():
    """Get open positions."""
    return jsonify(paper_trader.get_positions())


@app.route('/api/trades')
def api_trades():
    """Get trade history."""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(db.get_trade_history(limit=limit))


@app.route('/api/strategies')
def api_strategies():
    """Get strategy stats."""
    return jsonify({
        'strategies': strategy_engine.get_strategy_stats(),
        'performance': db.get_all_strategy_stats()
    })


@app.route('/api/dynamic_stats')
def api_dynamic_stats():
    """Get stats from dynamic autonomous systems."""
    stats = {}
    
    if dynamic_engine:
        stats['cascade'] = dynamic_engine.get_stats()
    
    if arbitrage_detector:
        stats['arbitrage'] = arbitrage_detector.get_stats()
    
    if whale_tracker:
        stats['whale_tracker'] = whale_tracker.get_stats()
        stats['whale_profiles'] = whale_tracker.get_whale_profiles()
    
    if adaptive_thresholds:
        stats['adaptive'] = adaptive_thresholds.get_stats()
        stats['strategy_performance'] = adaptive_thresholds.get_strategy_stats()
    
    if data_aggregator:
        stats['data_sources'] = data_aggregator.get_source_health()
    
    if smart_executor:
        stats['execution'] = smart_executor.get_stats()
    
    return jsonify(stats)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot_running': bot_running,
        'mode': Config.TRADING_MODE,
        'timestamp': datetime.now().isoformat()
    })


# ═══════════════════════════════════════════════════════════════════════════
# SCANNER LOOP
# ═══════════════════════════════════════════════════════════════════════════

def scanner_loop():
    """Main scanning loop for finding and executing trades."""
    global bot_running, last_scan_time, scan_count, signals_found
    
    print("\n" + "=" * 60)
    print("🚀 SPORTS POLYMARKET QUANT BOT STARTED")
    print("=" * 60)
    Config.print_status()
    
    # Send startup alert
    alerts.alert_bot_status('started')
    
    bot_running = True
    summary_last_sent = datetime.now()
    
    while bot_running:
        try:
            scan_start = time.time()
            
            # 1. Get sports markets from Polymarket FIRST (market-driven approach)
            # Use new improved method that fetches from /sports endpoint
            markets = polymarket.get_sports_markets_v2(limit=500)
            
            # 2. Get game data dynamically based on markets (NEW!)
            # This searches ESPN for teams mentioned in Polymarket markets
            market_games = sports_feed.get_game_data_for_markets(markets)
            live_games_found = sum(1 for g in market_games.values() if g.get('is_live'))
            
            # 3. Also get general live games as fallback
            all_games = sports_feed.get_all_live_games()
            total_games = sum(len(g) for g in all_games.values()) + live_games_found
            
            # 4. Detect sports events
            events = sports_feed.detect_all_events()
            
            # 5. Get current prices for position updates
            current_prices = {}
            for market in markets:
                market_id = market.get('id', '')
                price = polymarket.get_market_price(market)
                current_prices[market_id] = price
                market['current_price'] = price
            
            # 6. Update positions and check exits
            closed_trades = paper_trader.update_positions(current_prices)
            
            # Update adaptive thresholds with closed trade results
            if adaptive_thresholds and closed_trades:
                for trade in closed_trades:
                    strategy_name = trade.get('strategy', 'Unknown')
                    pnl = trade.get('pnl', 0)
                    adaptive_thresholds.record_trade(strategy_name, pnl)
            
            # Send alerts for closed trades
            for trade in closed_trades:
                alerts.alert_trade_closed(trade)
            
            # 7. Analyze markets with strategies
            all_signals = []
            
            # NEW: Use dynamic cascade engine if available
            if dynamic_engine:
                print(f"\n🔄 Running dynamic cascade scan...")
                
                # Prepare sports data for cascade
                sports_data = {
                    'market_games': market_games,
                    'all_games': all_games
                }
                
                # Run cascade scan (async compatible)
                try:
                    # Create event loop if needed
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Run cascade scan
                    cascade_signals = loop.run_until_complete(
                        dynamic_engine.cascade_scan(markets, sports_data, events)
                    )
                    all_signals.extend(cascade_signals)
                    
                except Exception as e:
                    print(f"⚠️ Dynamic cascade error: {e}")
                    # Fall back to traditional scanning
                    print("⚠️ Falling back to traditional strategy scan...")
            
            # Fallback: Use traditional strategy engine
            if not all_signals or not dynamic_engine:
                for market in markets:
                    market_id = market.get('id', '')
                    sport = market.get('sport', 'unknown')
                    
                    # Get game data - first try market-specific, then fallback to general
                    game_data = market_games.get(market_id, {})
                    if not game_data:
                        sport_games = all_games.get(sport, [])
                        game_data = sport_games[0] if sport_games else {}
                    
                    sports_data = {'game': game_data}
                    
                    # Check for relevant events
                    relevant_events = [e for e in events if e.sport == sport]
                    event_dict = None
                    if relevant_events:
                        e = relevant_events[0]
                        event_dict = {
                            'event_type': e.event_type.value,
                            'team': e.team,
                            'game_time': e.game_time,
                            'details': e.details
                        }
                    
                    # Run strategy analysis
                    signals = strategy_engine.analyze_market(market, sports_data, event_dict)
                    
                    for signal in signals:
                        # Convert TradeSignal to dict
                        signal_dict = {
                            'strategy': signal.strategy,
                            'signal_type': signal.signal_type.value,
                            'market_id': signal.market_id,
                            'market_question': signal.market_question,
                            'sport': signal.sport,
                            'entry_price': signal.entry_price,
                            'target_price': signal.target_price,
                            'stop_loss_price': signal.stop_loss_price,
                            'confidence': signal.confidence,
                            'size_usd': signal.size_usd,
                            'rationale': signal.rationale,
                            'metadata': signal.metadata
                        }
                        all_signals.append(signal_dict)
            
            signals_found += len(all_signals)
            
            # 8. Execute top signals
            for signal in all_signals[:3]:  # Max 3 trades per scan
                # Send signal alert
                alerts.alert_signal(signal)
                
                # Execute paper trade
                trade = paper_trader.execute_trade(signal)
                
                if trade:
                    alerts.alert_trade_opened(trade)
            
            # 9. Update scan stats
            last_scan_time = datetime.now()
            scan_count += 1
            scan_duration = time.time() - scan_start
            
            # Log scan summary
            positions_count = len(paper_trader.get_positions())
            print(f"\n📊 Scan #{scan_count} completed in {scan_duration:.1f}s")
            print(f"   Markets: {len(markets)} | Games: {total_games} | Market-matched: {len(market_games)}")
            print(f"   Signals: {len(all_signals)} | Positions: {positions_count}")
            
            # 9. Send periodic summary
            hours_since_summary = (datetime.now() - summary_last_sent).seconds / 3600
            if hours_since_summary >= Config.SUMMARY_INTERVAL_HOURS:
                stats = paper_trader.get_performance_stats()
                alerts.alert_summary(stats)
                summary_last_sent = datetime.now()
            
            # 10. Wait for next scan
            time.sleep(Config.SCAN_INTERVAL_SECONDS)
            
        except Exception as e:
            print(f"❌ Scanner error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)  # Wait 30s on error before retry
    
    print("🛑 Scanner stopped")


def start_scanner():
    """Start the scanner in a background thread."""
    scanner_thread = threading.Thread(target=scanner_loop, daemon=True)
    scanner_thread.start()
    return scanner_thread


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Start scanner
    start_scanner()
    
    # Use PORT from environment (Railway sets this) or fallback to config
    port = int(os.environ.get('PORT', Config.DASHBOARD_PORT))
    print(f"\n🌐 Dashboard running at http://localhost:{port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,  # Disable debug in production
        use_reloader=False  # Disable reloader to prevent duplicate scanner
    )

