from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from datetime import datetime

# إعداد التطبيق
app = FastAPI(title="Bus Fleet Tracking API")

# سماح للمتصفح بالاتصال بدون قيود CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# 1. السائق يرسل موقعه
@app.post("/update-location")
def update_driver_location(data: DriverLocationData):
    payload = data.model_dump()
    payload["updated_at"] = str(datetime.now())
    latest_route_locations[data.route_id] = payload
    return {
        "status": "success",
        "message": f"Location updated for route: {data.route_id}",
        "data": payload
    }

from datetime import datetime

# 2. العامل يطلب أحدث موقع لأتوبيس خط السير
@app.get("/get-location/{route_id}")
def get_bus_location(route_id: str):
    bus_location = latest_route_locations.get(route_id)
    if not bus_location:
        return {
            "status": "waiting",
            "message": "السائق لم يبدأ الرحلة بعد",
            "route_id": route_id
        }
    
    # حساب الفرق بين الوقت الحالي ووقت آخر إرسال من السائق
    last_update_str = bus_location.get("updated_at")
    if last_update_str:
        last_update_time = datetime.fromisoformat(last_update_str)
        time_difference = (datetime.now() - last_update_time).total_seconds()
        
        # لو فات أكتر من 30 ثانية من غير إرسال يعتبر غير متصل
        if time_difference > 30:
            return {
                "status": "offline",
                "message": "الأتوبيس متوقف أو غير متصل حالياً",
                "route_id": route_id,
                "data": bus_location
            }

    return {
        "status": "active",
        "route_id": route_id,
        "data": bus_location
    }
