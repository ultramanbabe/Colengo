# Observability Stack with Grafana, Loki, Tempo, and Mock App

## Quick Start

### 1. Start the Stack

```sh
docker-compose up -d
```

### 2. Access Grafana

Open [http://localhost:3000](http://localhost:3000)

- **Username:** `admin`  
- **Password:** `admin`

### 3. Import the Dashboard

1. In Grafana, click **+** (top-left) → **Import**
2. Click **Upload JSON file**
3. Select `dashboards/loki-dashboard.json`
4. Click **Load** → **Import**

### 4. Run the Mock Application

Install dependencies:
```sh
pip install -r requirements.txt
```

Run the app:
```sh
python mock_app.py
```