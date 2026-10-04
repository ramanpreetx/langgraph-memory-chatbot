"""One-time utility to export local chatbot conversations for evaluation.

This script reads conversations from the local PostgreSQL database and writes
the resulting data to conversations.json.
"""

import os
import json
import psycopg
from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver

load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")
OUTPUT_FILE = "evaluation/Extraction/10_Message/conversations.json"

if not DB_URI:
    raise ValueError("POSTGRES_URI not found in .env")


def get_thread_ids(conn):
    """
    Get all conversation/thread IDs stored by LangGraph.
    """
    rows = conn.execute(
        """
        SELECT DISTINCT thread_id
        FROM checkpoints
        ORDER BY thread_id
        """
    ).fetchall()

    return [row[0] for row in rows]


def extract_user_messages(checkpointer, thread_id):
    """
    Get the latest checkpoint for a thread and extract
    only human/user messages.
    """

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    checkpoints = list(checkpointer.list(config, limit=1))

    if not checkpoints:
        return []

    checkpoint_tuple = checkpoints[0]

    # LangGraph returns a CheckpointTuple object
    checkpoint = checkpoint_tuple.checkpoint

    channel_values = checkpoint["channel_values"]

    messages = channel_values.get("messages", [])

    user_messages = []

    for message in messages:

        if message.type != "human":
            continue

        content = message.content

        if isinstance(content, str):
            user_messages.append(content)
        else:
            user_messages.append(str(content))

    return user_messages


def main():

    results = []

    with psycopg.connect(DB_URI) as conn:

        thread_ids = get_thread_ids(conn)

        print(f"Found {len(thread_ids)} conversations.")

        checkpointer = PostgresSaver(conn)

        for index, thread_id in enumerate(thread_ids, start=1):

            user_messages = extract_user_messages(
                checkpointer,
                thread_id
            )

            if not user_messages:
                continue

            results.append(
                {
                    "conversation_id": thread_id,
                    "user_messages": user_messages
                }
            )

            print(
                f"[{index}] {thread_id} "
                f"→ {len(user_messages)} user messages"
            )

    # Keep only the 10 conversations you created
    results = results[:10]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print(f"Extracted {len(results)} conversations.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()