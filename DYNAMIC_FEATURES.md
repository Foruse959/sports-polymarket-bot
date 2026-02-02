# 🚀 Dynamic Autonomous Trading System

## Overview

The bot now features a **fully autonomous, self-healing trading system** that requires **ZERO manual configuration** to work. Every component gracefully degrades when resources are missing and auto-discovers what it needs.

---

## 🎯 Core Philosophy: "ALWAYS WORK, NEVER STOP"

1. **Work with whatever resources are available**
2. **Gracefully degrade when resources are missing**
3. **Auto-discover what it needs when possible**
4. **Never require manual configuration to function**

---

## 🆕 New Features

### 1. 🔄 Dynamic Strategy Cascade Engine

**Never stops looking for opportunities!**

- Wraps ALL existing strategies from `core/sports_strategies.py`
- Tries strategies in priority order (highest profit potential first)
- If Strategy A finds nothing → automatically tries B → C → etc.
- If ALL strategies find nothing → LOWERS thresholds and retries
- Tracks which strategies are working and prioritizes them

**Priority Levels:**
- **CRITICAL**: Arbitrage, resolved markets (risk-free)
- **HIGH**: Overreaction fade, lag arbitrage (time-sensitive)
- **MEDIUM**: Market-only, draw decay (good opportunities)
- **LOW**: Volatility scalp, favorite trap (lower confidence)

**Configuration:**
```bash
CASCADE_ENABLED=true                    # Enable cascade engine
CASCADE_THRESHOLD_DECAY=0.8            # Reduce thresholds by 20% per retry
CASCADE_MAX_RETRIES=3                  # Max retry attempts
```

### 2. 🎯 Self-Discovering Arbitrage Detector

**Automatically finds risk-free profit opportunities!**

- Scans ALL markets for YES + NO < $1.00 opportunities
- Scans resolved markets for winning shares < $1.00
- Works with just Polymarket API (no external dependencies)
- Auto-calculates optimal position sizes

**How it works:**
```
Market: "Will Lakers win?"
YES: $0.45
NO: $0.50
Total: $0.95

Action: Buy both for $0.95, redeem for $1.00
Profit: 5¢ per dollar invested (risk-free!)
```

**Configuration:**
```bash
ARB_ENABLED=true                       # Enable arbitrage detection
ARB_MIN_EDGE_CENTS=1.5                # Minimum edge in cents
ARB_SCAN_RESOLVED=true                # Scan resolved markets
```

### 3. 🐋 Auto-Discovering Whale Tracker

**CRITICAL: Works with ZERO configured wallets!**

- Monitors ALL trades on sports markets
- Tracks wallets making trades > $500
- Builds performance profile for each wallet
- Auto-promotes wallets with >65% win rate to "whale" status
- Starts copying their trades

**The bot DISCOVERS profitable wallets on its own!**

**Configuration:**
```bash
WHALE_TRACKING_ENABLED=true           # Enable whale tracking
WHALE_WALLETS=                        # Optional: Pre-configured wallets (comma-separated)
WHALE_AUTO_DISCOVER=true              # Auto-discover profitable wallets
WHALE_MIN_TRADE_USD=500              # Minimum trade size to track
WHALE_MIN_WIN_RATE=0.65              # Minimum win rate for promotion
WHALE_COPY_DELAY_SECONDS=30          # Delay before copying trades
```

### 4. 📊 Adaptive Threshold System

**Auto-tunes strategy thresholds based on performance!**

- Winning strategies → loosen thresholds (take more trades)
- Losing strategies → tighten thresholds (be selective)
- New strategies → start with defaults, learn over time

**Emergency Mode:**
- If no trades for 6+ hours → progressively loosen ALL thresholds
- Ensures bot always finds SOMETHING to trade

**Configuration:**
```bash
ADAPTIVE_ENABLED=true                 # Enable adaptive thresholds
ADAPTIVE_LOOKBACK_TRADES=50          # Number of trades to analyze
ADAPTIVE_EMERGENCY_HOURS=6           # Hours without trades triggers emergency
```

### 5. 📡 Multi-Source Data Aggregator

**NEVER FAILS TO GET DATA**

**For market data:**
1. Try Polymarket Gamma API
2. If fails → Try Polymarket CLOB API
3. If fails → Use cached data (up to 5 min old)
4. If no cache → Use last known prices

**For sports data:**
1. Try ESPN API (free, no key needed)
2. If fails → Use embedded free sports APIs
3. If fails → Trade without sports data (market-only strategies)

**For external odds:**
1. Try The Odds API (if key configured)
2. If no key → Skip odds comparison
3. Bot still works, just without this feature

**Configuration:**
```bash
ESPN_ENABLED=true                    # Enable ESPN API (free)
FREE_SPORTS_APIS=true               # Enable other free sports APIs
ODDS_API_KEY=                       # Optional: The Odds API key
POLYGONSCAN_API_KEY=                # Optional: Polygonscan API key
```

### 6. 🔌 Resilient WebSocket Feed

**ALWAYS CONNECTED (or gracefully degraded)**

1. Try WebSocket connection to Polymarket
2. If WebSocket fails → Fall back to fast polling (5 sec)
3. If fast polling fails → Fall back to normal polling (30 sec)
4. Auto-reconnect WebSocket when available

**Bot NEVER stops due to connection issues**

**Configuration:**
```bash
USE_WEBSOCKET=true                   # Try WebSocket first
WEBSOCKET_FALLBACK_POLL_SECONDS=5   # Fast poll interval
```

### 7. ⚡ Smart Order Execution

**Intelligent order execution with protection:**

- Slippage protection (max 2%)
- Liquidity checking
- Order splitting for large trades
- Retry logic with backoff

---

## 📊 Dashboard Enhancements

The dashboard now shows:

- **Cascade Signals**: Number of signals found via cascade engine
- **Arb Opportunities**: Arbitrage opportunities found today
- **Active Whales**: Number of whale wallets being tracked/copied
- **Adaptive Mode**: Current threshold adjustment mode

Access dynamic stats API:
```bash
GET /api/dynamic_stats
```

---

## 🧪 Test Scenarios

The bot handles ALL of these:

✅ **Zero Config**: Fresh deploy with no env vars → Bot runs with defaults  
✅ **No API Keys**: All external APIs missing → Bot uses Polymarket-only strategies  
✅ **No Whale Wallets**: Empty WHALE_WALLETS → Bot auto-discovers from trades  
✅ **API Failures**: ESPN down, Polymarket slow → Bot falls back and continues  
✅ **No Opportunities**: All strategies find nothing → Bot lowers thresholds and retries  
✅ **WebSocket Failure**: Connection drops → Auto-fallback to polling, auto-reconnect

---

## 📈 Expected Results

After implementation, the bot should:

- ✅ Find 5-20+ paper trade opportunities per day (vs 0 currently)
- ✅ Auto-discover 3-10 whale wallets within first week
- ✅ Maintain 65-80% win rate through adaptive thresholds
- ✅ Never have more than 30 minutes without scanning
- ✅ Gracefully handle any API/data source failure

---

## 🔑 Key Principles

1. **ZERO REQUIRED CONFIGURATION** - Bot works out of the box
2. **EVERYTHING IS OPTIONAL** - API keys, whale wallets, external data
3. **GRACEFUL DEGRADATION** - Missing resource? Use alternative. No alternative? Skip feature.
4. **SELF-DISCOVERY** - Bot finds profitable wallets, optimal thresholds on its own
5. **NEVER STOPS** - Always scanning, always trying, always adapting
6. **BACKWARDS COMPATIBLE** - All existing features keep working

---

## 🚀 Quick Start

### Minimal Configuration (Zero Config Mode)

Just set the trading mode and starting balance:

```bash
TRADING_MODE=paper
STARTING_BALANCE=1000
```

The bot will:
- ✅ Use Polymarket API (no key needed)
- ✅ Scan for arbitrage opportunities
- ✅ Auto-discover whale wallets
- ✅ Adapt thresholds automatically
- ✅ Fall back to polling if WebSocket unavailable

### Full Configuration (All Features)

```bash
# Trading
TRADING_MODE=paper
STARTING_BALANCE=1000

# Dynamic Engine
CASCADE_ENABLED=true
CASCADE_THRESHOLD_DECAY=0.8
CASCADE_MAX_RETRIES=3

# Arbitrage
ARB_ENABLED=true
ARB_MIN_EDGE_CENTS=1.5
ARB_SCAN_RESOLVED=true

# Whale Tracking
WHALE_TRACKING_ENABLED=true
WHALE_AUTO_DISCOVER=true
WHALE_MIN_TRADE_USD=500
WHALE_MIN_WIN_RATE=0.65

# Adaptive System
ADAPTIVE_ENABLED=true
ADAPTIVE_LOOKBACK_TRADES=50
ADAPTIVE_EMERGENCY_HOURS=6

# Data Sources (all optional)
ESPN_ENABLED=true
FREE_SPORTS_APIS=true
ODDS_API_KEY=your_key_here
USE_WEBSOCKET=true
```

---

## 🛠️ Architecture

```
Dynamic Engine (Cascade)
    ├── Priority: CRITICAL
    │   ├── Arbitrage Detector ✅
    │   └── Resolved Markets
    ├── Priority: HIGH
    │   ├── Overreaction Fade
    │   ├── Lag Arbitrage
    │   └── Wicket Shock
    ├── Priority: MEDIUM
    │   ├── Market Only
    │   ├── Draw Decay
    │   └── Run Reversion
    └── Priority: LOW
        ├── Volatility Scalp
        ├── Favorite Trap
        └── Liquidity Provision

Data Aggregator (Multi-Source)
    ├── Polymarket API (primary)
    ├── ESPN API (free sports data)
    ├── Cache Layer (5 min TTL)
    └── Last Known Values (fallback)

Whale Tracker (Auto-Discovery)
    ├── Monitor All Trades
    ├── Build Performance Profiles
    ├── Auto-Promote (>65% win rate)
    └── Copy Trades (optional)

Adaptive Thresholds
    ├── Track Performance
    ├── Adjust Thresholds
    ├── Emergency Mode
    └── Strategy Prioritization
```

---

## 📝 Logging Examples

The bot produces detailed logs:

```
🔄 Cascade: Strategy 'Overreaction Fade' found 0 signals, trying next...
🔄 Cascade: Strategy 'Market Only' found 2 signals!
🎯 Arbitrage: Found YES+NO=$0.97 opportunity (3¢ edge)
🐋 Whale Discovery: Wallet 0x123... promoted to whale status (72% win rate)
📊 Adaptive: Loosening 'Market Only' thresholds (win rate: 78%)
⚠️ ESPN API failed, falling back to cached sports data
✅ WebSocket reconnected after 30s outage
🚨 Emergency Mode: No trades for 6h, loosening all thresholds by 15%
```

---

## 🎯 Success Metrics

Track these metrics to measure autonomous system performance:

- **Opportunities Found**: Should increase 10-20x vs basic engine
- **Arbitrage Discoveries**: 2-5 per day in active markets
- **Whale Wallets Discovered**: 3-10 in first week
- **Cascade Efficiency**: 60-80% of signals from priority 1-2 strategies
- **Uptime**: 99.9% with graceful degradation
- **Data Source Health**: Multiple sources green

---

## 🤝 Contributing

The autonomous system is designed to be extended:

1. Add new strategies to `core/sports_strategies.py`
2. They automatically integrate into cascade engine
3. Adaptive system learns their performance
4. No configuration changes needed!

---

## 📚 API Endpoints

### Get Dynamic Stats
```bash
GET /api/dynamic_stats
```

Returns:
```json
{
  "cascade": {
    "total_scans": 100,
    "signals_found": 45,
    "cascade_enabled": true
  },
  "arbitrage": {
    "opportunities_found_today": 5
  },
  "whale_tracker": {
    "active_whales": 3,
    "discovered_whales": 8
  },
  "adaptive": {
    "emergency_mode": false,
    "strategies_tracked": 9
  },
  "data_sources": {
    "polymarket_gamma": {"status": "healthy"},
    "espn_api": {"status": "healthy"}
  }
}
```

---

## ⚠️ Important Notes

1. **Paper Trading**: System defaults to paper trading mode for safety
2. **API Rate Limits**: Respects rate limits with caching and fallbacks
3. **No Dependencies**: Core features work without external APIs
4. **Backwards Compatible**: Existing configurations still work
5. **Safe Defaults**: All new features have safe, conservative defaults

---

## 🎉 Summary

The bot is now **100% autonomous** with:

- ✅ Zero required configuration
- ✅ Self-healing capabilities
- ✅ Auto-discovery of opportunities
- ✅ Adaptive learning
- ✅ Graceful degradation
- ✅ Never stops trading

**The bot truly works: ALWAYS, EVERYWHERE, WITH ANYTHING!**
