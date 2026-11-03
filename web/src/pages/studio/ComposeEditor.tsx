import { useState } from "react";
import { Check, Copy, Shuffle } from "lucide-react";
import type {
  ComposeFormState,
  ComposeOptionsPayload,
  ComposePreviewPayload,
  LookCard,
  LookPart,
  SubjectKind,
} from "../../lib/api";
import { Term } from "../../components/Term";
import { LookCards } from "./LookCards";
import { Reference, type ReferenceFile } from "./Reference";

export type ComposeSubTab = "purpose" | "subject" | "scene" | "identity" | "more";

const KIND_LABELS: Record<SubjectKind, string> = {
  animal: "Pet photo",
  human: "People photo",
  object: "Object photo",
  place: "Place photo",
};

export interface ComposeEditorProps {
  form: ComposeFormState;
  options: ComposeOptionsPayload | null;
  preview: ComposePreviewPayload | null;
  kind: SubjectKind;
  provider: "kie" | "higgsfield";
  reference: ReferenceFile | null;
  cards: LookCard[];
  selectedCards: Record<string, string>;
  touchedCards: string[];
  overrides?: Record<string, string>;
  onUpdateField: <K extends keyof ComposeFormState>(
    key: K,
    value: ComposeFormState[K]
  ) => void;
  onReferenceChange: (ref: ReferenceFile | null) => void;
  onSelectCardOption: (cardId: string, optionKey: string) => void;
  onOpenLookTab: (part: LookPart) => void;
}

export function ComposeEditor({
  form,
  options,
  preview,
  kind,
  provider,
  reference,
  cards,
  selectedCards,
  touchedCards,
  overrides = {},
  onUpdateField,
  onReferenceChange,
  onSelectCardOption,
  onOpenLookTab,
}: ComposeEditorProps) {
  const [subTab, setSubTab] = useState<ComposeSubTab>("subject");
  const [copied, setCopied] = useState(false);

  const toggleSkinFeature = (key: string) => {
    const current = form.skin_features ?? [];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    onUpdateField("skin_features", next);
  };

  const handleCopyPrompt = () => {
    if (!preview?.prompt) return;
    void navigator.clipboard?.writeText(preview.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const reshuffleSeed = () => {
    onUpdateField("seed", (form.seed + 1) % 10000);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Five SpecEditor sub-tabs: Purpose, Subject, Scene, Identity, More */}
      <div
        role="tablist"
        aria-label="Compose spec sections"
        className="flex shrink-0 items-center gap-1 border-b border-hairline pb-2"
      >
        {(
          [
            ["purpose", "Purpose"],
            ["subject", "Subject"],
            ["scene", "Scene"],
            ["identity", "Identity"],
            ["more", "More"],
          ] as [ComposeSubTab, string][]
        ).map(([id, label]) => {
          const active = subTab === id;
          return (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={active}
              data-testid={`compose-subtab-${id}`}
              onClick={() => setSubTab(id)}
              className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-colors ${
                active
                  ? "border border-accent/60 bg-raised text-text"
                  : "border border-transparent text-muted hover:bg-raised/40 hover:text-text"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Scrollable active sub-tab body */}
      <div className="mt-3 flex-1 space-y-3 overflow-y-auto pr-1">
        {subTab === "purpose" && (
          <div className="space-y-3">
            <EditableComboField
              id="compose-purpose"
              label="Purpose"
              tooltipPlain="What the image is for. A listed placement sets the default shot and aspect unless you set them yourself."
              tooltipExample="Like picking 'Instagram post' so it automatically frames a 4:5 portrait."
              value={form.purpose}
              placeholder="(auto) or type placement e.g. LinkedIn banner"
              options={
                options?.purposes.map((p) => ({
                  value: p.key,
                  label: `${p.label} (${p.aspect || "auto"})`,
                })) ?? []
              }
              onChange={(v) => onUpdateField("purpose", v)}
            />

            <div className="space-y-1">
              <label
                htmlFor="compose-aspect"
                className="block text-xs font-semibold text-text"
              >
                <Term
                  word="Aspect"
                  plain="The width-to-height shape of the rectangle."
                  example="1:1 is a square, 4:5 is a vertical social post, 16:9 is widescreen."
                />
              </label>
              <select
                id="compose-aspect"
                value={form.aspect}
                onChange={(e) => onUpdateField("aspect", e.target.value)}
                className="w-full rounded-xl border border-hairline bg-ground px-3 py-2 text-xs text-text"
              >
                <option value="">(auto from purpose)</option>
                {(options?.aspects ?? ["1:1", "4:5", "3:2", "16:9", "9:16"])
                  .filter(Boolean)
                  .map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
              </select>
            </div>

            {preview?.notes.purpose && (
              <p className="rounded-xl border border-hairline bg-ground/60 p-2.5 text-[11px] leading-relaxed text-muted">
                {preview.notes.purpose}
              </p>
            )}
          </div>
        )}

        {subTab === "subject" && (
          <div className="space-y-2.5">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="photo-describe"
                  className="text-xs font-semibold text-text"
                >
                  Subject
                </label>
                <span
                  data-testid="subject-kind-chip"
                  className="rounded-full border border-hairline bg-raised px-2.5 py-0.5 text-[11px] font-medium text-muted"
                >
                  {KIND_LABELS[kind] ?? "Pet photo"}
                </span>
              </div>
              <textarea
                id="photo-describe"
                rows={2}
                value={form.subject}
                onChange={(e) => onUpdateField("subject", e.target.value)}
                placeholder="a woman in her late twenties with light freckles and dark wavy hair / my white Persian cat…"
                className="w-full resize-none rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs leading-relaxed text-text placeholder:text-muted"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <TextInputRow
                id="compose-wardrobe"
                label="Wardrobe"
                value={form.wardrobe}
                placeholder="an oversized cream knit sweater"
                onChange={(v) => onUpdateField("wardrobe", v)}
              />
              <TextInputRow
                id="compose-mood"
                label="Mood"
                value={form.mood}
                placeholder="calm and unhurried"
                onChange={(v) => onUpdateField("mood", v)}
              />
            </div>

            <TextInputRow
              id="compose-action"
              label="Action"
              value={form.action}
              placeholder="leaning against the counter with a mug"
              onChange={(v) => onUpdateField("action", v)}
            />

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="compose-posing"
                  className="text-xs font-semibold text-text"
                >
                  Posing
                </label>
                <button
                  type="button"
                  onClick={() => onOpenLookTab("posing")}
                  className="text-[11px] font-medium text-accent hover:underline"
                >
                  Open Posing section →
                </button>
              </div>
              <input
                id="compose-posing"
                type="text"
                value={form.posing}
                onChange={(e) => onUpdateField("posing", e.target.value)}
                placeholder="weight on the back foot, shoulders turned away from the camera"
                className="w-full rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs text-text placeholder:text-muted"
              />
            </div>

            {/* Realism toggles */}
            <div className="rounded-xl border border-hairline bg-ground/50 p-2.5 space-y-1.5">
              <span className="block text-[11px] font-semibold uppercase tracking-wider text-muted">
                Subject & physical realism
              </span>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                <CheckboxRow
                  label="Face / fur micro-detail"
                  checked={form.face_detail}
                  onChange={(v) => onUpdateField("face_detail", v)}
                />
                <CheckboxRow
                  label="Lived-in details (auto)"
                  checked={form.lived_in}
                  onChange={(v) => onUpdateField("lived_in", v)}
                />
                <CheckboxRow
                  label="Weight & contact"
                  checked={form.contact_detail}
                  onChange={(v) => onUpdateField("contact_detail", v)}
                />
                <CheckboxRow
                  label="Materials in scene"
                  checked={form.material_detail}
                  onChange={(v) => onUpdateField("material_detail", v)}
                />
                <CheckboxRow
                  label="Phone snapshot look"
                  checked={form.snapshot}
                  onChange={(v) => onUpdateField("snapshot", v)}
                />
                <CheckboxRow
                  label="Unstaged background"
                  checked={form.background_life}
                  onChange={(v) => onUpdateField("background_life", v)}
                />
                <CheckboxRow
                  label="Catch the moment"
                  checked={form.moment}
                  onChange={(v) => onUpdateField("moment", v)}
                />
              </div>

              {preview?.notes.physical && (
                <p className="pt-1 text-[11px] leading-relaxed text-muted">
                  {preview.notes.physical}
                </p>
              )}
            </div>

            {/* Skin features (people only) */}
            {options?.skin_features && options.skin_features.length > 0 && (
              <div className="rounded-xl border border-hairline bg-ground/50 p-2.5 space-y-1.5">
                <span className="block text-[11px] font-semibold uppercase tracking-wider text-muted">
                  Skin features (people only)
                </span>
                <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                  {options.skin_features.map((sf) => (
                    <CheckboxRow
                      key={sf.key}
                      label={sf.label}
                      title={sf.tip}
                      checked={form.skin_features.includes(sf.key)}
                      onChange={() => toggleSkinFeature(sf.key)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {subTab === "scene" && (
          <div className="space-y-2.5">
            <TextInputRow
              id="compose-setting"
              label="Setting"
              value={form.setting}
              placeholder="a bright apartment kitchen, mid-morning"
              onChange={(v) => onUpdateField("setting", v)}
            />

            <EditableComboField
              id="compose-shot"
              label="Shot"
              actionLabel="Open Camera Angle →"
              onAction={() => onOpenLookTab("camera")}
              value={form.shot}
              placeholder="(auto) or preset / custom shot"
              options={
                options?.shots.map((s) => ({ value: s, label: s })) ?? []
              }
              onChange={(v) => onUpdateField("shot", v)}
            />

            <EditableComboField
              id="compose-lighting"
              label="Lighting"
              actionLabel="Open Lighting →"
              onAction={() => onOpenLookTab("lighting")}
              value={form.lighting}
              placeholder="(auto) or pick / type lighting source"
              options={
                options?.lighting_terms.map((t) => ({ value: t, label: t })) ??
                []
              }
              onChange={(v) => onUpdateField("lighting", v)}
            />

            <EditableComboField
              id="compose-colour"
              label="Colour"
              actionLabel="Open Color Grading →"
              onAction={() => onOpenLookTab("color")}
              value={form.colour}
              placeholder="(auto) or pick / type colour grade"
              options={
                options?.colour_terms.map((t) => ({ value: t, label: t })) ?? []
              }
              onChange={(v) => onUpdateField("colour", v)}
            />

            <EditableComboField
              id="compose-composition"
              label="Composition"
              actionLabel="Open Composition →"
              onAction={() => onOpenLookTab("composition")}
              value={form.composition}
              placeholder="(none) or pick guide / type framing"
              options={
                options?.composition_guides.map((g) => ({
                  value: g.key,
                  label: g.label,
                })) ?? []
              }
              onChange={(v) => onUpdateField("composition", v)}
            />

            <div className="rounded-xl border border-hairline bg-ground/50 p-2.5 space-y-1">
              <CheckboxRow
                label="Match light to the scene"
                checked={form.match_light}
                onChange={(v) => onUpdateField("match_light", v)}
              />
              {preview?.notes.light && (
                <p className="text-[11px] leading-relaxed text-muted">
                  {preview.notes.light}
                </p>
              )}
            </div>
          </div>
        )}

        {subTab === "identity" && (
          <div className="space-y-3">
            <p className="text-xs leading-relaxed text-muted">
              Lock this character&apos;s face or pet&apos;s markings to a reference photo so later shots stay the same individual. The reference is sent alongside the prompt.
            </p>
            <Reference
              provider={provider}
              reference={reference}
              onChange={onReferenceChange}
            />
            <LookCards
              cards={cards}
              selected={selectedCards}
              touched={touchedCards}
              overrides={overrides}
              onSelectOption={onSelectCardOption}
              onOpenLookTab={(part) => onOpenLookTab(part ?? "lighting")}
            />
          </div>
        )}

        {subTab === "more" && (
          <div className="space-y-3">
            <div className="space-y-1">
              <label
                htmlFor="compose-extra"
                className="block text-xs font-semibold text-text"
              >
                Extra directions (one per line)
              </label>
              <textarea
                id="compose-extra"
                rows={2}
                value={form.extra}
                onChange={(e) => onUpdateField("extra", e.target.value)}
                placeholder="one extra direction per line"
                className="w-full resize-none rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs text-text placeholder:text-muted"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="compose-seed"
                    className="text-xs font-semibold text-text"
                  >
                    Seed
                  </label>
                  <button
                    type="button"
                    onClick={reshuffleSeed}
                    className="inline-flex items-center gap-1 text-[11px] text-accent hover:underline"
                  >
                    <Shuffle className="h-3 w-3" />
                    Reshuffle
                  </button>
                </div>
                <input
                  id="compose-seed"
                  type="number"
                  min={0}
                  max={9999}
                  value={form.seed}
                  onChange={(e) =>
                    onUpdateField("seed", Number(e.target.value) || 0)
                  }
                  className="w-full rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs text-text"
                />
              </div>

              <TextInputRow
                id="compose-slug"
                label="Slug"
                value={form.slug}
                placeholder="(auto from subject)"
                onChange={(v) => onUpdateField("slug", v)}
              />
            </div>

            <div className="flex items-center justify-between gap-3 rounded-xl border border-hairline bg-ground/50 px-3 py-2">
              <div className="flex items-center gap-2">
                <label
                  htmlFor="compose-form-mode"
                  className="text-xs font-medium text-text"
                >
                  Form
                </label>
                <select
                  id="compose-form-mode"
                  value={form.detailed ? "detailed" : "compact"}
                  onChange={(e) =>
                    onUpdateField("detailed", e.target.value === "detailed")
                  }
                  className="rounded-lg border border-hairline bg-surface px-2 py-1 text-xs text-text"
                >
                  <option value="compact">Compact</option>
                  <option value="detailed">Detailed</option>
                </select>
              </div>
              <CheckboxRow
                label="Body guard"
                checked={form.anatomy_guard}
                onChange={(v) => onUpdateField("anatomy_guard", v)}
              />
            </div>

            {/* Composed Prompt Preview + Realism Gate */}
            <div className="rounded-xl border border-hairline bg-ground p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-text">
                  Composed Prompt
                </span>
                <div className="flex items-center gap-2">
                  {preview && (
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        preview.lint.passed
                          ? "bg-ok/20 text-ok"
                          : "bg-accent/20 text-accent"
                      }`}
                    >
                      Realism {preview.lint.score}/{preview.lint.total}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handleCopyPrompt}
                    className="inline-flex items-center gap-1 rounded-lg border border-hairline bg-surface px-2 py-0.5 text-[11px] text-muted hover:text-text"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3 w-3 text-ok" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
              </div>
              <p className="max-h-28 overflow-y-auto rounded-lg border border-hairline bg-surface p-2 font-mono text-[11px] leading-relaxed text-muted">
                {preview?.prompt || "Composed prompt will appear here…"}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function TextInputRow({
  id,
  label,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  onChange: (val: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-xs font-semibold text-text">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs text-text placeholder:text-muted"
      />
    </div>
  );
}

function CheckboxRow({
  label,
  title,
  checked,
  onChange,
}: {
  label: string;
  title?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label
      title={title}
      className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] text-text"
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 rounded border-hairline accent-accent"
      />
      <span className="truncate">{label}</span>
    </label>
  );
}

function EditableComboField({
  id,
  label,
  tooltipPlain,
  tooltipExample,
  actionLabel,
  onAction,
  value,
  placeholder,
  options,
  onChange,
}: {
  id: string;
  label: string;
  tooltipPlain?: string;
  tooltipExample?: string;
  actionLabel?: string;
  onAction?: () => void;
  value: string;
  placeholder: string;
  options: { value: string; label: string }[];
  onChange: (val: string) => void;
}) {
  const listId = `${id}-datalist`;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-xs font-semibold text-text">
          {tooltipPlain && tooltipExample ? (
            <Term word={label} plain={tooltipPlain} example={tooltipExample} />
          ) : (
            label
          )}
        </label>
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={onAction}
            className="text-[11px] font-medium text-accent hover:underline"
          >
            {actionLabel}
          </button>
        )}
      </div>
      <div className="flex gap-1.5">
        <input
          id={id}
          list={listId}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-xl border border-hairline bg-ground px-3 py-1.5 text-xs text-text placeholder:text-muted"
        />
        {options.length > 0 && (
          <select
            aria-label={`${label} presets`}
            value={options.some((o) => o.value === value) ? value : ""}
            onChange={(e) => onChange(e.target.value)}
            className="w-28 shrink-0 truncate rounded-xl border border-hairline bg-raised px-2 py-1.5 text-[11px] text-text"
          >
            <option value="">Presets…</option>
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        )}
      </div>
      <datalist id={listId}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </datalist>
    </div>
  );
}
