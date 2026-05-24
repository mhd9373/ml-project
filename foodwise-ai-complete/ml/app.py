"""
FoodWise AI - Flask ML Prediction API
Serves the trained Random Forest + XGBoost models
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import pandas as pd
import json, os, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

FEATURE_COLS = ['day','weather','festival','category','restaurant','meal',
                'prev_sales','customers','is_weekend','is_festival','demand_per_cust']

def load_models():
    base = os.getenv('MODELS_DIR', 'models')
    return {
        'demand_rf':  joblib.load(f'{base}/demand_rf.joblib'),
        'demand_xgb': joblib.load(f'{base}/demand_xgb.joblib'),
        'wastage_rf': joblib.load(f'{base}/wastage_rf.joblib'),
        'encoders':   joblib.load(f'{base}/encoders.joblib'),
    }

try:
    MODELS = load_models()
    logger.info("Models loaded successfully")
except Exception as e:
    logger.warning(f"Could not load models: {e}. Run train_model.py first.")
    MODELS = None

def encode_input(data: dict, encoders: dict) -> pd.DataFrame:
    cat_cols = ['day','weather','festival','category','restaurant','meal']
    df = pd.DataFrame([data])
    for col in cat_cols:
        le = encoders[col]
        df[col] = le.transform(df[col].astype(str))
    df['is_weekend']      = 1 if data['day'] in ['Saturday','Sunday'] else 0
    df['is_festival']     = 0 if data['festival'] == 'None' else 1
    df['demand_per_cust'] = int(data['prev_sales']) / (int(data['customers']) + 1)
    return df[FEATURE_COLS]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'models_loaded': MODELS is not None})

@app.route('/predict', methods=['POST'])
def predict():
    if not MODELS:
        return jsonify({'error': 'Models not loaded. Run train_model.py first.'}), 503
    try:
        body = request.get_json()
        required = ['day','weather','festival','category','restaurant','meal','prev_sales','customers']
        for f in required:
            if f not in body:
                return jsonify({'error': f'Missing field: {f}'}), 400

        X = encode_input(body, MODELS['encoders'])
        d_rf  = float(MODELS['demand_rf'].predict(X)[0])
        d_xgb = float(MODELS['demand_xgb'].predict(X)[0])
        demand     = int(round(0.5 * d_rf + 0.5 * d_xgb))
        wastage    = float(np.clip(MODELS['wastage_rf'].predict(X)[0], 0, 1))
        recommended = int(round(demand * (1 - wastage * 0.6)))

        return jsonify({
            'demand': demand,
            'wastage_probability': round(wastage * 100, 1),
            'recommended_quantity': recommended,
            'waste_risk': 'High' if wastage > 0.25 else 'Medium' if wastage > 0.12 else 'Low',
            'rf_demand': int(round(d_rf)),
            'xgb_demand': int(round(d_xgb)),
        })
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/predict/bulk', methods=['POST'])
def bulk_predict():
    if not MODELS:
        return jsonify({'error': 'Models not loaded'}), 503
    try:
        rows = request.get_json()
        results = []
        for row in rows:
            X = encode_input(row, MODELS['encoders'])
            demand = int(round(0.5 * float(MODELS['demand_rf'].predict(X)[0])
                               + 0.5 * float(MODELS['demand_xgb'].predict(X)[0])))
            wastage = float(np.clip(MODELS['wastage_rf'].predict(X)[0], 0, 1))
            results.append({
                'input': row,
                'demand': demand,
                'wastage_probability': round(wastage * 100, 1),
                'recommended_quantity': int(round(demand * (1 - wastage * 0.6))),
                'waste_risk': 'High' if wastage > 0.25 else 'Medium' if wastage > 0.12 else 'Low',
            })
        return jsonify({'predictions': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/metrics', methods=['GET'])
def metrics():
    try:
        with open('models/metrics.json') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({'error': 'Metrics not found'}), 404

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
