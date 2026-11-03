"""Offline retrieval/triage evaluation; reports the complete labelled sample size."""

import json
import tempfile
from pathlib import Path

from supportforge.agent import TriagePlugin
from supportforge.config import Settings
from supportforge.knowledge import KnowledgeBase
from supportforge.store import Store


def main():
    cases = json.loads((Path(__file__).parent.parent / "evals/cases.json").read_text())
    hits = triage_hits = 0
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "evaluation.sqlite3")
        store.initialize()
        knowledge = KnowledgeBase(store)
        knowledge.ingest(Settings().knowledge_dir)
        for case in cases:
            sources = knowledge.search(case["question"], limit=3)
            retrieved = {source.document for source in sources}
            retrieval_ok = case["document"] in retrieved if case["document"] else not sources
            triage_ok = (
                json.loads(TriagePlugin().classify(case["question"]))["category"]
                == (case["category"])
            )
            hits += retrieval_ok
            triage_hits += triage_ok
            print(f"{'PASS' if retrieval_ok and triage_ok else 'FAIL'} | {case['question']}")
        print(f"Retrieval top-3 / abstention: {hits}/{len(cases)}")
        print(f"Triage accuracy: {triage_hits}/{len(cases)}")
    if hits != len(cases) or triage_hits != len(cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
