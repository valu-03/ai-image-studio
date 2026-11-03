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
  const checks = preview?.lint.checks ?? [];
  const score = preview?.lint.score ?? 0;
  const total = preview?.lint.total ?? 8;
  const passed = preview?.lint.passed ?? false;

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
      aria-label="Prompt and Realism check"
      data-testid="prompt-panel"
      className="grid h-[260px] shrink-0 grid-cols-1 gap-4 border-t border-hairline bg-surface px-5 py-3.5 lg:grid-cols-2"
    >
      {/* Left half: Composed Prompt + Form / Body guard / Reshuffle / Copy */}
      <div className="flex min-h-0 flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
            Prompt
          </h2>

          <div className="flex flex-wrap items-center gap-1.5">
            <div className="flex items-center gap-1">
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
                className="rounded-lg border border-hairline bg-raised px-2 py-1 text-[11px] text-text"
              >
                <option value="compact">Compact</option>
                <option value="detailed">Detailed</option>
              </select>
            </div>

            <label
              title="Append: no warped face, no distorted hands or extra fingers, no floating or extra limbs, no duplicated figures, no morphing."
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-hairline bg-raised px-2 py-1 text-[11px] text-text"
            >
              <input
                type="checkbox"
                checked={form.anatomy_guard}
                onChange={(e) =>
                  onUpdateField("anatomy_guard", e.target.checked)
                }
                className="h-3.5 w-3.5 rounded border-hairline accent-accent"
              />
              <span>Body guard</span>
            </label>

            <button
              type="button"
              onClick={handleReshuffle}
              title="Bump the seed — new vocabulary, same character"
              className="inline-flex items-center gap-1 rounded-lg border border-hairline bg-raised px-2 py-1 text-[11px] font-medium text-text hover:border-muted"
            >
              <Shuffle className="h-3 w-3 text-muted" />
              Reshuffle
            </button>

            <button
              type="button"
              onClick={handleCopy}
              disabled={!promptText}
              data-testid="copy-prompt-button"
              className="inline-flex items-center gap-1 rounded-lg border border-accent/60 bg-raised px-2.5 py-1 text-[11px] font-semibold text-text hover:bg-ground disabled:opacity-40"
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 text-ok" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 text-accent" />
                  Copy
                </>
              )}
            </button>
          </div>
        </div>

        <textarea
          readOnly
          aria-label="Composed prompt text"
          value={promptText}
          placeholder="The composed prompt appears here."
          onClick={(e) => e.currentTarget.select()}
          className="min-h-0 flex-1 resize-none rounded-xl border border-hairline bg-ground px-3 py-2 font-mono text-xs leading-relaxed text-text placeholder:text-muted"
        />
      </div>

      {/* Right half: 8/8 Realism check table (LAYER | DETAIL) */}
      <div className="flex min-h-0 flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-text">
              Realism check
            </h2>
            <span
              data-testid="realism-score-badge"
              className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                passed ? "bg-ok/20 text-ok" : "bg-danger/20 text-danger"
              }`}
            >
              {score}/{total}
            </span>
          </div>
          <span className="text-[11px] text-muted">
            {passed
              ? "Ready to generate."
              : "Fix the flagged items before generating."}
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-hairline bg-ground">
          <table className="w-full border-collapse text-left text-[11px]">
            <thead className="sticky top-0 border-b border-hairline bg-raised text-[10px] font-semibold uppercase tracking-wider text-muted">
              <tr>
                <th className="w-6 px-2 py-1 text-center"></th>
                <th className="w-44 px-2 py-1">Layer</th>
                <th className="px-2 py-1">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline/60">
              {checks.map((chk) => {
                const isWarn = chk.state === "warn";
                const mark = !chk.passed ? "✗" : isWarn ? "~" : "✓";
                const colorClass = !chk.passed
                  ? "text-danger"
                  : isWarn
                    ? "text-accent"
                    : "text-ok";
                const detailText =
                  !chk.passed || isWarn ? chk.fix : chk.ok_text;
                return (
                  <tr key={chk.key} className="hover:bg-surface/60">
                    <td className={`px-2 py-1 text-center font-bold ${colorClass}`}>
                      {mark}
                    </td>
                    <td className="px-2 py-1 font-medium text-text">
                      {chk.label}
                    </td>
                    <td className="px-2 py-1 text-muted">{detailText}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
