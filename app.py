# app.py - Main Flask application
from flask import Flask, render_template, request, jsonify, redirect, url_for
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'delta-hedging-dashboard-secret-key'

# Data storage path
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'delta_hedge_data.json')

# Make sure data directory exists
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

@dataclass
class OptionData:
    date: dt.date
    underlying_price: float
    strike_price: float
    option_price: float
    iv: float
    delta: float
    expiration: dt.date
    option_type: str  # 'call' or 'put'
    position_size: int  # number of contracts
    
    @property
    def days_to_expiration(self) -> int:
        return (self.expiration - self.date).days
    
    def to_dict(self):
        data = asdict(self)
        data['date'] = self.date.isoformat()
        data['expiration'] = self.expiration.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data):
        # Convert string dates back to date objects
        data['date'] = dt.date.fromisoformat(data['date'])
        data['expiration'] = dt.date.fromisoformat(data['expiration'])
        return cls(**data)

# Routes will be defined after the DeltaHedger class

# Import the rest of the application
from hedger import DeltaHedger
from routes import configure_routes

# Initialize the hedger
hedger = DeltaHedger(DATA_FILE)

# Configure routes
configure_routes(app, hedger)

if __name__ == '__main__':
    app.run(debug=True)
