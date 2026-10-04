import json
import sys
from pathlib import Path
from langchain_core.messages import HumanMessage

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from memory import extract_memories

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "conversation_with_expected.json"
OUTPUT_FILE = BASE_DIR / "extraction_results.json"


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    conversations = json.load(f)


print(f"Found {len(conversations)} conversations.")


results = []

for index, conversation in enumerate(conversations, start=1):

    conversation_id = conversation["conversation_id"]
    user_messages = conversation["user_messages"]
    expected_memories = conversation.get("expected_memories", [])

    print(
        f"\n[{index}/{len(conversations)}] "
        f"Processing {conversation_id}"
    )

    # Convert raw user messages into LangChain messages
    messages = [
        HumanMessage(content=message)
        for message in user_messages
    ]

    error = None

    try:

        generated = extract_memories(messages)

        generated_memories = [
            {
                "memory": memory.memory,
                "type": memory.type
            }
            for memory in generated
        ]

    except Exception as e:

        print(f"Extraction failed: {e}")

        generated_memories = []

        error = str(e)

    results.append(
        {
            "conversation_id": conversation_id,
            "conversation": user_messages,
            "expected_memories": expected_memories,
            "generated_memories": generated_memories,
            "error": error if error else None,
        }
    )

    print(
        f"Expected: {len(expected_memories)} | "
        f"Generated: {len(generated_memories)}"
    )


with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(
        results,
        f,
        indent=2,
        ensure_ascii=False
    )

print("Extraction evaluation completed.")
print(f"Saved to: {OUTPUT_FILE}")