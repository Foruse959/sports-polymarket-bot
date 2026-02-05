"""
AI Market Analyzer

Multi-provider AI integration with graceful fallbacks:
1. Ollama (local, free)
2. Groq (cloud, free tier)
3. Simple heuristics (no API needed)

Analyzes markets for:
- Value edge detection
- Mispriced probabilities  
- Sentiment and confidence
"""

import os
import sys
import json
import httpx
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


class AIProvider(Enum):
    """Available AI providers."""
    OLLAMA = 'ollama'
    GROQ = 'groq'
    HEURISTICS = 'heuristics'


@dataclass
class AIAnalysis:
    """Result of AI market analysis."""
    market_id: str
    provider: AIProvider
    confidence: float  # 0-1
    edge_detected: bool
    suggested_direction: str  # 'buy_yes', 'buy_no', 'hold'
    fair_value_estimate: Optional[float]
    rationale: str
    timestamp: datetime


class AIAnalyzer:
    """
    AI-powered market analyzer with multi-provider fallback.
    
    Fallback order:
    1. Ollama (if running locally)
    2. Groq (if API key configured)
    3. Simple heuristics (always available)
    """
    
    def __init__(self):
        self.ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2')
        self.groq_key = Config.GROQ_API_KEY
        
        # Track which providers are available
        self.ollama_available = False
        self.groq_available = bool(self.groq_key)
        
        # Stats
        self.calls_by_provider = {p: 0 for p in AIProvider}
        self.total_analyses = 0
        self.cache = {}  # market_id -> (timestamp, analysis)
        self.cache_ttl_seconds = 300  # 5 minutes
        
        # Check Ollama availability
        self._check_ollama()
    
    def _check_ollama(self) -> None:
        """Check if Ollama is running and accessible."""
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{self.ollama_url}/api/tags")
                self.ollama_available = response.status_code == 200
                if self.ollama_available:
                    print(f"✅ Ollama connected at {self.ollama_url}")
        except Exception:
            self.ollama_available = False
            print(f"⚠️ Ollama not available at {self.ollama_url} - will use fallbacks")
    
    def analyze_market(self, market: Dict) -> Optional[AIAnalysis]:
        """
        Analyze a market with AI.
        
        Tries providers in order until one succeeds.
        """
        market_id = market.get('id', '')
        
        # Check cache
        if market_id in self.cache:
            timestamp, cached = self.cache[market_id]
            age = (datetime.now() - timestamp).seconds
            if age < self.cache_ttl_seconds:
                return cached
        
        analysis = None
        
        # Try Ollama first
        if self.ollama_available:
            analysis = self._analyze_with_ollama(market)
        
        # Fallback to Groq
        if not analysis and self.groq_available:
            analysis = self._analyze_with_groq(market)
        
        # Fallback to heuristics
        if not analysis:
            analysis = self._analyze_with_heuristics(market)
        
        # Cache result
        if analysis and market_id:
            self.cache[market_id] = (datetime.now(), analysis)
        
        self.total_analyses += 1
        return analysis
    
    def _analyze_with_ollama(self, market: Dict) -> Optional[AIAnalysis]:
        """Analyze market using local Ollama."""
        try:
            prompt = self._build_analysis_prompt(market)
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    analysis = self._parse_ai_response(
                        market, 
                        result.get('response', ''),
                        AIProvider.OLLAMA
                    )
                    self.calls_by_provider[AIProvider.OLLAMA] += 1
                    return analysis
                    
        except Exception as e:
            print(f"⚠️ Ollama analysis failed: {e}")
        
        return None
    
    def _analyze_with_groq(self, market: Dict) -> Optional[AIAnalysis]:
        """Analyze market using Groq API."""
        try:
            prompt = self._build_analysis_prompt(market)
            
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": "You are a sports betting market analyst. Respond with JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    analysis = self._parse_ai_response(
                        market,
                        content,
                        AIProvider.GROQ
                    )
                    self.calls_by_provider[AIProvider.GROQ] += 1
                    return analysis
                    
        except Exception as e:
            print(f"⚠️ Groq analysis failed: {e}")
        
        return None
    
    def _analyze_with_heuristics(self, market: Dict) -> AIAnalysis:
        """
        Analyze market using simple heuristics.
        Always works - no API needed!
        """
        market_id = market.get('id', '')
        question = market.get('question', '')
        current_price = market.get('current_price', 0.5)
        
        # Heuristic rules
        edge_detected = False
        direction = 'hold'
        confidence = 0.3
        fair_value = 0.5
        rationale_parts = []
        
        # Rule 1: Extreme prices often mean value
        if current_price >= 0.88:
            # Very high favorite - look for trap
            edge_detected = True
            direction = 'buy_no'
            confidence = 0.55
            fair_value = current_price - 0.05
            rationale_parts.append("High favorite may be overvalued")
        elif current_price <= 0.15:
            # Extreme underdog - potential value
            edge_detected = True
            direction = 'buy_yes'
            confidence = 0.5
            fair_value = current_price + 0.03
            rationale_parts.append("Extreme underdog may have value")
        
        # Rule 2: Check momentum if available
        momentum = market.get('momentum_direction')
        if momentum == 'bullish' and current_price < 0.7:
            edge_detected = True
            direction = 'buy_yes'
            confidence = min(confidence + 0.15, 0.75)
            rationale_parts.append("Bullish momentum detected")
        elif momentum == 'bearish' and current_price > 0.3:
            edge_detected = True
            direction = 'buy_no'
            confidence = min(confidence + 0.15, 0.75)
            rationale_parts.append("Bearish momentum detected")
        
        # Rule 3: Recent price extreme (contrarian)
        extreme = market.get('price_extreme')
        if extreme == 'high' and current_price < 0.85:
            direction = 'buy_no'
            confidence = min(confidence + 0.1, 0.7)
            rationale_parts.append("Price at recent high - potential fade")
        elif extreme == 'low' and current_price > 0.15:
            direction = 'buy_yes'
            confidence = min(confidence + 0.1, 0.7)
            rationale_parts.append("Price at recent low - potential bounce")
        
        # Rule 4: Price change based edge
        price_change = market.get('price_change')
        if price_change and abs(price_change) > 0.03:
            edge_detected = True
            if price_change > 0 and current_price < 0.8:
                # Price went up - momentum buy
                direction = 'buy_yes'
                confidence = min(confidence + 0.1, 0.7)
                rationale_parts.append(f"Sharp upward move (+{price_change*100:.1f}%)")
            elif price_change < 0 and current_price > 0.2:
                # Price went down - fade or momentum
                direction = 'buy_no'
                confidence = min(confidence + 0.1, 0.7)
                rationale_parts.append(f"Sharp downward move ({price_change*100:.1f}%)")
        
        self.calls_by_provider[AIProvider.HEURISTICS] += 1
        
        return AIAnalysis(
            market_id=market_id,
            provider=AIProvider.HEURISTICS,
            confidence=confidence,
            edge_detected=edge_detected,
            suggested_direction=direction,
            fair_value_estimate=fair_value,
            rationale="; ".join(rationale_parts) if rationale_parts else "Standard market conditions",
            timestamp=datetime.now()
        )
    
    def _build_analysis_prompt(self, market: Dict) -> str:
        """Build prompt for AI analysis."""
        question = market.get('question', 'Unknown market')
        price = market.get('current_price', 0.5)
        sport = market.get('sport', 'unknown')
        prev_price = market.get('previous_price')
        momentum = market.get('momentum_direction', 'unknown')
        
        return f"""Analyze this sports betting market for trading opportunities:

MARKET: {question}
SPORT: {sport}
CURRENT PRICE: ${price:.2f} (YES outcome)
PREVIOUS PRICE: ${prev_price:.2f if prev_price else 'N/A'}
MOMENTUM: {momentum}

Respond in JSON format only:
{{
    "edge_detected": true/false,
    "direction": "buy_yes" or "buy_no" or "hold",
    "confidence": 0.0-1.0,
    "fair_value": 0.0-1.0,
    "rationale": "brief reason"
}}

Consider:
1. Is the current price likely mispriced?
2. Is there momentum to exploit?
3. Are the odds fair for this market?
"""
    
    def _parse_ai_response(self, market: Dict, response: str, provider: AIProvider) -> Optional[AIAnalysis]:
        """Parse AI response into AIAnalysis object."""
        try:
            # Try to extract JSON from response
            # Handle responses that might have text before/after JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                return AIAnalysis(
                    market_id=market.get('id', ''),
                    provider=provider,
                    confidence=float(data.get('confidence', 0.5)),
                    edge_detected=bool(data.get('edge_detected', False)),
                    suggested_direction=data.get('direction', 'hold'),
                    fair_value_estimate=float(data.get('fair_value', 0.5)) if data.get('fair_value') else None,
                    rationale=data.get('rationale', 'AI analysis'),
                    timestamp=datetime.now()
                )
        except Exception as e:
            print(f"⚠️ Failed to parse AI response: {e}")
        
        return None
    
    def analyze_markets(self, markets: List[Dict], top_n: int = 10) -> List[AIAnalysis]:
        """
        Analyze multiple markets, return top N with edge detected.
        
        Filters to markets most likely to have value.
        """
        # Pre-filter to interesting markets
        interesting = []
        for m in markets:
            price = m.get('current_price', 0.5)
            # Focus on markets with potential edge
            if price >= 0.85 or price <= 0.18 or m.get('price_change'):
                interesting.append(m)
        
        # Limit analysis to avoid rate limits
        to_analyze = interesting[:min(len(interesting), top_n * 2)]
        
        analyses = []
        for market in to_analyze:
            analysis = self.analyze_market(market)
            if analysis and analysis.edge_detected:
                analyses.append(analysis)
        
        # Sort by confidence
        analyses.sort(key=lambda a: a.confidence, reverse=True)
        return analyses[:top_n]
    
    def get_stats(self) -> Dict:
        """Get analyzer statistics."""
        return {
            'total_analyses': self.total_analyses,
            'calls_by_provider': {p.value: c for p, c in self.calls_by_provider.items()},
            'ollama_available': self.ollama_available,
            'groq_available': self.groq_available,
            'cache_size': len(self.cache)
        }
