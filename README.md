# bi-agent-chatbot-sales
BI Agent Chatbot (FastAPI + React) 

This is app lets users **ask questions** about sales data and get either a **number** or a **chart** back.
- **Backend:** FastAPI (`/ask` endpoint) with optional Snowflake connection.
- **Frontend:** React + Vite, renders responses and charts (Chart.js).
- **Data:** If Snowflake env vars are set, queries Snowflake; otherwise uses `backend/sample_sales.csv`.


## To Start

### 1) Backend
```bash
cd backend
Windows cmd: .venv\Scripts\activate #python -m venv .venv && source .venv/bin/activate  #
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Optional: set Snowflake environment variables before running to enable live queries:
```
export SNOWFLAKE_ACCOUNT=...
export SNOWFLAKE_USER=...
export SNOWFLAKE_PASSWORD=...
export SNOWFLAKE_WAREHOUSE=...
export SNOWFLAKE_DATABASE=...
export SNOWFLAKE_SCHEMA=...
```

### 2) Frontend
```bash
cd ../frontend
npm install
#cp .env.example .env          # adjust VITE_API_URL if needed
npm run dev
```

Open `http://localhost:5173` and try asking:
- `Show redemptions by fund type last quarter`
- `Purchases by wholesaler`
- `RVP Alice purchases last quarter`

## How it Works

- **/ask** accepts `{ question, user_context }`.
- A simple router parses:
  - Metric: purchases / redemptions / assets
  - Time: last quarter (can add others)
  - Grouping: by fund type / wholesaler / advisor / mandate
  - Optional **RVP** filter (e.g., "RVP Alice")
- Returns JSON for either a **chart** or **text**.
- React renders chart using Chart.js.

## Future Steps

- Add more time windows (YTD, MTD, rolling 12 months).
- Hook up real Snowflake table (change SQL in `load_data()`).
- Add auth (Clerk/Auth0/Entra ID) and pass user role/rvp to backend.
- Log questions + responses for improvement.
- Swap Chart.js for embedded Tableau where you have curated dashboards.
```

