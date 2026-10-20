from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from datetime import datetime

app = FastAPI(title="Bus Fleet Tracking API")

# هيكل بيانات موقع السائق
class DriverLocationData(BaseModel):
    driver_id: str
    route_id: str      # كود خط السير (مثل: route_maadi, route_haram)
    latitude: float
    longitude: float
    speed: float = 0.0

# ذاكرة لتخزين أحدث موقع لكل خط سير
latest_route_locations: Dict[str, dict] = {}

@app.get("/")
def root():
    return {
        "status": "Online",
        "system": "Company Bus Fleet Tracking Backend",
        "timestamp": str(datetime.now())
    }

# 1. السائق يرسل موقعه مع كود خط السير
@app.post("/api/driver/location")
def update_driver_location(data: DriverLocationData):
    payload = data.model_dump()
    payload["updated_at"] = str(datetime.now())
    
    # حفظ/تحديث موقع الأتوبيس المخصص لخط السير ده
    latest_route_locations[data.route_id] = payload
    
    return {
        "status": "success",
        "message": f"Location updated for route: {data.route_id}",
        "data": payload
    }

# 2. العامل يطلب أحدث موقع لأتوبيس خط السير بتاعه
@app.get("/api/worker/track/{route_id}")
def get_bus_location(route_id: str):
    bus_location = latest_route_locations.get(route_id)
    if not bus_location:
        return {
            "status": "waiting",
            "message": "السائق لم يبدأ الرحلة بعد أو لا يوجد موقع متاح حالياً لهذا الخط",
            "route_id": route_id
        }
    return {
        "status": "active",
        "route_id": route_id,
        "data": bus_location
    }
