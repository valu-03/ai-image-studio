import { useState } from "react";
import { Check, Copy, Shuffle } from "lucide-react";
import type { ComposeFormState, ComposePreviewPayload } from "../../lib/api";

export interface PromptPanelProps {
  form: ComposeFormState;
  preview: ComposePreviewPayload | null;
  onUpdateField: <K extends keyof ComposeFormState>(
    key: K,
    value: ComposeFormState[K]
  ) => void;
}

export function PromptPanel({
  form,
  preview,
  onUpdateField,
}: PromptPanelProps) {
  const [copied, setCopied] = useState(false);

  const promptText = preview?.prompt ?? "";

  const handleCopy = () => {
    if (!promptText) return;
    void navigator.clipboard?.writeText(promptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleReshuffle = () => {
    onUpdateField("seed", (form.seed + 1) % 10000);
  };

  return (
    <section
      aria-label="Prompt preview"
      data-testid="prompt-panel"
      className="flex shrink-0 flex-col gap-2.5 border-t border-hairline bg-surface px-5 py-3.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
            Prompt
          </h2>
          {preview && (
            <span
              data-testid="realism-score-badge"
              className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                preview.lint.passed
                  ? "bg-ok/20 text-ok"
                  : "bg-accent/20 text-accent"
              }`}
            >
              Realism check: {preview.lint.score}/{preview.lint.total}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5">
            <label
              htmlFor="prompt-form-mode"
              className="text-[11px] font-medium text-muted"
            >
              Form
            </label>
            <select
              id="prompt-form-mode"
              value={form.detailed ? "detailed" : "compact"}
              onChange={(e) =>
                onUpdateField("detailed", e.target.value === "detailed")
              }
              className="rounded-lg border border-hairline bg-raised px-2 py-1 text-xs text-text"
            >
              <option value="compact">Compact</option>
              <option value="detailed">Detailed</option>
            </select>
          </div>

          <label
            title="Append: no warped face, no distorted hands or extra fingers, no floating or extra limbs, no duplicated figures, no morphing."
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-hairline bg-raised px-2.5 py-1 text-xs text-text"
          >
            <input
              type="checkbox"
              checked={form.anatomy_guard}
              onChange={(e) => onUpdateField("anatomy_guard", e.target.checked)}
              className="h-3.5 w-3.5 rounded border-hairline accent-accent"
            />
            <span>Body guard</span>
          </label>

          <button
            type="button"
            onClick={handleReshuffle}
            title="Bump the seed — new vocabulary, same character"
            className="inline-flex items-center gap-1.5 rounded-lg border border-hairline bg-raised px-2.5 py-1 text-xs font-medium text-text hover:border-muted"
          >
            <Shuffle className="h-3.5 w-3.5 text-muted" />
            Reshuffle
          </button>

          <button
            type="button"
            onClick={handleCopy}
            disabled={!promptText}
            data-testid="copy-prompt-button"
            className="inline-flex items-center gap-1.5 rounded-lg border border-accent/60 bg-raised px-3 py-1 text-xs font-semibold text-text hover:bg-ground disabled:opacity-40"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-ok" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-accent" />
                Copy
              </>
            )}
          </button>
        </div>
      </div>

      <textarea
        readOnly
        rows={4}
        aria-label="Composed prompt text"
        value={promptText}
        placeholder="The composed prompt appears here."
        onClick={(e) => e.currentTarget.select()}
        className="w-full resize-none rounded-xl border border-hairline bg-ground px-3.5 py-2.5 font-mono text-xs leading-relaxed text-text placeholder:text-muted"
      />

      {preview?.lint.checks && (
        <div className="flex flex-wrap items-center gap-1.5">
          {preview.lint.checks.slice(0, 9).map((chk) => (
            <span
              key={chk.key}
              title={chk.passed ? chk.ok_text : chk.fix}
              className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${
                chk.passed
                  ? "border-hairline bg-ground text-muted"
                  : "border-danger/50 bg-danger/10 text-danger"
              }`}
            >
              {chk.passed ? "✓" : "✗"} {chk.label}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
