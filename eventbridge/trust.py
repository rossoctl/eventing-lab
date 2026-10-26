"""The chain of trust for one correlation, link by link, from stored evidence.

The demo proves each control separately — identity in one beat, a refused forgery in
another, the audit chain in a third. This assembles them into the thing the abstract
actually sells: a chain, where each link names what was checked, what the evidence was,
and **what the check does not prove.**

Pure. Takes already-read rows and returns verdicts, so the whole thing is testable
without a cluster — the same discipline `shared/audit.py` keeps, and for the same reason:
every one of the thirteen findings in `docs/specs/0003-phase2-identity-on-the-event-path.md`
§8 coexisted with a passing test suite, because the tests exercised the configuration each
claim was true in.

**Three of the eight links are AMBER by construction, and that is the point.** A page that
rendered eight green checks would be the exact failure the talk is about — an unchecked
control claim, stated more confidently than the evidence supports. The three:

  * **authorized** — the `EB_ALLOWED_USERS` gate is real and it passed, but nothing records
    that on the event. It is inferred from the request existing at all.
  * **request verified** — `eventrunner/consume.py` refuses an unsigned request before the
    agent runs, but the verdict lives in the runner's log and the request envelope is never
    persisted. What the store can show is that a *response* exists, which means the runner
    acted. That is evidence, not proof.
  * **which agent** — a `kid` resolving in the approved keyset proves *an* approved key
    signed. It does not prove this agent was permitted to answer **this** request. The specs
    name this "attribution, not restriction"; a flat keyset cannot distinguish them.

Amber is not a softer green. It is a different claim, and the `limit` field is what the
reader is meant to take away.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shared import audit, ce

GREEN = "green"
AMBER = "amber"
RED = "red"
GREY = "grey"      # not reached yet — the run is still in flight, or never happened


@dataclass
class Link:
    """One link. `limit` is the sentence that stops the page overclaiming."""
    key: str
    title: str
    state: str
    headline: str
    evidence: str = ""
    limit: str = ""
    detail: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Green only. Amber is deliberately not ok — see the module docstring."""
        return self.state == GREEN


def _terminal(rows: list[audit.Row]) -> audit.Row | None:
    """The verified terminal if there is one, else the last terminal seen.

    Same preference `audit.Chain.terminal` applies, and for the same reason: a genuine
    answer and a forgery can both be stored at different sequence numbers, so "the last
    one" would name the forgery as the answer.
    """
    terms = [r for r in rows if r.is_terminal]
    for r in terms:
        if r.verdict == audit.VERDICT_OK:
            return r
    return terms[-1] if terms else None


def _link_authenticated(prompts: list[dict]) -> Link:
    submitter = next((p.get("submitter") for p in prompts if p.get("submitter")), None)
    # `submitteriss` is not on the prompts row, so the issuer has to come off an event.
    # Handled by the caller, which passes it in `detail`; absent means a static token.
    if not submitter:
        return Link("authenticated", "The asker was authenticated", AMBER,
                    "no submitter recorded",
                    evidence="auth is off, or this request predates it",
                    limit="With no approved-user list configured, EventBridge accepts "
                          "anonymously. That is the default, and it is not a failure — "
                          "but nothing here identifies who asked.")
    return Link("authenticated", "The asker was authenticated", GREEN,
                f"{submitter}",
                evidence="read off the turn tape, not typed by the caller",
                detail={"submitter": submitter})


def _link_authorized(prompts: list[dict]) -> Link:
    submitter = next((p.get("submitter") for p in prompts if p.get("submitter")), None)
    if not submitter:
        return Link("authorized", "…and was on the approved list", GREY,
                    "not applicable", evidence="no identity to authorize")
    return Link("authorized", "…and was on the approved list", AMBER,
                f"{submitter} passed the gate",
                evidence="inferred: the request exists, so EB_ALLOWED_USERS let it through",
                limit="The gate is real and it ran — but the decision is not recorded on "
                      "the event, so this is inferred from the request existing rather "
                      "than read from evidence. A refused user leaves no request at all.")


def _link_request_signed(rows: list[audit.Row], prompts: list[dict]) -> Link:
    # The request envelope is never persisted (only a prompts row survives), so the
    # closest stored evidence is the response's `causationid` — a response that names a
    # wake event is a response to a request EventBridge published and therefore signed.
    t = _terminal(rows)
    if not rows:
        return Link("request_signed", "The wake event was signed", GREY,
                    "no events yet", evidence="the run has not produced anything")
    if t and t.causationid:
        return Link("request_signed", "The wake event was signed", AMBER,
                    f"caused by {t.causationid[:8]}",
                    evidence="the response names a wake event, so one was published",
                    limit="EventBridge signs every request it publishes, but the request "
                          "envelope is not stored — only the prompt. So this link reads "
                          "the response's causationid rather than the request's own "
                          "signature. Beat 4 proves the enforcement live.")
    return Link("request_signed", "The wake event was signed", AMBER,
                "no causation recorded",
                evidence="responses carry no causationid",
                limit="Without a causationid there is nothing stored that points back "
                      "at a wake event.")


def _link_request_verified(rows: list[audit.Row]) -> Link:
    if not rows:
        return Link("request_verified", "The runner verified it before working", GREY,
                    "no events yet", evidence="nothing ran")
    return Link("request_verified", "The runner verified it before working", AMBER,
                "the agent ran",
                evidence=f"{len(rows)} response event(s) exist, so the runner acted on it",
                limit="With ER_REQUIRE_SIGNATURE=true an unsigned request is refused "
                      "before the agent starts — but that verdict is in the runner's log, "
                      "not in this store. A response existing means the request was "
                      "accepted; it is evidence, not proof.")


def _link_response_signed(rows: list[audit.Row]) -> Link:
    t = _terminal(rows)
    if t is None:
        return Link("response_signed", "The answer was signed", GREY,
                    "no terminal yet", evidence="still running, or read too early")
    if t.verdict == audit.VERDICT_UNKNOWN:
        return Link("response_signed", "The answer was signed", AMBER,
                    "nothing was checked",
                    evidence="no keyset configured",
                    limit="Verification is off. Signatures may be present but none was "
                          "checked against an approved key, so this page can report "
                          "what the events claim and nothing more.")
    if t.signed:
        signed = sum(1 for r in rows if r.signed)
        return Link("response_signed", "The answer was signed", GREEN,
                    "the terminal event carries a signature",
                    evidence=f"{signed} of {len(rows)} events signed",
                    limit="Signing covers TERMINAL events only — a signature costs "
                          "~190-230 ms and signing every streamed frame would add "
                          "minutes to a chatty run. So this proves who finished the run, "
                          "not what it said along the way.",
                    detail={"signed": signed, "total": len(rows)})
    return Link("response_signed", "The answer was signed", RED,
                "the terminal event is unsigned",
                evidence=t.reason or "no ce_signature on a terminal event")


def _link_response_verified(rows: list[audit.Row], rejected: int) -> Link:
    t = _terminal(rows)
    if t is None:
        return Link("response_verified", "The bridge verified the answer", GREY,
                    "no terminal yet", evidence="still running, or read too early")
    if t.verdict == audit.VERDICT_UNKNOWN:
        return Link("response_verified", "The bridge verified the answer", AMBER,
                    "nothing was checked", evidence="no keyset configured",
                    limit="With no keyset there is no verification to report.")
    if t.verdict == audit.VERDICT_BAD:
        return Link("response_verified", "The bridge verified the answer", RED,
                    "a signature was present and did NOT verify",
                    evidence=t.reason)
    if rejected:
        return Link("response_verified", "The bridge verified the answer", RED,
                    f"{rejected} event(s) stored as refused",
                    evidence="rewritten to phase=error rather than dropped — a drop is "
                             "indistinguishable from an agent that never answered")
    if t.verdict == audit.VERDICT_OK:
        return Link("response_verified", "The bridge verified the answer", GREEN,
                    "verified against the approved key set",
                    evidence=f"stored as phase={t.phase}, not rewritten to error")
    return Link("response_verified", "The bridge verified the answer", RED,
                t.verdict, evidence=t.reason)


def _link_which_agent(rows: list[audit.Row], keyset_kids: tuple[str, ...]) -> Link:
    t = _terminal(rows)
    if t is None or not t.kid:
        return Link("which_agent", "…by a named, approved agent", GREY,
                    "no kid on the terminal", evidence="nothing to attribute")
    # Before any failure branch: with no keyset there was no check, so there is no
    # failure to report. Rendering RED here would be the page asserting an outcome it
    # never observed — the worst thing a trust view can do, and the §8.5.2 question
    # ("what is the default?") answered wrong.
    if t.verdict == audit.VERDICT_UNKNOWN:
        return Link("which_agent", "…by a named, approved agent", AMBER,
                    f"claims kid {t.kid}",
                    evidence="no keyset configured, so the claim was not checked",
                    limit="The event names a key. Nothing verified that the key is "
                          "approved, or that the signature is valid — so this is what "
                          "the event SAYS, not what was proven.",
                    detail={"kid": t.kid, "approved": []})
    if t.verdict != audit.VERDICT_OK:
        return Link("which_agent", "…by a named, approved agent", RED,
                    f"kid {t.kid} did not verify", evidence=t.reason)
    return Link("which_agent", "…by a named, approved agent", AMBER,
                f"kid {t.kid}",
                evidence=f"resolves in the approved set ({len(keyset_kids)} kid(s))",
                limit="This proves an APPROVED key signed, which is attribution. It does "
                      "not prove this agent was permitted to answer THIS request — a flat "
                      "keyset cannot express that, so any approved runner's key would "
                      "verify here. Group lifecycle events are the exception: those are "
                      "pinned to EventBridge's own kid.",
                detail={"kid": t.kid, "approved": list(keyset_kids)})


def _link_bound(rows: list[audit.Row]) -> Link:
    t = _terminal(rows)
    if t is None:
        return Link("bound", "The answer is bound to that wake", GREY,
                    "no terminal yet", evidence="still running, or read too early")
    if not t.causationid:
        return Link("bound", "The answer is bound to that wake", RED,
                    "no causationid", evidence="nothing ties this answer to a request")
    if t.verdict == audit.VERDICT_OK:
        return Link("bound", "The answer is bound to that wake", GREEN,
                    f"causationid {t.causationid[:8]}",
                    evidence="causationid is inside SIGNED_ATTRS, so the link cannot be "
                             "rewritten in flight",
                    detail={"causationid": t.causationid})
    return Link("bound", "The answer is bound to that wake", AMBER,
                f"causationid {t.causationid[:8]}",
                evidence="present, but on an event whose signature did not verify",
                limit="A causation link is only as good as the signature covering it.")


def rehydrate(envelope: dict) -> ce.CloudEvent:
    """A stored envelope back into a `CloudEvent`, so `shared.audit` can verify it.

    `Store.raw_events_for` returns what `ce.envelope_dict` produced — attributes and
    `data` flattened into one dict. `audit.row_for` verifies a signature, and
    `canonical()` reads `event.attrs` / `event.data` separately, so a flat dict raises
    `AttributeError` on `.attrs`. This is the exact inverse of `envelope_dict`.

    **`__`-prefixed keys are dropped**, not carried: those are local verdicts
    (`ce.KEY_REJECTED`), never wire attributes, and letting one into `attrs` would feed
    the canonicaliser a field the signer never covered.
    """
    attrs = {k: v for k, v in envelope.items()
             if k != "data" and not k.startswith("__")}
    return ce.CloudEvent(attrs=attrs, data=envelope.get("data"))


def links_for(raw_events: list[dict], prompts: list[dict], ks,
              *, bridge_kid: str | None = None,
              rejected: int = 0) -> list[Link]:
    """The eight links, in narrative order, for one correlation.

    `raw_events` are full stored envelopes (`Store.raw_events_for`) — NOT the projection
    `events_for` returns, which drops `signature`, `kid` and `causationid` and so cannot
    answer any of this.
    """
    rows = [audit.row_for(rehydrate(e), i, ks, bridge_kid=bridge_kid)
            for i, e in enumerate(raw_events)]
    kids = tuple(ks.kids) if ks is not None else ()
    return [
        _link_authenticated(prompts),
        _link_authorized(prompts),
        _link_request_signed(rows, prompts),
        _link_request_verified(rows),
        _link_response_signed(rows),
        _link_response_verified(rows, rejected),
        _link_which_agent(rows, kids),
        _link_bound(rows),
    ]


def summarise(links: list[Link]) -> dict[str, int]:
    """Counts by state, for the headline. `green` is deliberately not `green+amber`."""
    out = {GREEN: 0, AMBER: 0, RED: 0, GREY: 0}
    for ln in links:
        out[ln.state] = out.get(ln.state, 0) + 1
    out["total"] = len(links)
    return out


def as_json(links: list[Link]) -> list[dict]:
    """The shape the page polls. Keys match the dataclass so the JS needs no mapping."""
    return [{"key": ln.key, "title": ln.title, "state": ln.state,
             "headline": ln.headline, "evidence": ln.evidence, "limit": ln.limit,
             "detail": ln.detail} for ln in links]


def issuer_of(raw_events: list[dict], prompts: list[dict]) -> str:
    """Who vouched for the submitter: `github`, or empty for a static token.

    Not on the prompts row, so it comes off any event that carries it. An absent issuer
    is the weaker claim and the page says so — `docs/specs/0003-…md` §2.6: absent means
    an operator typed the name into an environment variable.
    """
    for e in raw_events:
        iss = e.get(ce.EXT_SUBMITTER_ISS)
        if iss:
            return str(iss)
    return ""
