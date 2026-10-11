import os
import sys
import json
import csv
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add ATL root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.audit_engine import AuditEngine
from core.schemas import AuditResult

DATASET_DIR = r"c:\Users\SANJAY RAJ\Downloads\Srishti-2K26-Datasets-All\PS-03_message_match_auditor_dataset\PS-03_message_match_auditor"

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Ad-to-Landing-Page Message Match Auditor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = AuditEngine()

class AuditRequest(BaseModel):
    ad_headline: str
    ad_description: str
    landing_page_html: Optional[str] = None
    landing_page_url: Optional[str] = None
    ad_call_to_action: Optional[str] = None

class FetchURLRequest(BaseModel):
    url: str

@app.post("/api/fetch-url")
@app.post("/fetch-url")
def fetch_url(req: FetchURLRequest):
    html_content, err, metadata = engine.fetcher.fetch_html(req.url)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {
        "url": req.url,
        "html": html_content,
        "metadata": metadata
    }

@app.post("/api/audit")
@app.post("/audit")
def run_audit(req: AuditRequest):
    try:
        if req.landing_page_url and not req.landing_page_html:
            result = engine.audit_url(
                ad_headline=req.ad_headline,
                ad_description=req.ad_description,
                landing_page_url=req.landing_page_url,
                ad_call_to_action=req.ad_call_to_action
            )
        else:
            result = engine.audit(
                ad_headline=req.ad_headline,
                ad_description=req.ad_description,
                landing_page_html=req.landing_page_html or "",
                ad_call_to_action=req.ad_call_to_action
            )
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/presets")
@app.get("/presets")
def get_presets():
    presets = []
    # 1. Bundled 60 pairs from benchmark dataset (works on Vercel and cloud)
    bundled_file = os.path.join(BASE_DIR, "samples", "benchmark_60_pairs.json")
    if os.path.exists(bundled_file):
        try:
            with open(bundled_file, "r", encoding="utf-8") as f:
                presets.extend(json.load(f))
        except Exception:
            pass

    # 2. Canonical benchmark cases fallback
    if not presets:
        preset_file = os.path.join(BASE_DIR, "samples", "benchmark_cases.json")
        if os.path.exists(preset_file):
            try:
                with open(preset_file, "r", encoding="utf-8") as f:
                    presets.extend(json.load(f))
            except Exception:
                pass

    # 3. Local dataset directory fallback if present
    if not presets:
        ads_csv = os.path.join(DATASET_DIR, "ads.csv")
        if os.path.exists(ads_csv):
            try:
                with open(ads_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        snap_path = os.path.join(DATASET_DIR, row["snapshot_file"])
                        html_content = ""
                        if os.path.exists(snap_path):
                            with open(snap_path, "r", encoding="utf-8") as sf:
                                html_content = sf.read()

                        headlines = " | ".join(filter(None, [row.get("headline_1", ""), row.get("headline_2", ""), row.get("headline_3", "")]))
                        desc = " ".join(filter(None, [row.get("description_1", ""), row.get("description_2", "")]))

                        presets.append({
                            "id": row["pair_id"],
                            "title": f"Pair {row['pair_id']}: {row['advertiser']} ({headlines[:35]}...)",
                            "ad_headline": headlines,
                            "ad_description": desc,
                            "html": html_content
                        })
            except Exception:
                pass

    return presets

@app.get("/api/report")
@app.get("/report")
def get_report(req_id: Optional[str] = None):
    sample_file = os.path.join(BASE_DIR, "sample_audit_report.json")
    if os.path.exists(sample_file):
        with open(sample_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"message": "Run an audit first to generate report."}

# Serve Static UI files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "UI under construction"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
