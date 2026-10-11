import os
import sys
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add ATL root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.audit_engine import AuditEngine
from core.schemas import AuditResult

app = FastAPI(title="Ad-to-Landing-Page Message Match Auditor API")

engine = AuditEngine()

class AuditRequest(BaseModel):
    ad_headline: str
    ad_description: str
    landing_page_html: str

@app.post("/api/audit", response_model=AuditResult)
def run_audit(req: AuditRequest):
    try:
        result = engine.audit(req.ad_headline, req.ad_description, req.landing_page_html)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/presets")
def get_presets():
    preset_file = os.path.join(BASE_DIR, "samples", "benchmark_cases.json")
    if os.path.exists(preset_file):
        with open(preset_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

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
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
