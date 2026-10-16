"""손님 API: 룰렛 칸 구성 조회(빈 틀). 석원이 만든다 (v7: GET /api/v1/roulette/prizes)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["사용자"])


