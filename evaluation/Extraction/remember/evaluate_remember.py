import json
from langchain_core.messages import HumanMessage
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[3]))

from memory import extract_memories
from evaluation.Extraction.remember.remember_cases import REMEMBER_CASES


def generate_results():

    results = []

    for index, case in enumerate(REMEMBER_CASES, start=1):

        print(f"Processing case {index}/{len(REMEMBER_CASES)}")
        print(f"Input: {case['input']}")

        message = HumanMessage(content=case["input"])

        try:
            extracted = extract_memories([message])

            generated = [
                {
                    "memory": memory.memory,
                    "type": memory.type,
                }
                for memory in extracted
            ]

            print("Generated:")

            if generated:
                for memory in generated:
                    print(
                        f"  - {memory['memory']} "
                        f"[{memory['type']}]"
                    )
            else:
                print("  - No memories")

            results.append({
                "case": index,
                "input": case["input"],
                "expected": case["expected"],
                "generated": generated,
            })

        except Exception as e:

            print(f"ERROR: {e}")

            results.append({
                "case": index,
                "input": case["input"],
                "expected": case["expected"],
                "generated": [],
                "error": str(e),
            })

        print("-" * 60)

    with open("evaluation/Extraction/remember/remember_results.json", "w", encoding="utf-8",) as file:

        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("Results saved to:")
    print("evaluation/Extraction/remember/remember_results.json")


if __name__ == "__main__":
    generate_results()