
import os
import re
import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

# Optional Snowflake imports will only be used if creds exist
USE_SNOWFLAKE = all(os.getenv(k) for k in [
    "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA"
])

if USE_SNOWFLAKE:
    try:
        import snowflake.connector
    except Exception as e:
        USE_SNOWFLAKE = False

app = FastAPI(title="BI Agent Chatbot (Sales)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str
    user_context: Optional[Dict[str, Any]] = None  # e.g., {"department":"marketing","rvp":"Alice"}

class AskResponse(BaseModel):
    type: str  # "chart" or "text" or "table"
    title: Optional[str] = None
    text: Optional[str] = None
    labels: Optional[List[str]] = None
    datasets: Optional[List[Dict[str, Any]]] = None
    table: Optional[List[Dict[str, Any]]] = None

# --- Load data helper ---
def load_data() -> pd.DataFrame:
    """
    Load dataset either from Snowflake (preferred) or from local sample CSV.
    Expected columns: date, purchases, redemptions, assets, wholesaler, advisor, mandate_name, fund_type, rvp
    """
    if USE_SNOWFLAKE:
        ctx = snowflake.connector.connect(
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DATABASE"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
        )
        sql = """
            SELECT
                CAST(date AS DATE) as date,
                purchases, redemptions, assets,
                wholesaler, advisor, mandate_name, fund_type, rvp
            FROM sales_snapshot  -- change to your table/view
            WHERE date >= DATEADD(year, -2, CURRENT_DATE())
        """
        df = pd.read_sql(sql, ctx)
        ctx.close()
        return df
    # Fallback to local sample data
    sample_path = os.path.join(os.path.dirname(__file__), "sample_sales.csv")
    df = pd.read_csv(sample_path, parse_dates=["date"])
    return df

_DATA_CACHE: Optional[pd.DataFrame] = None

def get_df() -> pd.DataFrame:
    global _DATA_CACHE
    if _DATA_CACHE is None:
        _DATA_CACHE = load_data()
    return _DATA_CACHE.copy()

# --- Simple time helpers ---
def parse_last_quarter(ref: Optional[date] = None):
    if ref is None:
        ref = date.today()
    q = (ref.month - 1) // 3 + 1
    # last quarter
    last_q = q - 1 if q > 1 else 4
    year = ref.year if q > 1 else ref.year - 1
    start_month = 3 * (last_q - 1) + 1
    start = date(year, start_month, 1)
    if start_month in [1,3,5,7,8,10,12]:
        month_days = {1:31,3:30+1,5:31,7:31,8:31,10:31,12:31}[start_month]  # quick hack for simplicity
    elif start_month == 2:
        month_days = 29 if (year%4==0 and (year%100!=0 or year%400==0)) else 28
    else: # Apr, Jun, Sep, Nov
        month_days = 30
    # end = start + 2 months end-day
    if start_month in [1,4,7,10]:
        # quarter months: start_month, start_month+1, start_month+2
        # compute last day of (start_month+2)
        em = start_month + 2
        if em in [1,3,5,7,8,10,12]:
            ed = {1:31,3:31,5:31,7:31,8:31,10:31,12:31}[em]
        elif em == 2:
            ed = 29 if (year%4==0 and (year%100!=0 or year%400==0)) else 28
        else:
            ed = 30
        end = date(year, em, ed)
    else:
        end = start  # fallback
    return start, end

# --- Very simple intent/router ---
def route_question(q: str, user_ctx: Optional[Dict[str,Any]] = None) -> AskResponse:
    q_low = q.lower()
    df = get_df()

    # Filter by RVP if mentioned or in user context
    rvp = None
    m = re.search(r"rvp\s+([a-zA-Z]+)", q_low)
    if m:
        rvp = m.group(1).title()
    elif user_ctx and user_ctx.get("rvp"):
        rvp = str(user_ctx["rvp"])

    if rvp:
        df = df[df["rvp"].str.lower() == rvp.lower()]

    # Time window: last quarter
    if "last quarter" in q_low or "past quarter" in q_low:
        start, end = parse_last_quarter()
        mask = (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
        df = df[mask]

    # Grouping
    group_field = None
    if "by fund type" in q_low:
        group_field = "fund_type"
    elif "by wholesaler" in q_low:
        group_field = "wholesaler"
    elif "by advisor" in q_low:
        group_field = "advisor"
    elif "by mandate" in q_low or "by mandate name" in q_low:
        group_field = "mandate_name"

    # Metric
    metric = None
    if "redemption" in q_low:
        metric = "redemptions"
    elif "purchase" in q_low:
        metric = "purchases"
    elif "asset" in q_low:
        metric = "assets"
    else:
        # default metric
        metric = "purchases"

    title_bits = [metric.title()]
    if rvp:
        title_bits.append(f"for RVP {rvp}")
    if "last quarter" in q_low or "past quarter" in q_low:
        title_bits.append("(Last Quarter)")
    if group_field:
        title_bits.append(f"by {group_field.replace('_',' ').title()}")
    title = " ".join(title_bits)

    if group_field:
        agg = df.groupby(group_field)[metric].sum().reset_index().sort_values(metric, ascending=False)
        labels = agg[group_field].astype(str).tolist()
        data = agg[metric].round(2).tolist()
        return AskResponse(
            type="chart",
            title=title,
            labels=labels,
            datasets=[{"label": metric, "data": data}],
        )

    # If time series requested
    if "trend" in q_low or "over time" in q_low or "by month" in q_low:
        ts = df.resample("M", on="date")[metric].sum().reset_index()
        labels = ts["date"].dt.strftime("%Y-%m").tolist()
        data = ts[metric].round(2).tolist()
        return AskResponse(
            type="chart",
            title=title + " (Monthly)",
            labels=labels,
            datasets=[{"label": metric, "data": data}],
        )

    # Otherwise return a single number (sum)
    total = float(df[metric].sum()) if not df.empty else 0.0
    return AskResponse(type="text", title=title, text=f"{metric.title()} = {total:,.2f}")

@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    return route_question(req.question, req.user_context)

@app.get("/health")
def health():
    return {"status": "ok"}
