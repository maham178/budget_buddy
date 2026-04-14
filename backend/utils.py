from datetime import datetime, timedelta

def format_currency(amount: int) -> str:
    """Format amount as currency"""
    return f"₹{amount:,.0f}"

def get_current_month_range():
    """Get start and end dates for current month"""
    today = datetime.now()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month+1, day=1) - timedelta(days=1)
    return start.date(), end.date()