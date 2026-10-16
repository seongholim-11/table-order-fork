"""손님 화면: 매장 정보 더미. (담당: 재현)"""


# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "GET /api/store, /api/v1/store": "store",
}


def store() -> dict:
    return {"name": "역전할머니맥주", "branch": "홍대점", "slogan": "옛날 그 맛 그대로, 시원한 생맥주 한 잔!", "tables": 30}
