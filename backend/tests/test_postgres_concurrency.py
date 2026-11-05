import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest

from app import db
from app.models import Inventory, OutboxEvent, OutboxEventStatus, Reservation, ReservationStatus
from app.services.reservations import InsufficientInventory, create_reservation
from app.services.tickets import TicketRejected, verify_and_consume
from app.services.worker import register_handler, run_worker_cycle


pytestmark = pytest.mark.skipif(
    not os.environ.get("FRAUDPROOF_TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="Requires an explicit disposable PostgreSQL test database.",
)


def test_one_hundred_competing_buyers_cannot_oversell(app, event_factory):
    event_id = event_factory(capacity=10)
    barrier = Barrier(100)

    def reserve(index):
        with app.app_context():
            barrier.wait()
            try:
                create_reservation(event_id=event_id, quantity=1, idempotency_key=f"concurrent-{index}", ttl_seconds=300)
                return "reserved"
            except InsufficientInventory:
                return "sold_out"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=100) as executor:
        outcomes = list(executor.map(reserve, range(100)))

    assert outcomes.count("reserved") == 10
    assert outcomes.count("sold_out") == 90
    with app.app_context():
        inventory = db.session.get(Inventory, event_id)
        assert inventory.sold_quantity == 0
        assert inventory.reserved_quantity == 10
        assert inventory.available_quantity == 0
        assert inventory.total_quantity == inventory.available_quantity + inventory.reserved_quantity + inventory.sold_quantity
        assert db.session.query(Reservation).filter_by(status=ReservationStatus.HELD).count() == 10


def test_two_concurrent_scans_admit_a_signed_ticket_exactly_once(app, client, event_factory):
    event_id = event_factory(capacity=1)
    reservation = client.post(
        "/api/reservations",
        json={"eventId": event_id, "quantity": 1, "attendeeNames": ["Scanner Test"]},
        headers={"Idempotency-Key": "scan-reservation"},
    ).json
    payment = client.post(
        f"/api/reservations/{reservation['reservationId']}/mock-payment",
        json={"outcome": "APPROVED"},
        headers={"Idempotency-Key": "scan-payment"},
    ).json
    token = payment["tickets"][0]["token"]
    barrier = Barrier(2)

    def scan():
        with app.app_context():
            barrier.wait()
            try:
                verify_and_consume(token=token, expected_event_id=event_id)
                return "accepted"
            except TicketRejected:
                return "rejected"
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: scan(), range(2)))

    assert outcomes.count("accepted") == 1
    assert outcomes.count("rejected") == 1



def test_two_concurrent_workers_claim_distinct_outbox_events(app):
    barrier = Barrier(2)
    lock = Lock()
    processed = []

    def handler(event):
        # Keep both worker calls in the handler at the same time. If claiming
        # is not atomic, this can expose duplicate or missing work.
        barrier.wait(timeout=15)
        with lock:
            processed.append(event.id)

    with app.app_context():
        register_handler("concurrent.worker_test", handler)
        events = [
            OutboxEvent(
                event_type="concurrent.worker_test",
                aggregate_id=f"worker-aggregate-{index}",
                payload={"index": index},
            )
            for index in range(2)
        ]
        db.session.add_all(events)
        db.session.commit()
        expected_ids = {event.id for event in events}

    def run_one_batch():
        with app.app_context():
            try:
                return run_worker_cycle(batch_size=1)
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_one_batch(), range(2)))

    assert results == [1, 1]
    assert set(processed) == expected_ids
    assert len(processed) == len(expected_ids)

    with app.app_context():
        states = db.session.query(OutboxEvent).filter(OutboxEvent.id.in_(expected_ids)).all()
        assert len(states) == 2
        assert all(event.status == OutboxEventStatus.DONE for event in states)
