from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import yfinance as yf
from datetime import datetime, timedelta
import threading
import time
import plotly
import plotly.graph_objs as go
import json
import operator

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Simulate databases
users = {}
portfolios = {}
stock_prices = {}  # Cache for stock prices
price_alerts = {}  # Store price alerts
last_update = {}   # Track last update time
stock_history = {} # Cache for historical data

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

def get_stock_history(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period='1mo')
        return hist
    except:
        return None

def create_stock_chart(symbol):
    if symbol not in stock_history or time.time() - stock_history[symbol]['timestamp'] > 3600:
        hist = get_stock_history(symbol)
        if hist is not None:
            fig = go.Figure(data=[go.Candlestick(x=hist.index,
                                                open=hist['Open'],
                                                high=hist['High'],
                                                low=hist['Low'],
                                                close=hist['Close'])])
            fig.update_layout(title=f'{symbol} Stock Price',
                            yaxis_title='Price',
                            template='plotly_dark')
            
            stock_history[symbol] = {
                'chart': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
                'timestamp': time.time()
            }
    
    return stock_history.get(symbol, {}).get('chart')

def get_stock_data(symbol, force_update=False):
    current_time = time.time()
    
    if (symbol not in last_update or 
        current_time - last_update.get(symbol, 0) > 60 or 
        force_update):
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            new_price = info.get('currentPrice', 0)
            old_price = stock_prices.get(symbol, {}).get('price', new_price)
            price_change = ((new_price - old_price) / old_price * 100) if old_price else 0
            
            stock_prices[symbol] = {
                'symbol': symbol,
                'name': info.get('longName', stock_list.get(symbol, 'Unknown')),
                'price': new_price,
                'old_price': old_price,
                'price_change': price_change,
                'change': info.get('regularMarketChangePercent', 0),
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('forwardPE', 0),
                'timestamp': current_time
            }
            last_update[symbol] = current_time
            
            # Check price alerts
            check_price_alerts(symbol, new_price)
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None
    
    return stock_prices.get(symbol)

def check_price_alerts(symbol, current_price):
    if symbol in price_alerts:
        for username, alerts in price_alerts[symbol].items():
            for alert in alerts:
                if (alert['type'] == 'above' and current_price > alert['price']) or \
                   (alert['type'] == 'below' and current_price < alert['price']):
                    if 'notifications' not in users[username]:
                        users[username]['notifications'] = []
                    users[username]['notifications'].append({
                        'message': f"{symbol} has reached ${current_price:.2f}",
                        'timestamp': datetime.now()
                    })

def update_portfolio_values():
    while True:
        try:
            for username, portfolio in portfolios.items():
                for stock in portfolio:
                    current_data = get_stock_data(stock['symbol'], force_update=True)
                    if current_data:
                        stock['current_price'] = current_data['price']
                        stock['value'] = stock['shares'] * stock['current_price']
                        stock['profit_loss'] = ((stock['current_price'] - stock['purchase_price']) / 
                                              stock['purchase_price']) * 100
                        stock['price_change'] = current_data['price_change']
        except Exception as e:
            print(f"Error in update thread: {e}")
        time.sleep(60)  # Update every minute

# Start the update thread
update_thread = threading.Thread(target=update_portfolio_values, daemon=True)
update_thread.start()

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    if username not in users:
        users[username] = {
            'balance': 10000,
            'password': 'temporary',
            'notifications': []
        }
        portfolios[username] = []
    
    portfolio = portfolios.get(username, [])
    
    # Initial portfolio update
    total_portfolio_value = users[username]['balance']
    for stock in portfolio:
        current_data = get_stock_data(stock['symbol'])
        if current_data:
            stock['current_price'] = current_data['price']
            stock['value'] = stock['shares'] * stock['current_price']
            stock['profit_loss'] = ((stock['current_price'] - stock['purchase_price']) / 
                                  stock['purchase_price']) * 100
            stock['price_change'] = current_data.get('price_change', 0)
            total_portfolio_value += stock['value']
    
    return render_template('dashboard.html',
                         balance=users[username]['balance'],
                         portfolio=portfolio,
                         stock_list=stock_list,
                         total_value=total_portfolio_value)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            return redirect(url_for('home'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            flash('Username already exists')
        else:
            users[username] = {
                'password': generate_password_hash(password),
                'balance': 10000,
                'notifications': []
            }
            session['username'] = username
            portfolios[username] = []
            return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/search', methods=['POST'])
def search():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    symbol = request.form['symbol'].upper()
    stock_data = get_stock_data(symbol)
    
    if stock_data:
        return render_template('dashboard.html',
                             balance=users[session['username']]['balance'],
                             portfolio=portfolios.get(session['username'], []),
                             stock_list=stock_list,
                             stock=stock_data)
    
    flash(f'Could not find stock with symbol {symbol}')
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
        flash('Could not get stock data')
        return redirect(url_for('home'))
    
    total_cost = shares * stock_data['price']
    
    if total_cost > users[username]['balance']:
        flash('Insufficient funds')
        return redirect(url_for('home'))
    
    users[username]['balance'] -= total_cost
    
    # Update portfolio
    portfolio = portfolios.get(username, [])
    for stock in portfolio:
        if stock['symbol'] == symbol:
            # Update existing position
            new_total_shares = stock['shares'] + shares
            new_total_cost = (stock['shares'] * stock['purchase_price']) + total_cost
            stock['shares'] = new_total_shares
            stock['purchase_price'] = new_total_cost / new_total_shares
            break
    else:
        # Add new position
        portfolio.append({
            'symbol': symbol,
            'shares': shares,
            'purchase_price': stock_data['price'],
            'current_price': stock_data['price'],
            'value': total_cost,
            'profit_loss': 0,
            'price_change': 0
        })
    
    portfolios[username] = portfolio
    flash(f'Successfully bought {shares} shares of {symbol}')
    return redirect(url_for('home'))

@app.route('/sell', methods=['POST'])
def sell():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    symbol = request.form['symbol']
    shares_to_sell = int(request.form['shares'])
    
    portfolio = portfolios.get(username, [])
    for stock in portfolio:
        if stock['symbol'] == symbol:
            if shares_to_sell > stock['shares']:
                flash('Not enough shares')
                return redirect(url_for('home'))
            
            stock_data = get_stock_data(symbol)
            if not stock_data:
                flash('Could not get stock data')
                return redirect(url_for('home'))
            
            sale_value = shares_to_sell * stock_data['price']
            users[username]['balance'] += sale_value
            
            if shares_to_sell == stock['shares']:
                portfolio.remove(stock)
            else:
                stock['shares'] -= shares_to_sell
            
            flash(f'Successfully sold {shares_to_sell} shares of {symbol}')
            break
    
    portfolios[username] = portfolio
    return redirect(url_for('home'))

@app.route('/get_updates')
def get_updates():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    username = session['username']
    portfolio = portfolios.get(username, [])
    
    updates = {
        'portfolio': [{
            'symbol': stock['symbol'],
            'current_price': stock['current_price'],
            'value': stock['value'],
            'profit_loss': stock['profit_loss'],
            'price_change': stock['price_change']
        } for stock in portfolio],
        'balance': users[username]['balance'],
        'notifications': users[username].get('notifications', [])
    }
    
    # Clear notifications after sending
    users[username]['notifications'] = []
    
    return jsonify(updates)

@app.route('/set_alert', methods=['POST'])
def set_alert():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    data = request.json
    symbol = data['symbol']
    price = float(data['price'])
    alert_type = data['type']  # 'above' or 'below'
    
    if symbol not in price_alerts:
        price_alerts[symbol] = {}
    
    if session['username'] not in price_alerts[symbol]:
        price_alerts[symbol][session['username']] = []
    
    price_alerts[symbol][session['username']].append({
        'price': price,
        'type': alert_type
    })
    
    return jsonify({'success': True})

@app.route('/get_chart/<symbol>')
def get_chart(symbol):
    chart_json = create_stock_chart(symbol)
    return jsonify(chart_json)

if __name__ == '__main__':
    app.run(debug=True)
