"""P5 (M4) — Pydantic schema: input ผิดรูปแบบ → FastAPI ตอบ 422 อัตโนมัติ

ตรวจที่นี่: field หาย, ชนิดผิด, date ผิดรูปแบบ, ค่าติดลบ, ต้นทุน > ราคา, field แปลกปลอม
ตรวจใน main.py (ต้องรู้ข้อมูล/โมเดล): article ไม่รู้จัก, date ไกลเกินช่วงที่ทำนายได้ → 422 เช่นกัน
"""
from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    article: str = Field(min_length=1, max_length=100, examples=["TRADITIONAL BAGUETTE"])
    date: Date = Field(examples=["2022-09-15"])


class RecommendRequest(PredictRequest):
    on_hand: int = Field(ge=0, le=100_000, description="ของที่มีอยู่แล้ว (ชิ้น)")
    unit_price: float = Field(gt=0, le=10_000, description="ราคาขายต่อชิ้น")
    unit_cost: float = Field(ge=0, le=10_000, description="ต้นทุนต่อชิ้น")

    @model_validator(mode="after")
    def cost_not_above_price(self):
        if self.unit_cost > self.unit_price:
            raise ValueError("unit_cost ต้องไม่มากกว่า unit_price")
        return self


class PredictResponse(BaseModel):
    article: str
    date: Date
    p50: float
    p_q: float
    q: float
    model_version: str


class RecommendResponse(BaseModel):
    article: str
    date: Date
    forecast: float = Field(description="ยอดขายคาดการณ์ที่ quantile q (F_q)")
    p50: float
    q: float = Field(description="critical ratio = (price - cost) / price")
    on_hand: int
    recommended_qty: int
    model_version: str
