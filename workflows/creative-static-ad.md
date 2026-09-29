# Workflow: A static ad with an argument in it

**Goal:** get from "we need an ad for this product" to a set of composed, scored
prompts you would actually show someone — without going through the phase where
every route is the product on a white background.

Lives in **Ads → Static ad**. Four tabs, in the order you should use them.

---

## The one idea behind the whole section

A static ad fails in a way a portrait cannot: it can be technically perfect and
still say nothing. So this section scores two different things and keeps them
apart.

| | judged by | shows as |
|---|---|---|
| Is the image photographic? | `realism_lint`, the same 8 layers as everything else | the per-shot `8/8` |
| Is the idea any good? | `creative_ad_lint`, ten creative-direction commands | the Critique gate |

The second one is the point of this section. The first one it inherits for free.

**Three colours, three different claims.** Green means a rule verified it. Amber
means a human asserted it. Red means nobody has. Command 10 refuses to say
"campaign-ready" until both amber rows are ticked *and* every other row is green
— that is the whole reason for keeping rows a rule cannot judge.

---

## 1 — Idea

Fill **insight**, then **idea**, then the product and its tier.

The order matters and the gate enforces it. An insight is about a *person* and a
*friction*: "people rinse a bottle they are about to throw away, and feel
slightly ridiculous doing it." A strategic idea is what you do with that. If you
write the idea first you will write a description, and command 1 will say so.

**Tier is not decoration.** It changes what "good" means:

- **mass** — speaks plainly and fast; busy is allowed, because the job is to be
  understood by someone who was not looking.
- **premium** — one idea, generous space, nothing shouted. Most of the work is
  deciding what to leave out.
- **luxury** — subtraction as the whole strategy. The product may be small, late,
  or barely lit; the restraint *is* the claim.

## 2 — Routes

Add **at least two**. Command 9 fails on one, and it is not being pedantic: one
route is not a choice, it is a first idea you have not interrogated.

Each route needs a **territory**, a **name**, a **device** and a **rationale**.
The device is the thing the gate reads hardest, because that is where a route
quietly becomes a packshot. Write what the picture *does*, not what is in it.

Two ways the gate will stop you here:

- **Command 8** matches the `product_photo_tells` list — "on a white
  background", "floating", "three-quarter view". If your device contains one,
  you have written a product photo and called it a route.
- **Command 5** matches the cliché list through `realism_lint.find_terms()`,
  which is negation-aware — so "no sunset silhouette" rules the trope out
  rather than tripping on it.

## 3 — Art direction

Typography: dominance, ratio, zone, lockup, reading order, plus the restraint
checkboxes. This is command 6, and it is the one people skip because it feels
like a layout decision rather than a creative one. It is not: a headline that
competes with the product is a different ad from one that yields to it.

There is **no text in the generated image**, deliberately — `prompt_bank.json`
appends "no text, logo or watermark" to every prompt this app composes, so
rendered type would be fighting that negative. What you compose here is the
direction for whoever sets the type afterwards.

## 4 — Critique

The ten commands, as a gate.

Eight are decided by a rule. **Two cannot be:**

- *Is this directed, or merely described?*
- *Does this look like the tier it is priced at?*

Tick them yourself. They are checkboxes because no rule can read them, and they
render amber when ticked because "somebody said so" is a weaker claim than
"something checked it" and the gate should not pretend otherwise.

**For a second opinion, not a verdict:** `brief.critique_static_ad()` builds a
prompt that argues both of those two and nothing else. It returns no pass, no
score and no boolean — on purpose, so there is nothing to wire into a checkbox
and quietly turn your assertion back into a machine's verdict. It returns four
things: whether it reads as directed, whether the tier lands, which route is
carrying the least, and the single change it would make first.

Run it from the CLI when you want it:

```bash
python tools/creative_ad_lint.py --help     # the ten commands, and what each asks
```

---

## Handing off

**Copy prompts** puts every route's composed prompt on the clipboard, each one
labelled with its own `8/8`. That is the handoff — the same one Compose's
Midjourney button and Videos' Copy for Kling use.

**This section spends no money.** It composes and scores; it does not generate.
That is not an oversight: `confirm_spend` guards every paid path in the app, and
adding a generation button here would have been a change to how the app spends
money smuggled in as a change to how it critiques ideas.

To actually render a route, paste its prompt into **Images → Compose** and
generate there, where the confirmation and the cost note live.

---

## If you only remember one thing

The gate is not there to be passed. `10/10` on a brief you do not believe in
means the brief is *coherent*, not good — and command 3 is the row that exists
to make you say so out loud.
