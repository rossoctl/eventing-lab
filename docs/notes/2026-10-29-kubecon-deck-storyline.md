# KubeCon NA 2026 — deck storyline

Date: 2026-10-29
Status: draft for review — section flow agreed, individual charts not yet designed.
Scope: the narrative spine for the PowerPoint. Not the run-of-show (that is
[`../demos/kubecon-na-2026-demo.md`](../demos/kubecon-na-2026-demo.md)) and not the status
assessment ([`kubecon-na-2026.md`](kubecon-na-2026.md)).

**Talk:** *The Seams Are the Trap: Agent Fleets from CNCF Parts You Already Have*
30-minute slot — ~22–24 min content, 4 min demo, 3–4 min questions.

---

## 0. The one sentence

> You already run the parts. The hard bit is not scaling agents — it is the four places
> the composition leaks, and knowing which of your own control claims are not true yet.

Everything in the deck serves that sentence. If a slide does not advance it, cut the slide.

## 1. The spine

| # | Section | Min | What it does | What it must NOT do |
| --- | --- | --- | --- | --- |
| 1 | The pitch you don't need | 0–2 | Earn attention with a contrarian claim | Bash vendors by name |
| 2 | The problem, precisely | 2–4 | Make it *their* problem | Claim agent-to-agent collaboration |
| 3 | Guiding principles | 4–6 | The contract with the audience | Read as a feature list |
| 4 | The eventing model | 6–8 | One idea: queue depth is the only wake signal | Explain Kafka |
| 5 | Architecture | 8–11 | Show what is stock vs. ours | Imply we built a platform |
| 6 | The four seams | 11–15 | **The take-home artifact** | Resolve all four — two are open |
| 7 | How it works | 15–17 | One flow chart, end to end | Repeat §5 |
| 8 | Demo | 17–21 | Recorded, narrated. Hard stop | Run live |
| 9 | The claims that did not hold | 21–25 | **The differentiator** | Sound like an apology |
| 10 | What's next, and the close | 25–27 | Name the upgrade path with its cost | Promise SPIRE |
| 11 | Questions | 27–30 | | |

Two deliberate departures from the obvious ordering:

**Principles come before the solution** (§3 before §4–5), so the architecture is visibly
*derived* from them rather than justified after the fact. An audience that has agreed to
seven principles will accept the architecture that follows; one shown the architecture first
will argue with it.

**The seams get their own section** (§6), between architecture and demo. They are what the
abstract promises and the only part of this talk that is reusable by someone who will never
run our code.

---

## 2. Section by section

### §1 The pitch you don't need (0–2)

Open on the line the abstract already commits to:

> "Every vendor is shipping an agent platform. You probably don't need one."

Then the turn: what you *do* need is to know how the parts you already run fit together —
and where they do not.

**Tone:** not anti-vendor. The claim is about *composition being sufficient*, not about
products being bad. One sentence acknowledging that a platform is the right answer for some
teams buys you credibility for the next 25 minutes.

### §2 The problem, precisely (2–4)

**Framing: a fleet, not a collaboration.** Many non-deterministic agents, running safely, at
a scale where you cannot babysit them.

State plainly what we are NOT claiming: these agents do not talk to each other. There is no
agent-to-agent protocol here. They are **consumers of a shared event log** — which is a more
interesting architectural claim than messaging, because it is what makes the state survive
the process.

Three properties that make this hard, and each one is a principle in §3:

1. **Non-deterministic** — the same input may not produce the same output, so you cannot test
   your way to confidence. You need to constrain what an agent *can do*, not predict what it
   will do.
2. **Bursty** — demand arrives in clumps. Idle capacity is waste; a cold start is latency.
3. **Untrusted by default** — an agent is a program someone else's model wrote. Treat its
   output as input.

**The number that makes "fleet" concrete:** 100 agents, fanned out and tracked to completion
in **1m02s, 0 failed** (`reports/phase1-report.md`).

### §3 Guiding principles (4–6)

Seven. This is the contract — every later slide should be traceable to one.

| Principle | What it rules out | Evidence in the demo |
| --- | --- | --- |
| **Scalable to zero** | always-on agent pools | idle at 0 replicas; wake 2.1–4.2 s |
| **Existing technologies** | a new runtime to learn | KEDA, Strimzi, CloudEvents — all stock |
| **No new platform** | a framework with our name on it | two services + a wire contract |
| **Trusted agents only** | "the broker is inside the perimeter" | forged response refused and inert |
| **Authorized users only** | an open submit endpoint | 401 → sign in → 202, submitter on the event |
| **Auditable after the fact** | trusting a dashboard | broker log; completions chain to signed wakes |
| **Fails closed** | a half-configured control that allows | zero-kid keyset refuses to **start** |

**On "minimal custom code":** I would not use that phrasing. The repo is a real wire
contract plus hand-rolled Ed25519 — not little code. The honest and stronger claim is **"no
new platform"**: no new concepts, no new control plane, nothing to learn that you do not
already run. Say *composition over framework*.

**"Fails closed" is the one to dwell on.** It is the principle that earns the §9 section:
every control here refuses rather than allows when misconfigured, and we have receipts.

### §4 The eventing model (6–8)

One idea, and it is the best idea in the system:

> **Lag means "work not finished", not "work not read".**

The Kafka offset is committed only after the terminal event. That single inversion does two
jobs at once:

- consumer lag becomes a *correct* queue gauge, so KEDA can scale on it
- it is structurally impossible for KEDA to scale away a pod mid-stream

The fix for "never miss an event" is also the fix for "don't kill a running agent." Observed
by accident: a run sat in 429 retry backoff for 300 s and replicas stayed ≥ 1 the whole time.

**Do not explain Kafka.** Assume the room knows what a topic and an offset are. One slide.

### §5 Architecture (8–11)

Two services, four stock projects. The slide's job is to show **how little is ours**.

```
  HTTP  →  EventBridge  →  Kafka:requests  →  EventRunner  →  agent
   ↑          (ours)          (Strimzi)         (ours)         │
   │                                                            ▼
  HTML / SSE  ←  EventBridge  ←  Kafka:responses  ←  CloudEvents
```

| Layer | What | Whose |
| --- | --- | --- |
| Scaling | KEDA `ScaledObject`, 0..N on consumer lag | stock |
| Transport | Strimzi-backed Kafka, binary CloudEvents | stock |
| Envelope | CloudEvents 1.0 + detached JWS (Ed25519) | stock spec |
| Front door | EventBridge — HTTP, store, views, auth | **ours** |
| Consumer | EventRunner — spawns the agent, emits events | **ours** |

**Say Strimzi, not Knative.** The abstract offers either; we built on Strimzi and the demo
runs on it. Claiming Knative would be an unverified claim on a slide — which is the one thing
this talk cannot afford.

**The deliberate non-choice worth one sentence:** a Deployment scaled 0..N, *not* a Job per
request. Kafka already assigns one partition to one consumer, so per-conversation ordering
holds across pods for free. Job-per-request is deferred as a *security* story (a per-run
capability envelope), not a scaling one.

### §6 The four seams (11–15)

**The take-home artifact.** Each seam is a named integration point between two projects where
the composition leaks.

| Seam | Where it leaks | Our status |
| --- | --- | --- |
| **Cold-start identity gap** | the agent egresses before SPIRE issues an SVID | ❌ no SPIRE — named as the upgrade path |
| **Trust-scope drift** | egress allowlist decided at deploy, stale by wake | 🟡 enforcement built and verified; no live beat |
| **Unverified delivery** | the broker hands off events before signature check | ✅ both directions, verified on a cluster |
| **Unbound audit** | completion not chained back to the signed wake | ✅ `ce_causationid`, verified |

**Do not resolve all four.** Two are open and the slide says so. A taxonomy where every entry
is already solved by the speaker is a product pitch; one with two honest gaps is a tool the
audience can use.

**The scope-drift point is the best one to explain**, because it is counter-intuitive and
free: the runner reads its allowlist at *startup*, and scale-to-zero means there is no
long-lived process holding a stale decision. Edit the list while replicas are 0 and the next
wake enforces the new one. **Scale-to-zero is a trust argument, not just a cost argument.**

### §7 How it works — the flow chart (15–17)

One chart, seven steps, each one a thing the demo then shows:

1. **Submit** — `POST /v0/agents`, GitHub sign-in verified, `ce_submitter` stamped
2. **Sign** — detached JWS over the envelope; `submitter` is a *signed* attribute
3. **Wake** — lag ≥ 1 on the requests topic; KEDA scales 0 → 1
4. **Verify** — runner checks the signature, *then* the submitter allowlist (order matters)
5. **Run** — agent executes; every stdout frame becomes a response CloudEvent
6. **Bind** — terminal event signed, carries `ce_causationid` back to the wake
7. **Zero** — offsets committed, lag 0, KEDA removes the replica

**The one annotation that makes the chart land:** step 4's ordering. The signature is checked
*before* the allowlist, because a verified signature is what makes `ce_submitter` trustworthy
— the attribute is covered by the signature, so a forger cannot claim an approved login. Get
that order backwards and you are filtering on a value the attacker chose.

### §8 Demo (17–21)

Recorded and narrated live. **Hard stop at 4 minutes.** It cannot be driven live: the wake
alone is 2–4 s and the cycle back to zero is ~31 s before the agent does any work.

Run order, and what to cut first if you are over:

| Beat | Shows | Cut order |
| --- | --- | --- |
| Act 1 — idle at zero | 0 replicas, no lag | keep |
| Act 2 — signed wake | signature verified, stored as the answer | **keep — this is the talk** |
| Act 3 — forged *response* refused | the answer is refused *and inert* | **keep** |
| Act 6 — forged *request* refused | it woke, declined, went away | **keep** |
| Act 5 — audit trail | bound vs orphaned chains | compress to the summary line |
| Act 4 — causation | `ce_causationid` | → a slide |
| §8.1 — `/continue` after zero | a NEW pod resumes at the right sequence | cut 2nd |
| §8.2 — replay guard | 23 stale requests dropped | cut 1st |

Acts 3 and 6 both stay: act 3 forges an **answer** to real work, act 6 forges the **work
itself**. Different topics, different directions, different refusing functions. Neither
substitutes for the other.

**Say the ratio out loud: 2 signed of 6 events.** Terminal-only by policy, because Ed25519
here is pure Python and `emit()` runs per stdout frame. So the signature proves *who finished
a run*, not what it said along the way. That is the honest limit and someone will ask.

### §9 The claims that did not hold (21–25)

**The differentiator.** Nobody else will stand up and catalogue their own unsupported control
claims.

Three waves, and the progression is the point:

**Wave 1 — thirteen, found by reading.** Writing the user-facing docs meant restating every
control claim for a reader who cannot see the code. Six review rounds checked each by running
it. Thirteen did not hold. The worst:

> `EB_REQUIRE_RESPONSE_SIGNATURE=true` with no keyset **refuses nothing** — the decision is
> never reached. The request side with no key refuses **everything**. Both were documented as
> "refusal is on." One was true.

**Wave 2 — seven, found by running it on a cluster.** None reachable locally. The slide is
four rows and needs no explanation:

| Reported | Actually true |
| --- | --- |
| `ALL 40 CHECKS PASSED` | the image contained no signing code |
| `applied with 2 kid(s)` | the overlay overwrote the keyset with `{}` |
| `deploy not needed — digest matches` | the keyset was never applied |
| `response verification ON (ENFORCING)` | zero approved keys, refusing everything |

Each check verified an **intent** — what the tooling *sent* — rather than a **state**: what
the cluster actually *held*.

**Wave 3 — four more, found the same way, ten days later.** A full end-to-end run on
2026-10-19 found that a `--tag` flag was parsed and ignored (so the deploy ran five-day-old
code while 51 of 52 checks passed), that preflight rejected locally built images as
un-pullable, that the demo's own stages never signed in, and that `/continue` published no
submitter — so turns were accepted with 202 and then silently never ran.

**And the finding that outranks all of them.** Throughout, **the control held.** The runner
refused unsigned requests, correctly, including the system's own genuine traffic. It failed
closed, silently, while every indicator was green.

Then: *five separate times*, our own verification tooling accused a correctly-working control
of being bypassed. The most recent was filed four days ago (#23).

> **A false alarm about a control is its own category of failure.** It consumes exactly the
> attention a real breach would need — and it is produced by the verification tooling, which
> is therefore not exempt from needing verification.

**Close the section with the reusable part — five questions to ask of any control claim:**

1. Which code path, by name? Follow it to the *outcome*, not just to the check.
2. What is the default? (Most controls here default to off.)
3. What happens when it is **half-configured**? ← highest yield
4. Can an attacker choose the input the check reads — including by *omitting* it?
5. What does the claim become one release from now?

And a sixth the cluster run added: **is the thing you checked the thing that is running?**

**Tone: not an apology.** This is rigor, presented as rigor. Going first — saying the thirteen
out loud — turns open bugs from something a sharp attendee catches into evidence of care.

### §10 What's next, and the close (25–27)

**SPIRE is the named upgrade path, not a promise.** Two of the four seams name it and there is
no SPIRE. Be specific about why that is not a flag flip: the verifier accepts EdDSA only,
SPIRE issues EC or RSA, so it needs an issuer-agnostic verifier — which means adding EC/RSA
to hand-rolled pure-Python crypto, or relaxing the no-C-extensions rule and adopting
`cryptography`. **That is the dominant engineering cost of the remaining plan.**

Say the boundary out loud: *SPIRE would gate whether the agent runs; it does not sign what the
agent says.*

**The closing line, which is the talk's title earned rather than asserted:**

> The seams are the trap. Not because the projects are bad — because every claim about where
> two of them meet is a claim somebody has to run.

---

## 3. What I would still decide before building charts

1. **Does the deck name Kagenti/rossoctl, and how prominently?** The abstract commits to
   vendor neutrality with "Kagenti/rossoctl referenced as OSS and itself a composition, not a
   platform." One slide, clearly labelled as a composition, seems right — but it is a
   judgement call about the room.
2. **§6 or §9 first?** This draft puts the taxonomy before the demo and the failures after.
   The alternative — failures before the demo — makes the demo land as "and here is what
   survived", which is stronger but riskier: an audience primed on failure may discount what
   they then see work.
3. **Is there a live fallback if the recording fails?** The §15 checklist says record and
   narrate. Worth one backup slide of stills.
4. **Chart count.** This spine implies roughly 18–22 slides for 24 minutes. If the real
   constraint is a fixed template or a shorter slot, §6 and §9 are where to compress — not
   the demo.
