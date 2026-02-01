"""
Database module for persistent storage of trades, positions, and history.
Uses SQLite for simplicity - can be swapped for PostgreSQL in production.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    """SQLite database for trades, positions, and performance tracking."""
    
    def __init__(self, db_path: str = 'sports_bot.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table - all executed trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                market_question TEXT,
                sport TEXT,
                strategy TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                size_usd REAL NOT NULL,
                pnl REAL,
                pnl_percent REAL,
                status TEXT DEFAULT 'open',
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                exit_reason TEXT,
                metadata TEXT
            )
        ''')
        
        # Positions table - current open positions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                trade_id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                market_question TEXT,
                sport TEXT,
                strategy TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                size_usd REAL NOT NULL,
                unrealized_pnl REAL DEFAULT 0,
                high_water_mark REAL,
                entry_time TEXT NOT NULL,
                last_update TEXT,
                metadata TEXT
            )
        ''')
        
        # Daily stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                starting_balance REAL,
                ending_balance REAL,
                trades_opened INTEGER DEFAULT 0,
                trades_closed INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                gross_pnl REAL DEFAULT 0,
                best_trade REAL DEFAULT 0,
                worst_trade REAL DEFAULT 0
            )
        ''')
        
        # Strategy performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_stats (
                strategy TEXT PRIMARY KEY,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                avg_win REAL DEFAULT 0,
                avg_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                last_updated TEXT
            )
        ''')
        
        # Market price history for momentum/volatility
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                price REAL NOT NULL,
                volume REAL,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    # ═══════════════════════════════════════════════════════════════
    # TRADES
    # ═══════════════════════════════════════════════════════════════
    
    def save_trade(self, trade: Dict[str, Any]) -> bool:
        """Save a new trade to database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO trades (
                    id, market_id, market_question, sport, strategy,
                    direction, entry_price, size_usd, status, entry_time, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
            ''', (
                trade['id'],
                trade['market_id'],
                trade.get('market_question', ''),
                trade.get('sport', 'unknown'),
                trade['strategy'],
                trade['direction'],
                trade['entry_price'],
                trade['size_usd'],
                trade['entry_time'],
                json.dumps(trade.get('metadata', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving trade: {e}")
            return False
        finally:
            conn.close()
    
    def close_trade(self, trade_id: str, exit_price: float, pnl: float, 
                    exit_reason: str) -> bool:
        """Close an existing trade."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Get entry price to calculate percent
            cursor.execute('SELECT entry_price, size_usd FROM trades WHERE id = ?', (trade_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            entry_price, size_usd = row
            pnl_percent = (pnl / size_usd) * 100 if size_usd > 0 else 0
            
            cursor.execute('''
                UPDATE trades SET
                    exit_price = ?,
                    pnl = ?,
                    pnl_percent = ?,
                    status = 'closed',
                    exit_time = ?,
                    exit_reason = ?
                WHERE id = ?
            ''', (exit_price, pnl, pnl_percent, datetime.now().isoformat(), 
                  exit_reason, trade_id))
            
            # Remove from positions
            cursor.execute('DELETE FROM positions WHERE trade_id = ?', (trade_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error closing trade: {e}")
            return False
        finally:
            conn.close()
    
    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trades WHERE status = 'open'")
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades
    
    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade history."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE status = 'closed' 
            ORDER BY exit_time DESC 
            LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades
    
    # ═══════════════════════════════════════════════════════════════
    # POSITIONS
    # ═══════════════════════════════════════════════════════════════
    
    def save_position(self, position: Dict[str, Any]) -> bool:
        """Save or update a position."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO positions (
                    trade_id, market_id, market_question, sport, strategy,
                    direction, entry_price, current_price, size_usd,
                    unrealized_pnl, high_water_mark, entry_time, last_update, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                position['trade_id'],
                position['market_id'],
                position.get('market_question', ''),
                position.get('sport', 'unknown'),
                position['strategy'],
                position['direction'],
                position['entry_price'],
                position.get('current_price', position['entry_price']),
                position['size_usd'],
                position.get('unrealized_pnl', 0),
                position.get('high_water_mark', position['entry_price']),
                position['entry_time'],
                datetime.now().isoformat(),
                json.dumps(position.get('metadata', {}))
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error saving position: {e}")
            return False
        finally:
            conn.close()
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM positions")
        columns = [desc[0] for desc in cursor.description]
        positions = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return positions
    
    def update_position_price(self, trade_id: str, current_price: float, 
                               unrealized_pnl: float) -> bool:
        """Update position with current price."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Get high water mark
            cursor.execute('SELECT high_water_mark, direction FROM positions WHERE trade_id = ?', 
                          (trade_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            high_water_mark, direction = row
            
            # Update high water mark for trailing stop
            if direction == 'BUY' and current_price > high_water_mark:
                high_water_mark = current_price
            elif direction == 'SELL' and current_price < high_water_mark:
                high_water_mark = current_price
            
            cursor.execute('''
                UPDATE positions SET
                    current_price = ?,
                    unrealized_pnl = ?,
                    high_water_mark = ?,
                    last_update = ?
                WHERE trade_id = ?
            ''', (current_price, unrealized_pnl, high_water_mark, 
                  datetime.now().isoformat(), trade_id))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error updating position: {e}")
            return False
        finally:
            conn.close()
    
    def delete_position(self, trade_id: str) -> bool:
        """Delete a position."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM positions WHERE trade_id = ?', (trade_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ Error deleting position: {e}")
            return False
        finally:
            conn.close()
    
    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    def get_daily_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a specific day."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM daily_stats WHERE date = ?", (date,))
        row = cursor.fetchone()
        
        if row:
            columns = [desc[0] for desc in cursor.description]
            stats = dict(zip(columns, row))
        else:
            stats = {
                'date': date,
                'trades_opened': 0,
                'trades_closed': 0,
                'wins': 0,
                'losses': 0,
                'gross_pnl': 0
            }
        
        conn.close()
        return stats
    
    def update_strategy_stats(self, strategy: str, win: bool, pnl: float):
        """Update strategy performance statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM strategy_stats WHERE strategy = ?', (strategy,))
            row = cursor.fetchone()
            
            if row:
                columns = [desc[0] for desc in cursor.description]
                stats = dict(zip(columns, row))
                
                stats['total_trades'] += 1
                stats['total_pnl'] += pnl
                
                if win:
                    stats['wins'] += 1
                    # Update avg win
                    stats['avg_win'] = ((stats['avg_win'] * (stats['wins'] - 1)) + pnl) / stats['wins']
                else:
                    stats['losses'] += 1
                    # Update avg loss
                    if stats['losses'] > 0:
                        stats['avg_loss'] = ((stats['avg_loss'] * (stats['losses'] - 1)) + pnl) / stats['losses']
                
                stats['win_rate'] = stats['wins'] / stats['total_trades'] if stats['total_trades'] > 0 else 0
                
                cursor.execute('''
                    UPDATE strategy_stats SET
                        total_trades = ?, wins = ?, losses = ?,
                        total_pnl = ?, avg_win = ?, avg_loss = ?,
                        win_rate = ?, last_updated = ?
                    WHERE strategy = ?
                ''', (stats['total_trades'], stats['wins'], stats['losses'],
                      stats['total_pnl'], stats['avg_win'], stats['avg_loss'],
                      stats['win_rate'], datetime.now().isoformat(), strategy))
            else:
                # Create new entry
                cursor.execute('''
                    INSERT INTO strategy_stats (
                        strategy, total_trades, wins, losses, total_pnl,
                        avg_win, avg_loss, win_rate, last_updated
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
                ''', (strategy, 1 if win else 0, 0 if win else 1, pnl,
                      pnl if win else 0, pnl if not win else 0,
                      1.0 if win else 0.0, datetime.now().isoformat()))
            
            conn.commit()
        except Exception as e:
            print(f"❌ Error updating strategy stats: {e}")
        finally:
            conn.close()
    
    def get_all_strategy_stats(self) -> List[Dict[str, Any]]:
        """Get performance stats for all strategies."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM strategy_stats ORDER BY total_pnl DESC")
        columns = [desc[0] for desc in cursor.description]
        stats = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return stats
    
    # ═══════════════════════════════════════════════════════════════
    # PRICE HISTORY
    # ═══════════════════════════════════════════════════════════════
    
    def save_price(self, market_id: str, price: float, volume: Optional[float] = None):
        """Save price point for market."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO price_history (market_id, price, volume, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (market_id, price, volume, datetime.now().isoformat()))
            conn.commit()
        except Exception as e:
            print(f"❌ Error saving price: {e}")
        finally:
            conn.close()
    
    def get_price_history(self, market_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent price history for a market."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT price, volume, timestamp FROM price_history
            WHERE market_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (market_id, limit))
        
        history = [{'price': row[0], 'volume': row[1], 'timestamp': row[2]} 
                   for row in cursor.fetchall()]
        
        conn.close()
        return history
