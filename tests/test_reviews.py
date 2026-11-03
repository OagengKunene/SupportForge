from concurrent.futures import ThreadPoolExecutor

import pytest

from supportforge.models import ReviewRequest, SupportRequest
from supportforge.store import ConflictError, Store


async def test_approval_is_atomic_and_idempotent(agent, store):
    run = await agent.draft(SupportRequest(message="Please help with a duplicate charge"))
    review = ReviewRequest(decision="approve", reviewer="Test Operator", note="Policy verified")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.review(run.id, review), range(2)))
    assert results[0].ticket_id == results[1].ticket_id
    assert results[0].status == "approved"
    assert store.stats()["tickets"] == 1
    audit = store.audit(run.id)
    assert [item["event"] for item in audit] == ["draft_created", "approved"]
    assert audit[1]["actor"] == "Test Operator"
    assert audit[1]["note"] == "Policy verified"


async def test_rejection_never_creates_ticket_and_conflicts_with_approval(agent, store):
    run = await agent.draft(SupportRequest(message="I forgot my password"))
    rejected = store.review(run.id, ReviewRequest(decision="reject", reviewer="Tester"))
    assert rejected.status == "rejected"
    assert rejected.ticket_id is None
    assert store.review(run.id, ReviewRequest(decision="reject", reviewer="Tester")) == rejected
    assert store.stats()["tickets"] == 0
    with pytest.raises(ConflictError, match="different decision"):
        store.review(run.id, ReviewRequest(decision="approve", reviewer="Other"))


def test_unknown_run_and_persistence(store, settings):
    assert store.get_run("missing") is None
    with pytest.raises(KeyError):
        store.review("missing", ReviewRequest(decision="approve", reviewer="Tester"))
    reopened = Store(settings.database)
    reopened.initialize()
    assert reopened.stats() == store.stats()


async def test_concurrent_idempotent_insert_reuses_saved_run(agent, store):
    from uuid import uuid4

    request = SupportRequest(message="Please explain the refund policy")
    first = await agent.draft(request, "concurrent-key")
    duplicate = first.model_copy(update={"id": uuid4().hex})
    assert store.save_run(duplicate, "concurrent-key").id == first.id
    assert store.stats()["runs"] == 1
