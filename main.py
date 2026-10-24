
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Bus Fleet Tracking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DriverLocationData(BaseModel):
    driver_id: str
    route_id: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed: float = Field(default=0.0, ge=0)

latest_route_locations: Dict[str, dict] = {}
routes_db: List[str] = []
data_lock = Lock()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
def root():
    return {"status": "Online", "system": "Bus Fleet Tracking API", "timestamp": now_iso()}

@app.get("/api/routes")
def get_routes():
    with data_lock:
        return {"routes": list(routes_db)}

@app.post("/api/admin/add-route")
def add_route(route_name: str):
    clean_name = route_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الخط غير صالح")
    with data_lock:
        if clean_name in routes_db:
            return {"status": "error", "message": "الخط موجود بالفعل", "routes": list(routes_db)}
        routes_db.append(clean_name)
        return {"status": "success", "message": f"تمت إضافة الخط {clean_name} بنجاح", "routes": list(routes_db)}

# ==========================================
# 🛑 هنا المكان الجديد لدوال التعديل والحذف 🛑
# ==========================================

@app.put("/api/admin/routes/{route_id}")
def update_route(route_id: str, route_name: str):
    clean_name = route_name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="اسم الخط غير صالح")
    with data_lock:
        if route_id in routes_db:
            index = routes_db.index(route_id)
            routes_db[index] = clean_name
            return {"status": "success", "message": "تم تعديل الخط بنجاح", "routes": list(routes_db)}
        elif clean_name in routes_db:
            raise HTTPException(status_code=400, detail="الخط موجود بالفعل")
        else:
            raise HTTPException(status_code=404, detail="خط السير غير موجود")

@app.delete("/api/admin/routes/{route_id}")
def delete_route(route_id: str):
    with data_lock:
        if route_id in routes_db:
            routes_db.remove(route_id)
            return {"status": "success", "message": "تم حذف الخط بنجاح", "routes": list(routes_db)}
        else:
            raise HTTPException(status_code=404, detail="خط السير غير موجود")

# ==========================================

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
    return {
        "status": status,
        "route_id": route_id,
        "lat": location["latitude"],
        "lng": location["longitude"],
        "updated_at": location["updated_at"],
        "speed": location["speed"],
        "data": location,
    }
