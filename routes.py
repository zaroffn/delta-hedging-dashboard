# routes.py - Flask routes
from flask import render_template, request, jsonify, redirect, url_for
import datetime as dt
from app import OptionData

def configure_routes(app, hedger):
    @app.route('/')
    def index():
        """Render dashboard homepage"""
        summary = hedger.get_summary_data()
        return render_template('index.html', summary=summary)
    
    @app.route('/data')
    def data():
        """Data management page"""
        return render_template('data.html', 
                               options_data=hedger.options_data, 
                               transaction_costs=hedger.transaction_costs)
    
    @app.route('/analysis')
    def analysis():
        """Analysis and charts page"""
        return render_template('analysis.html')
    
    @app.route('/settings')
    def settings():
        """Settings page"""
        return render_template('settings.html', 
                               transaction_costs=hedger.transaction_costs,
                               initial_capital=hedger.initial_capital)
    
    @app.route('/api/summary')
    def api_summary():
        """API endpoint for summary data"""
        return jsonify(hedger.get_summary_data())
    
    @app.route('/api/history')
    def api_history():
        """API endpoint for position history"""
        df = hedger.get_history_as_df()
        if df.empty:
            return jsonify([])
        return jsonify(df.to_dict(orient='records'))
    
    @app.route('/api/transactions')
    def api_transactions():
        """API endpoint for stock transactions"""
        df = hedger.get_transactions_as_df()
        if df.empty:
            return jsonify([])
        return jsonify(df.to_dict(orient='records'))
    
    @app.route('/api/plots')
    def api_plots():
        """API endpoint for plot data"""
        plots = hedger.generate_dashboard_plots()
        if plots is None:
            return jsonify({"status": "error", "message": "Not enough data points for plotting"})
        return jsonify(plots)
    
    @app.route('/api/option-data', methods=['POST'])
    def api_add_option_data():
        """API endpoint to add new option data"""
        try:
            data = request.json
            
            # Convert string dates to date objects
            date = dt.datetime.strptime(data['date'], "%Y-%m-%d").date()
            expiration = dt.datetime.strptime(data['expiration'], "%Y-%m-%d").date()
            
            option_data = OptionData(
                date=date,
                underlying_price=float(data['underlying_price']),
                strike_price=float(data['strike_price']),
                option_price=float(data['option_price']),
                iv=float(data['iv']),
                delta=float(data['delta']),
                expiration=expiration,
                option_type=data['option_type'],
                position_size=int(data['position_size'])
            )
            
            hedger.add_option_data(option_data)
            result = hedger.update_hedge()[2]
            
            return jsonify(result)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error adding data: {str(e)}"})
    
    @app.route('/api/option-data/<int:index>', methods=['PUT'])
    def api_edit_option_data(index):
        """API endpoint to edit option data"""
        try:
            data = request.json
            
            # Convert string dates to date objects
            date = dt.datetime.strptime(data['date'], "%Y-%m-%d").date()
            expiration = dt.datetime.strptime(data['expiration'], "%Y-%m-%d").date()
            
            option_data = OptionData(
                date=date,
                underlying_price=float(data['underlying_price']),
                strike_price=float(data['strike_price']),
                option_price=float(data['option_price']),
                iv=float(data['iv']),
                delta=float(data['delta']),
                expiration=expiration,
                option_type=data['option_type'],
                position_size=int(data['position_size'])
            )
            
            success = hedger.edit_option_data(index, option_data)
            if success:
                hedger.save_data()
                return jsonify({"status": "success", "message": "Data updated successfully"})
            else:
                return jsonify({"status": "error", "message": "Invalid index"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error updating data: {str(e)}"})
    
    @app.route('/api/option-data/<int:index>', methods=['DELETE'])
    def api_delete_option_data(index):
        """API endpoint to delete option data"""
        try:
            if 0 <= index < len(hedger.options_data):
                hedger.options_data.pop(index)
                hedger._recalculate_position_history(0)
                hedger.save_data()
                return jsonify({"status": "success", "message": "Data deleted successfully"})
            else:
                return jsonify({"status": "error", "message": "Invalid index"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error deleting data: {str(e)}"})
    
    @app.route('/api/transaction-costs', methods=['POST'])
    def api_set_transaction_costs():
        """API endpoint to set transaction costs"""
        try:
            data = request.json
            result = hedger.set_transaction_costs(
                fixed=data['fixed'],
                percentage=data['percentage']
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error setting transaction costs: {str(e)}"})
    
    @app.route('/api/initial-capital', methods=['POST'])
    def api_set_initial_capital():
        """API endpoint to set initial capital"""
        try:
            data = request.json
            hedger.initial_capital = float(data['initial_capital'])
            hedger._recalculate_position_history(0)
            hedger.save_data()
            return jsonify({"status": "success", "message": "Initial capital updated"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error setting initial capital: {str(e)}"})

# Additional routes from part 8

# Add these additional route handlers to routes.py

def add_data_routes(app, hedger):
    @app.route('/api/export-data')
    def api_export_data():
        """API endpoint to export all data"""
        data_dict = {
            'options_data': [option.to_dict() for option in hedger.options_data],
            'position_history': hedger.position_history,
            'stock_transactions': hedger.stock_transactions,
            'initial_capital': hedger.initial_capital,
            'current_capital': hedger.current_capital,
            'current_stock_units': hedger.current_stock_units,
            'transaction_costs': hedger.transaction_costs
        }
        return jsonify(data_dict)
    
    @app.route('/api/import-data', methods=['POST'])
    def api_import_data():
        """API endpoint to import data"""
        try:
            data = request.json
            
            # Validate data structure
            required_keys = ['options_data', 'position_history', 'stock_transactions', 
                            'initial_capital', 'current_capital', 'current_stock_units']
            
            for key in required_keys:
                if key not in data:
                    return jsonify({"status": "error", "message": f"Missing required key: {key}"})
            
            # Reset hedger data
            hedger.options_data = []
            hedger.position_history = []
            hedger.stock_transactions = []
            
            # Import options data
            for option_dict in data['options_data']:
                try:
                    hedger.options_data.append(OptionData.from_dict(option_dict))
                except Exception as e:
                    return jsonify({"status": "error", "message": f"Error parsing option data: {str(e)}"})
            
            # Import other data
            hedger.position_history = data['position_history']
            hedger.stock_transactions = data['stock_transactions']
            hedger.initial_capital = data['initial_capital']
            hedger.current_capital = data['current_capital']
            hedger.current_stock_units = data['current_stock_units']
            
            if 'transaction_costs' in data:
                hedger.transaction_costs = data['transaction_costs']
            
            # Save imported data
            hedger.save_data()
            
            return jsonify({"status": "success", "message": "Data imported successfully"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error importing data: {str(e)}"})
    
    @app.route('/api/clear-data', methods=['POST'])
    def api_clear_data():
        """API endpoint to clear all data"""
        try:
            hedger.options_data = []
            hedger.position_history = []
            hedger.stock_transactions = []
            hedger.initial_capital = 100000
            hedger.current_capital = 100000
            hedger.current_stock_units = 0
            hedger.transaction_costs = {'stock_fixed': 0, 'stock_percentage': 0}
            
            hedger.save_data()
            
            return jsonify({"status": "success", "message": "All data cleared successfully"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error clearing data: {str(e)}"})

# Update the configure_routes function to include data routes
def configure_routes(app, hedger):
    # Existing routes...
    
    # Add data management routes
    add_data_routes(app, hedger)

@app.route('/api/stock-position', methods=['POST'])
def api_add_stock_position():
    """API endpoint to add a new direct stock position"""
    try:
        data = request.json
        
        # Convert string date to date object
        date = dt.datetime.strptime(data['date'], "%Y-%m-%d").date()
        
        # Add manual stock position
        result = hedger.add_stock_position(
            date=date,
            price=float(data['price']),
            position_type=data['position_type'],  # 'LONG' or 'SHORT'
            shares=int(data['shares'])
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error adding stock position: {str(e)}"})

# README.md - Setup Instructions
"""
# Delta Hedging Dashboard

An interactive web dashboard for delta hedging your option positions.

## Features

- Input and track option data (price, IV, delta, etc.)
- Calculate required stock position for delta hedging
- Track position history and transaction costs
- Visualize your hedge with interactive charts
- Edit and manage your historical data
- Customize settings for transaction costs

## Installation

### Requirements
- Python 3.7+
- Flask
- Pandas
- Numpy
- Plotly

### Setup

1. Clone the repository:
```
git clone https://github.com/yourusername/delta-hedging-dashboard.git
cd delta-hedging-dashboard
```

2. Create a virtual environment and install dependencies:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
pip install -r requirements.txt
```

3. Run the application:
```
python app.py
```

4. Open your browser and go to `http://127.0.0.1:5000/`

## Deployment

To deploy this dashboard to a server:

### Heroku Deployment
1. Create a Procfile:
```
web: gunicorn app:app
```

2. Add gunicorn to requirements.txt
3. Push to Heroku:
```
heroku create
git push heroku main
```

### Docker Deployment
1. Build the Docker image:
```
docker build -t delta-hedging-dashboard .
```

2. Run the container:
```
docker run -p 5000:5000 delta-hedging-dashboard
```

## Usage

1. **Dashboard**: View key metrics and add new option data
2. **Data Management**: Edit or delete historical data entries
3. **Analysis**: View interactive charts of your hedge performance
4. **Settings**: Configure transaction costs and initial capital

## License

MIT
"""

# requirements.txt
"""
Flask==2.0.1
pandas==1.3.3
numpy==1.21.2
plotly==5.3.1
gunicorn==20.1.0
"""

# Dockerfile
"""
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
"""
