"""
Strategies module for advanced trading strategies.

Includes:
- FavoriteFlipStrategy: Aggressive mode favorite monitoring
- AIValueEdgeStrategy: AI-powered value detection (NEW!)
- MomentumStrategy: Trade sustained price movements (NEW!)
- ContrarianStrategy: Fade extreme moves (NEW!)
"""

from .favorite_flip import FavoriteFlipStrategy
from .ai_value_edge import AIValueEdgeStrategy
from .momentum_strategy import MomentumStrategy
from .contrarian_strategy import ContrarianStrategy

__all__ = [
    'FavoriteFlipStrategy',
    'AIValueEdgeStrategy',
    'MomentumStrategy', 
    'ContrarianStrategy'
]
