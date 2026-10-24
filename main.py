import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from threading import Lock
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Bus Fleet Tracking API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
latest_route_locations: Dict[str, dict] = {}
data_lock = Lock()

class DriverLocationData(BaseModel):
    driver_id: str
    route_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: float = Field(default=0.0, ge=0)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def db_request(method: str, path: str, payload=None):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير مهيأة. اضبط SUPABASE_URL و SUPABASE_SERVICE_ROLE_KEY في إعدادات السيرفر.")
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers={
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 409:
            raise HTTPException(status_code=409, detail="اسم خط السير موجود بالفعل")
        raise HTTPException(status_code=502, detail=f"خطأ في قاعدة البيانات: {detail[:300]}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تعذر الاتصال بقاعدة البيانات: {str(exc)[:200]}")

@app.get("/")
def root():
    return {"status": "Online", "system": "Bus Fleet Tracking API", "database_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY), "timestamp": now_iso()}

@app.get("/api/routes")
def get_routes():
    rows = db_request("GET", "bus_routes?select=id,name,created_at&order=created_at.asc")
    return {"routes": rows}

@app.post("/api/admin/add-route")
def add_route(route_name: str):
    clean_name = route_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الخط غير صالح")
    rows = db_request("POST", "bus_routes", {"name": clean_name})
    return {"status": "success", "message": f"تمت إضافة الخط {clean_name} بنجاح", "route": rows[0] if rows else None}

@app.put("/api/admin/routes/{route_id}")
def edit_route(route_id: str, route_name: str):
    clean_name = route_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الخط غير صالح")
    rows = db_request("PATCH", f"bus_routes?id=eq.{urllib.parse.quote(route_id, safe='')}", {"name": clean_name})
    if not rows:
        raise HTTPException(status_code=404, detail="خط السير غير موجود")
    return {"status": "success", "route": rows[0]}

@app.delete("/api/admin/routes/{route_id}")
def delete_route(route_id: str):
    rows = db_request("DELETE", f"bus_routes?id=eq.{urllib.parse.quote(route_id, safe='')}")
    if not rows:
        raise HTTPException(status_code=404, detail="خط السير غير موجود")
    return {"status": "success", "message": "تم حذف خط السير"}

@app.post("/update-location")
def update_driver_location(data: DriverLocationData):
    payload = data.model_dump()
    payload["updated_at"] = now_iso()
    with data_lock:
        latest_route_locations[data.route_id] = payload
    return {"status": "success", "message": "Location updated", "data": payload}

@app.get("/get-location/{route_id}")
def get_bus_location(route_id: str):
    with data_lock:
        location = latest_route_locations.get(route_id)
    if not location:
        return {"status": "waiting", "message": "السائق لم يبدأ الرحلة بعد", "route_id": route_id}
    try:
        last_update = datetime.fromisoformat(location["updated_at"])
        age_seconds = (datetime.now(timezone.utc) - last_update).total_seconds()
    except (KeyError, ValueError):
        age_seconds = 999999
    status = "offline" if age_seconds > 30 else "active"
    return {"status": status, "route_id": route_id, "lat": location["latitude"], "lng": location["longitude"], "updated_at": location["updated_at"], "speed": location["speed"], "data": location}
