from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from typing import Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
import invoice2data
from invoice2data import extract_data
from invoice2data.extract.loader import read_templates
from invoice2data.input import pdfminer_wrapper, pdftotext

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_DIR = Path(invoice2data.__file__).resolve().parent / "extract" / "templates"
TEMPLATE_DIR = Path(os.getenv("TEMPLATE_DIR", str(DEFAULT_TEMPLATE_DIR)))
DB_PATH = Path(os.getenv("RATE_DB", APP_DIR / "data" / "rate_limits.sqlite3"))
LIMITS = {"free": int(os.getenv("FREE_LIMIT", "100")), "pro": int(os.getenv("PRO_LIMIT", "10000"))}
KEYS = {
    "free": {k for k in os.getenv("FREE_KEYS", "free-demo-key").split(",") if k},
    "pro": {k for k in os.getenv("PRO_KEYS", "pro-demo-key").split(",") if k},
}
TEMPLATES = read_templates(str(TEMPLATE_DIR))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

with sqlite3.connect(DB_PATH) as conn:
    conn.execute("create table if not exists usage (api_key text, day text, count integer, primary key(api_key, day))")

app = FastAPI(title="InvoiceLens API", version="0.1.0", summary="Template-based invoice extraction for digital PDFs")
SITE_DIR = Path(__file__).resolve().parent


def authorize(api_key: Optional[str]) -> str:
    if not api_key:
        raise HTTPException(401, "Missing X-API-Key")
    for tier, keys in KEYS.items():
        if api_key in keys:
            return tier
    raise HTTPException(401, "Invalid API key")


def check_limit(api_key: str, tier: str) -> Dict[str, object]:
    today = date.today().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("select count from usage where api_key=? and day=?", (api_key, today))
        used = (cur.fetchone() or (0,))[0]
        if used >= LIMITS[tier]:
            raise HTTPException(429, f"Daily quota exceeded for {tier}")
        conn.execute(
            "insert into usage(api_key, day, count) values (?, ?, 1) on conflict(api_key, day) do update set count=count+1",
            (api_key, today),
        )
    return {"tier": tier, "used": used + 1, "limit": LIMITS[tier], "day": today}


@app.get("/")
def site_root() -> FileResponse:
    return FileResponse(SITE_DIR / "site_index.html", media_type="text/html")


@app.get("/style.css")
def site_css() -> FileResponse:
    return FileResponse(SITE_DIR / "style.css", media_type="text/css")


@app.get("/health")
def health() -> Dict[str, object]:
    return {"ok": True, "templates": len(TEMPLATES), "template_dir": str(TEMPLATE_DIR), "preferred_reader": "pdftotext"}


@app.post("/extract")
async def extract_invoice(request: Request, x_api_key: Optional[str] = Header(default=None)) -> Dict[str, object]:
    usage = check_limit(x_api_key or "", authorize(x_api_key))
    body = await request.body()
    if not body:
        raise HTTPException(400, "Request body must contain a PDF")
    if len(body) > int(os.getenv("MAX_FILE_BYTES", str(10 * 1024 * 1024))):
        raise HTTPException(413, "PDF too large")
    with NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(body)
        tmp.flush()
        data = {}
        for reader in (pdftotext, pdfminer_wrapper):
            try:
                data = extract_data(tmp.name, templates=TEMPLATES, input_module=reader)
            except Exception:
                data = {}
            if data:
                break
    if not data:
        raise HTTPException(422, "No matching template found")
    return {"usage": usage, "data": jsonable_encoder(data)}
