# Documentation style

Status: Accepted

How to write prose in this repository. The shape is borrowed from
[ASD-STE100](https://asd-ste100.org/) — Simplified Technical English — because the goal is
the same: a reader under time pressure, often not a native English speaker, who needs the
fact and not the flourish.

**This is about sentences, not about voice.** The rules below shorten and disambiguate.
They do not ask you to write blandly, and rule 6 exists to say so.

**Where this sits.** [`../CLAUDE.md`](../CLAUDE.md) § "Writing style for docs" governs
*what* a document must contain — be falsifiable, state the limits, write the correction as
the new fact. This file governs *how* the sentences read. Put a new rule in whichever file
it belongs to, rather than starting a third list. [`README.md`](README.md) decides which
*kind* of document you are writing in the first place.

---

## 1. One sentence, one fact

Cap descriptive prose at **25 words** and a procedural step at **20**.

The length in this repo comes almost entirely from semicolons, not from padding. When a
sentence runs long, look for `;` or `—` joining two independent facts and split there
first.

```diff
- a per-user ntfy topic must not contain the user's name, because the name travels to
-   the phone; a fetched skill bundle is a supply-chain artifact and passes five
-   fail-closed gates (source allowlist, empty by default because otherwise the runner
-   is an SSRF proxy; mandatory digest pinning; …)
+ **A per-user ntfy topic must not contain the user's name.** The name travels to the
+ phone.
+
+ **A fetched skill bundle is a supply-chain artifact.** It passes five fail-closed gates:
+
+ 1. a source allowlist, empty by default — otherwise the runner is an SSRF proxy
+ 2. mandatory digest pinning
```

A list of five things should look like a list of five things. Nested parentheticals hide
the count.

## 2. One word per concept

Pick one word for each action and keep it. A reader who meets `refuse` and `reject` on the
same page has to decide whether they are the same thing.

| Concept | Use | Not |
| --- | --- | --- |
| make an idle agent run | **wake** | start, trigger, invoke, launch, fire |
| decline an event, in prose | **refuse** | reject, deny, discard |
| decline an event, in code | **`rejected`** | — see below |
| put an event on a topic | **publish** | produce, emit, send |
| take an event off a topic | **consume** | read, pick up, pull down |
| confirm a signature | **verify** | validate, check |
| one prompt-and-reply exchange | **turn** | invocation, execution |
| show in a browser | **render** | display |
| remove a deployment | **delete** | tear down, destroy |

**`refuse` in prose, `rejected` in code.** This is not an inconsistency. `rejected` is
already a wire value and an identifier — `rejected_unsigned`, `is_rejected`, the literal
state `"rejected"` — so renaming it would break the audit tool and the stored verdicts.
Prose gets one verb; the protocol keeps its noun.

**Two words are deliberately not on the list.** `start` is fine in `cold start`,
`start offset` and `starting with`. `trigger` is a **Phase 3 feature name** with its own
`EXT_TRIGGERID` attribute. Do not rename either.

## 3. One action per step

A numbered step is one thing a reader does. If it contains "and then", it is two steps.

```diff
- 1. Deploy the overlay, then run the e2e test and check the replica count.
+ 1. Deploy the overlay.
+ 2. Run the e2e test.
+ 3. Check the replica count.
```

This matters most in `demos/`, which people read while typing. A step they cannot finish
in one action is a step they lose their place in.

## 4. Present tense, active voice, named actor

Say who does it.

```diff
- the signature is verified before the allowlist is consulted
+ EventRunner verifies the signature, then checks the allowlist
```

Passive voice hides the actor, and in this system the actor is the point: EventBridge
signs, EventRunner verifies, KEDA scales. Processes die; leases end; **EventRunner refuses
an unsigned terminal event.**

## 5. No `just`, `simply`, `easily`, `obviously`

These tell a stuck reader the problem is theirs.

```diff
- just pass --tag and it simply works
+ pass `--tag local1`. The deploy then patches both Deployments to that tag.
```

Also avoid `in order to` (use `to`), `a number of` (say how many), and `note that` (delete
it — the sentence after it is the note).

## 6. Keep the honesty markers

**This rule outranks brevity.** The most valuable sentences in these documents are the
ones that say what something does *not* do:

> "What the set does not do at all is attest anything. It records which keys an operator
> approved, not which workloads a platform vouched for." — `shared/keyset.py:33`
>
> "This proves who finished a run, not what it said along the way."
> — `docs/notes/kubecon-na-2026.md:812`, quoting spec 0003 §4.4 step 2

Do not shorten a limitation into a claim. If a rewrite makes a control sound stronger than
the code makes it, the rewrite is wrong. The same goes for the dry asides — "a cycle here
does not hang, *it bills*" is doing work, and it stays.

---

## What this does not apply to

- **`reports/`** — append-only by the rule in [`README.md`](README.md). A report records
  what was measured when it was written. Rewriting its prose, even harmlessly, erodes the
  one thing it is for. **Reports are exempt. Do not fix their sentences.**
- **Code blocks, command output, wire attribute names.** Transcribe them exactly. A
  shortened log line is a falsified log line.
- **Quoted material**, including docstrings quoted from source. Quote or rewrite, not both.

## Checking it

The repo has no linter for this, and a word-count gate would fight rule 6. Read the
diff and ask:

1. Is any sentence over 25 words? Can it split at a `;`?
2. Does one concept have two words on this page?
3. Does any numbered step contain "and then"?
4. Is there a `just` or a `simply`?
5. Did a limitation get quieter?

---

*Assisted-By: Claude Code*
