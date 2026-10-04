import json
from types import SimpleNamespace
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from memory import Memory, resolve_memory


with open("evaluation/Resolver/resolver_cases.json", "r", encoding="utf-8") as f:
    cases = json.load(f)


results = []
correct = 0

for case_id, case in cases.items():

    candidate = Memory(
        memory=case["candidate"],
        type="fact"
    )

    existing_memories = [
        SimpleNamespace(
            key=m["id"],
            value={"text": m["text"]}
        )
        for m in case["existing_memories"]
    ]

    result = resolve_memory(candidate, existing_memories)
    decision = result.decisions[0]

    expected_action = case["expected_action"]

    passed = decision.operation == expected_action

    if expected_action in {"NOOP", "UPDATE", "DELETE"}:
        expected_id = case["expected_memory_id"]

        if isinstance(expected_id, list):
            passed = passed and decision.target_memory_id in expected_id
        else:
            passed = passed and decision.target_memory_id == expected_id

    if passed:
        correct += 1

    results.append({
        "case_id": case_id,
        "expected_action": expected_action,
        "actual_action": decision.operation,
        "expected_memory_id": case.get("expected_memory_id"),
        "actual_memory_id": decision.target_memory_id,
        "correct": passed,
        "justification": decision.justification
    })

    print(f"{case_id}: {'PASS' if passed else 'FAIL'}")


# Save results
output = {
    "total_cases": len(cases),
    "correct": correct,
    "accuracy": correct / len(cases),
    "results": results
}

with open("evaluation/Resolver/resolver_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4)


print("\n--------------------")
print(f"Accuracy: {correct}/{len(cases)} ({correct / len(cases):.0%})")
print("Results saved to evaluation/Resolver/resolver_results.json")