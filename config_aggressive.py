"""
Aggressive Trading Configuration

This configuration transforms the bot from conservative to aggressive,
designed for exponential capital growth through:
- Compounding position sizes (% of equity)
- Pyramiding into winning positions
- Wider stops and delayed trailing stops
- Kelly Criterion optimal sizing
"""

import os


class AggressiveConfig:
    """Aggressive trading configuration for exponential growth."""
    
    # ═══════════════════════════════════════════════════════════════════
    # AGGRESSIVE MODE
    # ═══════════════════════════════════════════════════════════════════
    AGGRESSIVE_MODE = os.getenv('AGGRESSIVE_MODE', 'true').lower() == 'true'
    
    # ═══════════════════════════════════════════════════════════════════
    # POSITION SIZING (% of equity, not fixed $)
    # ═══════════════════════════════════════════════════════════════════
    POSITION_SIZE_PERCENT = float(os.getenv('POSITION_SIZE_PERCENT', '10'))  # 10% of equity per trade
    MAX_POSITION_PERCENT = float(os.getenv('MAX_POSITION_PERCENT', '25'))    # Max 25% in single trade
    MIN_POSITION_USD = float(os.getenv('MIN_POSITION_USD', '10'))            # Minimum trade size
    
    # ═══════════════════════════════════════════════════════════════════
    # KELLY CRITERION SIZING
    # ═══════════════════════════════════════════════════════════════════
    USE_KELLY_SIZING = os.getenv('USE_KELLY_SIZING', 'true').lower() == 'true'
    KELLY_FRACTION = float(os.getenv('KELLY_FRACTION', '0.25'))  # Quarter-Kelly for safety
    
    # ═══════════════════════════════════════════════════════════════════
    # EXITS (More aggressive - let winners run!)
    # ═══════════════════════════════════════════════════════════════════
    TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '50'))      # 50% profit target
    STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '15'))          # Wider stop
    TRAILING_STOP_ACTIVATION = float(os.getenv('TRAILING_STOP_ACTIVATION', '20'))  # Only after 20% profit
    TRAILING_STOP_PERCENT = float(os.getenv('TRAILING_STOP_PERCENT', '15'))  # 15% from high
    MAX_HOLD_MINUTES = int(os.getenv('MAX_HOLD_MINUTES', '240'))            # 4 hours
    
    # ═══════════════════════════════════════════════════════════════════
    # POSITIONS
    # ═══════════════════════════════════════════════════════════════════
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '20'))  # More positions
    MAX_POSITIONS_PER_EVENT = int(os.getenv('MAX_POSITIONS_PER_EVENT', '3'))
    
    # ═══════════════════════════════════════════════════════════════════
    # COMPOUNDING
    # ═══════════════════════════════════════════════════════════════════
    AUTO_COMPOUND = os.getenv('AUTO_COMPOUND', 'true').lower() == 'true'
    COMPOUND_THRESHOLD = float(os.getenv('COMPOUND_THRESHOLD', '1.1'))       # Increase size after 10% gain
    COMPOUND_MULTIPLIER = float(os.getenv('COMPOUND_MULTIPLIER', '1.2'))     # 20% larger positions
    
    # ═══════════════════════════════════════════════════════════════════
    # PYRAMIDING INTO WINNERS
    # ═══════════════════════════════════════════════════════════════════
    PYRAMID_ENABLED = os.getenv('PYRAMID_ENABLED', 'true').lower() == 'true'
    PYRAMID_TRIGGER_PROFIT = float(os.getenv('PYRAMID_TRIGGER_PROFIT', '10'))  # Add when 10% profit
    PYRAMID_SIZE_PERCENT = float(os.getenv('PYRAMID_SIZE_PERCENT', '50'))      # 50% of original size
    MAX_PYRAMID_LEVELS = int(os.getenv('MAX_PYRAMID_LEVELS', '3'))             # Max 3 add-ons
    
    # ═══════════════════════════════════════════════════════════════════
    # ML WHALE COPY TRADING
    # ═══════════════════════════════════════════════════════════════════
    ML_ENABLED = os.getenv('ML_ENABLED', 'true').lower() == 'true'
    ML_MODEL_PATH = os.getenv('ML_MODEL_PATH', 'models/whale_model.pkl')
    ML_MIN_CONFIDENCE = float(os.getenv('ML_MIN_CONFIDENCE', '0.6'))
    ML_AUTO_RETRAIN_SAMPLES = int(os.getenv('ML_AUTO_RETRAIN_SAMPLES', '50'))
    ML_MIN_TRAINING_SAMPLES = int(os.getenv('ML_MIN_TRAINING_SAMPLES', '20'))
    
    # ═══════════════════════════════════════════════════════════════════
    # BLOCKCHAIN MONITORING
    # ═══════════════════════════════════════════════════════════════════
    BLOCKCHAIN_MONITOR_ENABLED = os.getenv('BLOCKCHAIN_MONITOR_ENABLED', 'true').lower() == 'true'
    BLOCKCHAIN_POLL_SECONDS = int(os.getenv('BLOCKCHAIN_POLL_SECONDS', '10'))
    POLYMARKET_CLOB_CONTRACT = os.getenv('POLYMARKET_CLOB_CONTRACT', '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')
    
    # ═══════════════════════════════════════════════════════════════════
    # WHALE COPY EXECUTION
    # ═══════════════════════════════════════════════════════════════════
    WHALE_COPY_SIZE_MULTIPLIER = float(os.getenv('WHALE_COPY_SIZE_MULTIPLIER', '0.5'))  # Copy 50% of whale size
    WHALE_COPY_MIN_ML_CONFIDENCE = float(os.getenv('WHALE_COPY_MIN_ML_CONFIDENCE', '0.6'))
    WHALE_COPY_MAX_POSITION_PERCENT = float(os.getenv('WHALE_COPY_MAX_POSITION_PERCENT', '15'))
    
    # ═══════════════════════════════════════════════════════════════════
    # MULTI-SIGNAL ENGINE
    # ═══════════════════════════════════════════════════════════════════
    MAX_SIGNALS_PER_SCAN = int(os.getenv('MAX_SIGNALS_PER_SCAN', '5'))
    MIN_SIGNAL_CONFIDENCE = float(os.getenv('MIN_SIGNAL_CONFIDENCE', '0.6'))
    
    # ═══════════════════════════════════════════════════════════════════
    # FAVORITE FLIP STRATEGY
    # ═══════════════════════════════════════════════════════════════════
    FAVORITE_FLIP_ENABLED = os.getenv('FAVORITE_FLIP_ENABLED', 'true').lower() == 'true'
    FAVORITE_FLIP_MIN_DROP_PERCENT = float(os.getenv('FAVORITE_FLIP_MIN_DROP_PERCENT', '5'))
    FAVORITE_FLIP_LOOKBACK_MINUTES = int(os.getenv('FAVORITE_FLIP_LOOKBACK_MINUTES', '30'))
    
    # ═══════════════════════════════════════════════════════════════════
    # ODDS AGGREGATOR
    # ═══════════════════════════════════════════════════════════════════
    ODDS_AGGREGATOR_ENABLED = os.getenv('ODDS_AGGREGATOR_ENABLED', 'true').lower() == 'true'
    ODDS_API_SPORTS = ['basketball_nba', 'americanfootball_nfl', 'soccer_epl', 'cricket_test_match']
    ODDS_MIN_EDGE_PERCENT = float(os.getenv('ODDS_MIN_EDGE_PERCENT', '2'))  # 2% edge required
    
    @classmethod
    def print_status(cls):
        """Print aggressive configuration status."""
        print("\n" + "=" * 60)
        print("⚡ AGGRESSIVE MODE - EXPONENTIAL GROWTH CONFIGURATION")
        print("=" * 60)
        print(f"\n📊 Position Sizing:")
        print(f"   • Base size: {cls.POSITION_SIZE_PERCENT}% of equity (compounds!)")
        print(f"   • Max single position: {cls.MAX_POSITION_PERCENT}% of equity")
        print(f"   • Kelly sizing: {'✅ Enabled' if cls.USE_KELLY_SIZING else '⚪ Disabled'}")
        print(f"\n🎯 Exits:")
        print(f"   • Take profit: {cls.TAKE_PROFIT_PERCENT}% (vs 20% conservative)")
        print(f"   • Stop loss: {cls.STOP_LOSS_PERCENT}% (vs 10% conservative)")
        print(f"   • Trailing stop activates at: {cls.TRAILING_STOP_ACTIVATION}% profit")
        print(f"   • Max hold time: {cls.MAX_HOLD_MINUTES} minutes")
        print(f"\n📈 Pyramiding:")
        print(f"   • Enabled: {'✅ Yes' if cls.PYRAMID_ENABLED else '⚪ No'}")
        print(f"   • Trigger: {cls.PYRAMID_TRIGGER_PROFIT}% profit")
        print(f"   • Add size: {cls.PYRAMID_SIZE_PERCENT}% of original")
        print(f"   • Max levels: {cls.MAX_PYRAMID_LEVELS}")
        print(f"\n🤖 ML Whale Copy:")
        print(f"   • Enabled: {'✅ Yes' if cls.ML_ENABLED else '⚪ No'}")
        print(f"   • Min confidence: {cls.ML_MIN_CONFIDENCE}")
        print(f"   • Auto-retrain: Every {cls.ML_AUTO_RETRAIN_SAMPLES} samples")
        print(f"\n⛓️ Blockchain Monitor:")
        print(f"   • Enabled: {'✅ Yes' if cls.BLOCKCHAIN_MONITOR_ENABLED else '⚪ No'}")
        print(f"   • Poll interval: {cls.BLOCKCHAIN_POLL_SECONDS}s")
        print("=" * 60 + "\n")
