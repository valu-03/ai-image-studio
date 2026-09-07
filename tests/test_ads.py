"""The UGC ads section: timing, the gate, and the storyboard through the real UI.

The LumaWash worked example is the fixture. It must score full marks - including
beat 4's "zero sulfates, zero harsh chemicals", which is specification language
in the one beat where that is correct. If the emotion check ever starts flagging
that line, the linter has drifted into rejecting good ads and this suite says so.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

_EMPTY_ENV = Path(tempfile.gettempdir()) / "aivs-tests-empty.env"
_EMPTY_ENV.write_text("# intentionally empty" + chr(10), encoding="utf-8")
os.environ["AIVS_ENV_FILE"] = str(_EMPTY_ENV)
# A modal "are you sure" nobody can click is a hang, not a safeguard, so the
# spend confirmation is answered for us. It still prints the estimate.
os.environ.setdefault("AIVS_ASSUME_YES", "1")
# MainWindow reads AIVS_SETTINGS_APP at import time to pick which QSettings
# key it opens - without this the GUI test read AND WROTE the user's real
# saved provider/model/theme/window geometry.
os.environ.setdefault("AIVS_SETTINGS_APP", "Studio-Tests")

from PyQt6.QtWidgets import QApplication

import ad_lint as al
import build_ad as ba
import brief
import build_prompt as bp
import realism_lint as rl
from ui.main_window import MainWindow, NAV_ITEMS
from ui.theme import ThemeManager

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


bank = ba.load_bank()
image_bank = bp.load_bank()

# The worked example, verbatim.
LUMA = {
    "pain": "Your hair gets greasy 5 hours after washing it.",
    "relatable": "You've tried everything - drugstore brands, salon brands, TikTok hacks - "
                 "and still your scalp's a mess and your ends feel like straw.",
    "shift": "What if you could go 3 days without washing your hair - and still feel fresh?",
    "solution": "It's called LumaWash. A shampoo made with zero sulfates, zero harsh "
                "chemicals - and a formula that balances your scalp naturally.",
    "proof": "Over 10,000 bottles sold last month. Customers say their hair changed in just "
             "3 washes. And this week only, we're giving 20% off to first-time customers.",
}
BASE = {"subject": "a woman in her early thirties with dark wavy hair", "seed": 0,
        "setting": "a bright bathroom, morning"}

print("--- the bank ---")
check("five beats", len(ba.beats(bank)) == 5, str(len(ba.beats(bank))))
check("beats in order", [b["key"] for b in ba.beats(bank)]
      == ["pain", "relatable", "shift", "solution", "proof"])
check("four platforms", len(ba.platforms(bank)) == 4, str(len(ba.platforms(bank))))
check("every platform maps to a real purpose",
      all(cfg["purpose"] in image_bank["purposes"] for cfg in ba.platforms(bank).values()),
      str([cfg["purpose"] for cfg in ba.platforms(bank).values()]))
check("every beat suggests a real movement",
      all(b["movement"] in __import__("build_motion").load_bank()["movements"]
          for b in ba.beats(bank)))
check("only beat 4 and 5 sell the mechanism",
      [b["sells"] for b in ba.beats(bank)]
      == ["feeling", "feeling", "feeling", "mechanism", "mechanism"])

print("--- timing: the rule an even split breaks ---")
limit = bank["timing"]["product_by"]
bad = []
for platform, cfg in ba.platforms(bank).items():
    for seconds in cfg["lengths"]:
        timings = ba.beat_timings(bank, seconds, platform)
        starts = [t[1] for t in timings]
        product = starts[3]
        hook = timings[0][2]
        total = sum(t[2] for t in timings)
        if not (4 <= product <= limit):
            bad.append("{}/{}s product at {:.1f}s".format(platform, seconds, product))
        if hook > cfg["first_clip_seconds"] + 0.05:
            bad.append("{}/{}s hook {:.1f}s".format(platform, seconds, hook))
        if abs(total - seconds) > 0.05:
            bad.append("{}/{}s sums to {:.1f}".format(platform, seconds, total))
        if starts != sorted(starts):
            bad.append("{}/{}s out of order".format(platform, seconds))
check("12 platform x length combinations all hold", not bad, "; ".join(bad[:3]))

even = [b["weight"] for b in ba.beats(bank)]
check("weights are not equal", len(set(even)) > 1, str(even))
check("a 30s ad still shows the product by 10s",
      ba.product_starts_at(bank, 30, "tiktok") <= limit,
      "{:.1f}s".format(ba.product_starts_at(bank, 30, "tiktok")))
check("a 60s ad still shows the product by 10s",
      ba.product_starts_at(bank, 60, "youtube") <= limit,
      "{:.1f}s".format(ba.product_starts_at(bank, 60, "youtube")))

print("--- the LumaWash example is the fixture ---")
shots = ba.compose_ad(bank, BASE, "tiktok", 20, copy=LUMA, image_bank=image_bank)
results = al.lint(bank, shots, "tiktok", 20)
got, total = al.score(results)
for _, label, passed, detail in results:
    check("LumaWash: " + label, passed, detail)
check("LumaWash scores full marks", got == total, "{}/{}".format(got, total))

emotion = next((detail for key, _, passed, detail in results if key == "emotion"), "")
check("beat 4's 'zero sulfates' does not trip the emotion check",
      "beat 4" not in emotion, emotion)

print("--- every still in the ad still passes the realism gate ---")
weak = []
for shot in shots:
    present, _, banned, _, _ = rl.lint(shot["prompt"].lower(), image_bank)
    if len(present) != 8 or banned:
        weak.append("{} {}/8".format(shot["key"], len(present)))
check("all five shots are 8/8", not weak, ", ".join(weak))
check("every shot carries a motion prompt",
      all(s["motion_prompt"] for s in shots))
check("the platform's aspect reaches every shot",
      {s["spec"]["aspect"] for s in shots} == {"9:16"},
      str({s["spec"].get("aspect") for s in shots}))

print("--- one presenter across five shots ---")
locked = ba.compose_ad(bank, BASE, "tiktok", 20, copy=LUMA,
                       reference="temp/outputs/images/ref.png", image_bank=image_bank)
check("beat 1 invents the face", not locked[0]["spec"].get("lock_identity"))
check("beats 2-5 lock to it", all(s["spec"].get("lock_identity") for s in locked[1:]))
check("beats 2-5 carry the reference",
      all(s["spec"].get("reference") for s in locked[1:]))
check("each beat has its own slug",
      len({s["spec"]["slug"] for s in locked}) == 5)

print("--- the gate rejects what it should ---")
missing = ba.compose_ad(bank, BASE, "tiktok", 20,
                        copy={k: v for k, v in LUMA.items() if k != "proof"},
                        image_bank=image_bank)
res = al.lint(bank, missing, "tiktok", 20)
check("no beat-5 copy fails", not dict((k, p) for k, _, p, _ in res)["proof"])

specy = dict(LUMA)
specy["pain"] = "Our formulation delivers 17 active ingredients at clinically proven percentages."
res = al.lint(bank, ba.compose_ad(bank, BASE, "tiktok", 20, copy=specy, image_bank=image_bank),
              "tiktok", 20)
row = next((d for k, _, p, d in res if k == "emotion" and not p), "")
check("a spec-sheet opener is rejected", row and "beat 1" in row, row[:80])

no_urgency = dict(LUMA)
no_urgency["proof"] = "Over 10,000 bottles sold last month."
res = al.lint(bank, ba.compose_ad(bank, BASE, "tiktok", 20, copy=no_urgency,
                                  image_bank=image_bank), "tiktok", 20)
row = next((d for k, _, p, d in res if k == "proof" and not p), "")
check("proof without urgency is caught, and named", "urgency" in row, row[:80])

no_proof = dict(LUMA)
no_proof["proof"] = "This week only, grab yours before it ends."
res = al.lint(bank, ba.compose_ad(bank, BASE, "tiktok", 20, copy=no_proof,
                                  image_bank=image_bank), "tiktok", 20)
row = next((d for k, _, p, d in res if k == "proof" and not p), "")
check("urgency without proof is caught", "no proof" in row, row[:80])

check("a quantity counts as proof on its own",
      al.has_proof(bank, "Over 10,000 women swear by it."))
check("a discount is not social proof",
      not al.has_proof(bank, "This week only, 20% off."))

print("--- validators ---")
check("unknown platform rejected", ba.validate_platform(bank, "myspace") is not None)
check("known platform accepted", ba.validate_platform(bank, "tiktok") is None)
check("unknown emotion rejected", ba.validate_emotion(bank, "ennui") is not None)
check("a 35s TikTok ad is refused", ba.validate_length(bank, "tiktok", 35) is not None)
check("a 20s TikTok ad is fine", ba.validate_length(bank, "tiktok", 20) is None)

print("--- the copy gate (injected model replies) ---")
GOOD = ('{"pain":"Your hair gets greasy 5 hours after washing it.",'
        '"relatable":"You have tried everything and your ends still feel like straw.",'
        '"shift":"What if you could go 3 days and still feel fresh?",'
        '"solution":"It is called LumaWash, a sulfate-free shampoo.",'
        '"proof":"Over 10,000 bottles sold. This week only, 20% off - tap to shop."}')
r = brief.copy_from_idea(bank, image_bank, "LumaWash", "women 25-40", "tiktok", "relief",
                         ask=lambda *a, **k: (GOOD, None))
check("a good reply is accepted", r["ok"] and r["accepted"],
      r.get("reason", "")[:90])

BAD = ('{"pain":"Our formulation uses 17 active ingredients at clinically proven '
       'percentages.","relatable":"Advanced proprietary technology.","shift":'
       '"Engineered molecules.","solution":"It is called LumaWash.","proof":"Sold."}')
r = brief.copy_from_idea(bank, image_bank, "LumaWash", "women 25-40", "tiktok", "relief",
                         ask=lambda *a, **k: (BAD, None))
check("a spec-sheet reply is rejected", r["ok"] and not r["accepted"])
check("and says why", "specifications" in r["reason"], r["reason"][:90])

r = brief.copy_from_idea(bank, image_bank, "x", "y", "tiktok",
                         ask=lambda *a, **k: ('{"pain":"only this"}', None))
check("a partial reply is rejected", not r["ok"] and "skipped" in r["error"], str(r)[:90])

r = brief.copy_from_idea(bank, image_bank, "x", "y", "tiktok",
                         ask=lambda *a, **k: (None, "OPENROUTER_API_KEY is not set"))
check("no key fails cleanly", not r["ok"])

r = brief.copy_from_idea(bank, image_bank, "x", "y", "tiktok",
                         ask=lambda *a, **k: ('{"pain":"a","seed":99,"reference":"/etc/x"}', None))
check("the model cannot set seed or reference",
      "seed" in r.get("error", "") or "seed" not in str(r.get("copy", {})))

# ---------------------------------------------------------------- the UI ---- #
app = QApplication(sys.argv)
theme = ThemeManager(app)
theme.apply("dark")
win = MainWindow(theme)
win.show()
app.processEvents()

av = win.ads_view

print("--- the seventh nav section ---")
check("ads is in the rail", "ads" in win.nav_buttons)
check("its icon is not null", not win.nav_buttons["ads"].icon().isNull())
check("a view per nav item", win.stack.count() == len(NAV_ITEMS))
win.go_to("ads")
check("reachable", win.stack.currentIndex() == list(win.nav_buttons).index("ads"))
check("title follows", win.view_title.text() == "Ads", win.view_title.text())
check("five sub-tabs", av.tabs.count() == 5, str(av.tabs.count()))
check("tab names", [av.tabs.tabText(i) for i in range(5)]
      == ["Brief", "Storyboard", "Variants", "Checklist", "Publishing"],
      str([av.tabs.tabText(i) for i in range(5)]))

print("--- the storyboard reflects the brief ---")
av.platform.setCurrentIndex(av.platform.findData("tiktok"))
av.seconds.setValue(20)
av.set_copy(LUMA)
app.processEvents()
check("five beat rows", av.beat_tree.topLevelItemCount() == 5,
      str(av.beat_tree.topLevelItemCount()))
check("gate passes on the worked example", av.passing, av.lint_badge.text())
check("badge shows the full score", av.lint_badge.text() == "9/9", av.lint_badge.text())
check("timing line names the deadline", "by 10s" in av.timing_label.text(),
      av.timing_label.text())

print("--- switching platform re-times the ad ---")
av.platform.setCurrentIndex(av.platform.findData("youtube"))
app.processEvents()
check("length moved to YouTube's default", av.seconds.value() == 45, str(av.seconds.value()))
check("product still inside 10s",
      ba.product_starts_at(bank, av.seconds.value(), "youtube") <= limit)
check("aspect followed the platform",
      av.shots[0]["spec"]["aspect"] == "16:9", av.shots[0]["spec"].get("aspect"))
av.platform.setCurrentIndex(av.platform.findData("tiktok"))
app.processEvents()

print("--- a broken ad shows red rows, not a crash ---")
av.set_copy({k: v for k, v in LUMA.items() if k != "proof"})
app.processEvents()
check("gate fails", not av.passing, av.lint_badge.text())
check("rows still render", av.gate.tree.topLevelItemCount() == 9,
      str(av.gate.tree.topLevelItemCount()))
av.set_copy(LUMA)
app.processEvents()

print("--- the checklist splits auto from manual ---")
check("all seven sections", av.checklist_tree.topLevelItemCount() == 7,
      str(av.checklist_tree.topLevelItemCount()))
marks = []
for i in range(av.checklist_tree.topLevelItemCount()):
    parent = av.checklist_tree.topLevelItem(i)
    for j in range(parent.childCount()):
        marks.append((parent.child(j).text(0), parent.child(j).text(2)))
check("some rows are checked by the app", any(m and h == "checked by the app"
                                              for m, h in marks))
check("some rows are left to the user", any(h == "yours to judge" for _, h in marks))
check("no row claims to be checked without a mark",
      all(m for m, h in marks if h == "checked by the app"))

print("--- A/B on the hook ---")
av.hook_list.setPlainText(
    "Your hair gets greasy 5 hours after washing it." + chr(10)
    + "Our formulation contains 17 clinically proven ingredients.")
av.check_hooks()
app.processEvents()
check("both hooks scored", av.hook_tree.topLevelItemCount() == 2,
      str(av.hook_tree.topLevelItemCount()))
check("the spec-sheet hook is called out",
      "specification" in av.hook_tree.topLevelItem(1).text(2).lower(),
      av.hook_tree.topLevelItem(1).text(2)[:70])

print("--- publishing is reference only ---")
check("publishing rows present", av.tabs.widget(4) is not None)

print("--- generation is refused on a provider with no references ---")
sent = []
av.generate_requested.connect(lambda jobs: sent.append(jobs))
win.provider = "higgsfield"
av.request_generate()
app.processEvents()
check("five jobs were offered", sent and len(sent[-1]) == 5, str(len(sent[-1]) if sent else 0))
check("but the controller refused them",
      "different characters" in win.statusBar().currentMessage(),
      win.statusBar().currentMessage()[:80])
check("and nothing was submitted", not win.pool.busy)
win.provider = "kie"

# The refusal was always right; the submission used to ignore it. Every job went
# out with an EMPTY reference list, so the five shots were five different people
# on a provider that supports references too.
print("--- a locked sequence really carries the reference ---")
submitted = []
options = []


def fake_submit(jobs, provider=None, model=None, spec=None):
    submitted.append(list(jobs))
    options.append(dict(spec or {}))


win.pool.submit = fake_submit
av.request_generate()
app.processEvents()
check("only the first shot goes out alone", len(submitted) == 1 and len(submitted[0]) == 1,
      str([len(batch) for batch in submitted]))
check("and it carries no reference, because none exists yet",
      submitted[0][0][3] == [], str(submitted[0][0][3]))

win.on_item_finished(0, "temp/outputs/images/ad-1-pain.png")
win.on_batch_finished()
app.processEvents()
check("then the rest follow", len(submitted) == 2 and len(submitted[1]) == 4,
      str([len(batch) for batch in submitted]))
check("every one of them locked to the first shot's actual file",
      all(job[3] == ["temp/outputs/images/ad-1-pain.png"] for job in submitted[1]),
      str(submitted[1][0][3]))

# The GUI never passed a spec at all, so no aspect ratio and no resolution ever
# reached the provider - every image came back 1:1 at 1K whatever was selected.
check("the request carries the aspect the shot asked for",
      options[0].get("aspect") == av.shots[0]["spec"].get("aspect"),
      str(options[0]))
check("and the account's resolution and format",
      options[0].get("resolution") and options[0].get("output_format"),
      str(options[0]))

print()
if fails:
    print("FAILURES: " + ", ".join(fails))
    sys.exit(1)
print("ALL ADS CHECKS PASSED")
sys.exit(0)
