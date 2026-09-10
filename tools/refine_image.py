"""Generate an avatar image, then automatically fix what still looks fake.

This closes the manual loop the app has always required: generate -> look at
it -> notice it's off -> figure out which realism layer is weak -> re-prompt
by hand. `brief.critique_image()` already does the "what's wrong" step - a
vision-model call whitelisted against the 8 named `realism_lint` layers, the
same discipline every other AI-assisted feature in this project uses
(brief.py's SPEC_KEYS/CUSTOM_PROMPT_KEYS). This adds the missing piece: act on
the critique, strengthen exactly the layer it names using ONLY that layer's
own already-vetted terms from prompt_bank.json (never inventing new
vocabulary), and try again - capped, so an unlucky prompt cannot loop forever
or spend without limit.

Usage:
    python tools/refine_image.py --spec temp/resources/characters/x.json
    python tools/refine_image.py --subject "a tired mechanic" --max-retries 1
    python tools/refine_image.py --spec x.json --dry-run

Every attempt is logged through history.py exactly like any other generation,
tagged so a refine-loop attempt is traceable later. The critique step needs
OPENROUTER_API_KEY (see ask_llm.py); the image step needs whatever the chosen
provider needs (see generate_image.py). Standard library only beyond those two.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ask_llm  # noqa: E402
import brief  # noqa: E402
import build_prompt as bp  # noqa: E402
import generate_image as gi  # noqa: E402
import history  # noqa: E402
import realism_lint as rl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MAX_RETRIES = 2


def strengthen(bank, selected, layer):
    """A stronger, still-bank-only term set for one layer the critique flagged.

    `pick: 1` layers (camera, lighting) name a single, mutually-exclusive
    source - prompt_bank.json's own note warns that mixing daylight with
    golden hour contradicts itself, and stacking two cameras is nonsense the
    same way. So strengthening one of those means swapping to a different
    already-vetted term, never stacking more. `pick > 1` layers (core, lens,
    texture, colour, composition, grain) can safely carry one extra already-
    vetted term on top of what was already picked - more texture/grain/colour
    language never contradicts itself the way two light sources do.

    Returns None if the layer is unknown or has no vocabulary to draw from.
    """
    cfg = bank.get("layers", {}).get(layer, {})
    terms = cfg.get("terms", [])
    if not terms:
        return None
    tried = [t for t in (selected.get(layer) or []) if t in terms]
    untried = [t for t in terms if t not in tried]
    pick_count = cfg.get("pick", 2)
    if pick_count <= 1:
        pool = untried or terms
        return [pool[0]]
    extra = untried[:1]
    chosen = tried + extra
    if len(chosen) <= len(tried):
        chosen = terms[: min(len(terms), pick_count + 1)]
    return chosen[: min(len(terms), pick_count + 1)]


def _one_attempt(bank, spec, provider, model, base, dry_run, should_cancel,
                  on_stage, out_name):
    """Compose + generate one image. Returns (prompt, selected, score, passed,
    path, error) - exactly one of (path, error) is None, same as generate()."""
    prompt, selected = bp.compose(bank, spec)
    present, _, banned, _, _ = rl.lint(prompt.lower(), bank)
    score = len(present)
    passed = score == 8 and not banned
    # The spec stores the identity-lock image under the singular "reference"
    # key (spec_editor.set_reference, build_ad, build_story, variants all use
    # it); "references" was never a spec key, so this used to always send an
    # empty list and every refined regeneration invented a new face while the
    # prompt still claimed "the exact same person as in the reference image".
    references = [spec["reference"]] if spec.get("reference") else []
    path, error = gi.generate(
        provider=provider, prompt=prompt, out_name=out_name,
        references=references, model=model, base=base,
        dry_run=dry_run, should_cancel=should_cancel, on_stage=on_stage, spec=spec,
    )
    return prompt, selected, score, passed, path, error


def refine(bank, spec, provider="kie", model=None, base=None,
           max_retries=DEFAULT_MAX_RETRIES, dry_run=False, should_cancel=None,
           on_stage=None, ask=None, out_name=None,
           start_image=None, start_prompt=None, start_selected=None):
    """Generate (or start from an already-shown image), critique, strengthen
    the layer the critique names, and try again - up to `max_retries` times.

    Returns a report dict, never raises for an ordinary generation/critique
    failure (mirrors generate_image.generate()'s own (result, error)
    discipline, just with more to report than a single path):
        {"ok": True,
         "attempts": [{"round", "id", "prompt", "image", "score", "critique"}, ...],
         "result": <the last attempt's own dict>,
         "rounds": len(attempts)}
    or {"ok": False, "error": "...", "attempts": [...]} if a generation itself
    failed (a bad key, a network error, etc. - not "the critique found a
    problem", which is the loop's normal case, not a failure).

    `start_image`/`start_prompt`/`start_selected` let the caller critique an
    image that already exists (e.g. Compose's currently-shown one) without
    paying for a first generation of something never critiqued - round 0 then
    critiques that image directly and only regenerates from round 1 on, if
    the critique finds something.
    """
    ask = ask or ask_llm.ask
    spec = dict(spec)
    spec.setdefault("seed", 0)

    def stage(message, round_number):
        if on_stage:
            on_stage("Attempt {} of {}: {}".format(
                round_number + 1, max_retries + 1, message))

    attempts = []
    for round_number in range(max_retries + 1):
        if round_number == 0 and start_image:
            prompt = start_prompt or ""
            selected = start_selected or {}
            present, _, banned, _, _ = (
                rl.lint(prompt.lower(), bank) if prompt else ([], [], [], [], False)
            )
            score, passed, path, error = len(present), (len(present) == 8 and not banned), start_image, None
        else:
            prompt, selected, score, passed, path, error = _one_attempt(
                bank, spec, provider, model, base, dry_run, should_cancel,
                lambda m, n=round_number: stage(m, n),
                out_name if round_number == 0 else None,
            )
        if error:
            return {"ok": False, "error": str(error), "attempts": attempts}

        image_str = str(path) if path else ""
        entry_id = history.append(
            spec, prompt, selected, score, passed, image=image_str,
            note="refine-loop: attempt {} of {}".format(round_number + 1, max_retries + 1),
        )
        record = {"round": round_number, "id": entry_id, "prompt": prompt,
                  "image": image_str, "score": score}

        if dry_run:
            attempts.append(dict(record, critique=None))
            break

        stage("checking the result", round_number)
        critique = brief.critique_image(bank, prompt, path, ask=ask)
        if not critique.get("ok"):
            # No OPENROUTER key, or the call itself failed - stop here; this
            # is exactly what a plain, un-refined generation would have been.
            attempts.append(dict(record, critique=None, critique_error=critique.get("error")))
            break

        failing = critique.get("failing_layers", [])
        attempts.append(dict(record, critique=critique))

        if not failing or round_number == max_retries:
            break

        overrides = dict(spec.get("overrides", {}))
        for layer in failing:
            stronger = strengthen(bank, selected, layer)
            if stronger:
                overrides[layer] = stronger
        spec = dict(spec, overrides=overrides)

    return {"ok": True, "attempts": attempts, "result": attempts[-1], "rounds": len(attempts)}


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Generate an avatar, then automatically fix what looks fake.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--spec", help="path to a character spec JSON")
    p.add_argument("--subject", help="subject, when no --spec is given")
    p.add_argument("--provider", choices=sorted(gi.PROVIDERS), default="kie")
    p.add_argument("--model", help="override the model id for this call")
    p.add_argument("--base-url", help="override the API host (for testing)")
    p.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    p.add_argument("--dry-run", action="store_true",
                    help="build and log prompts without calling any API or needing a key")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    bank = bp.load_bank()
    if args.spec:
        path = Path(args.spec)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            sys.exit("Spec not found: {}".format(path))
        spec = json.loads(path.read_text(encoding="utf-8"))
    else:
        if not args.subject:
            sys.exit("Give --spec <path>, or at least --subject.")
        spec = {"subject": args.subject}

    result = refine(
        bank, spec, provider=args.provider, model=args.model, base=args.base_url,
        max_retries=args.max_retries, dry_run=args.dry_run,
        on_stage=lambda m: print(m, file=sys.stderr),
    )
    if not result["ok"]:
        print(result["error"], file=sys.stderr)
        return 3

    for a in result["attempts"]:
        print("\n=== attempt {} - {}/8 ===".format(a["round"] + 1, a["score"]))
        print("[image] {}".format(a["image"]))
        critique = a.get("critique")
        if critique is None:
            if a.get("critique_error"):
                print("[note]  no critique: {}".format(a["critique_error"]), file=sys.stderr)
            continue
        print("[verdict] {}".format(critique.get("verdict", "")))
        for layer in critique.get("failing_layers", []):
            print("  weak layer: {}".format(layer))

    final = result["result"]
    print("\n[final] {} ({}/8)".format(final["image"], final["score"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
