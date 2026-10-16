"""직원 호출 더미. (담당: 석원)"""


# 이 파일이 맡은 더미 엔드포인트. 실제 구현으로 바꾸면 해당 줄과 아래 함수를 같이 지운다.
ENDPOINTS = {
    "POST /api/calls": "call_created",
}


def call_created() -> dict:
    return {"id": 4}
