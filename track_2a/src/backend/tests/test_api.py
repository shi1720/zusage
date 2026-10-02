"""HTTP API: auth, roles, interviews, tracker, drills, privacy rights."""

from datetime import UTC, datetime, timedelta


def register(client, username, role="student", code=""):
    return client.post("/api/auth/register", json={"username": username, "password": "secret-pass-1",
                                                    "display_name": username.title(), "role": role,
                                                    "class_code": code, "ui_lang": "de"})


def test_register_login_logout(client):
    r = register(client, "mia")
    assert r.status_code == 200 and r.json()["role"] == "student"
    assert register(client, "mia").status_code == 409
    assert register(client, "x").status_code == 422
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={"username": "mia", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "MIA", "password": "secret-pass-1"}).status_code == 200


def test_login_is_rate_limited(client):
    register(client, "brute")
    client.post("/api/auth/logout")
    codes = [client.post("/api/auth/login", json={"username": "brute", "password": "nope-nope"}).status_code
             for _ in range(12)]
    assert codes[-1] == 429


def test_bearer_token_auth_for_harnesses(client):
    client.post("/api/auth/demo/student")
    token = client.cookies.get("__session")
    client.cookies.clear()
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_interview_lifecycle(student):
    iv = student.post("/api/interviews", json={"occupation_id": "informatik_efz", "language": "it",
                                               "length": "quick", "confidence_before": 2}).json()
    assert iv["status"] == "active" and iv["interviewer_message"].startswith("Buongiorno")
    for _ in range(12):
        if iv["done"]:
            break
        iv = student.post(f"/api/interviews/{iv['id']}/answer",
                          json={"answer": "Per esempio ho programmato un sito web per la mia squadra di calcio."}).json()
        assert iv["last_feedback"]["scores"]
    assert iv["done"] and iv["status"] == "completed"
    done = student.post(f"/api/interviews/{iv['id']}/finish", json={"confidence_after": 4}).json()
    assert done["confidence_after"] == 4 and done["report"]["overall"] >= 0
    assert student.post(f"/api/interviews/{iv['id']}/answer", json={"answer": "x"}).status_code == 409


def test_real_mode_hides_feedback_until_the_end(student):
    iv = student.post("/api/interviews", json={"occupation_id": "koch_efz", "mode": "real", "length": "quick"}).json()
    iv = student.post(f"/api/interviews/{iv['id']}/answer", json={"answer": "Ich koche gern Risotto für meine Familie."}).json()
    assert iv["last_feedback"] is None and "assessment" not in iv["turns"][0]
    assert not iv["can_retry"]
    assert student.post(f"/api/interviews/{iv['id']}/retry", json={"answer": "x"}).status_code == 409


def test_retry_and_self_rating(student):
    iv = student.post("/api/interviews", json={"occupation_id": "koch_efz", "length": "quick"}).json()
    iv = student.post(f"/api/interviews/{iv['id']}/answer", json={"answer": "Ich bin Amar."}).json()
    iv = student.post(f"/api/interviews/{iv['id']}/self-rating", json={"turn_idx": 0, "rating": 3}).json()
    assert iv["turns"][0]["self_rating"] == 3
    assert iv["can_retry"]
    iv = student.post(f"/api/interviews/{iv['id']}/retry",
                      json={"answer": "Ich bin Amar, 17, und koche jeden Sonntag für meine Familie, zum Beispiel Biryani."}).json()
    assert len(iv["turns"]) == 1 and iv["turns"][0]["previous"]["answer"] == "Ich bin Amar."


def test_users_cannot_read_each_others_interviews(client):
    client.post("/api/auth/demo/student")
    iv = client.post("/api/interviews", json={"occupation_id": "koch_efz"}).json()
    client.post("/api/auth/logout")
    register(client, "other")
    assert client.get(f"/api/interviews/{iv['id']}").status_code == 404


def test_teacher_cockpit_and_consent(client):
    client.post("/api/auth/demo/teacher")
    classes = client.get("/api/classes").json()
    assert len(classes[0]["code"]) == 6 and classes[0]["students"] == 8
    overview = client.get(f"/api/classes/{classes[0]['id']}").json()
    assert overview["weak_spots"] and len(overview["students"]) == 8
    by_name = {s["name"]: s for s in overview["students"]}
    shared = client.get(f"/api/classes/{classes[0]['id']}/students/{by_name['Lea']['id']}").json()
    private = client.get(f"/api/classes/{classes[0]['id']}/students/{by_name['Elif']['id']}").json()
    assert any("detail" in s for s in shared["sessions"])  # Lea opted in
    assert all("detail" not in s for s in private["sessions"])  # Elif did not


def test_students_cannot_use_teacher_endpoints(student):
    assert student.get("/api/classes").status_code == 403


def test_join_class_with_code(client):
    register(client, "neu")
    assert client.post("/api/me/join-class", json={"code": "nope00"}).status_code == 404
    me = client.post("/api/me/join-class", json={"code": "chur26"}).json()
    assert me["classroom"]["name"] == "3. Sek A"


def test_applications_track_status_history(student):
    app = student.post("/api/applications", json={"company": "Bäckerei Gut", "occupation_id": "detailhandel_efz",
                                                   "status": "applied"}).json()
    when = (datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None).isoformat()
    upd = student.patch(f"/api/applications/{app['id']}", json={"status": "interview", "interview_at": when}).json()
    assert upd["history"][-1] == {**upd["history"][-1], "from": "applied", "to": "interview"}
    dash = student.get("/api/dashboard").json()
    assert any(a["id"] == app["id"] for a in dash["upcoming_interviews"])
    assert student.delete(f"/api/applications/{app['id']}").status_code == 200
    assert all(a["id"] != app["id"] for a in student.get("/api/applications").json())
    assert student.post(f"/api/applications/{app['id']}/restore").status_code == 200


def test_interview_for_an_application_uses_its_company(student):
    app = student.post("/api/applications", json={"company": "Pflegezentrum Calanda", "town": "Chur",
                                                   "occupation_id": "fage_efz"}).json()
    iv = student.post("/api/interviews", json={"occupation_id": "fage_efz", "application_id": app["id"]}).json()
    assert iv["company"] == {"name": "Pflegezentrum Calanda", "town": "Chur"}
    assert "Pflegezentrum Calanda" in iv["interviewer_message"]


def test_drills_are_due_and_startable(student):
    dash = student.get("/api/dashboard").json()
    assert dash["due_drills"], "seeded sessions should leave drills due"
    drill = dash["due_drills"][0]
    iv = student.post(f"/api/drills/{drill['id']}/start").json()
    assert iv["mode"] == "drill" and iv["progress"]["planned"] == 1


def test_export_and_delete_account(client):
    register(client, "gone")
    client.post("/api/interviews", json={"occupation_id": "koch_efz"})
    data = client.get("/api/me/export").json()
    assert data["account"]["username"] == "gone" and len(data["interviews"]) == 1
    assert client.delete("/api/me").status_code == 200
    assert client.post("/api/auth/login", json={"username": "gone", "password": "secret-pass-1"}).status_code == 401


def test_catalog_and_config(client):
    assert client.get("/api/config").json()["mode"] == "offline"
    cat = client.get("/api/catalog").json()
    assert len(cat["occupations"]) == 12 and "gsw" in cat["languages"]
