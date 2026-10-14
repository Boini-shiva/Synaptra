# 🚀 Deploying SYNAPTRA to Vercel (Unified Full-Stack Guide)

SYNAPTRA is configured as a **unified monorepo** where both the **React / Vite frontend** and the **FastAPI Python backend** deploy together in a single Vercel project under one unified domain.

---

## 🏗 Architecture on Vercel

```
User Browser
    │
    ├──► https://your-project.vercel.app/           ──► React Vite SPA (frontend/dist)
    │
    └──► https://your-project.vercel.app/api/...    ──► Python Serverless Function (api/index.py)
                                                               │
                                                               ├──► Gemini AI Studio (Self-Healing & Copilot)
                                                               ├──► Lyzr Multi-Agent Swarm
                                                               └──► Qdrant Vector Memory
```

- **Frontend**: Vite compiles React components into `frontend/dist`.
- **Backend**: Vercel Python Serverless Runtime executes `api/index.py` (which mounts `backend/main.py`).
- **Unified Routing**: Handled seamlessly by `vercel.json` rewrites (`/api/(.*)` -> `api/index.py` and `/(.*)` -> `/index.html`).
- **No CORS Issues**: Because the frontend and backend share the exact same origin, browser requests to `/api/health`, `/api/workflows`, and `/api/chat` work natively without cross-origin blocks.

---

## ⚡ 1-Click Deployment Steps

### 1. Import Repository into Vercel
1. Log in to [Vercel](https://vercel.com).
2. Click **"Add New..."** ➔ **"Project"**.
3. Select your GitHub repository: `Boini-shiva/Synaptra`.
4. **Root Directory**: Keep as `./` (the root). Do NOT select `frontend` or `backend` because the unified `vercel.json` orchestrates both.

### 2. Configure Environment Variables in Vercel
Under **Settings ➔ Environment Variables** in your Vercel project, add the following keys:

| Variable | Description | Example / Default |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini AI Studio API Key (powers Copilot & Self-Healing) | `your_gemini_api_key` |
| `LYZR_API_KEY` | Lyzr Studio API Key | `sk-default-...` |
| `LYZR_PLANNER_AGENT_ID` | Lyzr Planner Agent ID | `6acf19c...` |
| `LYZR_EXECUTOR_AGENT_ID` | Lyzr Executor Agent ID | `6acf1a2...` |
| `LYZR_MEMORY_AGENT_ID` | Lyzr Memory Agent ID | `6acf1a5...` |
| `LYZR_REVIEWER_AGENT_ID` | Lyzr Reviewer Agent ID | `6acf1ac...` |
| `QDRANT_URL` | Qdrant Cloud Cluster URL (or cloud host) | `https://xxxx.gcp.cloud.qdrant.io:6333` |
| `QDRANT_COLLECTION` | Qdrant memory collection name | `synaptra_memory` |
| `QDRANT_API_KEY` | Qdrant Cloud API Key (if using Qdrant Cloud) | `your_qdrant_api_key` |
| `VITE_API_BASE_URL` | Frontend API Target (Leave empty for production) | *(leave blank to use same-origin `/api`)* |

> 💡 **Tip:** In production, leave `VITE_API_BASE_URL` empty or unset. The frontend automatically routes all API requests via relative `/api` paths to the Vercel serverless function!

### 3. Click Deploy!
- Vercel automatically runs `npm --prefix frontend run build`.
- Deploys the Python FastAPI serverless function at `/api`.
- Deploys the Vite SPA static bundle at `/`.

---

## 🧪 Post-Deployment Verification

After Vercel gives you your production URL (e.g., `https://synaptra.vercel.app`):

1. **Verify Backend Health**:
   ```bash
   curl https://synaptra.vercel.app/api/health
   ```
   Should return:
   ```json
   {
     "status": "ok",
     "service": "synaptra-backend",
     "version": "0.2.0"
   }
   ```

2. **Verify Frontend**:
   Open `https://synaptra.vercel.app` in your browser:
   - Dashboard will load metrics and health cards.
   - Go to **Settings** ➔ confirm **Gemini AI Studio** and agents show green badges.
   - Go to **AI Assistant** ➔ ask a question to test the live Copilot.
   - Go to **New Workflow** ➔ trigger an autonomous multi-agent audit pipeline!

---

## 💻 Local Development Workflow

To run both frontend and backend locally side-by-side:

### Terminal 1: Backend
```bash
# Windows
.\backend\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8002 --reload

# macOS / Linux
source backend/.venv/bin/activate
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8002 --reload
```

### Terminal 2: Frontend
```bash
npm run dev
```
Open `http://127.0.0.1:5173` in your browser.
