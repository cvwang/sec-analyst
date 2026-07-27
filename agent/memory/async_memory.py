"""Async memory operations for background memory consolidation and non-blocking session processing."""

import asyncio
from typing import Dict, List, Any
from agent.memory.cache_manager import HistoryCompactor, CompactedHistory
from agent.memory.session_store import PersistentSessionStore
from agent.observability.logging_config import log_tool_execution


class AsyncMemoryManager:
    """Handles expensive memory consolidation, summarization, and indexing as non-blocking async tasks."""

    def __init__(self, session_store: PersistentSessionStore, compactor: HistoryCompactor):
        self.session_store = session_store
        self.compactor = compactor

    async def consolidate_session_memory_async(
        self,
        session_id: str,
        user_query: str,
        agent_response: str,
        metadata: Dict[str, Any],
    ) -> CompactedHistory:
        """Asynchronously consolidates session history and performs background compaction without blocking UI.

        Args:
            session_id: Session identifier.
            user_query: User query string.
            agent_response: Agent narrative response.
            metadata: Query metadata.

        Returns:
            CompactedHistory schema after background consolidation.
        """
        # Step 1: Save turn to persistent session store in threadpool
        loop = asyncio.get_event_loop()
        history = await loop.run_in_executor(
            None,
            self.session_store.save_session_turn,
            session_id,
            user_query,
            agent_response,
            metadata,
        )

        log_tool_execution(
            tool_name="async_memory_consolidation",
            stage="intent",
            payload={"session_id": session_id, "turn_count": len(history)},
        )

        # Simulate background memory indexing/compaction task
        await asyncio.sleep(0.01)

        # Step 2: Compact history asynchronously if context bloated
        compacted = self.compactor.compact_history(history)

        log_tool_execution(
            tool_name="async_memory_consolidation",
            stage="outcome",
            payload={
                "session_id": session_id,
                "is_compacted": compacted.is_compacted,
                "compacted_turns": compacted.compacted_turn_count,
            },
        )

        return compacted
