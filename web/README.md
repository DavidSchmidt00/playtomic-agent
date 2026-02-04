# Playtomic Agent — Web Frontend

Development frontend (Vite + React) for interacting with the Playtomic agent.

Quick start

1. Install dependencies

```bash
cd web
npm install
```

2. Start the backend API in the project root:

```bash
pip install -e .
uvicorn playtomic_agent.api:app --host 0.0.0.0 --port 8082
```

3. Start the frontend (dev server):

```bash
npm run dev -- --port 8080
```

Open http://localhost:8080

Notes

- The Vite dev server proxies `/api` to `http://localhost:8082`.
- The UI intentionally only shows the final assistant reply (no internal thoughts or tool outputs).
