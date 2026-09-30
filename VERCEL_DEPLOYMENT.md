# Vercel Deployment

## Frontend

1. Import this GitHub repository into Vercel.
2. Set the Vercel project Root Directory to the repository root. The root `vercel.json` installs `frontend` dependencies, builds the Vite app, and rewrites client-side routes to `index.html`.
3. Set `VITE_API_BASE_URL` in Vercel's Environment Variables for each deployment environment. Its value must be the origin of the separately hosted FastAPI service, such as `https://your-api.example.com`; do not append `/api`.
4. Redeploy after changing environment variables. Vite embeds `VITE_` variables at build time.

## Backend

The FastAPI backend is not part of the Vercel deployment. The trained model files exceed Vercel Function size limits, and the backend writes a SQLite database and operational state that require persistent storage. Host it separately on a Python service with persistent disk and enough memory for the models. Install dependencies from `requirements.txt` and start it with:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Configure the backend with a unique `DISASTER_AI_SECRET_KEY`, set `DISASTER_AI_ALLOW_LAN_ORIGINS=false`, and set `DISASTER_AI_CORS_ORIGINS` to the exact Vercel frontend origin. Multiple allowed origins may be comma-separated. Do not use the placeholder credentials from `backend/.env.example` in production.

The Vercel deployment serves the frontend only; API functionality requires the separately deployed backend and a matching `VITE_API_BASE_URL`.