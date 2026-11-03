import { useEffect, useState } from "react";
import { Check, Sparkles, Trash2 } from "lucide-react";
import {
  composeLookPart,
  getLookOptions,
  setLookOverride,
  type LookOptionItem,
  type LookOptionsPayload,
  type LookPart,
  type LookSnapshot,
  type SubjectKind,
} from "../../lib/api";
import { Term } from "../../components/Term";

interface SubBuilderMeta {
  id: LookPart;
  label: string;
  plain: string;
  example: string;
}

export const LOOK_SUB_BUILDERS: SubBuilderMeta[] = [
  {
    id: "lighting",
    label: "Lighting",
    plain: "Where the light comes from, how soft or harsh it is, and what lamp or window makes it.",
    example: "Like choosing between a single rainy window on your left or a warm bedside lamp at night.",
  },
  {
    id: "composition",
    label: "Composition",
    plain: "Where the subject sits inside the rectangle and how the background leads the eye.",
    example: "Like placing your dog slightly off to one side so you can also see the hallway behind.",
  },
  {
    id: "camera",
    label: "Camera",
    plain: "How high the camera is held, which side of the subject it faces, and how close you stand.",
    example: "Like crouching down to eye level with a cat instead of pointing the phone down from standing height.",
  },
  {
    id: "color",
    label: "Color",
    plain: "The overall warmth, contrast, and film-like colour cast of the photo.",
    example: "Like the muted, slightly warm look of an everyday phone photo indoors without a filter.",
  },
  {
    id: "posing",
    label: "Posing",
    plain: "What the body, paws, or hands are doing at the moment the shutter clicks.",
    example: "Like catching someone mid-laugh or a dog mid-turn instead of sitting stiffly for a portrait.",
  },
  {
    id: "style",
    label: "Style",
    plain: "The overall visual medium or photographic approach.",
    example: "Leave blank for a candid real-life photo, or pick documentary / editorial photography when needed.",
  },
  {
    id: "capture",
    label: "Capture",
    plain: "The physical sensor, lens glass, exposure quirks, and tiny camera imperfections.",
    example: "Like mild indoor phone grain or a slightly soft background edge from a real lens.",
  },
  {
    id: "evidence",
    label: "Evidence",
    plain: "Small lived-in details on the fur, skin, clothes, and room that prove the moment is real.",
    example: "Like a creased sleeve, stray hairs on a cushion, or a water mug left on the table.",
  },
];

export interface LookTabProps {
  look: LookSnapshot;
  kind: SubjectKind;
  initialPart?: LookPart;
  onLookUpdated: (next: LookSnapshot) => void;
  onGoToCompose: () => void;
}

type BuilderSelections = Record<LookPart, Record<string, unknown>>;

function createInitialSelections(kind: SubjectKind): BuilderSelections {
  return {
    lighting: { setup: "", direction: "", quality: "", source: "", techniques: [], custom: "" },
    composition: { guide: "", techniques: [], custom: "" },
    camera: { vertical: "", side: "", size: "", custom: "" },
    color: { mood: "", film_look: "", techniques: [], custom: "" },
    posing: { pose: "", techniques: [], custom: "" },
    style: { style: "", custom: "" },
    capture: { film_stock: "", optics: [], exposure: [], evidence: [] },
    evidence: { kind, details: [], custom: "" },
  };
}

function toggleInArray(list: unknown, key: string): string[] {
  const arr = Array.isArray(list) ? (list as string[]) : [];
  return arr.includes(key) ? arr.filter((k) => k !== key) : [...arr, key];
}

export function LookTab({
  look,
  kind,
  initialPart = "lighting",
  onLookUpdated,
  onGoToCompose,
}: LookTabProps) {
  const [activePart, setActivePart] = useState<LookPart>(initialPart);
  const [options, setOptions] = useState<LookOptionsPayload | null>(null);
  const [selections, setSelections] = useState<BuilderSelections>(() =>
    createInitialSelections(kind)
  );
  const [previewPhrase, setPreviewPhrase] = useState<string>("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [statusMsg, setStatusMsg] = useState<string>("");

  useEffect(() => {
    setActivePart(initialPart);
  }, [initialPart]);

  useEffect(() => {
    void getLookOptions()
      .then(setOptions)
      .catch(() => {});
  }, []);

  const currentPick = selections[activePart];
  const overrides = look.overrides ?? {};

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await composeLookPart(activePart, currentPick, false);
        if (!cancelled) {
          setPreviewPhrase(res.phrases[activePart] ?? "");
          setWarnings(res.warnings ?? []);
        }
      } catch {
        if (!cancelled) {
          setPreviewPhrase("");
          setWarnings([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activePart, currentPick]);

  const updateField = (field: string, value: unknown) => {
    setStatusMsg("");
    setSelections((prev) => ({
      ...prev,
      [activePart]: {
        ...prev[activePart],
        [field]: value,
      },
    }));
  };

  const handleApply = async () => {
    try {
      const res = await composeLookPart(activePart, currentPick, true);
      onLookUpdated(res.look);
      setPreviewPhrase(res.phrases[activePart] ?? "");
      setWarnings(res.warnings ?? []);
      setStatusMsg(`Applied ${activeMeta.label} to Compose.`);
    } catch (err) {
      setStatusMsg(err instanceof Error ? err.message : "Could not apply phrase.");
    }
  };

  const handleClearPart = async (part: LookPart) => {
    try {
      const updated = await setLookOverride(part, "");
      onLookUpdated(updated);
      if (part === activePart) {
        setSelections((prev) => ({
          ...prev,
          [part]: createInitialSelections(kind)[part],
        }));
        setStatusMsg(`Cleared ${part} override.`);
      }
    } catch {
      // ignore
    }
  };

  const activeMeta =
    LOOK_SUB_BUILDERS.find((b) => b.id === activePart) ?? LOOK_SUB_BUILDERS[0];
  const appliedOverride = overrides[activePart] ?? "";

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden bg-ground text-text">
      {/* Left / Main Builder Area */}
      <section
        aria-label="Look builders"
        className="flex min-w-0 flex-1 flex-col overflow-hidden border-r border-hairline bg-surface"
      >
        {/* Sub-builder tab bar */}
        <div
          role="tablist"
          aria-label="Look toolkits"
          className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b border-hairline bg-ground/50 px-5 py-2.5"
        >
          {LOOK_SUB_BUILDERS.map((tab) => {
            const isActive = tab.id === activePart;
            const hasOverride = Boolean(overrides[tab.id]);
            return (
              <button
                key={tab.id}
                role="tab"
                type="button"
                aria-selected={isActive}
                data-testid={`look-subtab-${tab.id}`}
                onClick={() => {
                  setActivePart(tab.id);
                  setStatusMsg("");
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? "border-accent bg-raised text-text"
                    : "border-transparent bg-transparent text-muted hover:bg-raised/50 hover:text-text"
                }`}
              >
                <span>{tab.label}</span>
                {hasOverride && (
                  <span
                    className="h-1.5 w-1.5 rounded-full bg-accent"
                    title="Applied to Compose"
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Active sub-builder controls */}
        <div className="flex-1 space-y-5 overflow-y-auto p-6">
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-text">
              <Term
                word={activeMeta.label}
                plain={activeMeta.plain}
                example={activeMeta.example}
              />
            </h2>
            <p className="text-xs text-muted">{activeMeta.plain}</p>
            <p className="text-[11px] italic text-muted">
              Example: {activeMeta.example}
            </p>
          </div>

          {!options ? (
            <p className="text-xs text-muted">Loading Look options…</p>
          ) : (
            <div className="space-y-4">
              {activePart === "lighting" && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <SelectField
                      label="Setup"
                      value={String(currentPick.setup ?? "")}
                      options={options.lighting.setups}
                      onChange={(v) => updateField("setup", v)}
                    />
                    <SelectField
                      label="Direction"
                      value={String(currentPick.direction ?? "")}
                      options={options.lighting.directions}
                      onChange={(v) => updateField("direction", v)}
                    />
                    <SelectField
                      label="Quality"
                      value={String(currentPick.quality ?? "")}
                      options={options.lighting.qualities}
                      onChange={(v) => updateField("quality", v)}
                    />
                    <SelectField
                      label="Source"
                      value={String(currentPick.source ?? "")}
                      options={options.lighting.sources}
                      onChange={(v) => updateField("source", v)}
                    />
                  </div>
                  <MultiPillField
                    label="Lighting techniques"
                    selected={(currentPick.techniques as string[]) ?? []}
                    options={options.lighting.techniques}
                    onToggle={(k) =>
                      updateField("techniques", toggleInArray(currentPick.techniques, k))
                    }
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. faint warm hallway light spilling under the door…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "composition" && (
                <>
                  <SelectField
                    label="Framing guide"
                    value={String(currentPick.guide ?? "")}
                    options={options.composition.guides}
                    onChange={(v) => updateField("guide", v)}
                  />
                  <MultiPillField
                    label="Composition techniques"
                    selected={(currentPick.techniques as string[]) ?? []}
                    options={options.composition.techniques}
                    onToggle={(k) =>
                      updateField("techniques", toggleInArray(currentPick.techniques, k))
                    }
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. seen partly through the kitchen doorway…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "camera" && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <SelectField
                      label="Height (Vertical)"
                      value={String(currentPick.vertical ?? "")}
                      options={options.camera.verticals}
                      onChange={(v) => updateField("vertical", v)}
                    />
                    <SelectField
                      label="Side (Horizontal)"
                      value={String(currentPick.side ?? "")}
                      options={options.camera.sides}
                      onChange={(v) => updateField("side", v)}
                    />
                    <SelectField
                      label="Distance (Shot size)"
                      value={String(currentPick.size ?? "")}
                      options={options.camera.sizes}
                      onChange={(v) => updateField("size", v)}
                    />
                  </div>
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. handheld phone held slightly crooked at sofa height…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "color" && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <SelectField
                      label="Colour mood"
                      value={String(currentPick.mood ?? "")}
                      options={options.color.moods}
                      onChange={(v) => updateField("mood", v)}
                    />
                    <SelectField
                      label="Film look"
                      value={String(currentPick.film_look ?? "")}
                      options={options.color.film_looks}
                      onChange={(v) => updateField("film_look", v)}
                    />
                  </div>
                  <MultiPillField
                    label="Colour techniques"
                    selected={(currentPick.techniques as string[]) ?? []}
                    options={options.color.techniques}
                    onToggle={(k) =>
                      updateField("techniques", toggleInArray(currentPick.techniques, k))
                    }
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. neutral indoor white balance with warm tungsten lamps…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "posing" && (
                <>
                  <SelectField
                    label="Base pose"
                    value={String(currentPick.pose ?? "")}
                    options={options.posing.poses}
                    onChange={(v) => updateField("pose", v)}
                  />
                  <MultiPillField
                    label="Pose & candid cues"
                    selected={(currentPick.techniques as string[]) ?? []}
                    options={options.posing.techniques}
                    onToggle={(k) =>
                      updateField("techniques", toggleInArray(currentPick.techniques, k))
                    }
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. looking away toward the kitchen while one ear turns…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "style" && (
                <>
                  <SelectField
                    label="Style preset"
                    value={String(currentPick.style ?? "")}
                    options={options.style.styles}
                    onChange={(v) => updateField("style", v)}
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. candid everyday phone snapshot…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}

              {activePart === "capture" && (
                <>
                  <SelectField
                    label="Sensor / Film stock"
                    value={String(currentPick.film_stock ?? "")}
                    options={options.capture.film_stock ?? []}
                    onChange={(v) => updateField("film_stock", v)}
                  />
                  <MultiPillField
                    label="Optics & lens behaviour"
                    selected={(currentPick.optics as string[]) ?? []}
                    options={options.capture.optics ?? []}
                    onToggle={(k) =>
                      updateField("optics", toggleInArray(currentPick.optics, k))
                    }
                  />
                  <MultiPillField
                    label="Exposure & dynamic range"
                    selected={(currentPick.exposure as string[]) ?? []}
                    options={options.capture.exposure ?? []}
                    onToggle={(k) =>
                      updateField("exposure", toggleInArray(currentPick.exposure, k))
                    }
                  />
                  <MultiPillField
                    label="Capture artefacts & grain"
                    selected={(currentPick.evidence as string[]) ?? []}
                    options={options.capture.evidence ?? []}
                    onToggle={(k) =>
                      updateField("evidence", toggleInArray(currentPick.evidence, k))
                    }
                  />
                </>
              )}

              {activePart === "evidence" && (
                <>
                  <div className="space-y-1">
                    <label
                      htmlFor="evidence-kind-select"
                      className="block text-xs font-medium text-text"
                    >
                      Subject kind
                    </label>
                    <select
                      id="evidence-kind-select"
                      value={String(currentPick.kind ?? kind)}
                      onChange={(e) => {
                        updateField("kind", e.target.value);
                        updateField("details", []);
                      }}
                      className="w-full rounded-xl border border-hairline bg-ground px-3 py-2 text-xs text-text"
                    >
                      <option value="animal">Pet / animal</option>
                      <option value="human">Person / people</option>
                      <option value="object">Object / product</option>
                      <option value="place">Room / place</option>
                    </select>
                  </div>
                  <MultiPillField
                    label="Lived-in details"
                    selected={(currentPick.details as string[]) ?? []}
                    options={
                      options.evidence[String(currentPick.kind ?? kind)] ?? []
                    }
                    onToggle={(k) =>
                      updateField("details", toggleInArray(currentPick.details, k))
                    }
                  />
                  <CustomTextField
                    value={String(currentPick.custom ?? "")}
                    placeholder="e.g. a few white cat hairs on the dark cushion fabric…"
                    onChange={(v) => updateField("custom", v)}
                  />
                </>
              )}
            </div>
          )}

          {/* Live composed phrase preview + Apply to Compose */}
          <div className="rounded-2xl border border-hairline bg-ground p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-text">
                Built {activeMeta.label} phrase
              </span>
              {appliedOverride && (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] font-medium text-accent">
                  <Check className="h-3 w-3" />
                  Applied to Compose
                </span>
              )}
            </div>

            <p
              data-testid="look-composed-preview"
              className="min-h-[2.25rem] rounded-xl border border-hairline bg-surface px-3 py-2 text-xs leading-relaxed text-text"
            >
              {previewPhrase || (
                <span className="text-muted">
                  Pick options above to build a {activeMeta.label.toLowerCase()} phrase…
                </span>
              )}
            </p>

            {warnings.length > 0 && (
              <ul className="space-y-1 text-[11px] text-accent">
                {warnings.map((w, i) => (
                  <li key={i}>Note: {w}</li>
                ))}
              </ul>
            )}

            <div className="flex items-center justify-between gap-2 pt-1">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={!previewPhrase.trim()}
                  onClick={() => void handleApply()}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-on-accent transition-opacity hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Apply to Compose
                </button>
                {appliedOverride && (
                  <button
                    type="button"
                    onClick={() => void handleClearPart(activePart)}
                    className="inline-flex items-center gap-1 rounded-xl border border-hairline bg-surface px-3 py-2 text-xs font-medium text-muted hover:border-muted hover:text-text"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Clear {activeMeta.label}
                  </button>
                )}
              </div>
              {statusMsg && (
                <span className="text-xs font-medium text-ok">{statusMsg}</span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Right Summary Sidebar: Active Look in Compose */}
      <aside
        aria-label="Active Look summary"
        className="flex w-[360px] shrink-0 flex-col justify-between bg-ground p-5"
      >
        <div className="space-y-4 overflow-y-auto">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
              Active in Compose
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-muted">
              Every phrase you apply here is merged into your next photo in the{" "}
              <strong className="font-semibold text-text">Compose</strong> tab (and shared with Skit Studio).
            </p>
          </div>

          <div className="space-y-2">
            {LOOK_SUB_BUILDERS.map((part) => {
              const phrase = overrides[part.id];
              return (
                <div
                  key={part.id}
                  className={`rounded-xl border p-3 transition-colors ${
                    phrase
                      ? "border-accent/50 bg-surface"
                      : "border-hairline bg-surface/40"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setActivePart(part.id)}
                      className="text-xs font-semibold text-text hover:underline"
                    >
                      {part.label}
                    </button>
                    {phrase ? (
                      <button
                        type="button"
                        onClick={() => void handleClearPart(part.id)}
                        aria-label={`Clear ${part.label} override`}
                        className="text-[11px] text-muted hover:text-danger"
                      >
                        Clear
                      </button>
                    ) : (
                      <span className="text-[11px] text-muted">Default</span>
                    )}
                  </div>
                  {phrase && (
                    <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted">
                      {phrase}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="pt-4">
          <button
            type="button"
            onClick={onGoToCompose}
            className="w-full rounded-xl border border-accent bg-raised px-4 py-2.5 text-xs font-semibold text-text hover:bg-surface"
          >
            Back to Compose tab →
          </button>
        </div>
      </aside>
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: LookOptionItem[];
  onChange: (val: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-text">{label}</label>
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-hairline bg-ground px-3 py-2 text-xs text-text"
      >
        <option value="">— None / default —</option>
        {options.map((opt) => (
          <option key={opt.key} value={opt.key}>
            {opt.group ? `[${opt.group}] ${opt.label}` : opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function MultiPillField({
  label,
  selected,
  options,
  onToggle,
}: {
  label: string;
  selected: string[];
  options: LookOptionItem[];
  onToggle: (key: string) => void;
}) {
  const set = new Set(selected);
  return (
    <div className="space-y-1.5">
      <span className="block text-xs font-medium text-text">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const active = set.has(opt.key);
          return (
            <button
              key={opt.key}
              type="button"
              onClick={() => onToggle(opt.key)}
              title={opt.phrase}
              className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                active
                  ? "border-accent bg-raised text-text"
                  : "border-hairline bg-ground text-muted hover:border-muted hover:text-text"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function CustomTextField({
  value,
  placeholder,
  onChange,
}: {
  value: string;
  placeholder: string;
  onChange: (val: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-text">
        Custom phrase (optional)
      </label>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-hairline bg-ground px-3 py-2 text-xs text-text placeholder:text-muted"
      />
    </div>
  );
}

