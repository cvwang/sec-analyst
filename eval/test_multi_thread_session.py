"""Pytest unit tests for multi-thread session management & persistence."""

import os
import json
import tempfile
import pytest
from fastapi.testclient import TestClient

from agent.memory.session_store import PersistentSessionStore, SessionMetadata
from agent.api import app

client = TestClient(app)


def test_session_store_crud():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        store = PersistentSessionStore(storage_path=tmp_path)
        
        # 1. Initially empty
        sessions = store.list_sessions()
        assert len(sessions) == 0

        # 2. Create session
        meta = store.create_session(title="Apple Analysis")
        assert meta["title"] == "Apple Analysis"
        sid = meta["session_id"]

        # 3. Retrieve session
        sess = store.get_session(sid)
        assert sess is not None
        assert sess["metadata"]["title"] == "Apple Analysis"

        # 4. Save turn
        turns = store.save_session_turn(
            session_id=sid,
            user_query="What was AAPL revenue in 2023?",
            agent_response="AAPL revenue in 2023 was $383,285 million.",
            metadata={"ticker": "AAPL"},
        )
        assert len(turns) == 1
        assert turns[0]["user_query"] == "What was AAPL revenue in 2023?"

        # 5. Save last response
        store.save_last_response(sid, {"is_success": True, "ticker": "AAPL"})
        sess_updated = store.get_session(sid)
        assert sess_updated["last_response"]["is_success"] is True

        # 6. Update title
        store.update_session_title(sid, "AAPL FY23 Revenue")
        assert store.get_session(sid)["metadata"]["title"] == "AAPL FY23 Revenue"

        # 7. List sessions
        s_list = store.list_sessions()
        assert len(s_list) == 1
        assert s_list[0]["title"] == "AAPL FY23 Revenue"

        # 8. Delete session
        store.delete_session(sid)
        assert len(store.list_sessions()) == 0

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_legacy_session_migration():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        legacy_data = {
            "legacy_sess_001": [
                {
                    "turn_id": 1,
                    "user_query": "Compare MSFT and AAPL net income",
                    "agent_response": "Here is the comparison...",
                    "metadata": {"ticker": "AAPL"}
                }
            ]
        }
        json.dump(legacy_data, tmp)
        tmp_path = tmp.name

    try:
        store = PersistentSessionStore(storage_path=tmp_path)
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "legacy_sess_001"
        assert "Compare MSFT and AAPL" in sessions[0]["title"]
        assert sessions[0]["turn_count"] == 1
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_api_session_endpoints():
    # 1. Create session via REST API
    res = client.post("/api/v1/sessions", json={"title": "Test REST Thread"})
    assert res.status_code == 200
    meta = res.json()
    sid = meta["session_id"]
    assert meta["title"] == "Test REST Thread"

    # 2. List sessions
    res_list = client.get("/api/v1/sessions")
    assert res_list.status_code == 200
    sessions = res_list.json().get("sessions", [])
    assert any(s["session_id"] == sid for s in sessions)

    # 3. Get session details
    res_detail = client.get(f"/api/v1/sessions/{sid}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["metadata"]["session_id"] == sid

    # 4. Patch session title
    res_patch = client.patch(f"/api/v1/sessions/{sid}", json={"title": "Updated Title"})
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Updated Title"

    # 6. Delete session
    res_del = client.delete(f"/api/v1/sessions/{sid}")
    assert res_del.status_code == 200

    # 7. Verify 404 after deletion
    res_404 = client.get(f"/api/v1/sessions/{sid}")
    assert res_404.status_code == 404


def test_grounded_context_persistence_across_threads():
    """Verifies that grounded context (text_chunks, citations) is persisted and isolated per thread."""
    # Create thread A
    res_a = client.post("/api/v1/sessions", json={"title": "Apple Thread"})
    sid_a = res_a.json()["session_id"]

    # Save turn with grounded context in Thread A
    grounded_data_a = {
        "is_success": True,
        "ticker": "AAPL",
        "hybrid_search_result": {
            "text_chunks": [
                {
                    "company_name": "Apple Inc.",
                    "fiscal_year": 2023,
                    "section": "Item 7 - MD&A",
                    "content": "Total net sales were $383,285 million...",
                    "citation": "AAPL 10-K Filing",
                    "gcs_uri": "gs://sec-analyst-sec-reports/filings/AAPL_2023_Item7_MDA.md",
                }
            ],
            "grounded_citations": ["AAPL 10-K Filing"],
            "query_type": "financial_summary",
        },
    }

    # Save turn via store directly
    store = app.state if hasattr(app, "state") else None
    from agent.api import orchestrator
    orchestrator.session_store.save_session_turn(
        session_id=sid_a,
        user_query="Analyze Apple revenue 2023",
        agent_response="Apple 2023 revenue was $383,285M.",
        metadata={"last_response": grounded_data_a},
    )
    orchestrator.session_store.save_last_response(sid_a, grounded_data_a)

    # Retrieve Thread A details
    res_get_a = client.get(f"/api/v1/sessions/{sid_a}")
    assert res_get_a.status_code == 200
    detail_a = res_get_a.json()
    assert detail_a["last_response"]["ticker"] == "AAPL"
    assert len(detail_a["last_response"]["hybrid_search_result"]["text_chunks"]) == 1

    # Cleanup Thread A
    client.delete(f"/api/v1/sessions/{sid_a}")


def test_clear_all_sessions_api():
    """Verifies DELETE /api/v1/sessions resets all stored conversation threads."""
    client.post("/api/v1/sessions", json={"title": "Temp Thread 1"})
    client.post("/api/v1/sessions", json={"title": "Temp Thread 2"})

    res_clear = client.delete("/api/v1/sessions")
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "SUCCESS"

    res_list = client.get("/api/v1/sessions")
    assert len(res_list.json()["sessions"]) == 0


def test_constitution_source_citation_rule():
    """Verifies that SYSTEM_CONSTITUTION contains Rule 7 for granular source citation formatting."""
    from agent.constitution import SYSTEM_CONSTITUTION
    assert "GRANULAR GROUNDED SOURCE CITATION RULE" in SYSTEM_CONSTITUTION
    assert "(Source: <Ticker> <Year> 10-K <Section>, <gcs_uri>)" in SYSTEM_CONSTITUTION

