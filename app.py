from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Simulate a database
users = {}
portfolios = {}
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
    
    portfolio = portfolios.get(username, [])
    
    # Update portfolio with live data
    for stock in portfolio:
        current_data = get_stock_data(stock['symbol'])
        if current_data:
            stock['current_price'] = current_data['price']
            stock['value'] = stock['shares'] * stock['current_price']
            stock['profit_loss'] = stock['value'] - (stock['shares'] * stock['purchase_price'])
    
    return render_template('dashboard.html',  # Changed from index.html to dashboard.html
                         balance=users[username]['balance'],
                         portfolio=portfolio,
                         stock_list=stock_list)

@app.route('/search', methods=['POST'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    symbol = request.form['symbol'].upper()
    stock_data = get_stock_data(symbol)
    
    if stock_data:
        return render_template('dashboard.html',  # Changed from index.html to dashboard.html
                             balance=users[session['username']]['balance'],
                             portfolio=portfolios[session['username']],
                             stock_list=stock_list,
                             stock=stock_data)
    
    flash(f"Stock {symbol} not found!")
    return redirect(url_for('home'))

@app.route('/buy', methods=['POST'])
def buy():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    symbol = request.form['symbol']
    shares = int(request.form['shares'])
    
    stock_data = get_stock_data(symbol)
    if not stock_data:
        flash("Could not get stock data!")
        return redirect(url_for('home'))
    
    price = stock_data['price']
    total_cost = shares * price
    
    if total_cost <= users[username]['balance']:
        users[username]['balance'] -= total_cost
        
        portfolio = portfolios[username]
        for stock in portfolio:
            if stock['symbol'] == symbol:
                total_shares = stock['shares'] + shares
                total_cost = (stock['shares'] * stock['purchase_price']) + (shares * price)
                stock['purchase_price'] = total_cost / total_shares
                stock['shares'] = total_shares
                break
        else:
            portfolio.append({
                'symbol': symbol,
                'shares': shares,
                'purchase_price': price
            })
        
        flash(f"Successfully bought {shares} shares of {symbol} at ${price:.2f} per share")
    else:
        flash("Insufficient funds!")
    
    return redirect(url_for('home'))

@app.route('/sell', methods=['POST'])
def sell():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    symbol = request.form['symbol']
    shares_to_sell = int(request.form['shares'])
    
    stock_data = get_stock_data(symbol)
    if not stock_data:
        flash("Could not get stock data!")
        return redirect(url_for('home'))
    
    portfolio = portfolios[username]
    for stock in portfolio:
        if stock['symbol'] == symbol and stock['shares'] >= shares_to_sell:
            stock['shares'] -= shares_to_sell
            current_price = stock_data['price']
            users[username]['balance'] += shares_to_sell * current_price
            
            if stock['shares'] == 0:
                portfolio.remove(stock)
            
            flash(f"Successfully sold {shares_to_sell} shares of {symbol} at ${current_price:.2f} per share")
            break
    else:
        flash("You don't have enough shares to sell!")
    
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        
        flash('Invalid username or password!')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username in users:
            flash('Username already exists!')
            return redirect(url_for('register'))
        
        users[username] = {
            'password': generate_password_hash(password),
            'balance': 10000
        }
        portfolios[username] = []
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
