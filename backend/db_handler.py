import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseHandler:
    def __init__(self, db_path: str = "data/budget.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"Database initialized at {db_path}")
    
    def _init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount INTEGER NOT NULL,
                category TEXT NOT NULL,
                date DATE NOT NULL,
                description TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Categories table with budgets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                name TEXT PRIMARY KEY,
                monthly_budget INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default categories if empty
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ('groceries', 15000), ('transport', 8000),
                ('utilities', 10000), ('healthcare', 5000),
                ('dining', 6000), ('entertainment', 5000),
                ('shopping', 10000), ('other', 5000)
            ]
            cursor.executemany(
                "INSERT INTO categories (name, monthly_budget) VALUES (?, ?)",
                default_categories
            )
            logger.info("Default categories created")
        
        conn.commit()
        conn.close()
    
    def add_expenses_batch(self, expenses: List[Dict]) -> int:
        """Add multiple expenses to database"""
        if not expenses:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for exp in expenses:
            cursor.execute('''
                INSERT INTO transactions (amount, category, date, description, raw_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                exp['amount'],
                exp['category'],
                exp['date'],
                exp.get('description', ''),
                exp.get('raw_text', '')
            ))
        
        conn.commit()
        count = len(expenses)
        conn.close()
        
        logger.info(f"Added {count} expense(s)")
        return count
    
    def get_monthly_summary(self, year: Optional[int] = None, month: Optional[int] = None) -> pd.DataFrame:
        """Get spending summary by category"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        conn = sqlite3.connect(self.db_path)
        query = f'''
            SELECT 
                t.category,
                SUM(t.amount) as total_spent,
                COUNT(*) as transaction_count,
                c.monthly_budget as budget
            FROM transactions t
            LEFT JOIN categories c ON t.category = c.name
            WHERE strftime('%Y', t.date) = '{year}' 
              AND strftime('%m', t.date) = '{month:02d}'
            GROUP BY t.category
            ORDER BY total_spent DESC
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def check_budget_status(self, category: str) -> Dict:
        """Check if category is over/under budget"""
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total spent
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE category = ? 
              AND strftime('%Y', date) = ? 
              AND strftime('%m', date) = ?
        ''', (category, str(current_year), f"{current_month:02d}"))
        spent = cursor.fetchone()[0]
        
        # Get budget
        cursor.execute("SELECT monthly_budget FROM categories WHERE name = ?", (category,))
        budget_result = cursor.fetchone()
        budget = budget_result[0] if budget_result else 5000
        
        conn.close()
        
        return {
            "category": category,
            "spent": spent,
            "budget": budget,
            "remaining": budget - spent,
            "percentage": (spent / budget * 100) if budget > 0 else 0,
            "is_over": spent > budget
        }
    
    def update_budget(self, category: str, new_budget: int) -> bool:
        """Update budget for a category"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE categories SET monthly_budget = ? WHERE name = ?",
            (new_budget, category)
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        if success:
            logger.info(f"Updated {category} budget to {new_budget}")
        return success
    
    def get_transactions(self, limit: int = 50, category: Optional[str] = None) -> pd.DataFrame:
        """Get recent transactions"""
        conn = sqlite3.connect(self.db_path)
        
        if category:
            query = "SELECT * FROM transactions WHERE category = ? ORDER BY date DESC LIMIT ?"
            df = pd.read_sql_query(query, conn, params=(category, limit))
        else:
            query = "SELECT * FROM transactions ORDER BY date DESC LIMIT ?"
            df = pd.read_sql_query(query, conn, params=(limit,))
        
        conn.close()
        return df
    
    def get_categories(self) -> List[Dict]:
        """Get all categories with budgets"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, monthly_budget FROM categories ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [{"name": row[0], "budget": row[1]} for row in rows]