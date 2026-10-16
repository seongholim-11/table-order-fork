"""손님 API: DB에 저장된 룰렛 칸 구성 조회."""

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import require_admin
from app.routers.admin.owner import RoulettePrizeIn, save_roulette_prizes

router = APIRouter(prefix="/api", tags=["사용자"])


@router.get("/v1/roulette/prizes")
async def list_roulette_prizes(request: Request):
    return request.app.state.roulette_prizes.list()


@router.put("/v1/owner/roulette/prizes", dependencies=[Depends(require_admin)])
async def save_roulette_prizes_alias(prizes: list[RoulettePrizeIn], request: Request):
    """통합 API 문서의 경로도 지원한다. 관리자 화면 경로와 같은 저장 로직을 쓴다."""
    return await save_roulette_prizes(prizes, request)
