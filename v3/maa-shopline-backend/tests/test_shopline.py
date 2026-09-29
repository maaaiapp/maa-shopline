import hashlib, hmac, json, time
import httpx, pytest, respx
from app.shopline import oauth, signing, webhooks
from app.store import MemoryStore
from app.security.crypto import TokenCipher

def signed(params, secret="s3cret"):
    return {**params, "sign": signing.sign_params(params, secret)}

def test_params_sign_roundtrip_and_tamper():
    p = signed({"appkey": "appkey", "code": "c", "handle": "shop1", "timestamp": str(int(time.time()*1000))})
    assert signing.verify_params(p, "s3cret")
    assert not signing.verify_params({**p, "handle": "evil"}, "s3cret")
    assert not signing.verify_params(p, "wrong")

def test_params_replay_window():
    p = signed({"handle": "shop1", "timestamp": str(int(time.time()*1000) - 3_600_000)})
    assert not signing.verify_params(p, "s3cret")

def test_webhook_sig_matches_published_algorithm():
    body = b'{"id":1}'
    sig = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert signing.verify_webhook(body, sig, "s3cret")
    assert signing.verify_webhook(body, sig.upper(), "s3cret")
    assert not signing.verify_webhook(body + b" ", sig, "s3cret")
    assert not signing.verify_webhook(body, None, "s3cret")

@pytest.mark.parametrize("h", ["evil.com/x", "a.b", "", "UPPER", "x" * 70, "shop1.attacker"])
def test_handle_ssrf_guard(h):
    assert not oauth.valid_handle(h)

def _install(settings, store):
    url = oauth.authorize_url(settings, store, "shop1")
    state = url.split("customField=")[1]
    p = signed({"appkey": "appkey", "code": "abc", "handle": "shop1", "customField": state,
                "timestamp": str(int(time.time()*1000))})
    with respx.mock:
        route = respx.post("https://shop1.myshopline.com/admin/oauth/token/create").mock(
            return_value=httpx.Response(200, json={"code": 200, "data": {"accessToken": "TOK123456789", "expireTime": "2026-09-27T20:00:00.000+00:00", "scope": "read_orders"}}))
        shop_id = oauth.handle_callback(settings, store, p, httpx.Client())
        req = route.calls.last.request
        assert req.headers["sign"] == signing.sign_post(req.content.decode(), req.headers["timestamp"], "s3cret")
    return shop_id

def test_oauth_happy_path_encrypts_token(settings):
    store = MemoryStore(); shop_id = _install(settings, store)
    inst = store.get_installation("shop1")
    assert inst["shop_id"] == shop_id and "TOK123" not in inst["enc_token"]
    assert TokenCipher(settings.token_encryption_key).decrypt(inst["enc_token"], "shop1") == "TOK123456789"

def test_oauth_rejects_bad_state_and_signature(settings):
    store = MemoryStore()
    p = signed({"code": "x", "handle": "shop1", "customField": "forged", "timestamp": str(int(time.time()*1000))})
    with pytest.raises(oauth.OAuthError): oauth.handle_callback(settings, store, p, httpx.Client())
    p2 = {**p, "sign": "0" * 64}
    with pytest.raises(oauth.OAuthError): oauth.handle_callback(settings, store, p2, httpx.Client())
    assert {a["event"] for a in store.audits} == {"oauth_bad_state", "oauth_bad_signature"}

def test_state_is_single_use(settings):
    store = MemoryStore(); _install(settings, store)
    assert store.states == {}

def test_token_refresh_failure_marks_expired(settings):
    store = MemoryStore(); _install(settings, store)
    with respx.mock:
        respx.post("https://shop1.myshopline.com/admin/oauth/token/refresh").mock(return_value=httpx.Response(401))
        assert not oauth.refresh_token(settings, store, "shop1", httpx.Client())
    assert store.get_installation("shop1")["status"] == "token_expired"

def _hook(store, body, topic="orders/create", wid="w1", secret="s3cret", sig=None, domain="shop1.myshopline.com"):
    sig = sig or hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return webhooks.receive(store, "s3cret", {"X-Shopline-Hmac-Sha256": sig, "X-Shopline-Topic": topic,
                                              "X-Shopline-Webhook-Id": wid, "X-Shopline-Shop-Domain": domain}, body)

def test_webhook_forged_rejected_and_audited(settings):
    store = MemoryStore(); _install(settings, store)
    r = _hook(store, b'{"id":1}', sig="f" * 64)
    assert r.status == 401 and not store.webhooks and store.audits[-1]["event"] == "webhook_bad_signature"

def test_webhook_duplicate_processed_once(settings):
    store = MemoryStore(); _install(settings, store)
    assert _hook(store, b'{"id":1}').outcome == "accepted"
    assert _hook(store, b'{"id":1}').outcome == "duplicate"
    assert len(store.jobs) == 1

def test_webhook_unknown_shop_and_topic(settings):
    store = MemoryStore(); _install(settings, store)
    assert _hook(store, b"{}", domain="other.myshopline.com").outcome == "rejected_shop"
    assert _hook(store, b"{}", topic="carts/update", wid="w9").outcome == "ignored_topic"
    assert not store.jobs

def test_webhook_uninstall(settings):
    store = MemoryStore(); _install(settings, store)
    _hook(store, b"{}", topic="apps/uninstalled", wid="u1")
    inst = store.get_installation("shop1")
    assert inst["status"] == "uninstalled" and inst["enc_token"] is None


def test_ios_callback_redirects_to_app_with_fragment_only(settings):
    from urllib.parse import unquote
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.store import MemoryStore
    st = MemoryStore()
    c = TestClient(create_app(settings, store=st), follow_redirects=False)
    loc = c.get("/auth/shopline/start", params={"handle": "shop1", "client": "ios"}).headers["location"]
    state = unquote(loc.split("customField=")[1])
    p = signed({"appkey": "appkey", "code": "abc", "handle": "shop1", "customField": state,
                "timestamp": str(int(time.time() * 1000))})
    with respx.mock:
        respx.post("https://shop1.myshopline.com/admin/oauth/token/create").mock(return_value=httpx.Response(
            200, json={"code": 200, "data": {"accessToken": "TOK123456789", "expireTime": "", "scope": "read_orders"}}))
        r = c.get("/auth/shopline/callback", params=p)
    assert r.status_code == 302
    assert r.headers["location"].startswith("maashopline://auth#session=")      # token only in the fragment
    assert "?" not in r.headers["location"] and r.headers["cache-control"] == "no-store"
    # replaying the same callback fails: state is single use
    with respx.mock:
        respx.post("https://shop1.myshopline.com/admin/oauth/token/create").mock(return_value=httpx.Response(200, json={}))
        assert c.get("/auth/shopline/callback", params=p).status_code == 400
