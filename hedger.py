# hedger.py - DeltaHedger class
import pandas as pd
import numpy as np
import json
import os
import datetime as dt
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Import OptionData class
from app import OptionData

class DeltaHedger:
    def __init__(self, filename):
        self.options_data: List[OptionData] = []
        self.position_history: List[Dict] = []
        self.current_stock_units: float = 0
        self.stock_transactions: List[Dict] = []
        self.initial_capital: Optional[float] = None
        self.current_capital: float = 0
        self.transaction_costs: Dict = {'stock_fixed': 0, 'stock_percentage': 0}
        self.filename = filename
        
        # Load data if exists
        self.load_data()
        
    def add_option_data(self, option_data: OptionData) -> None:
        """Add new option data to the history"""
        self.options_data.append(option_data)
        
    def edit_option_data(self, index: int, option_data: OptionData) -> None:
        """Edit existing option data entry"""
        if 0 <= index < len(self.options_data):
            self.options_data[index] = option_data
            # Recalculate all position history after this point
            self._recalculate_position_history(index)
            return True
        return False
            
    def _recalculate_position_history(self, start_index: int) -> None:
        """Recalculate position history after editing an entry"""
        # Clear position history from this point forward
        self.position_history = self.position_history[:start_index]
        
        # Reset to the state at start_index
        if start_index > 0:
            prev_position = self.position_history[start_index-1]
            self.current_stock_units = prev_position['stock_position']
            self.current_capital = prev_position['capital']
        else:
            # If editing the first entry, use initial values
            latest = self.options_data[0]
            self.current_stock_units = self.calculate_hedge_units(latest.delta, latest.position_size)
            if self.initial_capital is None:
                self.initial_capital = 100000  # Default value
            self.current_capital = self.initial_capital - (self.current_stock_units * latest.underlying_price)
                
        # Recalculate each position from start_index onward
        for i in range(start_index, len(self.options_data)):
            option_data = self.options_data[i]
            new_hedge_units = self.calculate_hedge_units(option_data.delta, option_data.position_size)
            
            # Calculate adjustment needed
            adjustment = new_hedge_units - self.current_stock_units
            
            if abs(adjustment) > 0.01:  # Only adjust if meaningful change
                # Update capital and position
                transaction_cost = self._calculate_transaction_cost(adjustment, option_data.underlying_price)
                self.current_capital -= (adjustment * option_data.underlying_price + transaction_cost)
                self.current_stock_units = new_hedge_units
                
                if i > 0:  # Skip recording transaction for initial position
                    action = "BUY" if adjustment > 0 else "SELL"
                    self.stock_transactions.append({
                        'date': option_data.date.isoformat(),
                        'shares': abs(adjustment),
                        'price': option_data.underlying_price,
                        'action': action,
                        'cost': abs(adjustment) * option_data.underlying_price,
                        'transaction_fee': transaction_cost
                    })
            
            # Record the position
            self.position_history.append({
                'date': option_data.date.isoformat(),
                'underlying_price': option_data.underlying_price,
                'iv': option_data.iv,
                'delta': option_data.delta,
                'stock_position': self.current_stock_units,
                'capital': self.current_capital
            })
            
    def _calculate_transaction_cost(self, shares: float, price: float) -> float:
        """Calculate transaction cost based on settings"""
        volume = abs(shares) * price
        return self.transaction_costs['stock_fixed'] + (volume * self.transaction_costs['stock_percentage'])
            
    def update_hedge(self) -> Tuple[float, float, Dict]:
        """Update hedge based on latest option data"""
        if not self.options_data:
            return 0, 0, {"status": "error", "message": "No option data available"}
            
        latest = self.options_data[-1]
        
        # For the first entry, set initial position if not already set
        if len(self.position_history) == 0:
            self.current_stock_units = self.calculate_hedge_units(latest.delta, latest.position_size)
            
            if self.initial_capital is None:
                self.initial_capital = 100000  # Default starting capital
                
            self.current_capital = self.initial_capital - (self.current_stock_units * latest.underlying_price)
            
            result = {
                "status": "success",
                "message": f"Initial hedge: {'BUY' if self.current_stock_units > 0 else 'SELL'} {abs(self.current_stock_units):.2f} shares",
                "action": "BUY" if self.current_stock_units > 0 else "SELL",
                "shares": abs(self.current_stock_units),
                "price": latest.underlying_price
            }
        else:
            # Calculate hedge adjustment
            new_hedge_units = self.calculate_hedge_units(latest.delta, latest.position_size)
            
            # Calculate adjustment needed
            adjustment = new_hedge_units - self.current_stock_units
            
            if abs(adjustment) > 0.01:  # Only adjust if meaningful change
                action = "BUY" if adjustment > 0 else "SELL"
                
                # Calculate transaction cost
                transaction_cost = self._calculate_transaction_cost(adjustment, latest.underlying_price)
                
                # Update capital and position
                self.current_capital -= (adjustment * latest.underlying_price + transaction_cost)
                self.current_stock_units = new_hedge_units
                
                self.stock_transactions.append({
                    'date': latest.date.isoformat(),
                    'shares': abs(adjustment),
                    'price': latest.underlying_price,
                    'action': action,
                    'cost': abs(adjustment) * latest.underlying_price,
                    'transaction_fee': transaction_cost
                })
                
                result = {
                    "status": "success",
                    "message": f"Hedge adjustment: {action} {abs(adjustment):.2f} shares at ${latest.underlying_price:.2f}",
                    "action": action,
                    "shares": abs(adjustment),
                    "price": latest.underlying_price,
                    "fee": transaction_cost
                }
            else:
                result = {
                    "status": "success", 
                    "message": "No significant hedge adjustment needed",
                    "action": "NONE",
                    "shares": 0
                }
                
        self.position_history.append({
            'date': latest.date.isoformat(),
            'underlying_price': latest.underlying_price,
            'iv': latest.iv,
            'delta': latest.delta,
            'stock_position': self.current_stock_units,
            'capital': self.current_capital
        })
        
        # Save data after update
        self.save_data()
        
        return self.current_stock_units, adjustment if len(self.options_data) > 1 else self.current_stock_units, result
            
    @staticmethod
    def calculate_hedge_units(delta: float, num_options: int) -> float:
        """Calculate required stock units for delta hedging"""
        # Each option contract typically represents 100 shares
        # For a long option position, we need to take the opposite position in stock
        return -delta * num_options * 100
    
    def get_history_as_df(self):
        """Return position history as DataFrame"""
        if not self.position_history:
            return pd.DataFrame()
            
        df = pd.DataFrame(self.position_history)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    def get_transactions_as_df(self):
        """Return stock transactions as DataFrame"""
        if not self.stock_transactions:
            return pd.DataFrame()
            
        df = pd.DataFrame(self.stock_transactions)
        df['date'] = pd.to_datetime(df['date'])
        return df
    
    def get_summary_data(self):
        """Get summary statistics for the dashboard"""
        if not self.position_history:
            return {
                "current_stock": 0,
                "current_capital": 0,
                "total_trades": 0,
                "pnl": 0,
                "pnl_percent": 0,
                "current_price": 0,
                "latest_date": "N/A"
            }
            
        latest = self.position_history[-1]
        initial = self.position_history[0]
        
        # Calculate P&L
        stock_pl = self.current_stock_units * (latest['underlying_price'] - initial['underlying_price'])
        capital_change = latest['capital'] - self.initial_capital if self.initial_capital else 0
        
        return {
            "current_stock": self.current_stock_units,
            "current_capital": self.current_capital,
            "total_trades": len(self.stock_transactions),
            "pnl": capital_change,
            "pnl_percent": (capital_change / self.initial_capital * 100) if self.initial_capital else 0,
            "current_price": latest['underlying_price'],
            "latest_date": latest['date']
        }
    
    def generate_dashboard_plots(self):
        """Generate JSON-serializable plot data for the dashboard"""
        if len(self.position_history) < 2:
            return None
            
        df = self.get_history_as_df()
        
        # Create figures
        fig_price = go.Figure()
        fig_price.add_trace(go.Scatter(
            x=df['date'], 
            y=df['underlying_price'], 
            mode='lines+markers',
            name='Stock Price',
            line=dict(color='rgb(49, 130, 189)', width=2)
        ))
        fig_price.update_layout(
            title='Underlying Stock Price',
            xaxis_title='Date',
            yaxis_title='Price ($)',
            template='plotly_white',
            height=300,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # IV Chart
        fig_iv = go.Figure()
        fig_iv.add_trace(go.Scatter(
            x=df['date'], 
            y=df['iv'], 
            mode='lines+markers',
            name='IV',
            line=dict(color='rgb(214, 39, 40)', width=2)
        ))
        fig_iv.update_layout(
            title='Implied Volatility',
            xaxis_title='Date',
            yaxis_title='IV',
            template='plotly_white',
            height=300,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # Delta Chart
        fig_delta = go.Figure()
        fig_delta.add_trace(go.Scatter(
            x=df['date'], 
            y=df['delta'], 
            mode='lines+markers',
            name='Delta',
            line=dict(color='rgb(44, 160, 44)', width=2)
        ))
        fig_delta.update_layout(
            title='Option Delta',
            xaxis_title='Date',
            yaxis_title='Delta',
            template='plotly_white',
            height=300,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # Position Chart
        fig_position = go.Figure()
        fig_position.add_trace(go.Scatter(
            x=df['date'], 
            y=df['stock_position'], 
            mode='lines+markers',
            name='Stock Position',
            line=dict(color='rgb(148, 103, 189)', width=2)
        ))
        fig_position.update_layout(
            title='Hedge Position (Stock Units)',
            xaxis_title='Date',
            yaxis_title='Shares',
            template='plotly_white',
            height=300,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # Capital Chart
        fig_capital = go.Figure()
        fig_capital.add_trace(go.Scatter(
            x=df['date'], 
            y=df['capital'], 
            mode='lines+markers',
            name='Capital',
            line=dict(color='rgb(140, 86, 75)', width=2)
        ))
        fig_capital.update_layout(
            title='Available Capital',
            xaxis_title='Date',
            yaxis_title='Capital ($)',
            template='plotly_white',
            height=300,
            margin=dict(l=10, r=10, t=40, b=10)
        )
        
        # Convert to JSON
        return {
            'price': fig_price.to_json(),
            'iv': fig_iv.to_json(),
            'delta': fig_delta.to_json(),
            'position': fig_position.to_json(),
            'capital': fig_capital.to_json()
        }
        
    def save_data(self) -> None:
        """Save all data to a JSON file"""
        data_dict = {
            'options_data': [option.to_dict() for option in self.options_data],
            'position_history': self.position_history,
            'stock_transactions': self.stock_transactions,
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'current_stock_units': self.current_stock_units,
            'transaction_costs': self.transaction_costs
        }
        
        try:
            with open(self.filename, 'w') as f:
                json.dump(data_dict, f, indent=2)
            return {"status": "success", "message": f"Data saved successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Error saving data: {str(e)}"}
            
    def load_data(self) -> Dict:
        """Load data from a JSON file"""
        if not os.path.exists(self.filename):
            return {"status": "info", "message": "No saved data found."}
            
        try:
            with open(self.filename, 'r') as f:
                data_dict = json.load(f)
                
            # Restore options data
            self.options_data = [OptionData.from_dict(data) for data in data_dict.get('options_data', [])]
            
            # Restore other data
            self.position_history = data_dict.get('position_history', [])
            self.stock_transactions = data_dict.get('stock_transactions', [])
            self.initial_capital = data_dict.get('initial_capital')
            self.current_capital = data_dict.get('current_capital', 0)
            self.current_stock_units = data_dict.get('current_stock_units', 0)
            self.transaction_costs = data_dict.get('transaction_costs', {'stock_fixed': 0, 'stock_percentage': 0})
            
            return {"status": "success", "message": "Data loaded successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Error loading data: {str(e)}"}
    
    def set_transaction_costs(self, fixed: float, percentage: float) -> Dict:
        """Set transaction cost parameters"""
        try:
            self.transaction_costs['stock_fixed'] = float(fixed)
            self.transaction_costs['stock_percentage'] = float(percentage)
            self.save_data()
            return {
                "status": "success",
                "message": "Transaction costs updated",
                "fixed": self.transaction_costs['stock_fixed'],
                "percentage": self.transaction_costs['stock_percentage']
            }
        except ValueError as e:
            return {"status": "error", "message": f"Error: {str(e)}"}
