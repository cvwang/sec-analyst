"""Context bloat management, history compaction, and context caching for Gemini & ADK."""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from agent.observability.logging_config import log_tool_execution

logger = logging.getLogger("sec_edgar_agent.memory")


class CompactedHistory(BaseModel):
    """Result of conversational history compaction."""

    original_turn_count: int
    compacted_turn_count: int
    summary_of_older_turns: str
    active_history: List[Dict[str, Any]]
    is_compacted: bool


class HistoryCompactor:
    """Sliding window history compactor and summarizer for managing context bloat."""

    def __init__(self, max_turns: int = 5, max_chars_per_turn: int = 1500):
        self.max_turns = max_turns
        self.max_chars_per_turn = max_chars_per_turn

    def compact_history(
        self,
        history: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
    ) -> CompactedHistory:
        """Truncates and summarizes conversation history to prevent context bloat.

        Args:
            history: List of conversation turn dicts [{'role': 'user'|'agent', 'content': '...'}].
            system_instruction: Optional system prompt to preserve.

        Returns:
            CompactedHistory schema containing active turns and older summary.
        """
        original_count = len(history)

        if original_count <= self.max_turns:
            return CompactedHistory(
                original_turn_count=original_count,
                compacted_turn_count=original_count,
                summary_of_older_turns="",
                active_history=history,
                is_compacted=False,
            )

        # Separate older turns from active sliding window turns
        older_turns = history[:-self.max_turns]
        active_turns = history[-self.max_turns:]

        # Summarize older turns into a compact context summary
        summary_lines = []
        for turn in older_turns:
            role = turn.get("role", "unknown").upper()
            content = str(turn.get("content", ""))[:200]  # Truncate content preview
            summary_lines.append(f"[{role}]: {content}...")

        summary_text = "Prior Conversation Summary:\n" + "\n".join(summary_lines)

        log_tool_execution(
            tool_name="history_compaction",
            stage="outcome",
            payload={
                "original_count": original_count,
                "compacted_count": len(active_turns),
                "summary_length": len(summary_text),
            },
        )

        return CompactedHistory(
            original_turn_count=original_count,
            compacted_turn_count=len(active_turns),
            summary_of_older_turns=summary_text,
            active_history=active_turns,
            is_compacted=True,
        )


class ContextCacheManager:
    """Manages GCP Vertex AI Context Caching for large SEC 10-K filing documents."""

    def __init__(self, project_id: str, location: str):
        self.project_id = project_id
        self.location = location
        self._cached_contexts: Dict[str, Dict[str, Any]] = {}

    def get_or_create_cache(
        self,
        cache_key: str,
        content: str,
        ttl_minutes: int = 60,
    ) -> Dict[str, Any]:
        """Simulates/manages Vertex AI context caching for 10-K filing documents.

        Args:
            cache_key: Unique identifier for filing document (e.g. AAPL_2023_10K).
            content: Raw filing text content.
            ttl_minutes: Cache time-to-live.

        Returns:
            Dictionary containing cache metadata and status.
        """
        if cache_key in self._cached_contexts:
            return {
                "cache_key": cache_key,
                "status": "CACHE_HIT",
                "content_length": len(content),
                "ttl_minutes": ttl_minutes,
            }

        self._cached_contexts[cache_key] = {
            "content": content,
            "ttl": ttl_minutes,
        }
        return {
            "cache_key": cache_key,
            "status": "CACHE_CREATED",
            "content_length": len(content),
            "ttl_minutes": ttl_minutes,
        }
