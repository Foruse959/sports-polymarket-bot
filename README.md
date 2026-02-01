# Sports Polymarket Quant Trading Bot

A fully automated, quantitative sports trading system for Polymarket that exploits market inefficiencies—**not** a prediction-based betting system.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment file and configure
cp .env.example .env
# Edit .env with your Telegram credentials

# 3. Run the bot
python app.py
```

Open http://localhost:5000 to view the dashboard.

## Features

### 🎯 8 Quant Trading Strategies

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

### 📊 Live Sports Data
- Football (Soccer) via ESPN
- NBA Basketball via ESPN
- Cricket (T20/ODI) via ESPN
- Tennis via ESPN

### 🛡️ Risk Management
- Position size limits ($50 max default)
- Daily loss kill switch ($100 default)
- Loss streak pause (5 consecutive)
- Max open positions (10 default)

### 📱 Telegram Alerts
- Strategy signals with entry/exit
- Trade notifications with P&L
- Risk warnings
- Periodic summaries

## Configuration

All settings can be configured via environment variables. See `.env.example` for full list.

Key settings:
- `TRADING_MODE`: `paper` or `live`
- `STARTING_BALANCE`: Initial balance for paper trading
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: Your Telegram chat ID

## Project Structure

```
sports-polymarket-bot/
├── app.py                    # Main Flask application
├── config.py                 # Configuration
├── core/
│   ├── sports_strategies.py  # 8 quant strategies
│   └── live_sports_feed.py   # ESPN data integration
├── trading/
│   └── paper_trader.py       # Paper trading engine
├── risk/
│   └── risk_manager.py       # Risk controls
├── alerts/
│   └── telegram_alerts.py    # Telegram notifications
└── data/
    ├── database.py           # SQLite storage
    └── polymarket_client.py  # Polymarket API
```

## Deployment

### Railway
```bash
railway login
railway init
railway up
```

### Docker (Coming Soon)
```bash
docker build -t sports-bot .
docker run -p 5000:5000 --env-file .env sports-bot
```

## License

MIT
