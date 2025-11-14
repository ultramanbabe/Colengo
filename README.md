# Observability Stack with Grafana, Loki, Tempo, and Mock App

## Quick Start

### 1. Start the Stack

Use Docker Compose to start all services in the background:

```sh
docker-compose up -d
```

### 2. Access Grafana

Open your browser and go to:  
[http://localhost:3000](http://localhost:3000)

- **Username:** `admin`  
- **Password:** `admin`

### 3. Run the Mock Application

In a new terminal, run the mock app to start generating logs and traces:

```sh
python mock_app.py
```

## What’s Included

- **Grafana** for dashboards and visualization
- **Loki** for log aggregation
- **Tempo** for distributed tracing
- **Mock App** to generate sample logs and traces

---

You can now explore logs and traces in Grafana!