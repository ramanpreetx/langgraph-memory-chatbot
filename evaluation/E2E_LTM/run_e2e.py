import json
import uuid
import os
import time

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.store.postgres import PostgresStore
from langchain_core.messages import HumanMessage

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from memory import run_memory_pipeline, create_embedding_config


load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")


def create_store():
    pool = ConnectionPool(

        conninfo=DB_URI,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True},
    )

    store = PostgresStore(
        pool,
        index=create_embedding_config(),
    )

    store.setup()

    return store


def seed_memories(store, user_id, memories):
    namespace = (user_id, "memories")

    for memory in memories:
        store.put(
            namespace,
            memory["id"],
            {
                "text": memory["text"],
                "type": memory["type"],
                "status": "active",
                "version": 1,
                "source_thread_id": "eval",
            },
        )


def main():
    with open("evaluation/E2E_LTM/existing_memory.json") as f:            
        memories = json.load(f)

    with open("evaluation/E2E_LTM/LTM_automatic_cases.json") as f:
        automatic_cases = json.load(f)

    with open("evaluation/E2E_LTM/LTM_explicit_cases.json") as f:
        explicit_cases = json.load(f)

    store = create_store()

    results = {
    "automatic": {},
    "explicit": {},
    }

    for dataset_name, cases in [
        ("automatic", automatic_cases),
        ("explicit", explicit_cases),
    ]:
        for case_id, case in cases.items():

            user_id = f"eval_{uuid.uuid4()}"
            thread_id = str(uuid.uuid4())

            seed_memories(
                store,
                user_id,
                memories,
            )

            messages = [
                HumanMessage(content=text)
                for text in case["conversation"]
            ]

            eval_results = {}

            try:
                run_memory_pipeline(
                    store,
                    user_id,
                    thread_id,
                    messages,
                    0,
                    apply_decisions=False,
                    eval_results=eval_results,
                )
            except Exception as e:
                print(f"{dataset_name} {case_id}: ERROR - {type(e).__name__}")

                results[dataset_name][case_id] = {
                    "conversation": case["conversation"],
                    "expected_memories": case["expected_memories"],
                    "error": type(e).__name__,
                    "error_message": str(e),
                }

                time.sleep(10)
                continue

            results[dataset_name][case_id] = {
                "conversation": case["conversation"],
                "expected_memories": case["expected_memories"],
                **eval_results,
            }

            actual = [
                {
                    "operation": result["resolution_result"]["operation"],
                    "expected_memory_id": result["resolution_result"]["target_memory_id"],
                }
                for result in eval_results.get("extraction_result", [])
            ]

            expected = case["expected_memories"]

            if sorted(actual, key=str) == sorted(expected, key=str):
                print(f"{dataset_name} {case_id}: PASS")
            else:
                print(f"{dataset_name} {case_id}: FAIL")

            time.sleep(10)


    with open("evaluation/E2E_LTM/e2e_results.json", "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\nE2E evaluation complete.")
    print("Results saved to e2e_results.json")

if __name__ == "__main__":
    main()