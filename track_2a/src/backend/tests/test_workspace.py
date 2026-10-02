from datetime import timedelta

from sqlmodel import Session, select

from zusage.db import Application, User, Workspace, utcnow


def register(client, name="account.qa"):
    r = client.post(
        "/api/auth/register", json={"username": name, "display_name": "Tester", "password": "qa-strong-pass"}
    )
    assert r.status_code == 200
    assert r.json()["ui_lang"] == "en"
    return r.json()


def test_workspace_import_idempotency_errors_and_export(student):
    body = {
        "contents": "id,company,title,status,description\nx,Calanda,Care,applied,Patient care\nbad,,Missing,applied,No company\n",
        "kind": "applications",
    }
    r = student.post("/api/workspace/import", json=body)
    assert r.status_code == 200
    assert r.json()["imported"] == 1 and r.json()["errors"][0]["row"] == 3
    assert student.post("/api/workspace/import", json=body).json()["imported"] == 1
    apps = student.get("/api/applications").json()
    assert sum(a["company"] == "Calanda" for a in apps) == 1
    export = student.get("/api/workspace/export/applications")
    assert export.status_code == 200 and "Calanda" in export.text
    assert "attachment" in export.headers["content-disposition"]


def test_drafts_grounded_and_private(client):
    register(client)
    app = client.post("/api/applications", json={"company": "QA Care", "status": "applied"}).json()
    draft = client.post("/api/workspace/generate", json={"application_id": app["id"], "kind": "prep"}).json()
    assert draft["fallback"] is True and "real profile story" in draft["contents"]
    assert (
        client.patch(
            "/api/workspace/drafts/" + draft["id"], json={"contents": "My real story", "status": "sent"}
        ).status_code
        == 200
    )
    before = client.get("/api/workspace").json()["momentum"]["points"]
    client.patch("/api/workspace/drafts/" + draft["id"], json={"status": "sent"})
    assert client.get("/api/workspace").json()["momentum"]["points"] == before
    client.post("/api/auth/logout")
    register(client, "other.qa")
    assert client.get("/api/workspace").json()["drafts"] == []
    assert client.patch("/api/workspace/drafts/" + draft["id"], json={"contents": "stolen"}).status_code == 404
    assert client.post("/api/workspace/generate", json={"application_id": app["id"]}).status_code == 404


def test_recovery_single_use_and_password_revocation(client):
    register(client)
    token = client.cookies.get("__session")
    code = client.post("/api/workspace/recovery-code").json()["code"]
    assert "recovery_hash" not in str(client.get("/api/me/export").json())
    client.post("/api/auth/logout")
    body = {"username": "account.qa", "code": code, "new_password": "new-secure-pass"}
    assert client.post("/api/workspace/recover", json=body).status_code == 200
    assert client.post("/api/workspace/recover", json=body).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "account.qa", "password": "qa-strong-pass"}).status_code == 401
    )
    assert (
        client.post("/api/auth/login", json={"username": "account.qa", "password": "new-secure-pass"}).status_code
        == 200
    )
    assert (
        client.put(
            "/api/workspace/password", json={"current_password": "wrong", "new_password": "change-pass"}
        ).status_code
        == 401
    )
    token = client.cookies.get("__session")
    assert (
        client.put(
            "/api/workspace/password", json={"current_password": "new-secure-pass", "new_password": "change-pass"}
        ).status_code
        == 200
    )
    assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_key_encrypted_masked_and_default(client, monkeypatch):
    from zusage.api import workspace

    register(client)
    client.app.state.settings.offline = False
    client.app.state.settings.llm_base_url = "https://hackapertus.livemap.sh/v1"
    monkeypatch.setattr(workspace.ChatClient, "ping", lambda self: (True, "ok"))
    key = "sk-test-private-apertus-key"
    assert client.put("/api/workspace/key", json={"key": key}).status_code == 200
    data = client.get("/api/workspace").json()
    assert data["key_configured"] and key not in str(data)
    assert key not in str(client.get("/api/me/export").json())
    with Session(client.app.state.engine) as s:
        row = s.exec(select(Workspace)).first()
        assert key not in row.data["api_key"]
    assert client.delete("/api/workspace/key").status_code == 200
    assert client.get("/api/workspace").json()["key_configured"] is False


def test_nudges_idempotent_and_analytics(client):
    user = register(client)
    with Session(client.app.state.engine) as s:
        a = Application(
            user_id=user["id"], company="Quiet Care", status="applied", created_at=utcnow() - timedelta(days=6)
        )
        s.add(a)
        s.commit()
    r = client.post("/api/workspace/scan")
    assert r.status_code == 200 and len(r.json()["nudges"]) == 1
    assert len(client.post("/api/workspace/scan").json()["nudges"]) == 1
    assert len(client.get("/api/workspace").json()["drafts"]) == 1
    nudge = r.json()["nudges"][0]["id"]
    assert client.post("/api/workspace/nudges/" + nudge + "/done").status_code == 200
    assert client.get("/api/workspace").json()["nudges"][0]["done"]
    app = client.get("/api/applications").json()[0]
    client.patch("/api/applications/" + app["id"], json={"status": "interview"})
    client.patch("/api/applications/" + app["id"], json={"status": "offer"})
    stats = client.get("/api/workspace/analytics").json()
    assert stats["interview_rate"] == 100 and stats["offer_rate"] == 100


def test_preferences_and_account_erasure(client):
    u = register(client)
    assert client.patch("/api/workspace/preferences", json={"weekly_goal": 0}).status_code == 422
    assert client.patch("/api/workspace/preferences", json={"weekly_goal": 5, "tour_complete": True}).status_code == 200
    assert client.get("/api/workspace").json()["weekly_goal"] == 5
    client.post("/api/workspace/recovery-code")
    assert client.delete("/api/me").status_code == 200
    with Session(client.app.state.engine) as s:
        assert s.get(Workspace, u["id"]) is None
        assert s.get(User, u["id"]) is None


def test_scheduler_is_protected_and_skips_demo(student):
    assert student.post("/api/workspace/scheduled-scan").status_code == 403
    student.app.state.settings.task_key = "test-task-key"
    assert student.post("/api/workspace/scheduled-scan", headers={"X-Zusage-Task-Key": "wrong"}).status_code == 403
    response = student.post("/api/workspace/scheduled-scan", headers={"X-Zusage-Task-Key": "test-task-key"})
    assert response.status_code == 200 and response.json()["scanned"] == 0


def test_orphan_draft_adoption(student):
    response = student.post(
        "/api/workspace/import",
        json={"kind": "drafts", "contents": "id,jobId,type,contents,status\nd-1,j-1,follow_up,My real draft,draft"},
    )
    assert response.status_code == 200
    assert student.get("/api/workspace").json()["drafts"][0]["application_id"] is None
    response = student.post(
        "/api/workspace/import", json={"kind": "applications", "contents": "id,company,status\nj-1,Orphan Care,applied"}
    )
    assert response.status_code == 200
    assert student.get("/api/workspace").json()["drafts"][0]["application_id"]


def test_push_provider_and_blank_application_validation(student):
    assert student.post("/api/workspace/push", json={"endpoint": "http://127.0.0.1/", "keys": {}}).status_code == 422
    assert student.post("/api/applications", json={"company": "  "}).status_code == 422
    app = student.get("/api/applications").json()[0]
    assert student.patch("/api/applications/" + app["id"], json={"status": None}).status_code == 422
    assert student.patch("/api/applications/" + app["id"], json={"company": ""}).status_code == 422
