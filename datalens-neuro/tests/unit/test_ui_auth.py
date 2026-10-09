import json
import time
from urllib.parse import quote

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.errors import NeuroError
from app.ui_auth import UiUser, access_token_from_cookie, verify_access_token


def _keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private, pem


def _token(private, algorithm="RS256", **claims):
    payload = {"userId": "u1", "roles": ["datalens.admin"], "exp": int(time.time()) + 60}
    payload.update(claims)
    return jwt.encode(payload, private, algorithm=algorithm)


def test_cookie_json_and_quoted():
    raw = json.dumps({"accessToken": "abc"})
    assert access_token_from_cookie("auth=" + raw) == "abc"
    assert access_token_from_cookie("other=1; auth=" + quote(raw)) == "abc"
    assert access_token_from_cookie("auth=" + json.dumps({})) is None
    assert access_token_from_cookie(None) is None


def test_verify_admin():
    private, pem = _keys()
    user = verify_access_token(_token(private), pem)
    assert user == UiUser("u1", ("datalens.admin",))
    ps256 = verify_access_token(_token(private, algorithm="PS256"), pem)
    assert ps256 == UiUser("u1", ("datalens.admin",))


def test_rejects_bad_token():
    private, pem = _keys()
    other, _ = _keys()
    expired = _token(private, exp=int(time.time()) - 10)
    hs = jwt.encode({"userId": "u1", "roles": ["datalens.admin"], "exp": int(time.time()) + 60}, "secret", algorithm="HS256")
    for token in (expired, _token(other), hs, "not-a-jwt"):
        with pytest.raises(NeuroError) as exc:
            verify_access_token(token, pem)
        assert exc.value.status_code == 401 and exc.value.code == "UNAUTHENTICATED"
