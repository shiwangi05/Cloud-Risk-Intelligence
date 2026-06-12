# Local and Hosted Setup

The application supports both environments:

- Local: Vite frontend on port 5173, FastAPI backend on port 8000, SQLite.
- Hosted: Vercel frontend, Render FastAPI backend, Render PostgreSQL.

## Local

Create local environment files from the examples if they do not already exist.

Backend:

```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Frontend (in another terminal):

```powershell
cd frontend
npm run dev
```

Keep `VITE_API_URL` empty locally. Vite proxies API requests to
`http://localhost:8000`.

## Render Backend

1. Push the repository to GitHub.
2. In Render, create a Blueprint and select this repository.
3. Render reads `render.yaml` and creates the API and PostgreSQL database.
4. Set `ALLOWED_ORIGINS` to the Vercel URL, for example
   `https://your-project.vercel.app`.
5. Optionally set `GEMINI_API_KEY`.
6. Copy the generated `API_KEY`; Vercel needs the same value.

## Vercel Frontend

1. Import the same GitHub repository.
2. Set the Root Directory to `frontend`.
3. Vercel detects Vite. The build command is `npm run build` and output
   directory is `dist`.
4. Add these environment variables:

```text
VITE_API_URL=https://your-api.onrender.com
VITE_API_KEY=<same API_KEY value used by Render>
```

5. Deploy, then update Render's `ALLOWED_ORIGINS` if the final Vercel URL
   differs from the value entered earlier.

## Security

Every `VITE_*` value is included in the browser bundle. The current API key
acts only as a shared application boundary and is not a secret in a Vercel
deployment. JWT authentication should protect user-specific operations.

Never commit `.env` files. Rotate the Gemini key before deployment if it has
ever been committed, posted, or shared.
