# 🌿 FoodWise AI — Smart Food Waste Management System

> AI-powered food demand prediction and waste reduction for restaurants, cafeterias, hotels, and mess systems.

---

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  React Frontend  │────│ Spring Boot API  │────│  Python ML API  │
│  (Vercel)        │    │  (Railway)       │    │  (Railway)      │
└─────────────────┘    └────────┬────────┘    └─────────────────┘
                                │                        │
                       ┌────────▼────────┐    ┌─────────▼───────┐
                       │  PostgreSQL DB   │    │  Trained Models  │
                       │  (Neon)         │    │  RF + XGBoost    │
                       └─────────────────┘    └─────────────────┘
```

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Frontend   | React 18, Vite, Tailwind CSS, Recharts |
| Backend    | Spring Boot 3.3, Java 21, JWT Auth  |
| ML Service | Python 3.11, Flask, RandomForest, XGBoost |
| Database   | PostgreSQL 16 (Neon)                |
| Deploy     | Vercel (FE), Railway (BE + ML)      |
| Container  | Docker + Docker Compose             |

---

## Quick Start (Docker)

```bash
# 1. Clone and enter
git clone https://github.com/yourorg/foodwise-ai
cd foodwise-ai

# 2. Configure environment
cp .env.example .env
# Edit .env with your secrets

# 3. Launch everything
docker-compose -f docker/docker-compose.yml up --build

# Services:
# Frontend  → http://localhost:3000
# Backend   → http://localhost:8080
# ML API    → http://localhost:5001
# DB        → localhost:5432
```

---

## Local Development

### 1. Python ML Service

```bash
cd ml
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Train models (generates models/ directory)
python train_model.py

# Start Flask API
python app.py
# → http://localhost:5001
```

### 2. Spring Boot Backend

```bash
cd backend
# Set environment variables
export DATABASE_URL=jdbc:postgresql://localhost:5432/foodwise
export ML_SERVICE_URL=http://localhost:5001
export JWT_SECRET=your-256-bit-secret-key

mvn spring-boot:run
# → http://localhost:8080
```

### 3. React Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8080/api/v1

npm run dev
# → http://localhost:3000
```

---

## API Reference

### Authentication

```
POST /api/v1/auth/login
Body: { "email": "admin@foodwise.ai", "password": "..." }
Returns: { "token": "eyJ...", "user": {...} }

POST /api/v1/auth/register
Body: { "name", "email", "password", "role", "restaurant" }
```

### Prediction

```
POST /api/v1/predict-demand
Authorization: Bearer <token>
Body:
{
  "day": "Friday",
  "weather": "Rainy",
  "festival": "None",
  "category": "Rice & Grains",
  "restaurant": "Hotel Grand",
  "mealType": "Lunch",
  "previousSales": 280,
  "expectedCustomers": 350
}
Response:
{
  "demand": 342,
  "wastageProbability": 18.5,
  "recommendedQuantity": 312,
  "riskLevel": "Low",
  "savedKg": 7.5,
  "savedCost": 262.5
}

POST /api/v1/predict-demand/bulk
Content-Type: multipart/form-data
file: <CSV file>
```

### Analytics

```
GET /api/v1/analytics?days=30&restaurant=Hotel%20Grand
GET /api/v1/analytics/restaurants?days=30
GET /api/v1/analytics/categories
GET /api/v1/history?page=0&size=20&restaurant=...&riskLevel=High
```

### Export

```
GET /api/v1/export/csv?days=30
GET /api/v1/export/excel?days=30
```

### ML Service (Direct)

```
GET  http://ml-service:5001/health
POST http://ml-service:5001/predict     (single)
POST http://ml-service:5001/predict/bulk (array)
GET  http://ml-service:5001/metrics
```

---

## CSV Upload Format

```csv
day,weather,festival,category,restaurant,meal,prev_sales,customers
Friday,Sunny,None,Rice & Grains,Hotel Grand,Lunch,280,350
Saturday,Rainy,Diwali,Desserts,City Mess,Dinner,150,200
```

---

## Deployment Guide

### Deploy Frontend → Vercel

```bash
cd frontend
npm run build
# Then connect GitHub repo to Vercel
# Set environment variables in Vercel dashboard:
#   VITE_API_URL=https://your-backend.railway.app/api/v1
#   VITE_WS_URL=wss://your-backend.railway.app/ws
```

### Deploy Backend → Railway

1. Create new project on railway.app
2. Connect GitHub repo, set root directory to `backend/`
3. Set environment variables:
   ```
   DATABASE_URL=jdbc:postgresql://neon-host/foodwise
   ML_SERVICE_URL=https://your-ml-service.railway.app
   JWT_SECRET=<256-bit-secret>
   FRONTEND_URL=https://your-app.vercel.app
   ```

### Deploy ML Service → Railway

1. Create service, set root directory to `ml/`
2. Railway auto-detects Python via `requirements.txt`
3. Set start command: `python train_model.py && gunicorn app:app -b 0.0.0.0:5001`
4. Add persistent volume for `models/` directory

### Database → Neon (PostgreSQL)

1. Create project at neon.tech (free tier available)
2. Copy connection string
3. Run `docs/schema.sql` in the Neon SQL editor
4. Set `DATABASE_URL` in Railway backend service

---

## ML Model Details

| Model            | Algorithm         | Target             | R²    | MAE   |
|------------------|-------------------|--------------------|-------|-------|
| Demand predictor | RF + XGBoost (50/50 ensemble) | Portions demanded | ~0.94 | ~12 portions |
| Wastage estimator| Random Forest     | Wastage probability | ~0.89 | ~3%  |

**Features used:**
- Day of week (label-encoded)
- Weather condition
- Festival/holiday flag
- Food category
- Restaurant
- Meal type
- Previous day sales
- Expected customer count
- Derived: is_weekend, is_festival, demand_per_customer

**Model retraining:** Run `python train_model.py` periodically as new actual data accumulates in `food_sales_history` table. Recommended: weekly retrain with fresh data.

---

## Notifications

Real-time WebSocket alerts (STOMP over SockJS) are pushed to `/topic/alerts` when:
- Wastage probability > 25% → **High risk alert**
- Predicted demand < 60% of previous day → **Low demand warning**
- Festival detected the next day → **Festival prep reminder**

Frontend subscribes via:
```javascript
const client = new Client({ brokerURL: 'ws://localhost:8080/ws' });
client.subscribe('/topic/alerts', (msg) => { /* show notification */ });
```

---

## Environment Variables Reference

### Backend (.env)
```
DATABASE_URL=jdbc:postgresql://...
DB_USER=postgres
DB_PASSWORD=...
JWT_SECRET=...
ML_SERVICE_URL=http://localhost:5001
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)
```
VITE_API_URL=http://localhost:8080/api/v1
VITE_WS_URL=ws://localhost:8080/ws
VITE_APP_NAME=FoodWise AI
```

---

## Project Structure

```
foodwise/
├── ml/                        # Python ML service
│   ├── train_model.py         # Training pipeline
│   ├── app.py                 # Flask prediction API
│   ├── requirements.txt
│   └── Dockerfile
├── backend/                   # Spring Boot API
│   ├── src/main/java/com/foodwise/
│   │   ├── controller/        # REST endpoints
│   │   ├── service/           # Business logic
│   │   ├── model/             # JPA entities + DTOs
│   │   ├── repository/        # Spring Data repos
│   │   ├── security/          # JWT filter + config
│   │   └── config/            # Spring config
│   └── pom.xml
├── frontend/                  # React app
│   ├── src/
│   │   ├── pages/             # Dashboard, Predict, Analytics...
│   │   ├── components/        # Reusable UI components
│   │   ├── hooks/             # useAuth, usePrediction...
│   │   └── utils/             # API client, formatters
│   └── package.json
├── docs/
│   └── schema.sql             # PostgreSQL schema
├── docker/
│   └── docker-compose.yml
└── README.md
```

---

## License

MIT © 2026 FoodWise AI
