"""tm.providers (issue #66): one message per refusal cause, the free key check, the balance before a paid step."""

import json

import pytest
import requests

from tm import providers

KEY = "xi_TEST_secret_key_0123456789abcdef"
TOKEN = "r8_TEST_secret_token_0123456789abcdef"


# --- causes ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status,body,cause", [
    (401, {"detail": "Invalid token."}, "key"),
    (401, {"title": "Unauthenticated", "detail": "You did not pass a valid authentication token", "status": 401}, "key"),
    (402, {"title": "Insufficient credit", "detail": "You have insufficient credit to run this model.", "status": 402},
     "credit"),
    (429, {"detail": "Request was throttled. Your rate limit resets in ~30s."}, "rate"),
    (403, {"detail": "You do not have permission to run this model."}, None),
    (422, {"title": "Invalid input", "detail": "E006", "status": 422}, None),
    (500, "oops", None),
])
def test_replicate_causes(status, body, cause):
    assert providers.cause("replicate", status, body) == cause


@pytest.mark.parametrize("status,body,cause", [
    (401, {"detail": {"type": "authentication_error", "code": "invalid_api_key", "message": "x"}}, "key"),
    (401, {"detail": {"status": "invalid_api_key", "message": "x"}}, "key"),
    (401, {"detail": {"code": "missing_api_key"}}, "key"),
    (401, {"detail": {"status": "quota_exceeded", "message": "This request exceeds your quota."}}, "credit"),
    (402, {"detail": {"type": "payment_required", "code": "insufficient_credits"}}, "credit"),
    (402, {"detail": "no"}, "credit"),
    (401, {"detail": {"status": "missing_permissions", "message": "missing the permission text_to_speech"}},
     "permission"),
    (403, {"detail": {"code": "insufficient_permissions"}}, "permission"),
    (403, {"detail": {"code": "feature_not_available"}}, "plan"),
    (403, {"detail": {"code": "subscription_required"}}, "plan"),
    (403, {"detail": "no"}, "plan"),             # today's reading of a 403: the plan
    (429, {"detail": {"code": "concurrent_limit_exceeded"}}, "rate"),
    (429, {"detail": {"status": "system_busy"}}, "rate"),
    (401, {"detail": "invalid key"}, None),      # a 401 we don't recognise: today's message
    (500, "oops", None),
])
def test_elevenlabs_causes(status, body, cause):
    assert providers.cause("elevenlabs", status, body) == cause


def test_each_message_names_its_fix_and_link():
    key = providers.refusal("replicate", "key", status=401, detail="Invalid token", what="the run of x/y")
    assert "https://replicate.com/account/api-tokens" in key and "/plugin" in key and "same place" in key
    credit = providers.refusal("replicate", "credit", status=402, detail="no credit", what="the run of x/y",
                               need="$0.40")
    assert "https://replicate.com/account/billing" in credit and "$0.40" in credit and "Nothing was spent" in credit
    rate = providers.refusal("replicate", "rate", status=429, detail="throttled", what="the run of x/y")
    assert "payment method" in rate and "wait" in rate.lower()
    perm = providers.refusal("elevenlabs", "permission", status=401, detail="missing", what="the speech")
    assert "https://elevenlabs.io/app/settings/api-keys" in perm and "Text to Speech" in perm and "User" in perm
    plan = providers.refusal("elevenlabs", "plan", status=403, detail="no", what="the voice clone", feature="clone")
    assert "Starter" in plan and "https://elevenlabs.io/app/subscription" in plan
    credits = providers.refusal("elevenlabs", "credit", status=402, detail="no", what="the speech", need="1200 credits")
    assert "1200 credits" in credits and "https://elevenlabs.io/app/subscription" in credits


def test_a_message_without_the_need_leaves_the_sentence_out():
    text = providers.refusal("replicate", "credit", status=402, detail="no credit", what="the run of x/y")
    assert "needed about" not in text and "{need}" not in text


def test_the_unknown_answer_keeps_todays_message():
    text = providers.refusal("replicate", None, status=403, detail="nope", what="the run of x/y")
    assert "Check the token and the account's credit" in text
    text = providers.refusal("elevenlabs", None, status=401, detail="invalid key", what="the speech")
    assert "Check the key, the credits and that the plan includes this feature" in text


def test_need_comes_from_the_engine(monkeypatch):
    monkeypatch.delenv("TM_COST_ESTIMATE", raising=False)
    assert providers.need("replicate") is None
    monkeypatch.setenv("TM_COST_ESTIMATE", "0.4")
    assert providers.need("replicate") == "$0.40" and providers.need("elevenlabs") == "0.4 credits"
    monkeypatch.setenv("TM_COST_ESTIMATE", "1200")
    assert providers.need("elevenlabs") == "1200 credits" and providers.estimate() == 1200.0
    monkeypatch.setenv("TM_COST_ESTIMATE", "junk")
    assert providers.need("elevenlabs") is None and providers.estimate() is None


# --- the balance ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body,left", [
    ({"character_count": 100, "character_limit": 1000}, 900),
    ({"character_count": 1100, "character_limit": 1000}, 0),
    ({"character_count": 1000, "character_limit": 1000, "can_extend_character_limit": False,
      "max_credit_limit_extension": 5000}, 0),
    ({"character_count": 1000, "character_limit": 1000, "can_extend_character_limit": True,
      "max_credit_limit_extension": 5000}, 5000),
    ({"character_count": 1000, "character_limit": 1000, "can_extend_character_limit": True,
      "max_credit_limit_extension": 0}, 0),
    ({"character_count": 1000, "character_limit": 1000, "can_extend_character_limit": True,
      "max_credit_limit_extension": "unlimited"}, None),
    ({"character_count": 1000, "character_limit": 1000, "can_extend_character_limit": True}, None),
    ({"tier": "free"}, None),
])
def test_what_is_left_counts_usage_based_billing(body, left):
    assert providers.left(body) == left


# --- the key check -------------------------------------------------------------------------------------------------

class Answer:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, str):
            raise ValueError
        return self._body

    @property
    def text(self):
        return self._body if isinstance(self._body, str) else json.dumps(self._body)


@pytest.fixture
def keys(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("TM_PLUGIN_DATA", str(data))
    (data / "secrets.env").write_text(f"REPLICATE_API_TOKEN={TOKEN}\nELEVENLABS_API_KEY={KEY}\n")
    sent = []

    def answer(answers):
        def get(url, headers=None, timeout=None):
            sent.append((url, headers))
            got = answers[url]
            if isinstance(got, Exception):
                raise got
            return Answer(*got)
        monkeypatch.setattr(providers, "_get", get)
        return sent
    return answer


ACCOUNT = "https://api.replicate.com/v1/account"
SUBSCRIPTION = "https://api.elevenlabs.io/v1/user/subscription"


def test_a_working_replicate_token(keys):
    sent = keys({ACCOUNT: (200, {"type": "user", "username": "someone"})})
    got = providers.check("replicate")
    assert got.state == "works" and got.cause is None
    assert sent == [(ACCOUNT, {"Authorization": f"Bearer {TOKEN}"})]
    assert TOKEN not in got.fix + repr(got)


@pytest.mark.parametrize("status,body,cause", [(401, {"detail": "Invalid token."}, "key"),
                                               (429, {"detail": "Request was throttled."}, "rate"),
                                               (402, {"detail": "Insufficient credit"}, "credit")])
def test_a_refused_replicate_token_is_connected_but_unusable(keys, status, body, cause):
    keys({ACCOUNT: (status, body)})
    got = providers.check("replicate")
    assert got.state == "unusable" and got.cause == cause and got.fix
    assert TOKEN not in got.fix


def test_an_unrecognised_refusal_is_unusable_with_todays_words(keys):
    keys({ACCOUNT: (403, {"detail": "nope"})})
    got = providers.check("replicate")
    assert got.state == "unusable" and got.cause is None and "Check the token" in got.fix


def test_an_unreachable_provider_is_not_checked(keys):
    keys({ACCOUNT: requests.ConnectionError("no route")})
    assert providers.check("replicate").state == "unchecked"


def test_a_missing_key_is_missing_and_nothing_is_sent(keys, tmp_path):
    sent = keys({})
    (tmp_path / "data" / "secrets.env").write_text("")
    assert providers.check("replicate").state == "missing"
    assert providers.check("elevenlabs").state == "missing"
    assert sent == []


def test_elevenlabs_with_credits_works_and_reads_the_cloning_plan(keys):
    sent = keys({SUBSCRIPTION: (200, {"tier": "starter", "character_count": 10, "character_limit": 30000,
                                      "can_use_instant_voice_cloning": True})})
    got = providers.check("elevenlabs")
    assert got.state == "works" and got.left == 29990 and got.cloning is True
    assert sent == [(SUBSCRIPTION, {"xi-api-key": KEY})]


def test_elevenlabs_with_nothing_left_is_unusable(keys):
    keys({SUBSCRIPTION: (200, {"tier": "free", "character_count": 10000, "character_limit": 10000})})
    got = providers.check("elevenlabs")
    assert got.state == "unusable" and got.cause == "credit" and got.left == 0
    assert "https://elevenlabs.io/app/subscription" in got.fix


def test_elevenlabs_key_without_the_user_permission(keys):
    keys({SUBSCRIPTION: (401, {"detail": {"status": "missing_permissions",
                                          "message": "The API key you used is missing the permission user_read"}})})
    got = providers.check("elevenlabs")
    assert got.state == "unusable" and got.cause == "permission" and "User" in got.fix


def test_a_strange_subscription_answer_is_not_checked(keys):
    keys({SUBSCRIPTION: (200, "<html>")})
    assert providers.check("elevenlabs").state == "unchecked"


def test_the_evals_answer_file_stands_in_for_the_network(tmp_path, monkeypatch, keys):
    keys({})   # no network answers at all: the file must be used
    answers = tmp_path / "answers.json"
    answers.write_text(json.dumps({"replicate": {"status": 401, "body": {"detail": "Invalid token."}}}))
    monkeypatch.setenv("TM_PROVIDER_ANSWERS", str(answers))
    assert providers.check("replicate").cause == "key"
    assert providers.check("elevenlabs").state == "unchecked"   # not in the file: never the network


def test_the_setup_words_say_where_to_make_each_key():
    """#66 point 1: /plugin's description of each key names where to make it, with the link, and what it is for."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]   # this checkout's plugin, whatever ~/.trendsmesh points at
    config = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    rep = config["userConfig"]["replicate_api_token"]["description"]
    el = config["userConfig"]["elevenlabs_api_key"]["description"]
    assert providers.REPLICATE_TOKENS in rep and providers.REPLICATE_BILLING in rep and "AI images and video" in rep
    assert providers.ELEVENLABS_KEYS in el and "voices and the music" in el
    for permission in ("Text to Speech", "Voices (read and write)", "Audio Isolation", "Music Generation",
                       "History (read)", "User (read)"):
        assert permission in el and permission in i18n_t("keys.elevenlabs.permissions")
    assert providers.REPLICATE_TOKENS in i18n_t("keys.replicate.get")
    assert providers.ELEVENLABS_KEYS in i18n_t("keys.elevenlabs.get", permissions="x")


def i18n_t(key, **values):
    from tm import i18n

    return i18n.t(key, **values)
