import os
import json
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.store.postgres import PostgresStore

from candidates import candidates
from existing_memory import memories


load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=1,
    max_size=5,
    kwargs={"autocommit": True},
)

store = PostgresStore(
    pool,
    index={
        "dims": 384,
        "embed": embeddings,
        "fields": ["text"],
    },
)

store.setup()


# Separate namespace only for retrieval evaluation
namespace = ("retrieval_eval", "memories")


# Put existing_memory.py memories into the store
for memory_id, memory_text in memories.items():

    store.put(
        namespace,
        memory_id,
        {
            "text": memory_text,
            "status": "active",
        },
    )


# Evaluate retrieval
evaluation_results = {}

recall_hits = 0
recall_total = 0

for case in candidates:

    results = store.search(
        namespace,
        query=case["candidate"],
        limit=5,
        filter={"status": "active"},
    )

    retrieved_ids = [result.key for result in results]
    expected_ids = case["expected_relevant_ids"]

    # Recall@5
    if expected_ids:
        recall_total += 1
        if set(retrieved_ids) & set(expected_ids):
            recall_hits += 1

    evaluation_results[case["candidate_id"]] = {
        "candidate": case["candidate"],
        "expected": expected_ids,
        "retrieved": retrieved_ids,
    }


recall = recall_hits / recall_total if recall_total else 0

evaluation_results["final"] = {
    "recall_at_5": round(recall, 4)
}


with open("evaluation/Resolution_retrieval/retrieval_results.json", "w", encoding="utf-8") as f:
    json.dump(evaluation_results, f, indent=4)

pool.close()