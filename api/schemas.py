"""P5 (M4) — Pydantic schema: input ผิดรูปแบบ → FastAPI ตอบ 422 อัตโนมัติ"""
from datetime import date

from pydantic import BaseModel, Field, model_validator


class PredictRequest(BaseModel):
    article: str = Field(min_length=1)
    date: date


class RecommendRequest(PredictRequest):
    on_hand: int = Field(ge=0)
    unit_price: float = Field(gt=0)
    unit_cost: float = Field(ge=0)

    @model_validator(mode="after")
    def cost_not_above_price(self):
        if self.unit_cost > self.unit_price:
            raise ValueError("unit_cost ต้องไม่มากกว่า unit_price")
        return self
