"""Local API - lets Skit Studio use this app's image engine and Look while it is open.

The same idea as VoiceStudio's local API on port 3900: while AI Video Studio
runs, a small HTTP server on 127.0.0.1 answers Skit Studio (or any loopback
caller). Skit Studio sends its scene prompt and reference sheets; this app adds
the Look (the phrases the Look tab builds), generates through the same
generate_image.generate() the Compose tab uses, and records the result in
History tagged "Skit Studio".

Routes (all JSON unless noted):
  GET  /api/v1/health             app, version, which image keys are set
  GET  /api/v1/look/options       every Look list (lighting, camera, style, ...)
  GET  /api/v1/look/current       the Look phrases currently on the Compose form
  POST /api/v1/look/compose       Look choices -> phrases (the Build tabs' tools)
  POST /api/v1/prompt             {prompt, look, realism} -> the finished prompt, no spend
                                  (for pasting into Google Flow or any other tool)
  POST /api/v1/images             {prompt, look, realism, refine, references, aspect, ...} -> {id}
  GET  /api/v1/images/<id>        {state, stage, error, file, attempts, chosen, realism}
  GET  /api/v1/images/<id>/file   the image bytes (the chosen attempt)
  POST /api/v1/images/<id>/cancel stop before the next Refine retry

`realism` runs the Images tab's own free switches on a typed prompt - Phone
snapshot look, Unstaged background, Catch the moment, Match light to the scene,
Weight & contact, Materials, Lived-in details, Face (coat) micro-detail - read
from the subject / action / setting the caller names, then fills whichever of
the eight realism layers are still missing from the bank, so the prompt clears
the same 8/8 gate Compose does. `refine` (0-2 retries) is Compose's Refine:
generate, have the vision critique name the weak layer, strengthen it with the
bank's own words and try again, keeping the attempt the critique liked best.

Loopback only. An optional bearer token (AIVS_LOCAL_API_TOKEN) is required
when set. Spending: the caller's own approval gate is the yes - Skit Studio
shows its estimate and waits for Approve before it ever calls /images.

Run headless (no window) with:  python tools/local_api.py --serve
"""
import argparse
import base64
import hmac
import json
import mimetypes
import random
import re
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_camera_angle as bca  # noqa: E402
import build_capture as bcap  # noqa: E402
import build_color as bcol  # noqa: E402
import build_composition as bcomp  # noqa: E402
import ask_llm  # noqa: E402
import brief  # noqa: E402
import build_evidence as bev  # noqa: E402
import build_face_detail as bfd  # noqa: E402
import build_lighting as bl  # noqa: E402
import build_posing as bpos  # noqa: E402
import build_prompt as bp  # noqa: E402
import build_snapshot as bsn  # noqa: E402
import build_style as bst  # noqa: E402
import generate_image as gi  # noqa: E402
import history  # noqa: E402
import realism_lint as rl  # noqa: E402
import scene_variety as sv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = "AI Video Studio"
VERSION = 1
DEFAULT_PORT = 8785
PORT_VAR = "AIVS_LOCAL_API_PORT"
TOKEN_VAR = "AIVS_LOCAL_API_TOKEN"
# Same ceiling as ui/workers.py MAX_CONCURRENCY - Kie throttles past it.
MAX_JOBS = 3
KEEP_JOBS = 200
# A still plus up to three reference sheets, base64'd, is a few MB; refuse anything silly.
MAX_BODY = 40 * 1024 * 1024
REF_DIR = ROOT / "temp" / "outputs" / "local_api"
HISTORY_NOTE = "Skit Studio"

# Prompt order: style leads (it sets the whole medium), the rest follow the
# scene in the order a photographer would describe a shot.
LOOK_KEYS = ("style", "lighting", "camera", "composition", "posing", "color",
             "capture", "evidence")


# The Images tab's free switches, in the order build_prompt.compose() resolves
# them. Each reads the subject / action / setting and only ever adds a phrase.
REALISM_SWITCHES = ("face_detail", "lived_in", "scene_lighting", "contact_detail",
                    "material_detail", "snapshot", "background_life", "moment")
REALISM_TEXT = ("subject", "action", "setting", "shot", "species", "kind")
SUBJECT_KINDS = ("animal", "human", "object", "place")
# refine_image.DEFAULT_MAX_RETRIES - an unlucky prompt can never spend more than three images.
MAX_REFINE = 2
REFINE_NOTE = "Skit Studio - Refine attempt {}"
# Light no one filming on a phone at home has: a studio rig or painterly contrast.
PHONE_LIGHT_SKIP = ("chiaroscuro lighting", "studio softbox lighting")


class LookError(ValueError):
    """A Look choice the bank does not know, named by its part."""


# --------------------------------------------------------------------------- #
# Look
# --------------------------------------------------------------------------- #
def _labels(table, phrase_field="phrase"):
    return [{"key": key, "label": cfg.get("label", key),
             "phrase": cfg.get(phrase_field, "")}
            for key, cfg in table.items()]


def look_options():
    """Every list the Look tab offers, as {part: {field: [{key, label, phrase}]}}."""
    light = bl.load_bank()
    main = bp.load_bank()
    comp = bcomp.load_bank()
    cam = bca.load_bank()
    col = bcol.load_bank()
    pos = bpos.load_bank()
    sty = bst.load_bank()
    cap = bcap.load_bank()
    evi = bev.load_bank()
    styles = [dict(item, group=cfg["group"])
              for item, cfg in zip(_labels(bst.all_styles(sty), "keywords"),
                                   bst.all_styles(sty).values())]
    return {
        "lighting": {
            "setups": _labels(bl.setups(light)),
            "directions": _labels(bl.directions(light)),
            "qualities": _labels(bl.qualities(light)),
            "sources": _labels(bl.sources(light)),
            "techniques": _labels(bl.techniques(light)),
        },
        "composition": {
            "guides": _labels(bp.guides(main)),
            "techniques": _labels(bcomp.techniques(comp)),
        },
        "camera": {
            "verticals": _labels(bca.verticals(cam)),
            "sides": _labels(bca.sides(cam)),
            "sizes": _labels(bca.sizes(cam)),
        },
        "color": {
            "moods": _labels(bcol.moods(col)),
            "film_looks": _labels(bcol.film_looks(col)),
            "techniques": _labels(bcol.techniques(col)),
        },
        "posing": {
            "poses": _labels(bpos.poses(pos)),
            "techniques": _labels(bpos.techniques(pos)),
        },
        "style": {"styles": styles},
        "capture": {group: _labels(bcap.options(cap, group))
                    for group in bcap.groups(cap)},
        "evidence": {kind: _labels(bev.options(evi, kind))
                     for kind in evi.get("kinds", {})},
    }


def _list(value):
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if str(item).strip()]


def compose_look(choices):
    """Look choices -> ({part: phrase}, warnings).

    Each part takes the same fields its Build tab does, e.g.
    {"lighting": {"setup": "rembrandt"}, "style": {"style": "anime-manga"}}.
    A plain string for a part is used as the phrase itself. Parts left out or
    empty are simply not in the result. Raises LookError naming the part.
    """
    phrases, warnings = {}, []
    choices = dict(choices or {})
    for part in LOOK_KEYS:
        pick = choices.get(part)
        if not pick:
            continue
        if isinstance(pick, str):
            phrases[part] = pick.strip()
            continue
        if part == "capture" and isinstance(pick, list):
            phrases[part] = ", ".join(_list(pick))
            continue
        if not isinstance(pick, dict):
            raise LookError("{}: expected an object or a phrase".format(part))
        try:
            phrase, notes = _compose_part(part, pick)
        except ValueError as exc:
            raise LookError("{}: {}".format(part, exc)) from exc
        if phrase:
            phrases[part] = phrase
        warnings.extend("{}: {}".format(part, note) for note in notes)
    return phrases, warnings


def _compose_part(part, pick):
    custom = str(pick.get("custom") or "").strip()
    if part == "lighting":
        return bl.compose_lighting(
            bl.load_bank(), pick.get("setup") or None, pick.get("direction") or None,
            pick.get("quality") or None, pick.get("source") or None,
            _list(pick.get("techniques")), custom or None)
    if part == "composition":
        return bcomp.compose_composition(
            bp.load_bank(), bcomp.load_bank(), pick.get("guide") or None, custom or None,
            _list(pick.get("techniques")))
    if part == "camera":
        return bca.compose_camera_angle(
            bca.load_bank(), pick.get("vertical") or None, pick.get("side") or None,
            pick.get("size") or None, custom or None)
    if part == "color":
        return bcol.compose_color(
            bcol.load_bank(), pick.get("mood") or None, pick.get("film_look") or None,
            custom or None, _list(pick.get("techniques")))
    if part == "posing":
        return bpos.compose_posing(
            bpos.load_bank(), pick.get("pose") or None, _list(pick.get("techniques")),
            custom or None)
    if part == "style":
        return bst.compose_style(bst.load_bank(), pick.get("style") or None, custom or None)
    if part == "capture":
        by_layer, notes = bcap.compose_capture(
            bcap.load_bank(), pick.get("film_stock") or None, _list(pick.get("optics")),
            _list(pick.get("exposure")), _list(pick.get("evidence")))
        return bcap.phrase_for(by_layer), notes
    if part == "evidence":
        return bev.compose_evidence(
            bev.load_bank(), pick.get("kind") or "animal", _list(pick.get("details")),
            custom)
    raise LookError("unknown part")


def clean_phrases(phrases):
    """{part: str} for the known parts, capture lists flattened, blanks dropped."""
    clean = {}
    for part in LOOK_KEYS:
        value = (phrases or {}).get(part)
        if isinstance(value, (list, tuple)):
            value = ", ".join(_list(value))
        value = str(value or "").strip()
        if value:
            clean[part] = value
    return clean


def assemble_prompt(base, phrases):
    """Scene prompt + Look. Style opens the prompt, the rest follow the scene.

    A trailing "No text..." sentence in `base` stays last, so the look never
    lands after the instruction the model should read as the final word.
    """
    phrases = clean_phrases(phrases)
    base = str(base or "").strip()
    tail = ""
    match = re.search(r"\s*(No text[^.]*\.?)\s*$", base)
    if match:
        tail = match.group(1)
        base = base[:match.start()].rstrip()
    parts = []
    if phrases.get("style"):
        parts.append(phrases["style"].rstrip(".") + ".")
    if base:
        parts.append(base if base.endswith(".") else base + ".")
    rest = [phrases[key].rstrip(".") for key in LOOK_KEYS[1:] if phrases.get(key)]
    if rest:
        parts.append("; ".join(rest) + ".")
    if tail:
        parts.append(tail)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Realism - the Images tab's switches and the 8/8 gate, for a typed prompt
# --------------------------------------------------------------------------- #
def clean_realism(raw):
    """Validated realism options, or None when none were asked for. Raises ValueError.

    `true` means every switch on. Switches left out default to on, so a caller
    names only the ones it wants off (a character sheet on a plain backdrop has
    no background to bring to life).
    """
    if raw in (None, False, {}, ""):
        return None
    if raw is True:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("realism must be an object or true")
    # `phone` keeps the fill to phone-camera words without the snapshot's
    # "who took it" line - for a character sheet in a phone-footage skit.
    opts = {"fill": bool(raw.get("fill", True)), "phone": bool(raw.get("phone", False))}
    opts.update({key: bool(raw.get(key, True)) for key in REALISM_SWITCHES})
    opts.update({key: str(raw.get(key) or "").strip()[:600] for key in REALISM_TEXT})
    if opts["kind"] and opts["kind"] not in SUBJECT_KINDS:
        raise ValueError("realism.kind must be one of: " + ", ".join(SUBJECT_KINDS))
    try:
        opts["seed"] = int(raw.get("seed") or 0)
    except (TypeError, ValueError):
        raise ValueError("realism.seed must be a whole number")
    return opts


def _detect_subject(opts):
    """The subject text the detectors read. A named species or kind leads,
    because build_evidence knows "dog" and "cat" but not "Golden Retriever" -
    a breed name alone reads as an object and would get the human texture gate."""
    head = ("a " + opts["species"]) if opts["species"] else {
        "animal": "an animal", "human": "a person"}.get(opts["kind"], "")
    return ", ".join(part for part in (head, opts["subject"]) if part)


def realism_spec(opts):
    """A Compose spec carrying only what the switches read, resolved by
    build_prompt's own apply_* steps - the same calls compose() makes."""
    spec = {"subject": _detect_subject(opts), "action": opts["action"],
            "setting": opts["setting"], "seed": opts["seed"]}
    spec.update({key: opts[key] for key in REALISM_SWITCHES})
    # The typed shot picks the coat-detail tier only. Handed to the snapshot
    # step it would read as a deliberate camera and switch the phone look off.
    spec = dict(bp.apply_subject_detail(dict(spec, shot_custom=opts["shot"])))
    spec.pop("shot_custom", None)
    spec = bp.apply_scene_light(spec)
    spec = bp.apply_physical(spec)
    return bp.apply_snapshot(bp.load_bank(), spec)


def _kind_of(spec):
    return bev.subject_kind(bev.load_bank(), spec.get("subject", ""))


def _layer_hits(text, layer, kind):
    return rl.layer_hits(rl.detect_for(kind)[layer]["keys"], text.lower())


def layer_candidates(layer, kind, phone=False, species=""):
    """Every already-vetted term that can fill `layer`, best first.

    Narrowed the way select_layers() narrows its own pick: no skin words on
    anything but a person, and on the phone look only the phone camera and
    lens, none of the cinema words snapshot_bank.json skips. An animal's
    texture comes from pet_realism_bank.json's coat phrases first."""
    bank = bp.load_bank()
    terms = list(bank["layers"][layer]["terms"])
    if kind != "human":
        terms = [t for t in terms if not bp.SKIN_WORDS.search(t)]
    if phone:
        sb = bsn.load_bank()
        skip = set(sb["snapshot"]["layer_skip"].get(layer, []))
        phone_terms = bsn.phone_layers(sb, bank).get(layer, [])
        if layer == "camera":
            terms = []
        terms = phone_terms + [t for t in terms if t not in skip and "cinematic" not in t
                               and not bp.FOCAL_TERM.search(t) and t not in PHONE_LIGHT_SKIP]
    if layer == "texture" and kind == "animal":
        fb = bfd.load_bank()
        coat = (bfd.animal_pool(fb, "close", species) if species in fb["animal"]["species_words"]
                else fb["_pet"]["groups"]["coat"]["phrases"])
        terms = list(coat) + terms
    return list(dict.fromkeys(terms))


def fill_layers(text, spec, kind, phone=False):
    """Terms that bring `text` to 8/8: AI Video Studio's own weighted pick for
    the layer first (select_layers - scene-matched light, phone camera), then
    the rest of the bank's vetted terms, one at a time, only while they still
    add a hit the layer is short of."""
    bank = bp.load_bank()
    selected, _preset = bp.select_layers(bank, spec, random.Random(spec.get("seed", 0)))
    phone = phone or bool(spec.get("_phone_snapshot"))
    species = bfd.species_of(bfd.load_bank(), spec.get("subject", "")) or ""
    added = []
    for layer in rl.LAYER_ORDER:
        need = rl.required_hits(layer)
        current = ", ".join([text] + added)
        if len(set(_layer_hits(current, layer, kind))) >= need:
            continue
        candidates = layer_candidates(layer, kind, phone, species)
        picked = list(selected.get(layer, []))
        if phone:  # select_layers only narrows for the snapshot switch itself
            picked = [t for t in picked if t in candidates]
        for term in picked + candidates:
            current = ", ".join([text] + added)
            if term.lower() in current.lower():
                continue
            if len(set(_layer_hits(current + ", " + term, layer, kind))) > \
                    len(set(_layer_hits(current, layer, kind))):
                added.append(term)
            if len(set(_layer_hits(", ".join([text] + added), layer, kind))) >= need:
                break
    return added


def score(text, kind):
    """(score out of 8, missing layer names, banned hits) - realism_lint's own gate."""
    present, missing, banned, _warn, _neg = rl.lint(text, bp.load_bank(), kind=kind)
    return len(present), [name for name, _cfg, _hit in missing], banned


def apply_realism(prompt, opts):
    """(phrases to add, report) for a finished `prompt` and clean_realism() options."""
    spec = realism_spec(opts)
    kind = _kind_of(spec)
    lines = bp.free_overrides(spec)
    text = ", ".join([prompt] + lines)
    added = fill_layers(text, spec, kind, opts["phone"]) if opts["fill"] else []
    before, _missing, _banned = score(prompt, kind)
    after, missing, banned = score(", ".join([text] + added), kind)
    return lines + added, {"kind": kind, "phone": opts["phone"] or bool(spec.get("_phone_snapshot")),
                           "before": before, "score": after,
                           "missing": missing, "banned": banned,
                           "lines": lines, "added": added}


_STYLISED = None


def is_stylised(style_phrase):
    """True when the Look's style is one of the bank's stylised styles (anime,
    oil painting, ...): photo-realism words would fight it, so none are added."""
    global _STYLISED
    if _STYLISED is None:
        bank = bst.load_bank()
        _STYLISED = set()
        for key, cfg in bst.all_styles(bank).items():
            if cfg["group"] == "stylised":
                try:
                    _STYLISED.add(bst.compose_style(bank, key)[0].strip().lower())
                except ValueError:
                    pass
    return bool(style_phrase) and style_phrase.strip().lower() in _STYLISED


def insert_before_tail(prompt, phrases):
    """`prompt` with `phrases` as one sentence before its "No text..." tail."""
    phrases = [p.strip().rstrip(".") for p in phrases if p and p.strip()]
    if not phrases:
        return prompt
    sentence = ", ".join(phrases)
    sentence = sentence[0].upper() + sentence[1:] + "."
    match = re.search(r"\s*(No text[^.]*\.?)\s*$", prompt)
    if not match:
        return prompt.rstrip() + " " + sentence
    return prompt[:match.start()].rstrip() + " " + sentence + " " + match.group(1)


# --------------------------------------------------------------------------- #
# Image jobs
# --------------------------------------------------------------------------- #
class Jobs:
    """In-memory job table. Jobs live as long as the app does."""

    def __init__(self, on_image=None):
        self.lock = threading.Lock()
        self.items = {}
        self.pool = ThreadPoolExecutor(max_workers=MAX_JOBS, thread_name_prefix="aivs-api")
        self.on_image = on_image

    def get(self, job_id):
        with self.lock:
            job = self.items.get(job_id)
            return dict(job) if job else None

    def _update(self, job_id, **fields):
        with self.lock:
            self.items[job_id].update(fields)

    def submit(self, request):
        job_id = uuid.uuid4().hex[:12]
        with self.lock:
            if len(self.items) >= KEEP_JOBS:
                finished = [k for k, v in self.items.items()
                            if v["state"] in ("done", "failed")]
                for key in finished[:len(self.items) - KEEP_JOBS + 1]:
                    del self.items[key]
            self.items[job_id] = {"id": job_id, "state": "queued", "stage": "",
                                  "error": "", "file": "", "prompt": request["prompt"],
                                  "tag": request.get("tag", ""), "created": time.time(),
                                  "attempts": [], "chosen": None, "cancel": False,
                                  "realism": request.get("realism"),
                                  "refine": request.get("refine", 0)}
        self.pool.submit(self._run, job_id, request)
        return job_id

    def cancel(self, job_id):
        with self.lock:
            if job_id not in self.items:
                return False
            self.items[job_id]["cancel"] = True
            return True

    def _cancelled(self, job_id):
        with self.lock:
            return self.items[job_id].get("cancel", False)

    def _run(self, job_id, request):
        self._update(job_id, state="running", stage="Starting...")
        refs = []
        try:
            REF_DIR.mkdir(parents=True, exist_ok=True)
            for n, ref in enumerate(request.get("references") or []):
                path = REF_DIR / "{}-ref{}.png".format(job_id, n)
                path.write_bytes(base64.b64decode(ref.get("b64", "")))
                refs.append(path)
            path, error = self._attempts(job_id, request, refs)
            if error is not None:
                self._update(job_id, state="failed", error=str(error), stage="")
            else:
                self._update(job_id, state="done", file=str(path), stage="Done")
        except Exception as exc:  # a bad reference or a disk error, never a crash
            self._update(job_id, state="failed", error=str(exc), stage="")
        finally:
            for ref in refs:
                try:
                    ref.unlink()
                except OSError:
                    pass
        if self.on_image:
            try:
                self.on_image(self.get(job_id))
            except Exception:
                pass

    def _attempts(self, job_id, request, refs):
        """Generate, and with `refine` retries critique and retry - Compose's
        Refine on a typed prompt. Returns (chosen path, error).

        Each retry strengthens exactly the layers the critique named, with the
        bank's own terms (layer_candidates), and the attempt the critique
        found least wrong is kept - a retry that came out worse never replaces
        a better first image. A failed critique ends the loop with what exists.
        """
        retries = request.get("refine", 0)
        prompt = request["prompt"]
        attempts, used = [], set()
        bank = bp.load_bank()
        for round_number in range(retries + 1):
            label = ("Attempt {} of {}: ".format(round_number + 1, retries + 1)
                     if retries else "")

            def on_stage(message, label=label):
                self._update(job_id, stage=label + message)

            path, error = gi.generate(
                request.get("provider") or "kie", prompt,
                out_name="skit-{}-{}.png".format(job_id, round_number + 1)
                if retries else "skit-{}.png".format(job_id),
                references=refs, model=request.get("model") or None,
                on_stage=on_stage, spec=request.get("spec") or {})
            if error is not None:
                if attempts:  # keep what an earlier round already paid for
                    break
                return None, error
            attempt = {"round": round_number + 1, "file": str(path), "prompt": prompt,
                       "failing_layers": [], "verdict": ""}
            attempts.append(attempt)
            record_history(dict(request, prompt=prompt), path,
                           note=REFINE_NOTE.format(round_number + 1) if retries else None)
            if not retries:
                break
            on_stage("checking how real it looks...")
            critique = brief.critique_image(bank, prompt, path)
            if not critique.get("ok"):
                attempt["verdict"] = "critique failed: {}".format(critique.get("error", ""))
                break
            attempt["failing_layers"] = critique.get("failing_layers", [])
            attempt["verdict"] = critique.get("verdict", "")
            self._update(job_id, attempts=[dict(a) for a in attempts])
            if not attempt["failing_layers"] or round_number == retries:
                break
            if self._cancelled(job_id):
                break
            stronger = []
            for layer in attempt["failing_layers"]:
                for term in layer_candidates(layer, request.get("kind") or "human",
                                             phone=request.get("phone", False),
                                             species=request.get("species", "")):
                    if term not in used and term.lower() not in prompt.lower():
                        used.add(term)
                        stronger.append(term)
                        break
            if not stronger:  # nothing left in the bank to strengthen with
                break
            prompt = insert_before_tail(prompt, stronger)
        best = min(range(len(attempts)),
                   key=lambda i: (len(attempts[i]["failing_layers"]), -i))
        self._update(job_id, attempts=[dict(a) for a in attempts], chosen=best + 1,
                     prompt=attempts[best]["prompt"])
        return Path(attempts[best]["file"]), None

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def refine_available():
    """Refine's critique is a vision call through OpenRouter."""
    return bool(gi.env_value(ask_llm.KEY_VAR))


def record_history(request, path, note=None):
    """One History row, scored by the same realism gate as any other prompt."""
    prompt = request["prompt"]
    bank = bp.load_bank()
    kind = request.get("kind") or bev.subject_kind(bev.load_bank(), request.get("base") or prompt)
    present, _missing, banned, _warn, _neg = rl.lint(prompt, bank, kind=kind)
    layers = {name: [hit] for name, _cfg, hit in present}
    spec = {"subject": (request.get("base") or prompt)[:300],
            "slug": request.get("tag") or "skit-studio", "seed": 0,
            "aspect": (request.get("spec") or {}).get("aspect", "")}
    history.append(spec, prompt, layers, len(present),
                   len(present) == 8 and not banned, image=str(path), note=note or HISTORY_NOTE)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def parse_prompt_request(body, current_look):
    """{prompt, look} -> (base, finished prompt, phrases, warnings). Raises ValueError."""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")
    base = str(body.get("prompt") or "").strip()
    if not base:
        raise ValueError("prompt is required")
    look = body.get("look")
    if look == "current":
        phrases, warnings = clean_phrases(current_look()), []
    elif isinstance(look, dict):
        phrases, warnings = compose_look(look)
    elif look in (None, "", "none"):
        phrases, warnings = {}, []
    else:
        raise ValueError("look must be 'current', an object, or null")
    phrases = clean_phrases(phrases)
    prompt = assemble_prompt(base, phrases)
    realism = clean_realism(body.get("realism"))
    report = None
    if realism and is_stylised(phrases.get("style", "")):
        warnings = warnings + ["realism: the Look's style is stylised - no photo-realism "
                               "words added"]
    elif realism:
        # Scene variety: a prompt that names no light source gets one, chosen
        # from the skit tag (so a skit's shots share it) or else the prompt text.
        # parse_image_request delegates here, so /images inherits this.
        if not sv.names_light_source(prompt):
            kind = bev.subject_kind(bev.load_bank(), realism.get("subject") or base)
            key = str(body.get("tag") or "").strip() or base
            outdoor = sv.names_outdoor(" ".join([prompt, str(realism.get("setting") or "")]))
            prompt = insert_before_tail(prompt, [sv.pick(key, kind, outdoor)["light"]])
        extra, report = apply_realism(prompt, realism)
        prompt = insert_before_tail(prompt, extra)
    return base, prompt, phrases, warnings, report


def parse_image_request(body, current_look):
    """Validated /images body -> request dict for Jobs.submit. Raises ValueError."""
    base, prompt, phrases, warnings, report = parse_prompt_request(body, current_look)
    provider = body.get("provider") or "kie"
    if provider not in gi.PROVIDERS:
        raise ValueError("unknown provider: {}".format(provider))
    refs = body.get("references") or []
    if not isinstance(refs, list) or any(not isinstance(r, dict) or not r.get("b64")
                                         for r in refs):
        raise ValueError("references must be a list of {name, b64}")
    spec = {key: str(body[key]) for key in ("aspect", "resolution", "output_format")
            if body.get(key)}
    try:
        refine = int(body.get("refine") or 0)
    except (TypeError, ValueError):
        raise ValueError("refine must be 0, 1 or 2 (retries)")
    if not 0 <= refine <= MAX_REFINE:
        raise ValueError("refine must be 0, 1 or 2 (retries)")
    kind = (report or {}).get("kind") or bev.subject_kind(bev.load_bank(), base)
    return {"base": base, "prompt": prompt, "look": phrases,
            "warnings": warnings, "provider": provider, "model": body.get("model"),
            "references": refs, "spec": spec, "tag": str(body.get("tag") or "")[:80],
            "realism": report, "refine": refine, "kind": kind,
            "phone": bool((report or {}).get("phone")),
            "species": str((body.get("realism") or {}).get("species") or "")
            if isinstance(body.get("realism"), dict) else ""}


def make_handler(jobs, current_look, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, payload):
            raw = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _authorised(self):
            if not token:
                return True
            if hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                return True
            self._send(401, {"error": "missing or wrong token"})
            return False

        def _body(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("request body over {} MB".format(MAX_BODY // (1024 * 1024)))
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/api/v1/health":
                env = gi.read_env()
                providers = {name: not gi.missing_credentials(
                    cfg, *gi.credentials(cfg, env)) for name, cfg in gi.PROVIDERS.items()}
                return self._send(200, {"app": APP, "version": VERSION,
                                        "providers": providers,
                                        "look_current": bool(clean_phrases(current_look())),
                                        "realism": list(REALISM_SWITCHES),
                                        "refine": refine_available(),
                                        "max_refine": MAX_REFINE})
            if path == "/api/v1/look/options":
                return self._send(200, look_options())
            if path == "/api/v1/look/current":
                phrases = clean_phrases(current_look())
                return self._send(200, {key: phrases.get(key, "") for key in LOOK_KEYS})
            match = re.fullmatch(r"/api/v1/images/([0-9a-f]+)(/file)?", path)
            if match:
                job = jobs.get(match.group(1))
                if not job:
                    return self._send(404, {"error": "no such image job"})
                if not match.group(2):
                    return self._send(200, {k: job.get(k) for k in
                                            ("id", "state", "stage", "error", "file", "prompt",
                                             "attempts", "chosen", "realism", "refine")})
                if job["state"] != "done":
                    return self._send(409, {"error": "image not ready"})
                data = Path(job["file"]).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type",
                                 mimetypes.guess_type(job["file"])[0] or "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._authorised():
                return
            path = self.path.split("?", 1)[0].rstrip("/")
            try:
                body = self._body()
            except (ValueError, UnicodeDecodeError) as exc:
                return self._send(400, {"error": "body is not valid JSON"
                                        if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError))
                                        else str(exc)})
            try:
                if path == "/api/v1/look/compose":
                    phrases, warnings = compose_look(body)
                    return self._send(200, {"phrases": phrases, "warnings": warnings})
                if path == "/api/v1/prompt":
                    _base, prompt, phrases, warnings, report = parse_prompt_request(
                        body, current_look)
                    return self._send(200, {"prompt": prompt, "look": phrases,
                                            "warnings": warnings, "realism": report})
                if path == "/api/v1/images":
                    request = parse_image_request(body, current_look)
                    if request["refine"] and not refine_available():
                        request["warnings"].append(
                            "refine: no OPENROUTER_API_KEY in AI Video Studio's .env - "
                            "one image, no critique")
                        request["refine"] = 0
                    job_id = jobs.submit(request)
                    return self._send(202, {"id": job_id, "prompt": request["prompt"],
                                            "warnings": request["warnings"],
                                            "realism": request["realism"],
                                            "refine": request["refine"]})
                match = re.fullmatch(r"/api/v1/images/([0-9a-f]+)/cancel", path)
                if match:
                    if not jobs.cancel(match.group(1)):
                        return self._send(404, {"error": "no such image job"})
                    return self._send(200, {"ok": True})
            except ValueError as exc:
                return self._send(400, {"error": str(exc)})
            self._send(404, {"error": "not found"})

    return Handler


class LocalApi:
    """The running server. start() returns it; stop() closes it."""

    def __init__(self, server, jobs, thread):
        self.server, self.jobs, self.thread = server, jobs, thread

    @property
    def port(self):
        return self.server.server_address[1]

    def stop(self):
        # A job still running finishes on its own thread; it must not call back into a
        # window that is closing.
        self.jobs.on_image = None
        self.server.shutdown()
        self.server.server_close()
        self.jobs.shutdown()


def configured_port():
    value = gi.env_value(PORT_VAR) or ""
    try:
        return int(value) if value.strip() else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


def start(port=None, current_look=None, on_image=None, token=None):
    """Start serving on 127.0.0.1. Raises OSError if the port is taken."""
    port = configured_port() if port is None else port
    token = gi.env_value(TOKEN_VAR) if token is None else token
    jobs = Jobs(on_image)
    handler = make_handler(jobs, current_look or (lambda: {}), token or "")
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                              name="aivs-local-api")
    thread.start()
    return LocalApi(server, jobs, thread)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--serve", action="store_true",
                        help="run headless until Ctrl+C (no current look - no window)")
    parser.add_argument("--port", type=int, default=None,
                        help="port (default {} or {})".format(PORT_VAR, DEFAULT_PORT))
    parser.add_argument("--options", action="store_true", help="print the Look lists")
    args = parser.parse_args(argv)
    if args.options:
        print(json.dumps(look_options(), indent=2, ensure_ascii=False))
        return 0
    if args.serve:
        api = start(args.port)
        print("AI Video Studio local API on http://127.0.0.1:{}".format(api.port), flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            api.stop()
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
