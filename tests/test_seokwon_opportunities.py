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
    assert set(first) == {"items", "page", "pages"}
    assert 1 <= len(first["items"]) <= 4
    assert all(set(card) == {"title", "why", "action"} for card in first["items"])
    assert repo.opportunities(first["pages"])["items"] == first["items"]

