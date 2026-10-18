"""석원 TODO 3: 관리자 화면이 같은 추천 응답 계약을 사용하는지 확인한다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import admin_repository as ar
from admin_dummy_data import DummyBackend


def test_dummy_opportunities_shape_and_round_cycle():
    repo = ar.AdminRepository(DummyBackend())
    first = repo.opportunities(0)
    assert set(first) == {"items", "page", "pages", "summary", "total"}
    assert set(first["summary"]) == {"members", "orders"}
    assert 1 <= len(first["items"]) <= 4
    assert all({"title", "why", "action", "action_type", "target_grades", "member_ids", "sms_body"} <= set(card)
               for card in first["items"])
    assert first["total"] >= 30  # 1,000명 더미의 생애주기·취향·시간대 조합으로 수십 개를 만든다.
    all_titles = [card["title"] for page in range(first["pages"])
                  for card in repo.opportunities(page)["items"]]
    assert len(all_titles) == first["total"] == len(set(all_titles))
    assert all(len(repo.opportunities(page)["items"]) == 4 for page in range(first["pages"]))
    assert repo.opportunities(first["pages"])["items"] == first["items"]

