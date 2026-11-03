"""Black-box HTTP check for a running demo/test deployment. Creates local test data."""

import json
import os
import sys
from uuid import uuid4

import httpx


def main():
    origin = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    token = os.getenv("SUPPORTFORGE_API_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=origin, headers=headers, timeout=60) as client:
        health = client.get("/healthz")
        health.raise_for_status()
        assert health.json()["status"] == "ok"
        assert "SupportForge" in client.get("/").text
        assert client.get("/api/meta").json()["mode"] == "demo", "Use a demo/test instance"
        key = uuid4().hex
        payload = {"customer_name": "SMOKE TEST", "message": "I was charged twice for my invoice"}
        result = client.post("/api/runs", json=payload, headers={"Idempotency-Key": key})
        result.raise_for_status()
        run = result.json()
        assert run["sources"] and run["status"] == "pending"
        retry = client.post("/api/runs", json=payload, headers={"Idempotency-Key": key})
        assert retry.json()["id"] == run["id"]
        review_url = f"/api/runs/{run['id']}/review"
        review = {"decision": "approve", "reviewer": "Automated smoke test"}
        approved = client.post(review_url, json=review)
        approved.raise_for_status()
        ticket = approved.json()["ticket_id"]
        assert ticket and client.post(review_url, json=review).json()["ticket_id"] == ticket
        assert len(client.get(f"/api/runs/{run['id']}/audit").json()) == 2
        print(
            json.dumps(
                {
                    "health": "ok",
                    "draft": "ok",
                    "sources": len(run["sources"]),
                    "approval": "ok",
                    "duplicate_protection": "ok",
                    "ticket_id": ticket,
                }
            )
        )


if __name__ == "__main__":
    main()
