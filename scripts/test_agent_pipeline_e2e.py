import os
import time

os.environ["LLM_API_KEY"] = ""

from fastapi.testclient import TestClient
from sqlalchemy import bindparam, text

from backend.app.database.session import SessionLocal
from backend.app.main import app


def main() -> None:
    marker = str(int(time.time() * 1000))
    username = f"agent_pipeline_{marker}"
    password = f"Agent-{marker}-Aa9!"
    user_id = None
    conversation_ids: list[str] = []
    client = TestClient(app)
    try:
        registered = client.post(
            "/api/register",
            json={"username": username, "password": password, "nickname": "智能体回归", "role": "student"},
        )
        assert registered.status_code == 200, registered.text
        user_id = int(registered.json()["user_id"])

        response = client.get("/api/diagnose")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["user_id"] == user_id
        assert isinstance(payload["weak_points"], list)
        assert isinstance(payload["strategy"], dict)
        assert payload["needs_first_test"] is True
        assert payload["negotiation"]["rounds_used"] <= 3
        assert payload["negotiation"]["duration_ms"] >= 0
        conversation_ids.append(payload["negotiation"]["conversation_id"])

        with SessionLocal() as db:
            calls = int(
                db.execute(
                    text("SELECT COUNT(*) FROM llm_call_log WHERE conversation_id=:conversation_id"),
                    {"conversation_id": conversation_ids[0]},
                ).scalar()
                or 0
            )
        assert calls >= 4
        print("AGENT_PIPELINE_E2E_OK")
    finally:
        client.close()
        if user_id is not None:
            with SessionLocal() as db:
                if conversation_ids:
                    statement = text("DELETE FROM llm_call_log WHERE conversation_id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    )
                    db.execute(statement, {"ids": conversation_ids})
                db.execute(text("DELETE FROM negotiation_log WHERE user_id=:user_id"), {"user_id": user_id})
                db.execute(text("DELETE FROM auth_sessions WHERE user_id=:user_id"), {"user_id": user_id})
                db.execute(text("DELETE FROM users WHERE id=:user_id"), {"user_id": user_id})
                db.commit()


if __name__ == "__main__":
    main()
