"""
FoodWise AI - ML Training Pipeline
Random Forest + XGBoost for food demand prediction and wastage probability
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb
import joblib
import json
import os

OUTPUT_DIR = "models"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── 1. Generate synthetic training dataset ───────────────────────────────────

def generate_dataset(n=15000):
    np.random.seed(42)
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    weathers = ['Sunny','Cloudy','Rainy','Hot','Cold']
    festivals = ['None','None','None','None','None','Diwali','Holi','Eid','Christmas','New Year','Local Holiday']
    categories = ['Rice & Grains','Bread & Roti','Vegetables','Proteins','Desserts','Beverages','Snacks']
    restaurants = ['Hotel Grand','City Mess','Campus Cafe','Office Hub','Resort Dine','Star Canteen']
    meals = ['Breakfast','Lunch','Dinner']

    day_factors   = {'Monday':1.0,'Tuesday':0.95,'Wednesday':1.05,'Thursday':1.0,'Friday':1.35,'Saturday':1.25,'Sunday':0.85}
    weather_factors = {'Sunny':1.0,'Cloudy':0.95,'Rainy':1.30,'Hot':0.90,'Cold':1.10}
    festival_factors = {'None':1.0,'Diwali':1.65,'Holi':1.55,'Eid':1.60,'Christmas':1.50,'New Year':1.70,'Local Holiday':1.30}
    category_base = {'Rice & Grains':300,'Bread & Roti':280,'Vegetables':220,'Proteins':250,'Desserts':120,'Beverages':350,'Snacks':180}
    restaurant_base = {'Hotel Grand':1.25,'City Mess':0.90,'Campus Cafe':1.0,'Office Hub':1.15,'Resort Dine':1.20,'Star Canteen':0.85}
    meal_factors = {'Breakfast':0.75,'Lunch':1.20,'Dinner':1.05}
    waste_base = {'Rice & Grains':0.08,'Bread & Roti':0.10,'Vegetables':0.15,'Proteins':0.07,'Desserts':0.35,'Beverages':0.20,'Snacks':0.22}

    records = []
    for _ in range(n):
        day      = np.random.choice(days)
        weather  = np.random.choice(weathers)
        festival = np.random.choice(festivals, p=[0.72,0.04,0.04,0.04,0.04,0.04,0.04,0.04])
        category = np.random.choice(categories)
        restaurant = np.random.choice(restaurants)
        meal     = np.random.choice(meals)
        prev_sales = np.random.randint(80, 500)
        customers  = int(prev_sales * np.random.uniform(0.8, 1.2))

        base = category_base[category]
        demand = (
            base
            * day_factors[day]
            * weather_factors[weather]
            * festival_factors[festival]
            * restaurant_base[restaurant]
            * meal_factors[meal]
            * (1 + 0.15 * np.random.randn())
            + 0.2 * prev_sales
            + 0.1 * customers
        )
        demand = max(20, int(demand))

        waste_prob = (
            waste_base[category]
            + (0.08 if weather == 'Sunny' else 0.0)
            + (0.12 if festival != 'None' else 0.0)
            + np.random.uniform(-0.05, 0.05)
        )
        waste_prob = float(np.clip(waste_prob, 0.02, 0.65))

        records.append({
            'day': day, 'weather': weather, 'festival': festival,
            'category': category, 'restaurant': restaurant, 'meal': meal,
            'prev_sales': prev_sales, 'customers': customers,
            'demand': demand, 'wastage_prob': waste_prob
        })

    return pd.DataFrame(records)

# ─── 2. Feature engineering ───────────────────────────────────────────────────

def encode_features(df, encoders=None, fit=True):
    cat_cols = ['day','weather','festival','category','restaurant','meal']
    df_enc = df.copy()

    if fit:
        encoders = {}
        for col in cat_cols:
            le = LabelEncoder()
            df_enc[col] = le.fit_transform(df_enc[col].astype(str))
            encoders[col] = le
    else:
        for col in cat_cols:
            le = encoders[col]
            df_enc[col] = le.transform(df_enc[col].astype(str))

    # Derived features
    df_enc['is_weekend']      = df_enc['day'].isin([5, 6]).astype(int) if fit else df_enc['day'].apply(lambda x: 1 if x >= 5 else 0)
    df_enc['is_festival']     = (df_enc['festival'] != 0).astype(int)
    df_enc['demand_per_cust'] = df_enc['prev_sales'] / (df_enc['customers'] + 1)

    return df_enc, encoders

FEATURE_COLS = ['day','weather','festival','category','restaurant','meal',
                'prev_sales','customers','is_weekend','is_festival','demand_per_cust']

# ─── 3. Train demand model ────────────────────────────────────────────────────

def train_demand_model(df_enc):
    X = df_enc[FEATURE_COLS]
    y = df_enc['demand']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf = RandomForestRegressor(n_estimators=200, max_depth=12, min_samples_split=5,
                               n_jobs=-1, random_state=42)
    rf.fit(X_train, y_train)

    xgb_model = xgb.XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05,
                                  subsample=0.8, colsample_bytree=0.8, random_state=42)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    rf_pred  = rf.predict(X_test)
    xgb_pred = xgb_model.predict(X_test)
    ensemble = 0.5 * rf_pred + 0.5 * xgb_pred

    r2  = r2_score(y_test, ensemble)
    mae = mean_absolute_error(y_test, ensemble)
    rmse= np.sqrt(mean_squared_error(y_test, ensemble))
    print(f"[Demand Model] R²={r2:.4f}  MAE={mae:.2f}  RMSE={rmse:.2f}")

    return rf, xgb_model, {'r2': r2, 'mae': mae, 'rmse': rmse}

# ─── 4. Train wastage model ───────────────────────────────────────────────────

def train_wastage_model(df_enc):
    X = df_enc[FEATURE_COLS]
    y = df_enc['wastage_prob']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf_w = RandomForestRegressor(n_estimators=150, max_depth=10, n_jobs=-1, random_state=42)
    rf_w.fit(X_train, y_train)

    r2  = r2_score(y_test, rf_w.predict(X_test))
    mae = mean_absolute_error(y_test, rf_w.predict(X_test))
    print(f"[Wastage Model] R²={r2:.4f}  MAE={mae:.4f}")

    return rf_w, {'r2': r2, 'mae': mae}

# ─── 5. Prediction API function ───────────────────────────────────────────────

def predict(input_dict: dict, models: dict, encoders: dict) -> dict:
    """
    input_dict keys: day, weather, festival, category, restaurant, meal,
                     prev_sales (int), customers (int)
    Returns: demand (int), wastage_prob (float), recommended_qty (int)
    """
    df = pd.DataFrame([input_dict])
    df_enc, _ = encode_features(df, encoders=encoders, fit=False)
    X = df_enc[FEATURE_COLS]

    demand_rf  = models['demand_rf'].predict(X)[0]
    demand_xgb = models['demand_xgb'].predict(X)[0]
    demand     = int(round(0.5 * demand_rf + 0.5 * demand_xgb))

    wastage_prob = float(np.clip(models['wastage_rf'].predict(X)[0], 0, 1))
    recommended  = int(round(demand * (1 - wastage_prob * 0.6)))

    return {
        'demand': demand,
        'wastage_probability': round(wastage_prob * 100, 1),
        'recommended_quantity': recommended,
        'waste_risk': 'High' if wastage_prob > 0.25 else 'Medium' if wastage_prob > 0.12 else 'Low'
    }

# ─── 6. Main ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Generating training dataset...")
    df = generate_dataset(n=15000)
    print(f"Dataset shape: {df.shape}")
    df.to_csv(f"{OUTPUT_DIR}/training_data.csv", index=False)

    print("\nEncoding features...")
    df_enc, encoders = encode_features(df, fit=True)

    print("\nTraining demand model...")
    demand_rf, demand_xgb, demand_metrics = train_demand_model(df_enc)

    print("\nTraining wastage model...")
    wastage_rf, wastage_metrics = train_wastage_model(df_enc)

    models = {'demand_rf': demand_rf, 'demand_xgb': demand_xgb, 'wastage_rf': wastage_rf}

    print("\nSaving models...")
    joblib.dump(demand_rf,  f"{OUTPUT_DIR}/demand_rf.joblib")
    joblib.dump(demand_xgb, f"{OUTPUT_DIR}/demand_xgb.joblib")
    joblib.dump(wastage_rf, f"{OUTPUT_DIR}/wastage_rf.joblib")
    joblib.dump(encoders,   f"{OUTPUT_DIR}/encoders.joblib")

    metrics = {'demand': demand_metrics, 'wastage': wastage_metrics}
    with open(f"{OUTPUT_DIR}/metrics.json", 'w') as f:
        json.dump(metrics, f, indent=2)

    print("\nAll models saved. Testing prediction...")
    test_input = {
        'day': 'Friday', 'weather': 'Rainy', 'festival': 'None',
        'category': 'Rice & Grains', 'restaurant': 'Hotel Grand',
        'meal': 'Lunch', 'prev_sales': 280, 'customers': 350
    }
    result = predict(test_input, models, encoders)
    print(f"Test prediction: {json.dumps(result, indent=2)}")
    print("\nTraining complete!")
