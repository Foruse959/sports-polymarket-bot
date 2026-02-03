"""
ML Whale Behavior Learner

Learns from whale trading patterns using machine learning.
Trains two models:
1. Entry Model: Should we copy this whale trade?
2. Outcome Model: Will this trade win?

Features extracted from each whale trade:
- Temporal: hour_of_day, day_of_week, time_to_event
- Market: market_price, spread, liquidity, is_favorite
- Momentum: price_momentum_1h, price_momentum_24h, volume_ratio
- Sentiment: whale_sentiment (aggregated from multiple whales)
- Odds: odds_vs_consensus (if available)
"""

import sys
import os
import pickle
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_aggressive import AggressiveConfig

try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not installed. ML features disabled.")


class WhaleBehaviorModel:
    """
    ML model for learning from whale trading patterns.
    
    Trains two models:
    1. Entry Model: Predicts if we should copy a whale trade (classification)
    2. Outcome Model: Predicts if trade will be profitable (classification)
    """
    
    def __init__(self, model_path: str = None):
        if not SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn required for ML features")
        
        self.model_path = model_path or AggressiveConfig.ML_MODEL_PATH
        
        # Models
        self.entry_model = None  # Should we copy?
        self.outcome_model = None  # Will it win?
        self.scaler = StandardScaler()
        
        # Training data
        self.training_samples = []
        self.feature_names = self._get_feature_names()
        
        # Stats
        self.samples_collected = 0
        self.models_trained_count = 0
        self.last_training_time = None
        
        # Load existing model if available
        self._load_model()
        
        print(f"🤖 ML Whale Behavior Model initialized")
        print(f"   Model path: {self.model_path}")
        print(f"   Features: {len(self.feature_names)}")
        print(f"   Samples collected: {self.samples_collected}")
        if self.entry_model:
            print(f"   ✅ Pre-trained model loaded")
    
    def _get_feature_names(self) -> List[str]:
        """Get list of feature names (12 features)."""
        return [
            'hour_of_day',          # 0-23
            'day_of_week',          # 0-6 (Monday=0)
            'market_price',         # 0-1
            'price_momentum_1h',    # % change in last hour
            'price_momentum_24h',   # % change in last 24h
            'volume_ratio',         # Recent volume vs average
            'time_to_event',        # Hours until event (if known)
            'market_liquidity',     # Total market liquidity
            'spread',               # Bid-ask spread
            'whale_sentiment',      # Net whale sentiment (-1 to 1)
            'is_favorite',          # 1 if favorite, 0 if underdog
            'odds_vs_consensus'     # Polymarket odds vs sportsbook consensus
        ]
    
    def extract_features(self, whale_trade: Dict, market_data: Dict = None) -> np.ndarray:
        """
        Extract 12 features from a whale trade.
        
        Args:
            whale_trade: Dict with whale trade info
            market_data: Optional dict with additional market context
        
        Returns:
            numpy array of 12 features
        """
        market_data = market_data or {}
        
        # Temporal features
        timestamp = whale_trade.get('timestamp', datetime.now())
        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()
        
        # Market features
        market_price = whale_trade.get('price', 0.5)
        
        # Momentum features (from market_data or defaults)
        price_momentum_1h = market_data.get('price_momentum_1h', 0.0)
        price_momentum_24h = market_data.get('price_momentum_24h', 0.0)
        volume_ratio = market_data.get('volume_ratio', 1.0)
        
        # Event features
        time_to_event = market_data.get('time_to_event_hours', 24.0)
        
        # Liquidity features
        market_liquidity = market_data.get('liquidity', 1000.0)
        spread = market_data.get('spread', 0.02)
        
        # Sentiment features
        whale_sentiment = market_data.get('whale_sentiment', 0.0)
        
        # Position features
        is_favorite = 1.0 if market_price > 0.5 else 0.0
        
        # Odds comparison
        odds_vs_consensus = market_data.get('odds_vs_consensus', 0.0)
        
        features = np.array([
            hour_of_day,
            day_of_week,
            market_price,
            price_momentum_1h,
            price_momentum_24h,
            volume_ratio,
            time_to_event,
            market_liquidity,
            spread,
            whale_sentiment,
            is_favorite,
            odds_vs_consensus
        ])
        
        return features
    
    def add_training_sample(
        self,
        whale_trade: Dict,
        market_data: Dict,
        copied: bool,
        outcome: Optional[bool] = None
    ):
        """
        Add a training sample.
        
        Args:
            whale_trade: Whale trade info
            market_data: Market context
            copied: Did we copy this trade?
            outcome: Did the trade win? (None if still open)
        """
        features = self.extract_features(whale_trade, market_data)
        
        sample = {
            'features': features,
            'copied': copied,
            'outcome': outcome,
            'timestamp': datetime.now()
        }
        
        self.training_samples.append(sample)
        self.samples_collected += 1
        
        # Auto-retrain if we have enough new samples
        if self.samples_collected % AggressiveConfig.ML_AUTO_RETRAIN_SAMPLES == 0:
            if self.samples_collected >= AggressiveConfig.ML_MIN_TRAINING_SAMPLES:
                print(f"🤖 Auto-retraining ML model ({self.samples_collected} samples)...")
                self.train()
    
    def train(self) -> Dict:
        """
        Train both entry and outcome models.
        
        Returns:
            Dict with training metrics
        """
        if len(self.training_samples) < AggressiveConfig.ML_MIN_TRAINING_SAMPLES:
            print(f"⚠️ Not enough samples to train ({len(self.training_samples)} < {AggressiveConfig.ML_MIN_TRAINING_SAMPLES})")
            return {}
        
        # Prepare data
        X = np.array([s['features'] for s in self.training_samples])
        y_entry = np.array([s['copied'] for s in self.training_samples])
        
        # For outcome model, only use samples with known outcome
        completed_samples = [s for s in self.training_samples if s['outcome'] is not None]
        
        if len(completed_samples) < 10:
            print("⚠️ Not enough completed trades for outcome model")
            outcome_metrics = {}
        else:
            X_outcome = np.array([s['features'] for s in completed_samples])
            y_outcome = np.array([s['outcome'] for s in completed_samples])
            
            # Train outcome model
            outcome_metrics = self._train_outcome_model(X_outcome, y_outcome)
        
        # Train entry model
        entry_metrics = self._train_entry_model(X, y_entry)
        
        # Save model
        self._save_model()
        
        self.models_trained_count += 1
        self.last_training_time = datetime.now()
        
        print(f"✅ ML models trained successfully")
        print(f"   Entry model accuracy: {entry_metrics.get('accuracy', 0):.1%}")
        if outcome_metrics:
            print(f"   Outcome model accuracy: {outcome_metrics.get('accuracy', 0):.1%}")
        
        return {
            'entry': entry_metrics,
            'outcome': outcome_metrics,
            'samples': len(self.training_samples),
            'completed_samples': len(completed_samples)
        }
    
    def _train_entry_model(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Train the entry model (should we copy?)."""
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        if len(X) > 50:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
        else:
            # Too small for split, use all data
            X_train, X_test = X_scaled, X_scaled
            y_train, y_test = y, y
        
        # Train Gradient Boosting model
        self.entry_model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=3,
            random_state=42
        )
        
        self.entry_model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.entry_model.predict(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0)
        }
        
        return metrics
    
    def _train_outcome_model(self, X: np.ndarray, y: np.ndarray) -> Dict:
        """Train the outcome model (will it win?)."""
        # Note: Scaler was already fitted in _train_entry_model which is always called first
        # So we can safely use transform here
        X_scaled = self.scaler.transform(X)
        
        # Split data
        if len(X) > 50:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
        else:
            X_train, X_test = X_scaled, X_scaled
            y_train, y_test = y, y
        
        # Train Random Forest model
        self.outcome_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        
        self.outcome_model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.outcome_model.predict(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0)
        }
        
        return metrics
    
    def predict_should_copy(
        self,
        whale_trade: Dict,
        market_data: Dict
    ) -> Tuple[bool, float]:
        """
        Predict if we should copy a whale trade.
        
        Args:
            whale_trade: Whale trade info
            market_data: Market context
        
        Returns:
            (should_copy: bool, confidence: float)
        """
        if self.entry_model is None:
            # No model trained yet, use simple heuristic
            return True, 0.5
        
        # Extract features
        features = self.extract_features(whale_trade, market_data)
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        
        # Predict
        prediction = self.entry_model.predict(features_scaled)[0]
        confidence = self.entry_model.predict_proba(features_scaled)[0][1]
        
        should_copy = confidence >= AggressiveConfig.ML_MIN_CONFIDENCE
        
        return should_copy, confidence
    
    def predict_outcome(
        self,
        whale_trade: Dict,
        market_data: Dict
    ) -> Tuple[bool, float]:
        """
        Predict if trade will be profitable.
        
        Args:
            whale_trade: Whale trade info
            market_data: Market context
        
        Returns:
            (will_win: bool, confidence: float)
        """
        if self.outcome_model is None:
            # No model trained yet, use simple heuristic
            return True, 0.5
        
        # Extract features
        features = self.extract_features(whale_trade, market_data)
        features_scaled = self.scaler.transform(features.reshape(1, -1))
        
        # Predict
        prediction = self.outcome_model.predict(features_scaled)[0]
        confidence = self.outcome_model.predict_proba(features_scaled)[0][1]
        
        will_win = prediction == 1
        
        return will_win, confidence
    
    def _save_model(self):
        """Save model to disk."""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            model_data = {
                'entry_model': self.entry_model,
                'outcome_model': self.outcome_model,
                'scaler': self.scaler,
                'training_samples': self.training_samples,
                'samples_collected': self.samples_collected,
                'models_trained_count': self.models_trained_count,
                'last_training_time': self.last_training_time,
                'feature_names': self.feature_names
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            print(f"💾 Model saved to {self.model_path}")
        
        except Exception as e:
            print(f"⚠️ Failed to save model: {e}")
    
    def _load_model(self):
        """Load model from disk."""
        if not os.path.exists(self.model_path):
            return
        
        try:
            with open(self.model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            self.entry_model = model_data.get('entry_model')
            self.outcome_model = model_data.get('outcome_model')
            self.scaler = model_data.get('scaler')
            self.training_samples = model_data.get('training_samples', [])
            self.samples_collected = model_data.get('samples_collected', 0)
            self.models_trained_count = model_data.get('models_trained_count', 0)
            self.last_training_time = model_data.get('last_training_time')
            
            print(f"✅ Loaded model from {self.model_path}")
        
        except Exception as e:
            print(f"⚠️ Failed to load model: {e}")
    
    def get_stats(self) -> Dict:
        """Get model statistics."""
        return {
            'samples_collected': self.samples_collected,
            'models_trained_count': self.models_trained_count,
            'last_training_time': self.last_training_time.isoformat() if self.last_training_time else None,
            'entry_model_trained': self.entry_model is not None,
            'outcome_model_trained': self.outcome_model is not None,
            'feature_count': len(self.feature_names)
        }


if __name__ == "__main__":
    # Test the model
    model = WhaleBehaviorModel()
    
    # Simulate some training data
    print("\nSimulating training data...")
    for i in range(30):
        whale_trade = {
            'price': np.random.uniform(0.3, 0.7),
            'timestamp': datetime.now() - timedelta(hours=i)
        }
        
        market_data = {
            'price_momentum_1h': np.random.uniform(-5, 5),
            'price_momentum_24h': np.random.uniform(-10, 10),
            'volume_ratio': np.random.uniform(0.8, 1.5),
            'liquidity': np.random.uniform(500, 5000),
            'spread': np.random.uniform(0.01, 0.05)
        }
        
        copied = np.random.random() > 0.5
        outcome = np.random.random() > 0.4 if copied else None
        
        model.add_training_sample(whale_trade, market_data, copied, outcome)
    
    print(f"\nStats: {model.get_stats()}")
    
    # Test prediction
    print("\nTesting prediction...")
    test_trade = {
        'price': 0.45,
        'timestamp': datetime.now()
    }
    test_data = {
        'price_momentum_1h': 2.5,
        'liquidity': 2000
    }
    
    should_copy, confidence = model.predict_should_copy(test_trade, test_data)
    print(f"Should copy: {should_copy} (confidence: {confidence:.1%})")
