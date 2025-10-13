from backend.auth.passwords import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    raw = "S3cretPass!"
    hashed = hash_password(raw)

    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong", hashed) is False
