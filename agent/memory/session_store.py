"""Persistent session state store for managing conversational history and state across turns."""

import json
import os
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from agent.guardrails.pii_scrubber import PIIScrubber


class SessionTurn(BaseModel):
    """Single turn in a persistent session."""

    turn_id: int
    user_query: str
    agent_response: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PersistentSessionStore:
    """Manages persistent conversational session state on disk/database across user interactions."""

    def __init__(self, storage_path: str = "agent_sessions.json"):
        self.storage_path = os.path.abspath(storage_path)
        self._sessions: Dict[str, List[Dict[str, Any]]] = self._load_store()

    def _load_store(self) -> Dict[str, List[Dict[str, Any]]]:
        """Loads sessions from persistent disk JSON file."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_store(self) -> None:
        """Saves session state to persistent disk JSON file."""
        try:
            scrubbed_sessions = PIIScrubber.scrub_data(self._sessions)
            with open(self.storage_path, "w") as f:
                json.dump(scrubbed_sessions, f, indent=2)
        except Exception:
            pass

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves conversational history for a given session ID."""
        return self._sessions.get(session_id, [])

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
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        history = self._sessions[session_id]
        turn_number = len(history) + 1

        turn = SessionTurn(
            turn_id=turn_number,
            user_query=user_query,
            agent_response=agent_response,
            metadata=metadata or {},
        )

        history.append(turn.model_dump())
        self._save_store()
        return history

    def clear_session(self, session_id: str) -> bool:
        """Clears persistent history for a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_store()
            return True
        return False
