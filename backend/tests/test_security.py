from datetime import timedelta

import pytest
from passlib.hash import bcrypt

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)


def test_new_passwords_use_argon2id_with_distinct_salts():
    password = "বাংলা" * 20
    first = hash_password(password)
    second = hash_password(password)
    assert first.startswith("$argon2id$") and first != second
    assert verify_password(password, first)
    assert not verify_password(password + "!", first)
    assert not password_needs_rehash(first)
    assert not verify_password(password, "invalid-hash")


def test_bcrypt_remains_valid_but_needs_rehash():
    legacy_hash = bcrypt.hash("legacy-password")
    assert verify_password("legacy-password", legacy_hash)
    assert not verify_password("wrong-password", legacy_hash)
    assert password_needs_rehash(legacy_hash)


def test_tokens_receive_unique_jtis_and_expire():
    first = decode_access_token(create_access_token({"sub": "1"}))
    second = decode_access_token(create_access_token({"sub": "1"}))
    assert first["jti"] != second["jti"]
    assert first["exp"] > first["iat"]
    expired = create_access_token({"sub": "1"}, timedelta(seconds=-5))
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_access_token(expired)
