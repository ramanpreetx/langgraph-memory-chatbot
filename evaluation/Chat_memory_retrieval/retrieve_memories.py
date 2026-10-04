import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.store.postgres import PostgresStore

sys.path.append(str(Path(__file__).resolve().parents[2]))

load_dotenv()

from memory import create_embedding_config
from evaluation.Chat_memory_retrieval.existing_memories import existing_memories
from evaluation.Chat_memory_retrieval.threshold_cases import chat_retrieval_cases


DB_URI = os.getenv("POSTGRES_URI")
USER_ID = "test_user"

OUTPUT_FILE = Path(__file__).resolve().parent / "chat_retrieval_results.json"

namespace = (USER_ID, "memories")


store_pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=1,
    max_size=5,
    kwargs={"autocommit": True},
    check=ConnectionPool.check_connection,
)

store_pool.open()

store = PostgresStore(
    store_pool,
    index=create_embedding_config(),
)

store.setup()


for memory_id, text in existing_memories.items():
    store.put(
        namespace,
        memory_id,
        {
            "text": text,
            "status": "active",
        },
    )

print(f"Seeded {len(existing_memories)} memories.")


results = []

for case in chat_retrieval_cases:

    retrieved = store.search(
        namespace,
        query=case["query"],
        limit=5,
        filter={"status": "active"},
    )

    results.append(
        {
            "case": case["case"],
            "text": case["query"],
            "expected": case["expected_relevant"],
            "retrieved": [
                {
                    "memory_id": memory.key,
                    "score": memory.score,
                }
                for memory in retrieved
            ],
        }
    )

thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

threshold_evaluation = []

for threshold in thresholds:
    positive_total = 0
    positive_found = 0
    negative_cases = 0
    negative_false_positives = 0

    for result in results:
        retrieved_above_threshold = {
            item["memory_id"]
            for item in result["retrieved"]
            if item["score"] >= threshold
        }

        expected = set(result["expected"])

        if result["case"].startswith("positive"):
            positive_total += len(expected)
            positive_found += len(expected & retrieved_above_threshold)

        elif result["case"].startswith("negative"):
            negative_cases += 1

            if retrieved_above_threshold:
                negative_false_positives += 1

    recall = (
        positive_found / positive_total
        if positive_total
        else 0
    )

    false_positive_rate = (
        negative_false_positives / negative_cases
        if negative_cases
        else 0
    )

    threshold_evaluation.append(
        {
            "threshold": threshold,
            "positive_recall": round(recall, 3),
            "negative_false_positive_rate": round(false_positive_rate, 3),
        }
    )

# Add threshold evaluation at the end of the results JSON
output = {
    "cases": results,
    "threshold_evaluation": threshold_evaluation,
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("\nThreshold evaluation:")

for item in threshold_evaluation:
    print(
        f"threshold={item['threshold']:.2f} | "
        f"positive_recall={item['positive_recall']:.3f} | "
        f"negative_false_positive_rate={item['negative_false_positive_rate']:.3f}"
    )

print(f"Saved {len(results)} cases to {OUTPUT_FILE}")