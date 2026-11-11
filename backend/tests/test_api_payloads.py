import json


def test_mutation_endpoints_handle_non_object_json_without_server_errors(client):
    malformed_bodies = [
        ("/api/auth/register", [], 400, {}),
        ("/api/auth/login", "not-an-object", 401, {}),
        (
            "/api/reservations",
            ["unexpected", "array"],
            400,
            {"Idempotency-Key": "non-object-reservation"},
        ),
        (
            "/api/reservations/00000000-0000-0000-0000-000000000000/mock-payment",
            "unexpected",
            409,
            {"Idempotency-Key": "non-object-payment"},
        ),
        ("/api/tickets/verify", [1, 2, 3], 400, {}),
        ("/api/bookings", ["unexpected"], 400, {}),
    ]

    for path, payload, expected_status, headers in malformed_bodies:
        response = client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            headers=headers,
        )
        assert response.status_code == expected_status, (
            f"{path} returned {response.status_code} for a non-object JSON body"
        )
