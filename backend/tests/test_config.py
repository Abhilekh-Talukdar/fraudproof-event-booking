from app.config import parse_cors_origins


def test_parse_cors_origins_trims_whitespace_and_ignores_empty_entries():
    assert parse_cors_origins(
        " http://localhost:4200, https://app.example.test , ,http://127.0.0.1:4200 "
    ) == [
        "http://localhost:4200",
        "https://app.example.test",
        "http://127.0.0.1:4200",
    ]


def test_parse_cors_origins_uses_local_default_when_unset():
    assert parse_cors_origins() == ["http://localhost:4200"]


def test_parse_cors_origins_keeps_empty_allowlist_empty():
    assert parse_cors_origins(" ,  , ") == []
