"""
Kelly Criterion Position Sizing

Calculates optimal bet size based on edge and odds.
Uses fractional Kelly (typically 1/4 or 1/2) for safety.

Formula: f* = (bp - q) / b
Where:
- b = odds received (decimal odds - 1)
- p = probability of winning
- q = probability of losing (1 - p)
- f* = fraction of bankroll to bet
"""

from typing import Optional


def kelly_bet_size(
    win_probability: float,
    odds: float,
    bankroll: float,
    fraction: float = 0.25,
    max_bet_percent: float = 0.25
) -> float:
    """
    Calculate optimal bet size using Kelly Criterion.
    
    Args:
        win_probability: Probability of winning (0-1)
        odds: Decimal odds (e.g., 2.0 for even money)
        bankroll: Total bankroll in USD
        fraction: Fraction of Kelly to use (0.25 = quarter-Kelly)
        max_bet_percent: Maximum bet as % of bankroll (safety cap)
    
    Returns:
        Recommended bet size in USD
    
    Example:
        >>> kelly_bet_size(0.6, 2.0, 1000, fraction=0.25)
        50.0  # 5% of bankroll (quarter-Kelly)
    """
    # Validate inputs
    if not 0 < win_probability < 1:
        raise ValueError(f"win_probability must be between 0 and 1, got {win_probability}")
    
    if odds <= 1:
        raise ValueError(f"odds must be > 1, got {odds}")
    
    if bankroll <= 0:
        raise ValueError(f"bankroll must be > 0, got {bankroll}")
    
    if not 0 < fraction <= 1:
        raise ValueError(f"fraction must be between 0 and 1, got {fraction}")
    
    # Calculate Kelly percentage
    b = odds - 1  # Net odds (e.g., 2.0 odds = 1.0 net odds)
    p = win_probability
    q = 1 - p
    
    # Kelly formula: f* = (bp - q) / b
    kelly_percent = (b * p - q) / b
    
    # If Kelly is negative or zero, no bet should be made
    if kelly_percent <= 0:
        return 0.0
    
    # Apply fractional Kelly
    kelly_percent *= fraction
    
    # Cap at max bet percent
    kelly_percent = min(kelly_percent, max_bet_percent)
    
    # Calculate bet size
    bet_size = bankroll * kelly_percent
    
    return bet_size


def kelly_from_price(
    price: float,
    estimated_true_prob: float,
    bankroll: float,
    fraction: float = 0.25,
    max_bet_percent: float = 0.25
) -> float:
    """
    Calculate Kelly bet size from market price and estimated true probability.
    
    Args:
        price: Current market price (0-1, e.g., 0.5 = 50%)
        estimated_true_prob: Your estimated true probability (0-1)
        bankroll: Total bankroll in USD
        fraction: Fraction of Kelly to use
        max_bet_percent: Maximum bet as % of bankroll
    
    Returns:
        Recommended bet size in USD
    
    Example:
        >>> kelly_from_price(0.4, 0.6, 1000, fraction=0.25)
        # Market prices outcome at 40%, you think it's 60%
        # Returns recommended bet size
    """
    # Validate inputs
    if not 0 < price < 1:
        raise ValueError(f"price must be between 0 and 1, got {price}")
    
    if not 0 < estimated_true_prob < 1:
        raise ValueError(f"estimated_true_prob must be between 0 and 1, got {estimated_true_prob}")
    
    # Convert price to decimal odds
    # If buying YES at price p, odds = 1/p
    odds = 1 / price
    
    # Use estimated true probability as win probability
    win_probability = estimated_true_prob
    
    return kelly_bet_size(win_probability, odds, bankroll, fraction, max_bet_percent)


def calculate_edge(price: float, true_prob: float) -> float:
    """
    Calculate edge percentage.
    
    Edge = (True Probability * Odds) - 1
    
    Args:
        price: Market price (0-1)
        true_prob: True probability (0-1)
    
    Returns:
        Edge as decimal (0.1 = 10% edge)
    """
    if not 0 < price < 1 or not 0 < true_prob < 1:
        return 0.0
    
    odds = 1 / price
    edge = (true_prob * odds) - 1
    
    return edge


def optimal_position_size(
    confidence: float,
    market_price: float,
    bankroll: float,
    base_size_percent: float = 0.10,
    use_kelly: bool = True,
    kelly_fraction: float = 0.25,
    max_position_percent: float = 0.25
) -> float:
    """
    Calculate optimal position size combining confidence and Kelly Criterion.
    
    This is the main function to use in the trading system.
    
    Args:
        confidence: Strategy confidence (0-1)
        market_price: Current market price (0-1)
        bankroll: Total bankroll in USD
        base_size_percent: Base position size as % of bankroll (default 10%)
        use_kelly: Whether to use Kelly Criterion adjustment
        kelly_fraction: Fraction of Kelly to use
        max_position_percent: Maximum position as % of bankroll
    
    Returns:
        Position size in USD
    """
    # Start with base size
    base_size = bankroll * base_size_percent
    
    if not use_kelly:
        # Simple confidence scaling
        size = base_size * confidence
    else:
        # Estimate true probability from confidence and market price
        # If confidence is high, assume market is underpricing
        # Simple heuristic: true_prob = price + (confidence - 0.5) * adjustment
        adjustment = 0.3  # Max 30% adjustment from market price
        estimated_true_prob = market_price + (confidence - 0.5) * adjustment
        estimated_true_prob = max(0.51, min(0.95, estimated_true_prob))  # Clamp to reasonable range
        
        # Calculate Kelly size
        try:
            kelly_size = kelly_from_price(
                market_price,
                estimated_true_prob,
                bankroll,
                fraction=kelly_fraction,
                max_bet_percent=max_position_percent
            )
            
            # Blend base size with Kelly size (weighted by confidence)
            size = base_size * (1 - confidence) + kelly_size * confidence
        except (ValueError, ZeroDivisionError):
            # Fall back to base size if Kelly calculation fails
            size = base_size * confidence
    
    # Apply max position cap
    max_size = bankroll * max_position_percent
    size = min(size, max_size)
    
    return size


if __name__ == "__main__":
    # Example usage
    print("Kelly Criterion Position Sizing Examples\n")
    
    bankroll = 1000
    
    # Example 1: Good edge
    print("Example 1: Market price 40%, estimated true prob 60%")
    size = kelly_from_price(0.4, 0.6, bankroll, fraction=0.25)
    print(f"  Recommended bet: ${size:.2f} ({size/bankroll*100:.1f}% of bankroll)\n")
    
    # Example 2: Slight edge
    print("Example 2: Market price 48%, estimated true prob 55%")
    size = kelly_from_price(0.48, 0.55, bankroll, fraction=0.25)
    print(f"  Recommended bet: ${size:.2f} ({size/bankroll*100:.1f}% of bankroll)\n")
    
    # Example 3: No edge
    print("Example 3: Market price 50%, estimated true prob 50%")
    size = kelly_from_price(0.5, 0.5, bankroll, fraction=0.25)
    print(f"  Recommended bet: ${size:.2f} (no edge!)\n")
    
    # Example 4: Using optimal_position_size (main function)
    print("Example 4: Using optimal_position_size with high confidence")
    size = optimal_position_size(
        confidence=0.8,
        market_price=0.45,
        bankroll=bankroll,
        base_size_percent=0.10,
        use_kelly=True
    )
    print(f"  Recommended bet: ${size:.2f} ({size/bankroll*100:.1f}% of bankroll)\n")
