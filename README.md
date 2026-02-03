# Sports Polymarket Quant Trading Bot

A fully automated, quantitative sports trading system for Polymarket with **aggressive AI-powered trading** designed for exponential growth.

## 🚀 What's New: Aggressive Trading Mode

This bot now features two modes:

### 💼 Conservative Mode (Default)
- Fixed position sizing ($50 default)
- Tight stops (10%)
- Single trade per scan
- Traditional paper trading

### ⚡ Aggressive Mode (NEW!)
- **Compounding position sizes** (10% of equity - grows with wins!)
- **Kelly Criterion** optimal bet sizing
- **Pyramiding** into winners (up to 3 add-ons)
- **ML-powered whale copy trading** with blockchain monitoring
- **Multi-signal engine** (execute 5+ trades per scan)
- **Favorite Flip strategy** (buy underdog when favorite drops)
- **Real-time WebSocket** price feeds
- 50% profit targets with delayed trailing stops

**Example Growth with Compounding:**
```
$1,000 → $1,500 → $2,250 → $3,375 → $5,062 → $7,593
5 wins at 50% each = 7.6x return!
```

## Quick Start

```bash
# 1. Install dependencies (now includes ML libraries)
pip install -r requirements.txt

# 2. Copy environment file and configure
cp .env.example .env
# Edit .env - set AGGRESSIVE_MODE=true for exponential growth

# 3. Run the bot
python app.py
```

Open http://localhost:5000 to view the dashboard.

## Features

### 🎯 Trading Strategies

**Original Strategies:**
| Strategy | Sport | Edge Source |
|----------|-------|-------------|
| **Overreaction Fade** | All | Fade 5%+ moves after goals/wickets |
| **Draw Decay** | Football | Time decay on draw probability |
| **Run Reversion** | NBA | Fade 10+ point scoring runs |
| **Wicket Shock** | Cricket | Buy dips after early wickets |
| **Favorite Trap** | All | Sell 90%+ favorites late game |
| **Volatility Scalp** | All | Scalp wide spread moments |
| **Lag Arbitrage** | All | Exploit delayed price updates |
| **Liquidity Provision** | All | Market make during panic |

**NEW Aggressive Strategies:**
| Strategy | Description | Confidence |
|----------|-------------|-----------|
| **Favorite Flip** | Buy underdog when favorite drops 5%+ | 60-90% |
| **Whale Copy** | ML-validated copy of profitable whale trades | 60%+ |
| **Odds Arbitrage** | Compare Polymarket vs sportsbooks | High |

### 🤖 ML Whale Copy Trading

**How it works:**
1. **Blockchain Monitor** detects whale trades (>$500) on Polygon
2. **WhaleTracker** validates wallet profitability (>65% win rate)
3. **ML Model** predicts if we should copy (12 features):
   - Temporal: hour, day, time to event
   - Market: price, liquidity, spread
   - Momentum: 1h/24h price changes, volume
   - Sentiment: whale consensus, odds vs market
4. **Smart Execution** with Kelly sizing and ML confidence
5. **Continuous Learning** from trade outcomes

**ML Models:**
- Entry Model: GradientBoostingClassifier (should we copy?)
- Outcome Model: RandomForestClassifier (will it win?)

### 📊 Live Sports Data
- Football (Soccer) via ESPN
- NBA Basketball via ESPN
- Cricket (T20/ODI) via ESPN
- Tennis via ESPN
- Real-time WebSocket feed from Polymarket

### ⚡ Aggressive Trading Features

**1. Compounding Position Sizing**
- Position size = % of current equity (not fixed $)
- Auto-compounds when equity grows 10%+
- Kelly Criterion for optimal bet sizing

**2. Pyramiding**
- Add to winning positions (up to 3 levels)
- Trigger: +10% profit per level
- Size: 50% of original position per add-on

**3. Multi-Signal Engine**
- Execute multiple trades per scan (5 max)
- Diversification bonus for uncorrelated signals
- Manages exposure by correlation

**4. Delayed Trailing Stops**
- Only activates after 20% profit (vs 0% in conservative)
- Trails by 15% from high water mark
- Lets winners run to 50% targets

### 🛡️ Risk Management

**Conservative Mode:**
- Position size: Fixed $50
- Stop loss: 10%
- Take profit: 20%
- Max positions: 10

**Aggressive Mode:**
- Position size: 10% of equity (compounds!)
- Stop loss: 15% (wider)
- Take profit: 50% (aggressive)
- Max positions: 20
- Trailing stop: Only after 20% profit

### 📱 Telegram Alerts
- Strategy signals with entry/exit
- Trade notifications with P&L
- Whale trade detections
- ML model training updates
- Risk warnings
- Periodic summaries

## Configuration

All settings can be configured via environment variables. See `.env.example` for full list.

### Key Settings:

**Basic:**
- `TRADING_MODE`: `paper` or `live`
- `STARTING_BALANCE`: Initial balance for paper trading
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID

**Aggressive Mode (NEW!):**
- `AGGRESSIVE_MODE`: Set to `true` for exponential growth mode
- `POSITION_SIZE_PERCENT`: Position size as % of equity (default: 10)
- `USE_KELLY_SIZING`: Enable Kelly Criterion (default: true)
- `ML_ENABLED`: Enable ML whale copy trading (default: true)
- `BLOCKCHAIN_MONITOR_ENABLED`: Monitor Polygon blockchain (default: false)
- `FAVORITE_FLIP_ENABLED`: Enable favorite flip strategy (default: true)
- `MAX_SIGNALS_PER_SCAN`: Max trades per scan (default: 5)

## Project Structure

```
sports-polymarket-bot/
├── app.py                         # Main Flask application
├── config.py                      # Configuration
├── config_aggressive.py           # Aggressive mode config (NEW!)
├── core/
│   ├── sports_strategies.py       # 8 quant strategies
│   ├── live_sports_feed.py        # ESPN data integration
│   ├── kelly_criterion.py         # Kelly Criterion sizing (NEW!)
│   ├── blockchain_monitor.py      # Polygon monitoring (NEW!)
│   ├── ml_whale_learner.py        # ML models (NEW!)
│   ├── multi_signal_engine.py     # Multi-signal execution (NEW!)
│   └── strategies/
│       └── favorite_flip.py       # Favorite flip strategy (NEW!)
├── trading/
│   ├── paper_trader.py            # Conservative paper trading
│   ├── aggressive_trader.py       # Aggressive compounding trader (NEW!)
│   └── whale_copy_executor.py     # Whale copy automation (NEW!)
├── risk/
│   └── risk_manager.py            # Risk controls
├── alerts/
│   └── telegram_alerts.py         # Telegram notifications
├── data/
│   ├── database.py                # SQLite storage
│   ├── polymarket_client.py       # Polymarket API
│   ├── websocket_feed.py          # Real-time feed (NEW!)
│   └── odds_aggregator.py         # Multi-sportsbook comparison (NEW!)
└── models/                        # ML model storage (NEW!)
```

## Deployment

### Railway
```bash
railway login
railway init
railway up
```

### Environment Variables
Make sure to set these in Railway/Heroku:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `AGGRESSIVE_MODE=true` (optional)
- `BLOCKCHAIN_MONITOR_ENABLED=false` (requires web3)
- `ODDS_API_KEY` (optional - for odds aggregator)

## Performance Comparison

| Metric | Conservative | Aggressive |
|--------|--------------|-----------|
| Position Size | Fixed $50 | 10% of equity (compounds!) |
| Take Profit | 20% (exits ~1% due to trailing) | 50% with smart trailing |
| Max Positions | 10 | 20 |
| Signals/Scan | 1 best signal | Up to 5 signals |
| Whale Copy | ❌ Tracking only | ✅ ML-validated execution |
| ML Learning | ❌ None | ✅ Continuous improvement |
| Growth Potential | ~1.2x | ~7.6x (5 wins at 50%) |

## Requirements

- Python 3.8+
- Dependencies: Flask, scikit-learn, web3, websockets (see requirements.txt)
- Optional: Telegram bot token, Odds API key, Polygonscan API key

## License

MIT
