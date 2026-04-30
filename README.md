# Voyage Map

Pin a point, draw a circle, share the URL. Anyone with the link can drop marks
and leave notes on the map. Vintage cartography aesthetic.

Stack: Vue 3 + Vite (frontend), FastAPI + SQLite (backend), Leaflet (map),
Nominatim (geocoding).

## Dev

Two terminals:

```bash
# Backend (port 8000)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000

# Frontend (port 5173, proxies /api → 8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Production (single container)

```bash
docker build -t voyage-map .
docker run -p 8080:8080 -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:////app/data/voyage_map.db \
  voyage-map
```

The Vue app is built into `frontend/dist` and served by FastAPI as the SPA
fallback. SQLite lives next to the process.

## Deploy to Render

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint** and select the repo.
3. Render reads `render.yaml`, provisions one Docker web service + a 1 GB persistent
   disk mounted at `/data`. SQLite lives there, so it survives redeploys.
4. First deploy takes ~5 min (multi-stage Docker build).

The health check at `/api/health` gates each deploy. The `starter` plan is the
smallest tier that supports persistent disks — switch to `free` only for a
short-lived test (your DB will not survive a sleep/restart).

## API

- `POST   /api/maps`                          create map
- `GET    /api/maps/{slug}`                   fetch map + points
- `PATCH  /api/maps/{slug}`                   edit title / center / radius
- `POST   /api/maps/{slug}/points`            add point
- `PATCH  /api/maps/{slug}/points/{id}`       edit point
- `DELETE /api/maps/{slug}/points/{id}`       delete point
