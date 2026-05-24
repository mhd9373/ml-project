-- FoodWise AI - PostgreSQL Database Schema
-- Run on Neon (neon.tech) or any PostgreSQL 14+ instance

-- ─── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,   -- bcrypt hashed
    role        VARCHAR(20)  NOT NULL DEFAULT 'CHEF',  -- ADMIN, MANAGER, CHEF, ANALYST
    restaurant  VARCHAR(100),
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Restaurants ──────────────────────────────────────────────────────────────
CREATE TABLE restaurants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    location    VARCHAR(200),
    type        VARCHAR(50),  -- hotel, mess, cafeteria, canteen
    capacity    INT,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Prediction Records ───────────────────────────────────────────────────────
CREATE TABLE prediction_records (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant          VARCHAR(100) NOT NULL,
    day                 VARCHAR(15)  NOT NULL,
    weather             VARCHAR(20)  NOT NULL,
    festival            VARCHAR(50)  NOT NULL,
    category            VARCHAR(50)  NOT NULL,
    meal_type           VARCHAR(20)  NOT NULL,
    previous_sales      INT          NOT NULL,
    expected_customers  INT          NOT NULL,
    predicted_demand    INT          NOT NULL,
    wastage_probability DECIMAL(5,2) NOT NULL,  -- 0.00 to 100.00 (%)
    recommended_quantity INT         NOT NULL,
    risk_level          VARCHAR(10)  NOT NULL,   -- Low, Medium, High
    actual_demand       INT,          -- filled in later
    actual_wastage_kg   DECIMAL(6,2),
    saved_kg            DECIMAL(6,2),
    saved_cost          DECIMAL(10,2),
    created_by          UUID REFERENCES users(id),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── Historical Food Sales (for model training) ───────────────────────────────
CREATE TABLE food_sales_history (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant  VARCHAR(100) NOT NULL,
    sale_date   DATE         NOT NULL,
    day_of_week VARCHAR(15)  NOT NULL,
    weather     VARCHAR(20),
    festival    VARCHAR(50)  DEFAULT 'None',
    category    VARCHAR(50)  NOT NULL,
    meal_type   VARCHAR(20)  NOT NULL,
    portions_prepared INT    NOT NULL,
    portions_sold     INT    NOT NULL,
    wastage_kg        DECIMAL(6,2),
    customers         INT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── Notifications / Alerts ───────────────────────────────────────────────────
CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant      VARCHAR(100) NOT NULL,
    category        VARCHAR(50),
    alert_type      VARCHAR(30)  NOT NULL,  -- HIGH_WASTAGE, LOW_DEMAND, FESTIVAL_REMINDER
    message         TEXT         NOT NULL,
    wastage_pct     DECIMAL(5,2),
    prediction_id   UUID REFERENCES prediction_records(id),
    acknowledged    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── Notification rules ───────────────────────────────────────────────────────
CREATE TABLE notification_rules (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_name       VARCHAR(100) NOT NULL,
    alert_type      VARCHAR(30)  NOT NULL,
    threshold       DECIMAL(5,2) NOT NULL,
    active          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX idx_pred_restaurant   ON prediction_records(restaurant);
CREATE INDEX idx_pred_created_at   ON prediction_records(created_at DESC);
CREATE INDEX idx_pred_risk         ON prediction_records(risk_level);
CREATE INDEX idx_pred_category     ON prediction_records(category);
CREATE INDEX idx_sales_restaurant  ON food_sales_history(restaurant, sale_date DESC);
CREATE INDEX idx_alerts_restaurant ON alerts(restaurant, created_at DESC);
CREATE INDEX idx_alerts_ack        ON alerts(acknowledged) WHERE acknowledged = FALSE;

-- ─── Seed data ────────────────────────────────────────────────────────────────
INSERT INTO restaurants (name, location, type, capacity) VALUES
    ('Hotel Grand',   'MG Road, Kolhapur',     'hotel',     300),
    ('City Mess',     'Shahupuri, Kolhapur',   'mess',      150),
    ('Campus Café',   'Shivaji University',    'cafeteria', 200),
    ('Office Hub',    'MIDC, Kolhapur',        'canteen',   400),
    ('Resort Dine',   'Rankala Lake, Kolhapur','hotel',     180),
    ('Star Canteen',  'Rajarampuri, Kolhapur', 'canteen',   120);

INSERT INTO notification_rules (rule_name, alert_type, threshold) VALUES
    ('High wastage alert',       'HIGH_WASTAGE',        25.0),
    ('Low demand warning',       'LOW_DEMAND',          40.0),
    ('Festival boost reminder',  'FESTIVAL_REMINDER',    0.0);

INSERT INTO users (name, email, password, role) VALUES
    ('Admin User', 'admin@foodwise.ai', '$2a$10$example_hash', 'ADMIN');

-- ─── View: daily summary ──────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_daily_summary AS
SELECT
    DATE(created_at)               AS prediction_date,
    restaurant,
    COUNT(*)                       AS total_predictions,
    SUM(predicted_demand)          AS total_predicted,
    AVG(wastage_probability)       AS avg_wastage_pct,
    SUM(saved_kg)                  AS total_saved_kg,
    SUM(saved_cost)                AS total_saved_cost,
    COUNT(*) FILTER (WHERE risk_level = 'High') AS high_risk_count
FROM prediction_records
GROUP BY DATE(created_at), restaurant;
