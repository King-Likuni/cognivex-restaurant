from app.core.webhooks import build_hmac_signature, verify_hmac_signature


def test_hmac_signature_verification_accepts_valid_signature():
    body = b'{"reference":"CS-MM-260904-001","status":"PAID"}'
    secret = "dev-payment-webhook-secret"
    signature = build_hmac_signature(body, secret)

    assert verify_hmac_signature(body, signature, secret)


def test_hmac_signature_verification_rejects_tampered_body():
    body = b'{"reference":"CS-MM-260904-001","status":"PAID"}'
    tampered_body = b'{"reference":"CS-MM-260904-001","status":"FAILED"}'
    secret = "dev-payment-webhook-secret"
    signature = build_hmac_signature(body, secret)

    assert not verify_hmac_signature(tampered_body, signature, secret)


def test_hmac_signature_verification_rejects_missing_signature():
    assert not verify_hmac_signature(b"{}", None, "dev-payment-webhook-secret")
