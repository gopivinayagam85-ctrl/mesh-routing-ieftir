# Production Deployment and Environment Configuration

## 1. Architecture Overview
- **Backend Service**: FastAPI asynchronous Python service (`backend/main.py`), utilizing the high-performance Uvicorn ASGI server.
- **Frontend Service**: Production Single Page Application compiled with React 18, Recharts, and Vite 6 (`frontend/`).
- **Communication & Networking**: REST API over HTTP/JSON with CORS support across standard ports. In Docker, an Nginx reverse proxy routes `/api/` directly to the backend service.

---

## 2. Environment Variables & Runtime Configuration

### Backend
| Variable | Default | Purpose |
|:---|:---|:---|
| `PORT` | `8000` | Port for the Uvicorn server |
| `HOST` | `0.0.0.0` (Production) / `127.0.0.1` (Dev) | Network interface binding |
| `WORKERS` | `2` | Uvicorn worker process count for production |

### Frontend
| Variable | Default | Purpose |
|:---|:---|:---|
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL for FastAPI backend endpoints |

---

## 3. Production Deployment Guide

### Option A: Standard Production Server (Bare-Metal / Virtual Machine / Windows Host)

#### 1. Backend Service:
```powershell
# In PowerShell (or bash on Linux):
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # On Linux: source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

#### 2. Frontend Production Server:
```powershell
cd frontend
npm ci
npm run build
npm run preview -- --port 4173 --host 0.0.0.0
```
- Access the production preview dashboard at: `http://localhost:4173`
- Backend API docs: `http://localhost:8000/docs`
- Backend health probe: `http://localhost:8000/api/health`

---

### Option B: Containerized Deployment (Docker / Docker Compose)

The repository provides audited Dockerfiles and an Nginx reverse-proxy configuration:

#### 1. Backend Dockerfile (`backend/Dockerfile`):
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Frontend Dockerfile with Nginx Reverse Proxy (`frontend/Dockerfile`):
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### 3. Frontend Nginx Reverse Proxy Configuration (`frontend/nginx.conf`):
Routes `/` to static assets and proxies `/api/` to `http://backend:8000/api/` inside the Docker network.

#### 4. Orchestration Manifest (`docker-compose.yml`):
```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - PORT=8000
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: unless-stopped
```

#### 5. Launch with Docker Compose:
```bash
docker compose up -d --build
```
Access the application on port 80: `http://localhost`

---

## 4. Production Health Checks & Verification Probes

- **Backend Health Probe**:
  `GET http://localhost:8000/api/health`
  Returns: `{"status": "ok", "service": "mesh-routing-research-simulator"}` (HTTP 200).
- **Frontend SPA Root**:
  `GET http://localhost:4173` (Preview) or `http://localhost:80` (Docker)
  Returns: HTTP 200 with HTML shell, CSS, JS bundles, and `favicon.svg`.
- **API Simulation Probe**:
  `POST http://localhost:8000/api/simulate?algorithm=incremental` with standard JSON payload.
