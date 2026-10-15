def test_store_info_is_served_on_both_paths(client):
    r = client.get("/api/v1/store")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] and body["branch"] and {"slogan", "tables"} <= body.keys()
    assert client.get("/api/store").json() == body  # 기존 경로도 같은 응답


def test_store_info_comes_from_db_table_not_settings(client):
    client.app.state.store_info.db.run("UPDATE store_info SET name=?, branch=? WHERE id=1", ("바뀐매장", "강남점"))
    body = client.get("/api/v1/store").json()
    assert body["name"] == "바뀐매장" and body["branch"] == "강남점" and body["tables"] == 30
