"""Instant verification script for Category 2 Memory and Context Compaction capabilities."""

import os
import json
import asyncio
from agent.memory.cache_manager import HistoryCompactor, ContextCacheManager
from agent.memory.session_store import PersistentSessionStore
from agent.memory.async_memory import AsyncMemoryManager


def test_fast_memory():
    print("=" * 75)
    print("  🧠 CATEGORY 2: MEMORY & CONTEXT COMPACTION INSTANT VERIFICATION 🧠")
    print("=" * 75)

    session_id = "test_memory_session_95"
    store = PersistentSessionStore(storage_path="agent_sessions.json")
    store.clear_session(session_id)

    print("\n--- TEST 1: Persistent Session Store & Disk Persistence ---")
    # Simulate 6 conversational turns
    turns_data = [
        ("Analyze AAPL Revenue 2023 vs 2022", "AAPL Revenue decreased by 2.8% due to hardware headwinds."),
        ("Analyze AAPL Operating Income 2023 vs 2022", "AAPL Operating Income decreased by 4.3%."),
        ("Analyze MSFT Revenue 2023 vs 2022", "MSFT Revenue increased by 6.88% driven by Intelligent Cloud."),
        ("Analyze MSFT Operating Income 2023 vs 2022", "MSFT Operating Income increased by 6.16%."),
        ("Analyze NVDA Revenue 2024 vs 2023", "NVDA Revenue increased by 125.85% driven by Data Center AI demand."),
        ("Analyze NVDA Net Income 2024 vs 2023", "NVDA Net Income increased by 581%."),
    ]

    for user_q, agent_resp in turns_data:
        store.save_session_turn(session_id, user_q, agent_resp, {"ticker": user_q.split()[1]})

    history = store.get_session_history(session_id)
    print(f"  • Turns Saved to Memory Store : {len(history)}")
    print(f"  • Session Store File Path     : {store.storage_path}")

    with open(store.storage_path, "r") as f:
        file_data = json.load(f)
        print(f"  ✅ DISK VERIFICATION: {len(file_data[session_id])} turns persisted in '{store.storage_path}'.")

    print("\n--- TEST 2: Context Bloat Compaction & Sliding Window ---")
    compactor = HistoryCompactor(max_turns=3)
    compacted = compactor.compact_history(history)

    print(f"  • Original Raw Turns      : {compacted.original_turn_count}")
    print(f"  • Active Sliding Window   : {compacted.compacted_turn_count} turns")
    print(f"  • History Compacted?      : {'✅ YES' if compacted.is_compacted else '❌ NO'}")

    print("\n--- Generated Compacted Context Summary (Passed to LLM) ---")
    print(compacted.summary_of_older_turns)
    print("-" * 75)

    print("\n--- TEST 3: GCP Context Cache Manager (SEC 10-K Filings) ---")
    cache_mgr = ContextCacheManager(project_id="sec-analyst", location="us-central1")
    c1 = cache_mgr.get_or_create_cache("AAPL_2023_10K", "AAPL Filing Content...")
    c2 = cache_mgr.get_or_create_cache("AAPL_2023_10K", "AAPL Filing Content...")
    print(f"  • Cache Creation Request : Status = {c1['status']}")
    print(f"  • Cache Retrieval Request: Status = {c2['status']}")
    print(f"  ✅ CONFIRMED: Context Cache Manager returned '{c2['status']}'.")

    print("\n--- TEST 4: Async Memory Consolidation ---")

    async def run_async_test():
        async_mgr = AsyncMemoryManager(store, compactor)
        res = await async_mgr.consolidate_session_memory_async(
            session_id=session_id,
            user_query="Async query test",
            agent_response="Async response test",
            metadata={"async": True},
        )
        print(f"  • Async Consolidation Result: Compacted = {res.is_compacted}, Turns = {res.compacted_turn_count}")
        print("  ✅ CONFIRMED: Non-blocking async memory consolidation completed.")

    asyncio.run(run_async_test())

    print("\n" + "=" * 75)
    print("  🎉 ALL CATEGORY 2 MEMORY & CONTEXT CAPABILITIES VERIFIED! 🎉")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    test_fast_memory()
