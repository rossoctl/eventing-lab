# KubeCon NA 2026 — the screenplay

**The commands, in order, nothing else.** This is the card you hold while recording.
[`kubecon-na-2026-demo.md`](kubecon-na-2026-demo.md) is the reference — why each beat
exists, what it does *not* prove, and the full assertion list. This file is the shot list.

**Six beats, ~4 minutes of screen time.** The slides carry the explanation; the demo only
has to make the value *visible*. Every beat here answers one question in one screen.

| # | Beat | Question it answers | Screen time | State |
| --- | --- | --- | --- | --- |
| **0** | No pods at all | "What does idle cost?" | 15 s | ✅ verified |
| **1** | Approved user in, everyone else out | "Who may ask?" | 45 s | ✅ verified 2026-10-19 |
| **2** | 100 agents, one POST | "Does it scale?" | 90 s | ⚠️ **never run on a cluster** |
| **3** | Back to zero | "What does it cost when nobody asks?" | 30 s | ✅ verified |
| **4** | A forged wake is refused | "Who may answer?" | 45 s | ✅ verified 2026-10-14 |
| **5** | The audit trail | "How would you *know*?" | 30 s | ✅ verified 2026-10-14 |

**Record all of it.** Beat 3 cannot be done live — the cooldown is 30 s in the kind overlay
and 300 s in base, which is dead air either way. Beat 2 drains in about a minute. And the
ingress drops ~40% of POSTs ([#9](https://github.com/rossoctl/eventing-lab/issues/9)), so
every verified number came through a **port-forward** — a live POST over the Route is a
coin flip in front of a room. Narrate over the recording; keep a terminal open for
questions.

> **Beat 2 is not yet verified.** `--group 100` exists and is documented as the demo figure,
> but the 2026-10-14 cluster run never drove it — only a 2-member group for the forgery
> target. It needs one rehearsal run, which folds into
> [#14](https://github.com/rossoctl/eventing-lab/issues/14)'s rebuilt rig. **Do not record
> beat 2 until it has run once.** If it does not run in time, cut it and say the fan-out
> figure from a slide instead — the §1.2 rule applies: a cut beat is stated, not narrated.

---

## Setup — before the camera rolls

Not on screen. Done and warm before the first take.

```sh
# 1. Key material. Never committed; the overlay mounts it as a Secret.
python3 scripts/gen_signing_keys.py --out ~/.eventing-keys

# 2. The cluster: Strimzi, KEDA, ingress-nginx.
python3 scripts/kind_setup.py --check     # report gaps, change nothing
python3 scripts/kind_setup.py

# 3. Sign in, so beat 1 has a real GitHub identity rather than a pasted token.
eval "$(python3 scripts/login.py --client-id Ov23liA2Z4jfbFRoJKZn --open --export)"
echo "signed in as: ${DEMO_GH_LOGIN:?login did not come back — pass --gh-login by hand}"

# 4. Put YOUR login in the overlay. Both ship as CHANGEME on purpose.
#    EB_ALLOWED_USERS      — who may ask (EventBridge, at the edge)
#    ER_ALLOWED_SUBMITTERS — who the runner will act for
$EDITOR k8s/overlays/kind-signed-device/kustomization.yaml

# 5. Deploy with signing ENFORCED in both directions.
python3 scripts/k8s_deploy.py --yes --overlay kind-signed-device \
  --signing-keys ~/.eventing-keys

# 6. Port-forward, and keep it up for the whole recording. NOT the ingress (#9).
kubectl -n kev1 port-forward svc/eventbridge 18080:8080 &
export EB=http://127.0.0.1:18080

# 7. Prove the whole thing green once, before recording a single frame.
python3 scripts/k8s_demo_flow.py --overlay kind-signed-device \
  --gh-login "$DEMO_GH_LOGIN" --public-url "$EB" --tag local1
```

Step 7 is the rehearsal. **If it does not report all checks passed, do not record** — every
beat below is a slice of that run, and the flow is what proves the slices are honest.

**Two panes, side by side, for every beat.** Left: the command. Right:
`watch_topics.py` running. The queue depth is the through-line of the whole demo and the
thing that makes KEDA concrete rather than a slogan.

```sh
# the right-hand pane, started once and left alone
python3 scripts/watch_topics.py --interval 2
```

---

## Beat 0 — there are no pods  (15 s)

```sh
kubectl -n kev1 get deploy eventrunner
```

```text
NAME          READY   UP-TO-DATE   AVAILABLE   AGE
eventrunner   0/0     0            0           12m
```

**Say:** "No agent is running. Not idle — *absent*. Nothing is consuming, nothing is
costing anything. The only thing that will create a replica is depth on a Kafka topic."

**Why it opens the demo:** it is the baseline beats 2 and 3 are measured against. Skip it
and the fan-out has nothing to fan out *from*.

---

## Beat 1 — who may ask  (45 s)

Three POSTs. The first two fail, and they fail *differently*.

```sh
# (a) no credential at all
curl -i -sS -X POST "$EB/v0/agents" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Summarise the incident.","max_turns":1}' | head -6

# (b) a token that is not a GitHub token
curl -i -sS -X POST "$EB/v0/agents" \
  -H 'Authorization: Bearer ghp_definitely_not_a_real_token' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Summarise the incident.","max_turns":1}' | head -4

# (c) the approved user
CORR=$(curl -sS -X POST "$EB/v0/agents" \
  -H "Authorization: Bearer $DEMO_GH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Summarise the incident.","max_turns":1}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["correlationid"])')
echo "accepted as $CORR"

# and who the event says asked — read back off the turn tape, not typed by the caller
curl -sS "$EB/v0/agents/$CORR/turns" \
  -H "Authorization: Bearer $DEMO_GH_TOKEN" | python3 -m json.tool | grep -i submitter
```

```text
(a) HTTP/1.1 401 Unauthorized
    WWW-Authenticate: Bearer realm="eventbridge"
(b) HTTP/1.1 401 Unauthorized
(c) accepted as brave-otter-4718
    "submitter": "<your-login>",
    "submitteriss": "github"
```

**Say:** "The first request was not refused by a signature check — it never became an event
at all. EventBridge refuses before the first write: no transcript, no correlation id,
nothing on the topic. The third request is the same request, from a user on the approved
list — and the event now records *who asked*, verified by GitHub rather than typed by the
caller."

**The line that makes it more than HTTP status codes:** `submitter` is in
`signing.SIGNED_ATTRS`, so the identity is covered by the signature and **cannot be
relabelled in flight**. That is why the runner checks its allowlist *after* the signature
check, not before.

**If a 403 would land better than a 401:** add a login that is *not* on the approved list
and show it — `403`, with the body naming the refused login, and deliberately **no**
`WWW-Authenticate`, because retrying with another credential is not the remedy. Costs
another 15 s; the 401/403 distinction is a good slide either way.

---

## Beat 2 — 100 agents, one POST  (90 s)  ⚠️ REHEARSE FIRST

The centrepiece. One call submits a hundred agents; KEDA does the rest.

```sh
GID=$(curl -sS -X POST "$EB/v0/groups" \
  -H "Authorization: Bearer $DEMO_GH_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c '
import json
print(json.dumps({"label": "kubecon-100",
                  "prompts": [f"Triage finding {i+1}. Reply OK." for i in range(100)],
                  "max_turns": 1}))')" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["groupid"])')
echo "batch $GID"
```

Then let the two panes tell the story — do not type anything else for ~60 s.

```sh
# left pane: the batch, in user units
python3 scripts/watch_topics.py --group "$GID" --url "$EB" --interval 2

# a third pane, or cut to it: the pods appearing
kubectl -n kev1 get pods -l app.kubernetes.io/name=eventrunner -w
```

**On screen, in this order:** lag jumps to 100 → `0/0` becomes `1/1`, then more → pods
appear until **10** → the group page's percentage climbs → lag drains to 0.

**Say:** "One POST, a hundred agents. Nobody provisioned anything. KEDA is reading queue
depth and creating pods — it stops at ten because `maxReplicaCount` is ten, and because
the topic has twelve partitions, which is the real ceiling: a partition is the unit of
assignment, so eleven pods would leave one idle."

**The detail worth pointing at:** the watcher splits lag into *claimed* and *unclaimed*.
That split exists because this system defers the Kafka offset commit until the agent's
terminal event — so **lag means "work not finished", not "work not read"**. It is a correct
queue gauge, and it is also what makes it structurally impossible for KEDA to scale away a
pod mid-run.

**Limits to state, since the talk is about unchecked claims:** mock mode, so this measures
the event path and not a hundred real model calls; one Kind node; and the batch figure from
Phase 1 (100 agents in 1m02s) was a different repo, pre-signing — use the number from your
own rehearsal, not that one.

---

## Beat 3 — back to zero  (30 s)

```sh
kubectl -n kev1 get deploy eventrunner -w
```

```text
eventrunner   10/10
eventrunner   0/0        # ~30s after the last terminal event
```

**Say:** "The queue is empty, so the capacity goes away. Scale-to-zero is not a cost
optimisation here — it is the thing that makes the trust-scope question interesting, because
an allowlist read at pod start is re-read on the *next* wake. Change it while there are zero
pods and the next request is judged by the new rules."

**Cut the wait in the edit.** An explicit on-screen `+30 s` jump is honest and keeps the
pace; dead air is not. The cooldown is 30 s in the kind overlay, 300 s in base — say which
rig if a number appears on a slide.

---

## Beat 4 — who may answer  (45 s)

A forged **wake** — an event injected straight onto the requests topic, correctly encoded
and unsigned, exactly as an attacker with broker access would write it.

There is no flag that runs this stage alone — `--skip` is declared but unused, so passing
it does nothing and you get the whole flow. The shortest honest path is the fast flow, then
cut to the log in the edit:

```sh
# ~2 min: skips the two slow gates, keeps every signed beat
python3 scripts/k8s_demo_flow.py --overlay kind-signed-device \
  --gh-login "$DEMO_GH_LOGIN" --public-url "$EB" --tag local1 \
  --skip-cold-continue --skip-idle-replay
```

The frame that matters is the runner refusing it:

```sh
kubectl -n kev1 logs deploy/eventrunner --tail=-1 | grep -i 'reject\|unsigned'
```

```text
[eventrunner] rejecting unsigned/badly-signed request corr=forged-1761…:
  no ce_signature attribute (ER_REQUIRE_SIGNATURE=true) — offset committed, not retried
```

**Say:** "That event reached the broker. Anything with network access to Kafka can write to
a topic — the broker is plaintext and this demo does not pretend otherwise. What it cannot
do is make an agent *act*. The runner verified the signature against an approved key set,
refused it, committed the offset so it is not retried, and **never started the agent**."

**The sentence that lands the seam:** "The broker handed off the event. The *runner* is what
refused it. That is the difference between a queue and a trust boundary — and the abstract
calls it unverified delivery."

**One honest limit:** signing covers terminal events only, because Ed25519 in pure Python
costs ~190–230 ms per operation and signing every streamed frame would add minutes to a
chatty run. So this proves **who finished a run, not what it said along the way**. Say it;
someone will ask.

---

## Beat 5 — how would you know?  (30 s)

Beat 4 showed the gate holding. This is the question auditors actually ask.

```sh
python3 scripts/audit_topic.py --chains
```

```text
  wake 27504bea  brave-otter-4718   2 result(s)  BOUND
         wake and result both verified
  wake (none)    -                  1 result(s)  ORPHANED
         results naming a wake event that is not on this topic

summary
  signed-ok     29
  signed-BAD     2
  unsigned       4
  unsigned-ok   76
  terminals     15 (13 verified)
```

**Say:** "Every result is chained back to the signed wake event that caused it —
`causationid`, which is itself inside the signature, so the link cannot be rewritten. The
forgery shows up as `ORPHANED`: an answer to a question nobody asked. And `unsigned-ok` is
seventy-six streamed frames that are unsigned *by policy* — a tool that flagged those would
bury the two findings that matter in noise."

**Why it closes the demo:** beats 1 and 4 are controls — they say no. This says *what
happened*, after the fact, from the log alone. That is the fourth seam, and the one most
teams discover they cannot answer.

---

## If you are over time

Cut in this order. Each cut is stated on a slide, never narrated as if it ran.

1. **Beat 3** (back to zero) — fold it into beat 2's tail as a single `+30 s` jump.
2. **Beat 5's chain view** — keep the summary line only.
3. **Beat 1's 403 variant**, if you added it.
4. **Beat 2** — if it has not been rehearsed, it was never in. Say the figure from a slide.

**Never cut beats 1 and 4.** Those two are the talk: who may ask, and who may answer.

---

## The one-command fallback

If the edit falls apart the night before, this drives acts 1–7 with assertions and timings
and can be screen-captured as-is. Less cinematic, entirely honest, and it prints its own
verdict:

```sh
python3 scripts/k8s_demo_flow.py --overlay kind-signed-device \
  --gh-login "$DEMO_GH_LOGIN" --public-url "$EB" --tag local1 --group 100
```

---

## Pre-flight, the night before

- [ ] `k8s_demo_flow.py` reports **all checks passed** on the rig you will record on
- [ ] Beat 2 rehearsed at least once — the fan-out reached 10 pods and drained
- [ ] `DEMO_GH_LOGIN` is non-empty (`login.py` can emit a token without it; §8.3)
- [ ] Port-forward up; **the public Route is NOT exposed** ([#1](https://github.com/rossoctl/eventing-lab/issues/1): `PUT /transcript` is unauthenticated)
- [ ] Every number that reaches a slide is labelled with the cluster it came from
- [ ] Terminal font large enough to read at the back of the room
- [ ] `watch_topics.py` pane is wide enough that the claimed/unclaimed split does not wrap
