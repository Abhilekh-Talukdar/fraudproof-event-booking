def test_oversized_request_body_returns_json_413(client, app):
    limit = app.config["MAX_CONTENT_LENGTH"]
    response = client.post(
        "/api/auth/login",
        data=b"x" * (limit + 1),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "error": "request_too_large",
        "message": "Request body exceeds the configured size limit.",
    }
