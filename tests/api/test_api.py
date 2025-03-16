def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Workflow already start up with healthy status."
    }
