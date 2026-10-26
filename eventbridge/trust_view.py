"""The chain-of-trust page. One correlation, eight links, live.

The demo proves each control in its own beat. This is the page that shows them as a
chain — and shows, in the same glance, which links are weaker than a tick would suggest.

**Why amber exists.** Three of the eight links cannot be proven from stored evidence
(`eventbridge/trust.py` names them). A page of eight green ticks would be a more
confident claim than the evidence supports, which is the failure the talk this page was
built for is *about*. So amber is a first-class state with the reason rendered beside it,
not a footnote — and `limit` is the field a reader is meant to leave with.

Follows `group_view.py`: dark palette, `.card`, `.chip` where the class is the state, an
f-string body, and `string.Template` for the JS so literal braces pass through
unescaped. Updates by polling the JSON sibling once a second and patching in place —
the SSE stream carries `events_for()` rows, which drop `signature`, `kid` and
`causationid`, so it cannot answer a single question this page asks.
"""
from __future__ import annotations

import html
import json
from string import Template

_CSS = """
:root{--bg:#0f1115;--fg:#e6e6e6;--dim:#9aa0a6;--line:#262a31;--card:#161a20;
--ok:#3fb950;--run:#58a6ff;--fail:#f85149;--wait:#6e7681;--accent:#d29922}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:19px;margin:0 0 4px;font-weight:600}
a{color:var(--run);text-decoration:none}a:hover{text-decoration:underline}
.sub{color:var(--dim);font-size:13px;margin-bottom:18px}
.back{font-size:13px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin-bottom:16px}
.tally{font-size:26px;font-weight:650;letter-spacing:-.4px}
.tally .seg{margin-right:14px;white-space:nowrap}
.tally .n{font-variant-numeric:tabular-nums}
.g{color:var(--ok)}.a{color:var(--accent)}.r{color:var(--fail)}.w{color:var(--wait)}
.tally .lbl{color:var(--dim);font-weight:400;font-size:13px;margin-left:3px}
/* The chain. Each link is a row; the rail on the left is what makes it read as a
   sequence rather than a checklist. */
.chain{list-style:none;margin:0;padding:0}
.link{position:relative;padding:12px 0 12px 40px;border-bottom:1px solid var(--line)}
.link:last-child{border-bottom:0}
.link::before{content:"";position:absolute;left:11px;top:34px;bottom:-12px;width:2px;
background:var(--line)}
.link:last-child::before{display:none}
.mark{position:absolute;left:0;top:12px;width:24px;height:24px;border-radius:50%;
display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;
border:2px solid var(--line);background:#20242b;color:var(--wait)}
.link.green .mark{border-color:var(--ok);color:var(--ok);background:#0f2e18}
.link.amber .mark{border-color:var(--accent);color:var(--accent);background:#3d2b0d}
.link.red .mark{border-color:var(--fail);color:var(--fail);background:#3d1416}
.title{font-weight:600}
.headline{color:var(--dim);font-size:13px;margin-top:2px}
.headline .mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--fg)}
.ev{color:var(--dim);font-size:12px;margin-top:3px}
/* The limit is the point of the page, so it is styled to be read, not dismissed. */
.limit{margin-top:7px;padding:7px 10px;border-left:2px solid var(--accent);
background:#1d1a12;color:#d8cdb0;font-size:12.5px;border-radius:0 4px 4px 0}
.link.red .limit{border-color:var(--fail);background:#1f1416;color:#e3bdbd}
.chip{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;
font-weight:600;vertical-align:middle;margin-left:6px}
.chip.green{background:#0f2e18;color:var(--ok)}
.chip.amber{background:#3d2b0d;color:var(--accent)}
.chip.red{background:#3d1416;color:var(--fail)}
.chip.grey{background:#20242b;color:var(--wait)}
.note{margin-top:14px;padding:10px 12px;border-left:2px solid var(--accent);
background:#1d1a12;color:#d8cdb0;font-size:13px;border-radius:0 4px 4px 0}
.updated{margin-top:12px;color:var(--dim);font-size:12px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--ok);
margin-left:6px;vertical-align:middle;animation:pulse 2s ease-in-out infinite}
.dot.off{background:var(--wait);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@media (max-width:640px){.tally{font-size:20px}.tally .seg{display:block;margin:0 0 2px}}
"""

_GLYPH = {"green": "✓", "amber": "!", "red": "✕", "grey": "·"}

# Outside the f-string on purpose: embedded there, every literal JS brace needs doubling,
# which group_view.py records as the source of one bug. Template only touches $name.
_JS = Template("""<script>
const S = $state;
const $$ = (id) => document.getElementById(id);
const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
  return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
});
const GLYPH = {green: "\\u2713", amber: "!", red: "\\u2715", grey: "\\u00b7"};
let lastPayload = null, lastFetch = Date.now();

function linkHtml(l) {
  let h = '<li class="link ' + esc(l.state) + '" id="lk-' + esc(l.key) + '">';
  h += '<span class="mark">' + GLYPH[l.state] + '</span>';
  h += '<div class="title">' + esc(l.title)
    + '<span class="chip ' + esc(l.state) + '">' + esc(l.state) + '</span></div>';
  h += '<div class="headline"><span class="mono">' + esc(l.headline) + '</span></div>';
  if (l.evidence) h += '<div class="ev">' + esc(l.evidence) + '</div>';
  if (l.limit) h += '<div class="limit">' + esc(l.limit) + '</div>';
  return h + '</li>';
}

function paint(p) {
  $$("chain").innerHTML = p.links.map(linkHtml).join("");
  const t = p.tally;
  $$("tally").innerHTML =
      '<span class="seg g"><span class="n">' + t.green + '</span>'
    + '<span class="lbl">proven</span></span>'
    + '<span class="seg a"><span class="n">' + t.amber + '</span>'
    + '<span class="lbl">weaker than it looks</span></span>'
    + '<span class="seg r"><span class="n">' + t.red + '</span>'
    + '<span class="lbl">failed</span></span>'
    + '<span class="seg w"><span class="n">' + t.grey + '</span>'
    + '<span class="lbl">not reached</span></span>';
}

async function tick() {
  try {
    const r = await fetch(S.json_url, {cache: "no-store"});
    if (r.ok) {
      const p = await r.json();
      lastFetch = Date.now();
      const sig = JSON.stringify(p);
      if (sig !== lastPayload) { lastPayload = sig; paint(p); }
    }
  } catch (e) { /* keep the clock running; the next tick retries */ }
  setTimeout(tick, 1000);
}

// A separate ticker, so a stalled poll shows as a growing number rather than a page
// that merely looks fine. Same reasoning as the group page.
setInterval(function () {
  const age = Math.round((Date.now() - lastFetch) / 1000);
  $$("age").textContent = age <= 1 ? "just now" : age + "s ago";
  $$("dot").className = age > 4 ? "dot off" : "dot";
}, 1000);
setTimeout(tick, 1000);
</script>""")


def _link_html(ln: dict) -> str:
    state = ln.get("state", "grey")
    out = [f'<li class="link {html.escape(state)}" id="lk-{html.escape(ln["key"])}">',
           f'<span class="mark">{_GLYPH.get(state, "·")}</span>',
           f'<div class="title">{html.escape(ln["title"])}'
           f'<span class="chip {html.escape(state)}">{html.escape(state)}</span></div>',
           f'<div class="headline"><span class="mono">'
           f'{html.escape(ln.get("headline", ""))}</span></div>']
    if ln.get("evidence"):
        out.append(f'<div class="ev">{html.escape(ln["evidence"])}</div>')
    if ln.get("limit"):
        out.append(f'<div class="limit">{html.escape(ln["limit"])}</div>')
    out.append("</li>")
    return "".join(out)


def render(correlationid: str, links: list[dict], tally: dict, *,
           enforcing: bool = False, issuer: str = "", keyset_kids: int = 0) -> str:
    """Server-render, then the JS patches in place. A reload replays nothing."""
    corr = html.escape(correlationid)
    chain = "".join(_link_html(ln) for ln in links)
    tiles = (
        f'<span class="seg g"><span class="n">{tally.get("green", 0)}</span>'
        f'<span class="lbl">proven</span></span>'
        f'<span class="seg a"><span class="n">{tally.get("amber", 0)}</span>'
        f'<span class="lbl">weaker than it looks</span></span>'
        f'<span class="seg r"><span class="n">{tally.get("red", 0)}</span>'
        f'<span class="lbl">failed</span></span>'
        f'<span class="seg w"><span class="n">{tally.get("grey", 0)}</span>'
        f'<span class="lbl">not reached</span></span>'
    )

    # The honest-default banner. With no keyset nothing was checked, and a page that
    # stayed quiet about that would let colour imply verification that never happened.
    if not enforcing:
        banner = ('<div class="note"><strong>Verification is off.</strong> No approved-key '
                  'set is configured, so nothing on this page was checked against one. '
                  'What you see is what the events <em>claim</em>.</div>')
    else:
        iss = (f'identity vouched for by <strong>{html.escape(issuer)}</strong>'
               if issuer else
               'identity from a <strong>static token</strong> — an operator typed the '
               'name, so it is the weaker claim')
        banner = (f'<div class="note">Enforcing against <strong>{keyset_kids}</strong> '
                  f'approved key(s); {iss}.</div>')

    state = json.dumps({"json_url": f"/v0/agents/{correlationid}/trust?format=json"})
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>chain of trust — {corr}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<div class="back"><a href="/v0/agents/{corr}">&larr; transcript</a></div>
<h1>Chain of trust</h1>
<div class="sub"><span class="mono">{corr}</span></div>

<div class="card">
  <div class="tally" id="tally">{tiles}</div>
  {banner}
  <div class="updated">updated <span id="age">just now</span><span class="dot" id="dot"></span></div>
</div>

<div class="card"><ul class="chain" id="chain">{chain}</ul></div>

<div class="sub">Amber is not a softer green. It marks a link that is true but proves
less than a tick would suggest — the reason is beside each one. A page of eight ticks
would be exactly the kind of unchecked claim this system exists to catch.</div>
</div>
{_JS.substitute(state=state)}
</body></html>"""
