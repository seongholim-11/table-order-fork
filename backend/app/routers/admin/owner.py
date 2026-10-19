"""관리자 API: 관리자 설정. 현재는 룰렛 칸 전체 교체를 제공한다."""

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

router = APIRouter()


class RoulettePrizeIn(BaseModel):
    label: str = Field(min_length=1)
    short: str = Field(min_length=1)
    emoji: str = "🎁"
    color: str
    kind: str
    percent: int | None = None
    item_id: str | None = None
    weight: float = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_kind_fields(self):
        if self.kind == "discount" and not (self.percent is not None and 1 <= self.percent <= 100 and self.item_id is None):
            raise ValueError("할인 칸은 1~100의 percent만 필요합니다.")
        if self.kind == "free" and not (self.item_id and self.percent is None):
            raise ValueError("서비스 칸은 item_id만 필요합니다.")
        if self.kind not in ("discount", "free"):
            raise ValueError("kind는 discount 또는 free여야 합니다.")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.color):
            raise ValueError("색상은 #RRGGBB 형식이어야 합니다.")
        return self


@router.put("/owner/roulette/prizes")
async def save_roulette_prizes(prizes: list[RoulettePrizeIn], request: Request):
    """검증을 통과한 2~8개 룰렛 칸을 한 번에 교체한다."""
    if not 2 <= len(prizes) <= 8:
        raise HTTPException(422, "룰렛 칸은 2~8개여야 합니다.")
    weights = [prize.weight for prize in prizes]
    # 화면을 거치지 않는 요청도 1% 단위와 합계 100% 규칙을 동일하게 검사한다.
    if any(weight % 1 for weight in weights) or sum(weights) != 100:
        raise HTTPException(422, "확률은 1% 단위로 입력하고 전체 합계를 100%로 맞춰야 합니다.")
    missing = [prize.item_id for prize in prizes
               if prize.kind == "free" and not request.app.state.roulette_prizes.service_menu_exists(prize.item_id)]
    if missing:
        raise HTTPException(422, f"존재하지 않는 서비스 메뉴입니다: {missing[0]}")
    return request.app.state.roulette_prizes.replace([prize.model_dump(exclude_none=True) for prize in prizes])
