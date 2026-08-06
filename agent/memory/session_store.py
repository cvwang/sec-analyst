"""Persistent session state store for managing multi-thread conversational history and state across turns."""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class SessionTurn(BaseModel):
    """Single turn in a persistent session."""

    turn_id: int
    user_query: str
    agent_response: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionMetadata(BaseModel):
    """Header metadata for a conversation thread."""

    session_id: str
    title: str = "New Analysis"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    turn_count: int = 0
    last_preview: str = ""


class PersistentSessionStore:
    """Manages persistent multi-thread conversational session state on disk/database."""

    def __init__(self, storage_path: str = "agent_sessions.json"):
        self.storage_path = os.path.abspath(storage_path)
        self._store: Dict[str, Dict[str, Any]] = self._load_store()

    def _load_store(self) -> Dict[str, Dict[str, Any]]:
        """Loads sessions from persistent disk JSON file with automatic legacy migration."""
        if not os.path.exists(self.storage_path):
            return {}

        try:
            with open(self.storage_path, "r") as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                return {}

            store: Dict[str, Dict[str, Any]] = {}
            now_iso = datetime.now(timezone.utc).isoformat()

            for key, val in raw_data.items():
                if isinstance(val, list):
                    # Legacy migration: val is a list of SessionTurns
                    turns = val
                    first_query = turns[0].get("user_query", "New Analysis") if turns else "New Analysis"
                    title = first_query[:40] + ("..." if len(first_query) > 40 else "")
                    last_query = turns[-1].get("user_query", "") if turns else ""

                    meta = SessionMetadata(
                        session_id=key,
                        title=title,
                        created_at=now_iso,
                        updated_at=now_iso,
                        turn_count=len(turns),
                        last_preview=last_query[:60],
                    )

                    store[key] = {
                        "metadata": meta.model_dump(),
                        "turns": turns,
                        "last_response": None,
                    }
                elif isinstance(val, dict) and "metadata" in val:
                    store[key] = val
                else:
                    # Fallback empty format
                    meta = SessionMetadata(session_id=key, title="New Analysis")
                    store[key] = {
                        "metadata": meta.model_dump(),
                        "turns": [],
                        "last_response": None,
                    }

            return store
        except Exception:
            return {}

    def _save_store(self) -> None:
        """Saves session state to persistent disk JSON file."""
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self._store, f, indent=2)
        except Exception:
            pass

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lists all conversation thread metadata summaries, sorted by updated_at descending."""
        summaries = [s["metadata"] for s in self._store.values() if "metadata" in s]
        return sorted(summaries, key=lambda x: x.get("updated_at", ""), reverse=True)

    def create_session(self, session_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Explicitly creates a new conversation session thread."""
        sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        t = title or "New Analysis"

        meta = SessionMetadata(
            session_id=sid,
            title=t,
            created_at=now_iso,
            updated_at=now_iso,
            turn_count=0,
            last_preview="",
        )

        session_obj = {
            "metadata": meta.model_dump(),
            "turns": [],
            "last_response": None,
        }

        self._store[sid] = session_obj
        self._save_store()
        return meta.model_dump()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete session object including metadata, turns history, and last response."""
        if session_id not in self._store:
            return None
        return self._store[session_id]

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves conversational history turns for a given session ID."""
        session = self.get_session(session_id)
        if session:
            return session.get("turns", [])
        return []

    def save_session_turn(
        self,
        session_id: str,
        user_query: str,
        agent_response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Saves a conversation turn to persistent session state.

        Args:
            session_id: Unique session identifier.
            user_query: User query text.
            agent_response: Agent narrative response.
            metadata: Optional execution metadata (ticker, variance, model).

        Returns:
            Updated conversation history list for the session.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        if session_id not in self._store:
            self.create_session(session_id=session_id)

        session = self._store[session_id]
        meta = session["metadata"]
        turns = session["turns"]

        # Auto-update title on first query if title is default
        if meta.get("title") in ("New Analysis", "Conversation Session", "", None) and user_query:
            clean_q = user_query.strip()
            meta["title"] = clean_q[:40] + ("..." if len(clean_q) > 40 else "")

        turn_number = len(turns) + 1
        turn = SessionTurn(
            turn_id=turn_number,
            user_query=user_query,
            agent_response=agent_response,
            metadata=metadata or {},
        )

        turns.append(turn.model_dump())

        if metadata and "last_response" in metadata:
            session["last_response"] = metadata["last_response"]

        # Update metadata stats
        meta["updated_at"] = now_iso
        meta["turn_count"] = len(turns)
        meta["last_preview"] = user_query[:60]

        self._save_store()
        return turns

    def save_last_response(self, session_id: str, response_data: Dict[str, Any]) -> None:
        """Persists the latest AnalysisResponse payload for restoring split-pane source drawer."""
        if session_id in self._store:
            self._store[session_id]["last_response"] = response_data
            self._store[session_id]["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_store()

    def update_session_title(self, session_id: str, title: str) -> Optional[Dict[str, Any]]:
        """Updates the custom display title of a session thread."""
        if session_id not in self._store:
            return None
        self._store[session_id]["metadata"]["title"] = title
        self._store[session_id]["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_store()
        return self._store[session_id]["metadata"]

    def delete_session(self, session_id: str) -> bool:
        """Deletes a conversation session thread from persistent storage."""
        if session_id in self._store:
            del self._store[session_id]
            self._save_store()
            return True
        return False

    def clear_all_sessions(self) -> None:
        """Clears all persistent conversation session threads in memory and on disk."""
        self._store = {}
        self._save_store()

    def clear_session(self, session_id: str) -> bool:
        """Clears persistent history for a session."""
        return self.delete_session(session_id)


