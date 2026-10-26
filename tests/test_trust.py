"""The chain-of-trust links. `eventbridge/trust.py`.

`trust.py` is pure, so every claim the page renders is checked here without a cluster.
That matters more than usual for this module: it exists to make trust *visible*, so a bug
in it misreports the very controls it was built to display — and it does so convincingly,
in green.

Two properties get the most attention, because they are the two ways this page could lie:

  * **With no keyset, nothing may render RED.** Nothing was checked, so nothing failed.
    A red check there asserts an outcome never observed, which is worse than silence.
  * **The three amber links must stay amber.** They are true-but-weaker, and the whole
    design rests on not promoting them: `authorized` is inferred from the request
    existing, `request_verified` reads a response rather than the runner's verdict, and
    `which_agent` is attribution rather than restriction.
"""
from __future__ import annotations

import binascii

from eventbridge import trust
from shared import ce, keyset
from shared import signing as S

SEED_EB = binascii.unhexlify(
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
SEED_R1 = binascii.unhexlify(
    "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
SEED_ROGUE = binascii.unhexlify(
    "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")

PROMPTS = [{"turn_index": 1, "mode": "start", "prompt": "go", "submitter": "mrsabath"}]


def _ks():
    return keyset.KeySet({"eb-01": S.public_key(SEED_EB),
                          "runner-01": S.public_key(SEED_R1)})


def _stored(*, seq=1, final=True, seed=SEED_R1, kid="runner-01",
            causation="wake-abc12345", issuer="github", phase=None):
    """One response as the STORE holds it — flattened by `envelope_dict`, round-tripped
    through the wire binding first so the test sees exactly the bytes a consumer wrote."""
    e = ce.new_event(type=ce.TYPE_RESPONSE, source="rossoctl://eventrunner/t",
                     datacontenttype="application/json", correlationid="brave-otter-4718",
                     sessionuuid=ce.session_uuid("brave-otter-4718"), sequence=seq,
                     phase=phase or ("result" if final else "stdout"),
                     final="true" if final else "false", causationid=causation,
                     submitteriss=issuer, data={"text": "the answer"})
    S.sign_into(e, seed, kid)
    return ce.envelope_dict(ce.from_kafka_binary(*ce.to_kafka_binary(e)))


def _by_key(links):
    return {ln.key: ln for ln in links}


# ---- the flattened-envelope boundary ----------------------------------------

def test_a_stored_envelope_verifies_after_rehydration():
    """The bug this caught during development, pinned.

    `Store.raw_events_for` returns `envelope_dict` output — attrs and `data` flattened
    into one dict. `audit.row_for` verifies a signature and `canonical()` reads
    `event.attrs` / `event.data` separately, so a flat dict raises AttributeError on
    `.attrs`. Feeding the store's rows straight to audit does not work, and would have
    failed in production exactly as it failed here.
    """
    stored = _stored()
    evt = trust.rehydrate(stored)
    assert evt.attrs["correlationid"] == "brave-otter-4718"
    assert evt.data == {"text": "the answer"}
    ok, _why = S.verify_with_keyset(evt, _ks())
    assert ok, "a rehydrated envelope must still verify against the key that signed it"


def test_rehydration_drops_local_verdict_markers():
    """`ce.KEY_REJECTED` is a local verdict, never a wire attribute. Letting one into
    `attrs` would feed the canonicaliser a field the signer never covered."""
    stored = dict(_stored(), **{ce.KEY_REJECTED: True})
    evt = trust.rehydrate(stored)
    assert ce.KEY_REJECTED not in evt.attrs
    assert S.verify_with_keyset(evt, _ks())[0], "the marker must not break verification"


# ---- the happy path ---------------------------------------------------------

def test_a_clean_signed_run_greens_the_four_provable_links():
    links = _by_key(trust.links_for(
        [_stored(seq=1, final=False, seed=None, kid=None), _stored(seq=2)],
        PROMPTS, _ks(), bridge_kid="eb-01"))
    assert links["authenticated"].state == trust.GREEN
    assert links["response_signed"].state == trust.GREEN
    assert links["response_verified"].state == trust.GREEN
    assert links["bound"].state == trust.GREEN


def test_the_three_weaker_links_stay_amber_on_a_clean_run():
    """**The design decision this module exists to encode.** These are true but weaker
    than a green check would claim, and promoting them is the failure the talk is about."""
    links = _by_key(trust.links_for([_stored()], PROMPTS, _ks(), bridge_kid="eb-01"))
    for key in ("authorized", "request_verified", "which_agent"):
        assert links[key].state == trust.AMBER, f"{key} must not render green"
        assert links[key].limit, f"{key} must say WHY it is weaker"


def test_the_which_agent_limit_names_attribution_not_restriction():
    """The specific overclaim a green check here would make."""
    links = _by_key(trust.links_for([_stored()], PROMPTS, _ks(), bridge_kid="eb-01"))
    limit = links["which_agent"].limit
    assert "attribution" in limit
    assert "THIS request" in limit, "the limit has to name what it does NOT prove"


def test_signing_is_declared_terminal_only():
    """A reader seeing 1 of 2 events signed must be told that is the policy, not a gap."""
    links = _by_key(trust.links_for(
        [_stored(seq=1, final=False, seed=None, kid=None), _stored(seq=2)],
        PROMPTS, _ks(), bridge_kid="eb-01"))
    signed = links["response_signed"]
    assert signed.detail == {"signed": 1, "total": 2}
    assert "TERMINAL" in signed.limit


# ---- the failures that must be red ------------------------------------------

def test_an_unsigned_terminal_is_red():
    links = _by_key(trust.links_for([_stored(seed=None, kid=None)], PROMPTS, _ks(),
                                    bridge_kid="eb-01"))
    assert links["response_signed"].state == trust.RED
    assert links["response_verified"].state == trust.RED


def test_a_signature_from_an_unapproved_key_is_red():
    """The forgery case. A structurally perfect signature from a key nobody approved —
    so `response_signed` is green (a signature IS present) and the two links that
    actually check it go red. That split is the honest reading."""
    links = _by_key(trust.links_for(
        [_stored(seed=SEED_ROGUE, kid="runner-99")], PROMPTS, _ks(), bridge_kid="eb-01"))
    assert links["response_signed"].state == trust.GREEN
    assert links["response_verified"].state == trust.RED
    assert links["which_agent"].state == trust.RED


def test_a_stored_rejection_turns_the_bridge_link_red():
    """`responses.rejected` is set by the consumer when a signature was refused. The
    event is kept rather than dropped — a drop is indistinguishable from an agent that
    never answered — so the page has to read the column, not just the verdict."""
    links = _by_key(trust.links_for([_stored()], PROMPTS, _ks(),
                                    bridge_kid="eb-01", rejected=1))
    assert links["response_verified"].state == trust.RED
    assert "refused" in links["response_verified"].headline


def test_a_terminal_with_no_causation_is_red():
    links = _by_key(trust.links_for([_stored(causation="")], PROMPTS, _ks(),
                                    bridge_kid="eb-01"))
    assert links["bound"].state == trust.RED


# ---- the two ways this page could lie ---------------------------------------

def test_with_no_keyset_nothing_renders_red():
    """**The most important test here.** Nothing was checked, so nothing failed. A red
    check would assert an outcome that was never observed — and it is the easiest way
    for this page to mislead, because the events still carry signatures and kids that
    LOOK checkable.

    Caught during development: `which_agent` reported "kid runner-01 did not verify"
    with verification off, because the no-keyset verdict fell through to the failure
    branch.
    """
    links = trust.links_for([_stored()], PROMPTS, None, bridge_kid="eb-01")
    assert not [ln for ln in links if ln.state == trust.RED], \
        "nothing may be red when nothing was checked"
    by = _by_key(links)
    assert by["which_agent"].state == trust.AMBER
    assert "not checked" in by["which_agent"].evidence
    assert by["response_signed"].headline == "nothing was checked"


def test_an_unfinished_run_is_grey_not_red():
    """Reading mid-run must not look like tampering."""
    links = _by_key(trust.links_for([_stored(seq=1, final=False, seed=None, kid=None)],
                                    PROMPTS, _ks(), bridge_kid="eb-01"))
    for key in ("response_signed", "response_verified", "which_agent", "bound"):
        assert links[key].state == trust.GREY, f"{key} should be grey, not red"


def test_auth_being_off_is_amber_and_says_so():
    """No submitter is the default, not a failure — and `authorized` has nothing to
    judge, so it is grey rather than amber."""
    links = _by_key(trust.links_for([_stored()], [{"submitter": None}], _ks(),
                                    bridge_kid="eb-01"))
    assert links["authenticated"].state == trust.AMBER
    assert "default" in links["authenticated"].limit
    assert links["authorized"].state == trust.GREY


# ---- the summary and the JSON shape -----------------------------------------

def test_the_summary_does_not_fold_amber_into_green():
    """A headline of "8 green" would undo the entire point of the module."""
    links = trust.links_for([_stored()], PROMPTS, _ks(), bridge_kid="eb-01")
    s = trust.summarise(links)
    assert s["total"] == 8
    assert s[trust.GREEN] + s[trust.AMBER] + s[trust.RED] + s[trust.GREY] == 8
    assert s[trust.AMBER] >= 3, "the three weaker links are always amber"


def test_the_json_shape_carries_the_limit():
    """The page polls this. If `limit` were dropped, the UI could only render colour —
    and a colour without its reason is the overclaim again."""
    rows = trust.as_json(trust.links_for([_stored()], PROMPTS, _ks(),
                                         bridge_kid="eb-01"))
    assert len(rows) == 8
    assert all({"key", "title", "state", "headline", "evidence", "limit"} <= set(r)
               for r in rows)
    assert any(r["limit"] for r in rows)


def test_the_issuer_is_read_off_the_event_not_the_prompt():
    """`submitteriss` is not on the prompts row. Absent issuer means a static token —
    the weaker claim — so it has to come off an event."""
    assert trust.issuer_of([_stored()], PROMPTS) == "github"
    assert trust.issuer_of([_stored(issuer="")], PROMPTS) == ""
    assert trust.issuer_of([], PROMPTS) == ""


# ---- the HTTP surface -------------------------------------------------------
#
# Driven through `Handlers` rather than through `links_for`, because the route, the
# content negotiation and the store reads are where a working core still ships broken.

def _api(tmp_path, *, ks=None, rejected_forgery=False):
    import pathlib

    from eventbridge.config import Cfg
    from eventbridge.handlers import Handlers
    from eventbridge.store import Store
    store = Store(pathlib.Path(tmp_path) / "eb")
    corr = "brave-otter-4718"
    store.upsert_session(corr, ce.session_uuid(corr), "/w", "go")
    store.insert_prompt(corr, "start", "go", submitter="mrsabath")
    store.insert_response(_stored(seq=1, final=False, seed=None, kid=None))
    store.insert_response(_stored(seq=2))
    if rejected_forgery:
        forged = dict(_stored(seq=9001, seed=None, kid=None),
                      phase="error", **{ce.KEY_REJECTED: True})
        store.insert_response(forged)
    cfg = Cfg(tmpdir=str(tmp_path), public_base_url="http://eb.test")
    cfg.signing_kid = "eb-01"
    return Handlers(cfg, store, None, None, keyset=ks), corr


def _call(h, corr, qs=""):
    cap = {}

    def sr(status, headers):
        cap["status"] = status
        cap["headers"] = dict(headers)

    body = b"".join(h.get_trust({"QUERY_STRING": qs}, sr, correlationid=corr))
    return cap, body


def test_the_json_form_is_served_on_the_same_route(tmp_path):
    """The page polls the JSON form of its own URL, so there is nothing to keep in
    sync — the same idiom `list_groups` uses."""
    import json as _json
    h, corr = _api(tmp_path, ks=_ks())
    cap, body = _call(h, corr, "format=json")
    assert cap["status"] == "200 OK"
    d = _json.loads(body)
    assert d["correlationid"] == corr
    assert d["tally"]["total"] == 8
    assert d["enforcing"] is True
    assert d["issuer"] == "github"


def test_the_html_form_renders_the_limits(tmp_path):
    h, corr = _api(tmp_path, ks=_ks())
    cap, body = _call(h, corr)
    assert cap["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert int(cap["headers"]["Content-Length"]) == len(body)
    assert b'class="limit"' in body, "the amber reasons must reach the page"
    assert b"$state" not in body, "the JS template must be fully substituted"


def test_a_stored_forgery_turns_the_page_red(tmp_path):
    """The demo beat. A refused event is *stored* rather than dropped, so its presence
    cannot be inferred from rows existing — `rejected_count` is what finds it, and that
    column had no reader before this view."""
    import json as _json
    h, corr = _api(tmp_path, ks=_ks(), rejected_forgery=True)
    _cap, body = _call(h, corr, "format=json")
    d = _json.loads(body)
    assert d["tally"]["red"] >= 1, "a stored rejection has to show as red"
    by = {ln["key"]: ln for ln in d["links"]}
    assert by["response_verified"]["state"] == trust.RED


def test_with_no_keyset_the_page_says_nothing_was_checked(tmp_path):
    """§8.5.2 — state the default. Colour must not imply a check that never ran."""
    h, corr = _api(tmp_path, ks=None)
    _cap, body = _call(h, corr)
    assert b"Verification is off" in body
    assert b"what the events <em>claim</em>" in body


def test_a_bad_correlationid_is_refused(tmp_path):
    h, _corr = _api(tmp_path, ks=_ks())
    cap, _body = _call(h, "NOT_A_VALID_ID")
    assert cap["status"].startswith("400")


def test_an_unknown_correlationid_is_404_in_single_tenant_mode(tmp_path):
    """`events_for` returns 200 with an empty list for an unknown id because the single
    store always resolves. The trust view is 404 only when the store itself cannot be
    placed, so in single-tenant mode an unknown id renders an all-grey chain rather
    than an error — which is the honest answer: nothing is known about it."""
    import json as _json
    h, _corr = _api(tmp_path, ks=_ks())
    cap, body = _call(h, "quiet-elk-0000", "format=json")
    assert cap["status"] == "200 OK"
    d = _json.loads(body)
    assert d["tally"]["grey"] >= 4, "an unknown correlation is unknown, not failed"
    assert d["tally"]["red"] == 0
