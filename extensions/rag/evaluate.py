import json
from pathlib import Path

from extensions.rag.assistant import EvidenceAssistant

CASES = [
    ("What are the payment terms?", "Payment terms", "30"),
    ("What is the delivery lead time?", "Lead time", "21"),
    ("What currency is specified?", "Currency", "USD"),
    ("Which Incoterm is specified?", "Incoterm", "DAP"),
    ("What service level is promised?", "Service level", "98"),
]


def main():
    assistant = EvidenceAssistant()
    results = []
    for question, clause, expected in CASES:
        response = assistant.answer(question, 1)
        evidence = response["cited_source"]
        retrieval_pass = clause.lower() in evidence["text"].lower()
        answer_pass = expected.lower() in response["answer"].lower()
        results.append(
            {
                "question": question,
                "expected": expected,
                "retrieval_pass": retrieval_pass,
                "answer_pass": answer_pass,
                "response": response,
            }
        )
    receipt = {
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "generator": "google/flan-t5-small",
        "cases": len(results),
        "retrieval_hits": sum(r["retrieval_pass"] for r in results),
        "answer_hits": sum(r["answer_pass"] for r in results),
        "results": results,
        "scope": "Small synthetic golden benchmark, not a real-document accuracy estimate",
    }
    Path("docs/rag-evaluation.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: v for k, v in receipt.items() if k != "results"}))


if __name__ == "__main__":
    main()
