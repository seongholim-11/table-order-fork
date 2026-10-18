def test_store_info_is_served_on_both_paths(client):
    client.app.state.store_info.db.run("UPDATE store_info SET name=?, branch=?, slogan=?, tables=? WHERE id=1",
                                       ("DB매장", "DB지점", "DB 슬로건", 12))
    r = client.get("/api/v1/store")
    assert r.status_code == 200
    body = r.json()
    assert body == {"name": "DB매장", "branch": "DB지점", "slogan": "DB 슬로건", "tables": 12}
    assert client.get("/api/store").json() == body  # 기존 경로도 같은 응답


def test_store_info_store_reads_db_table_not_settings(client):
    """저장소가 환경설정이 아니라 store_info 테이블을 읽는지 확인한다."""
    client.app.state.store_info.db.run("UPDATE store_info SET name=?, branch=? WHERE id=1", ("바뀐매장", "강남점"))
    body = client.app.state.store_info.get()
    assert body["name"] == "바뀐매장" and body["branch"] == "강남점" and body["tables"] == 30
