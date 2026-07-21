import json
import threading

from app.services.seo_security import consume_oauth_state, new_oauth_state, validate_oauth_owner

class AtomicRedis:
    def __init__(self, value):
        self.value = value
        self.lock = threading.Lock()
    def getdel(self, _key):
        with self.lock:
            value, self.value = self.value, None
            return value

def test_state_is_opaque_and_contains_server_side_binding():
    state, payload = new_oauth_state("gsc", 7, 11)
    assert state and state not in payload
    record = json.loads(payload)
    assert record["provider"] == "gsc"
    assert record["user_id"] == 7
    assert record["org_id"] == 11
    assert record["nonce"]

def test_provider_mismatch_and_malformed_state_are_rejected():
    state, payload = new_oauth_state("gsc", 7, 11)
    assert state
    assert consume_oauth_state(AtomicRedis(payload), "x")["provider"] == "gsc"
    assert consume_oauth_state(AtomicRedis(json.dumps({"provider": "gsc"})), "x") is None
    assert consume_oauth_state(AtomicRedis("not-json"), "x") is None

def test_getdel_allows_exactly_one_consumer_under_race():
    _, payload = new_oauth_state("ga4", 7, 11)
    redis = AtomicRedis(payload)
    results = []
    threads = [threading.Thread(target=lambda: results.append(consume_oauth_state(redis, "x"))) for _ in range(20)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert sum(result is not None for result in results) == 1

def test_missing_state_is_rejected_closed():
    assert consume_oauth_state(AtomicRedis(None), "x") is None
