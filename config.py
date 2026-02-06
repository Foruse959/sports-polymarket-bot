"""
Sports Polymarket Quant Trading Bot - Configuration

All configuration values with environment variable overrides.
"""

import os


class Config:
    """Central configuration for the sports trading bot."""
    
    # ═══════════════════════════════════════════════════════════════════
    # TRADING MODE
    # ═══════════════════════════════════════════════════════════════════
    TRADING_MODE = os.getenv('TRADING_MODE', 'paper')  # 'paper' or 'live'
    
    # ═══════════════════════════════════════════════════════════════════
    # PAPER TRADING
    # ═══════════════════════════════════════════════════════════════════
    STARTING_BALANCE = float(os.getenv('STARTING_BALANCE', '1000'))
    
    # ═══════════════════════════════════════════════════════════════════
    # RISK MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════
    MAX_POSITION_USD = float(os.getenv('MAX_POSITION_USD', '50'))
    MAX_DAILY_LOSS_USD = float(os.getenv('MAX_DAILY_LOSS_USD', '100'))
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '10'))
    MAX_HOURLY_TRADES = int(os.getenv('MAX_HOURLY_TRADES', '20'))
    LOSS_STREAK_PAUSE_LIMIT = int(os.getenv('LOSS_STREAK_PAUSE_LIMIT', '5'))
    MAX_SLIPPAGE_PERCENT = float(os.getenv('MAX_SLIPPAGE_PERCENT', '2.0'))
    MIN_LIQUIDITY_USD = float(os.getenv('MIN_LIQUIDITY_USD', '500'))
    MAX_POSITIONS_PER_EVENT = int(os.getenv('MAX_POSITIONS_PER_EVENT', '2'))
    
    # ═══════════════════════════════════════════════════════════════════
    # STRATEGY TOGGLES
    # ═══════════════════════════════════════════════════════════════════
    OVERREACTION_FADE_ENABLED = os.getenv('OVERREACTION_FADE_ENABLED', 'true').lower() == 'true'
    DRAW_DECAY_ENABLED = os.getenv('DRAW_DECAY_ENABLED', 'true').lower() == 'true'
    RUN_REVERSION_ENABLED = os.getenv('RUN_REVERSION_ENABLED', 'true').lower() == 'true'
    WICKET_SHOCK_ENABLED = os.getenv('WICKET_SHOCK_ENABLED', 'true').lower() == 'true'
    FAVORITE_TRAP_ENABLED = os.getenv('FAVORITE_TRAP_ENABLED', 'true').lower() == 'true'
    VOLATILITY_SCALP_ENABLED = os.getenv('VOLATILITY_SCALP_ENABLED', 'true').lower() == 'true'
    LAG_ARBITRAGE_ENABLED = os.getenv('LAG_ARBITRAGE_ENABLED', 'true').lower() == 'true'
    LIQUIDITY_PROVISION_ENABLED = os.getenv('LIQUIDITY_PROVISION_ENABLED', 'false').lower() == 'true'
    MARKET_ONLY_ENABLED = os.getenv('MARKET_ONLY_ENABLED', 'true').lower() == 'true'  # Enabled by default!
    
    # ═══════════════════════════════════════════════════════════════════
    # SPORT-SPECIFIC PARAMETERS
    # ═══════════════════════════════════════════════════════════════════
    # Football (Soccer)
    FOOTBALL_FADE_THRESHOLD = float(os.getenv('FOOTBALL_FADE_THRESHOLD', '0.05'))  # 5% move
    FOOTBALL_DRAW_DECAY_START_MINUTE = int(os.getenv('FOOTBALL_DRAW_DECAY_START_MINUTE', '70'))
    
    # NBA Basketball
    NBA_RUN_REVERSION_POINTS = int(os.getenv('NBA_RUN_REVERSION_POINTS', '10'))
    NBA_FOUL_TROUBLE_THRESHOLD = int(os.getenv('NBA_FOUL_TROUBLE_THRESHOLD', '4'))
    
    # Cricket
    CRICKET_WICKET_DIP_PERCENT = float(os.getenv('CRICKET_WICKET_DIP_PERCENT', '0.15'))
    CRICKET_POWERPLAY_BOOST = float(os.getenv('CRICKET_POWERPLAY_BOOST', '1.2'))
    
    # Tennis
    TENNIS_SET_FADE_THRESHOLD = float(os.getenv('TENNIS_SET_FADE_THRESHOLD', '0.10'))
    
    # ═══════════════════════════════════════════════════════════════════
    # EXIT PARAMETERS
    # ═══════════════════════════════════════════════════════════════════
    TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '20'))
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '10'))
    TRAILING_STOP_ENABLED = os.getenv('TRAILING_STOP_ENABLED', 'true').lower() == 'true'
    TRAILING_STOP_PERCENT = float(os.getenv('TRAILING_STOP_PERCENT', '8'))
    MAX_HOLD_MINUTES = int(os.getenv('MAX_HOLD_MINUTES', '60'))  # Auto-exit after 1 hour
    
    # ═══════════════════════════════════════════════════════════════════
    # TELEGRAM ALERTS
    # ═══════════════════════════════════════════════════════════════════
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    ALERT_ON_ENTRY = os.getenv('ALERT_ON_ENTRY', 'true').lower() == 'true'
    ALERT_ON_EXIT = os.getenv('ALERT_ON_EXIT', 'true').lower() == 'true'
    ALERT_ON_SIGNAL = os.getenv('ALERT_ON_SIGNAL', 'true').lower() == 'true'
    SUMMARY_INTERVAL_HOURS = int(os.getenv('SUMMARY_INTERVAL_HOURS', '4'))
    
    # ═══════════════════════════════════════════════════════════════════
    # LIVE TRADING (Future)
    # ═══════════════════════════════════════════════════════════════════
    POLYGON_WALLET_PRIVATE_KEY = os.getenv('POLYGON_WALLET_PRIVATE_KEY', '')
    POLYGON_RPC_URL = os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
    
    # ═══════════════════════════════════════════════════════════════════
    # OPTIONAL APIS
    # ═══════════════════════════════════════════════════════════════════
    ODDS_API_KEY = os.getenv('ODDS_API_KEY', '')
    SPORTRADAR_API_KEY = os.getenv('SPORTRADAR_API_KEY', '')
    CRICBUZZ_API_KEY = os.getenv('CRICBUZZ_API_KEY', '')
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')  # FREE! Get key: https://console.groq.com
    FOOTBALL_DATA_API_KEY = os.getenv('FOOTBALL_DATA_API_KEY', '')  # Free: 10 req/min
    POLYGONSCAN_API_KEY = os.getenv('POLYGONSCAN_API_KEY', '')  # Optional
    
    # ═══════════════════════════════════════════════════════════════════
    # DYNAMIC ENGINE SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    CASCADE_ENABLED = os.getenv('CASCADE_ENABLED', 'true').lower() == 'true'
    CASCADE_THRESHOLD_DECAY = float(os.getenv('CASCADE_THRESHOLD_DECAY', '0.8'))  # 20% reduction per retry
    CASCADE_MAX_RETRIES = int(os.getenv('CASCADE_MAX_RETRIES', '3'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ARBITRAGE SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    ARB_ENABLED = os.getenv('ARB_ENABLED', 'true').lower() == 'true'
    ARB_MIN_EDGE_CENTS = float(os.getenv('ARB_MIN_EDGE_CENTS', '1.5'))
    ARB_SCAN_RESOLVED = os.getenv('ARB_SCAN_RESOLVED', 'true').lower() == 'true'
    
    # ═══════════════════════════════════════════════════════════════════
    # WHALE TRACKING (works with zero config!)
    # ═══════════════════════════════════════════════════════════════════
    WHALE_TRACKING_ENABLED = os.getenv('WHALE_TRACKING_ENABLED', 'true').lower() == 'true'
    WHALE_WALLETS = [w.strip() for w in os.getenv('WHALE_WALLETS', '').split(',') if w.strip()]  # Optional!
    WHALE_AUTO_DISCOVER = os.getenv('WHALE_AUTO_DISCOVER', 'true').lower() == 'true'  # Find whales automatically
    WHALE_MIN_TRADE_USD = float(os.getenv('WHALE_MIN_TRADE_USD', '500'))
    WHALE_MIN_WIN_RATE = float(os.getenv('WHALE_MIN_WIN_RATE', '0.65'))
    WHALE_COPY_DELAY_SECONDS = int(os.getenv('WHALE_COPY_DELAY_SECONDS', '30'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ADAPTIVE SYSTEM
    # ═══════════════════════════════════════════════════════════════════
    ADAPTIVE_ENABLED = os.getenv('ADAPTIVE_ENABLED', 'true').lower() == 'true'
    ADAPTIVE_LOOKBACK_TRADES = int(os.getenv('ADAPTIVE_LOOKBACK_TRADES', '50'))
    ADAPTIVE_EMERGENCY_HOURS = int(os.getenv('ADAPTIVE_EMERGENCY_HOURS', '6'))  # Loosen if no trades
    
    # ═══════════════════════════════════════════════════════════════════
    # DATA SOURCES (all optional!)
    # ═══════════════════════════════════════════════════════════════════
    USE_WEBSOCKET = os.getenv('USE_WEBSOCKET', 'true').lower() == 'true'
    WEBSOCKET_FALLBACK_POLL_SECONDS = int(os.getenv('WEBSOCKET_FALLBACK_POLL_SECONDS', '5'))
    
    # ═══════════════════════════════════════════════════════════════════
    # MULTI-SIGNAL ENGINE
    # ═══════════════════════════════════════════════════════════════════
    MIN_SIGNAL_CONFIDENCE = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.5'))  # Relaxed from 0.6

    MAX_SIGNALS_PER_SCAN = int(os.getenv('MAX_SIGNALS_PER_SCAN', '5'))
    MAX_CORRELATED_EXPOSURE_USD = float(os.getenv('MAX_CORRELATED_EXPOSURE_USD', '100'))
    DIVERSIFICATION_BONUS = float(os.getenv('DIVERSIFICATION_BONUS', '0.1'))
    
    # ═══════════════════════════════════════════════════════════════════
    # FREE SPORTS DATA SOURCES
    # ═══════════════════════════════════════════════════════════════════
    # These are FREE and don't need API keys
    ESPN_ENABLED = os.getenv('ESPN_ENABLED', 'true').lower() == 'true'
    FREE_SPORTS_APIS = os.getenv('FREE_SPORTS_APIS', 'true').lower() == 'true'
    
    # ═══════════════════════════════════════════════════════════════════
    # DASHBOARD & DEBUGGING
    # ═══════════════════════════════════════════════════════════════════
    DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5000'))
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    SCAN_INTERVAL_SECONDS = int(os.getenv('SCAN_INTERVAL_SECONDS', '30'))
    
    # ═══════════════════════════════════════════════════════════════════
    # POLYMARKET API
    # ═══════════════════════════════════════════════════════════════════
    POLYMARKET_GAMMA_URL = 'https://gamma-api.polymarket.com'
    POLYMARKET_CLOB_URL = 'https://clob.polymarket.com'
    
    # ═══════════════════════════════════════════════════════════════════
    # SPORTS MARKET SETTINGS
    # ═══════════════════════════════════════════════════════════════════
    INCLUDE_UPCOMING_MARKETS = os.getenv('INCLUDE_UPCOMING_MARKETS', 'true').lower() == 'true'
    UPCOMING_HOURS_AHEAD = int(os.getenv('UPCOMING_HOURS_AHEAD', '24'))
    PRIORITY_SPORTS = [s.strip() for s in os.getenv('PRIORITY_SPORTS', 'cricket,football,nba,nfl,tennis,ufc').split(',')]
    FETCH_FUTURES_MARKETS = os.getenv('FETCH_FUTURES_MARKETS', 'true').lower() == 'true'  # Season-long bets
    
    # ═══════════════════════════════════════════════════════════════════
    # AGGRESSIVE MODE (NEW!)
    # ═══════════════════════════════════════════════════════════════════
    AGGRESSIVE_MODE = os.getenv('AGGRESSIVE_MODE', 'false').lower() == 'true'
    FAVORITE_FLIP_ENABLED = os.getenv('FAVORITE_FLIP_ENABLED', 'false').lower() == 'true'
    POSITION_SIZE_PERCENT = float(os.getenv('POSITION_SIZE_PERCENT', '10'))
    USE_KELLY_SIZING = os.getenv('USE_KELLY_SIZING', 'true').lower() == 'true'
    KELLY_FRACTION = float(os.getenv('KELLY_FRACTION', '0.25'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ML WHALE COPY (NEW!)
    # ═══════════════════════════════════════════════════════════════════
    ML_ENABLED = os.getenv('ML_ENABLED', 'true').lower() == 'true'
    ML_MODEL_PATH = os.getenv('ML_MODEL_PATH', 'models/whale_model.pkl')
    ML_MIN_CONFIDENCE = float(os.getenv('ML_MIN_CONFIDENCE', '0.6'))
    ML_AUTO_RETRAIN_SAMPLES = int(os.getenv('ML_AUTO_RETRAIN_SAMPLES', '50'))
    
    # ═══════════════════════════════════════════════════════════════════
    # BLOCKCHAIN MONITORING (NEW!)
    # ═══════════════════════════════════════════════════════════════════
    BLOCKCHAIN_MONITOR_ENABLED = os.getenv('BLOCKCHAIN_MONITOR_ENABLED', 'false').lower() == 'true'
    BLOCKCHAIN_POLL_SECONDS = int(os.getenv('BLOCKCHAIN_POLL_SECONDS', '10'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ODDS AGGREGATOR (NEW!)
    # ═══════════════════════════════════════════════════════════════════
    ODDS_AGGREGATOR_ENABLED = os.getenv('ODDS_AGGREGATOR_ENABLED', 'false').lower() == 'true'
    ODDS_MIN_EDGE_PERCENT = float(os.getenv('ODDS_MIN_EDGE_PERCENT', '2'))
    
    # ═══════════════════════════════════════════════════════════════════
    # AI ANALYSIS (NEW!) - Uses Ollama (local) or Groq (cloud, free)
    # ═══════════════════════════════════════════════════════════════════
    AI_ANALYSIS_ENABLED = os.getenv('AI_ANALYSIS_ENABLED', 'true').lower() == 'true'
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2')
    AI_FALLBACK_TO_GROQ = os.getenv('AI_FALLBACK_TO_GROQ', 'true').lower() == 'true'
    AI_CACHE_TTL_SECONDS = int(os.getenv('AI_CACHE_TTL_SECONDS', '300'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ALWAYS-ON STRATEGIES (NEW!) - Work without live events
    # ═══════════════════════════════════════════════════════════════════
    AI_VALUE_EDGE_ENABLED = os.getenv('AI_VALUE_EDGE_ENABLED', 'true').lower() == 'true'
    MOMENTUM_STRATEGY_ENABLED = os.getenv('MOMENTUM_STRATEGY_ENABLED', 'true').lower() == 'true'
    CONTRARIAN_STRATEGY_ENABLED = os.getenv('CONTRARIAN_STRATEGY_ENABLED', 'true').lower() == 'true'
    
    # NEW: Over/Under and BTTS strategies
    OVER_UNDER_STRATEGY_ENABLED = os.getenv('OVER_UNDER_STRATEGY_ENABLED', 'true').lower() == 'true'
    BTTS_STRATEGY_ENABLED = os.getenv('BTTS_STRATEGY_ENABLED', 'true').lower() == 'true'
    
    # AI Value Edge thresholds (RELAXED)
    AI_MIN_TRADE_CONFIDENCE = float(os.getenv('AI_MIN_TRADE_CONFIDENCE', '0.5'))  # Was 0.6
    AI_MIN_EDGE_PERCENT = float(os.getenv('AI_MIN_EDGE_PERCENT', '2.5'))  # Was 3
    
    # Momentum thresholds (RELAXED)
    MOMENTUM_MIN_STRENGTH = float(os.getenv('MOMENTUM_MIN_STRENGTH', '0.3'))  # Was 0.5
    
    # Contrarian thresholds (RELAXED for more trades)
    CONTRARIAN_MIN_MOVE = float(os.getenv('CONTRARIAN_MIN_MOVE', '0.02'))  # Was 0.04 (2% instead of 4%)
    
    # Over/Under thresholds
    OVER_UNDER_MIN_CONFIDENCE = float(os.getenv('OVER_UNDER_MIN_CONFIDENCE', '0.55'))
    OVER_UNDER_MIN_EDGE = float(os.getenv('OVER_UNDER_MIN_EDGE', '0.5'))  # 0.5 goals/points
    
    # BTTS thresholds
    BTTS_MIN_CONFIDENCE = float(os.getenv('BTTS_MIN_CONFIDENCE', '0.55'))
    
    # ═══════════════════════════════════════════════════════════════════
    # EMERGENCY TRADE MODE (NEW!) - Triggers when no trades for X hours
    # ═══════════════════════════════════════════════════════════════════
    EMERGENCY_TRADE_MODE_ENABLED = os.getenv('EMERGENCY_TRADE_MODE_ENABLED', 'true').lower() == 'true'
    EMERGENCY_TRADE_HOURS = int(os.getenv('EMERGENCY_TRADE_HOURS', '6'))  # Activate after 6 hours no trades
    EMERGENCY_THRESHOLD_MULTIPLIER = float(os.getenv('EMERGENCY_THRESHOLD_MULTIPLIER', '0.5'))  # Halve thresholds
    
    # ═══════════════════════════════════════════════════════════════════
    # RELAXED THRESHOLDS (for Market Only strategy - more trades!)
    # ═══════════════════════════════════════════════════════════════════
    MARKET_ONLY_FAVORITE_THRESHOLD = float(os.getenv('MARKET_ONLY_FAVORITE_THRESHOLD', '0.80'))  # Was 0.85
    MARKET_ONLY_UNDERDOG_THRESHOLD = float(os.getenv('MARKET_ONLY_UNDERDOG_THRESHOLD', '0.20'))  # Was 0.18
    SPREAD_SCALP_MIN_PERCENT = float(os.getenv('SPREAD_SCALP_MIN_PERCENT', '2.0'))  # Was 2.5

    

    @classmethod
    def is_paper_mode(cls) -> bool:
        """Check if running in paper trading mode."""
        return cls.TRADING_MODE.lower() == 'paper'
    
    @classmethod
    def is_telegram_configured(cls) -> bool:
        """Check if Telegram alerts are configured."""
        return bool(cls.TELEGRAM_BOT_TOKEN and cls.TELEGRAM_CHAT_ID)
    
    @classmethod
    def get_enabled_strategies(cls) -> list:
        """Get list of enabled strategy names."""
        strategies = []
        if cls.OVERREACTION_FADE_ENABLED:
            strategies.append('overreaction_fade')
        if cls.DRAW_DECAY_ENABLED:
            strategies.append('draw_decay')
        if cls.RUN_REVERSION_ENABLED:
            strategies.append('run_reversion')
        if cls.WICKET_SHOCK_ENABLED:
            strategies.append('wicket_shock')
        if cls.FAVORITE_TRAP_ENABLED:
            strategies.append('favorite_trap')
        if cls.VOLATILITY_SCALP_ENABLED:
            strategies.append('volatility_scalp')
        if cls.LAG_ARBITRAGE_ENABLED:
            strategies.append('lag_arbitrage')
        if cls.LIQUIDITY_PROVISION_ENABLED:
            strategies.append('liquidity_provision')
        return strategies
    
    @classmethod
    def print_status(cls):
        """Print configuration status."""
        print("\n" + "=" * 60)
        print("🤖 SPORTS POLYMARKET QUANT BOT - CONFIGURATION")
        print("=" * 60)
        print(f"\n📊 Mode: {'PAPER' if cls.is_paper_mode() else 'LIVE'} TRADING")
        print(f"💰 Starting Balance: ${cls.STARTING_BALANCE:,.2f}")
        print(f"📱 Telegram: {'✅ Configured' if cls.is_telegram_configured() else '⚪ Not configured'}")
        print(f"\n🎯 Enabled Strategies ({len(cls.get_enabled_strategies())}):")
        for s in cls.get_enabled_strategies():
            print(f"   • {s.replace('_', ' ').title()}")
        print(f"\n🛡️ Risk Limits:")
        print(f"   • Max position: ${cls.MAX_POSITION_USD}")
        print(f"   • Max daily loss: ${cls.MAX_DAILY_LOSS_USD}")
        print(f"   • Max open positions: {cls.MAX_OPEN_POSITIONS}")
        print("=" * 60 + "\n")
