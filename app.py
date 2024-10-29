from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
from datetime import datetime, timedelta
import operator

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Simulate databases
users = {}
portfolios = {}
competitions = {
    'weekly': {
        'start_date': datetime.now(),
        'end_date': datetime.now() + timedelta(days=7),
        'participants': {},
        'leaderboard': []
    }
}

stock_list = {
    'AAPL': 'Apple Inc.',
    'GOOGL': 'Alphabet Inc.',
    'MSFT': 'Microsoft Corporation',
    'AMZN': 'Amazon.com Inc.',
    'TSLA': 'Tesla Inc.',
    'META': 'Meta Platforms Inc.',
    'NFLX': 'Netflix Inc.',
    'NVDA': 'NVIDIA Corporation'
}

def get_stock_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return {
            'symbol': symbol,
            'name': info.get('longName', stock_list.get(symbol, 'Unknown')),
            'price': info.get('currentPrice', 0),
            'change': info.get('regularMarketChangePercent', 0),
            'volume': info.get('volume', 0),
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('forwardPE', 0),
            'dividend_yield': info.get('dividendYield', 0)
        }
    except:
        return None

def update_competition_standings():
    weekly_comp = competitions['weekly']
    
    # Reset leaderboard
    weekly_comp['leaderboard'] = []
    
    # Calculate total portfolio value for each participant
    for username in users:
        portfolio_value = users[username]['balance']
        
        # Add value of stocks
        for stock in portfolios.get(username, []):
            current_data = get_stock_data(stock['symbol'])
            if current_data:
                portfolio_value += stock['shares'] * current_data['price']
        
        weekly_comp['participants'][username] = portfolio_value
        weekly_comp['leaderboard'].append({
            'username': username,
            'value': portfolio_value
        })
    
    # Sort leaderboard by value
    weekly_comp['leaderboard'].sort(key=operator.itemgetter('value'), reverse=True)
    
    # Check if competition needs to be reset
    if datetime.now() > weekly_comp['end_date']:
        # Archive results and start new competition
        weekly_comp['start_date'] = datetime.now()
        weekly_comp['end_date'] = datetime.now() + timedelta(days=7)
        weekly_comp['participants'] = {}

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    if username not in users:
        users[username] = {
            'balance': 10000,
            'password': 'temporary'
        }
        portfolios[username] = []
    
    # Update competition standings
    update_competition_standings()
    
    portfolio = portfolios.get(username, [])
    
    # Update portfolio with live data
    total_portfolio_value = users[username]['balance']
    for stock in portfolio:
        current_data = get_stock_data(stock['symbol'])
        if current_data:
            stock['current_price'] = current_data['price']
            stock['value'] = stock['shares'] * stock['current_price']
            stock['profit_loss'] = ((stock['current_price'] - stock['purchase_price']) / stock['purchase_price']) * 100
            total_portfolio_value += stock['value']
    
    # Get user's rank in competition
    user_rank = next((index + 1 for (index, d) in enumerate(competitions['weekly']['leaderboard']) 
                     if d['username'] == username), 0)
    
    return render_template('dashboard.html',
                         balance=users[username]['balance'],
                         portfolio=portfolio,
                         stock_list=stock_list,
                         leaderboard=competitions['weekly']['leaderboard'][:5],
                         user_rank=user_rank,
                         total_value=total_portfolio_value,
                         competition_end=competitions['weekly']['end_date'])

# ... (keep your existing routes for login, register, search, buy, sell, logout)

@app.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    update_competition_standings()
    return render_template('leaderboard.html',
                         leaderboard=competitions['weekly']['leaderboard'],
                         end_date=competitions['weekly']['end_date'])

if __name__ == '__main__':
    app.run(debug=True)
