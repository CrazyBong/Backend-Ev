from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal

# Admin specific schemas can be added here
class AdminUserStats(BaseModel):
    total_users: int
    active_users: int

class AdminStationStats(BaseModel):
    total_stations: int
    active_stations: int
    total_slots: int
    available_slots: int
