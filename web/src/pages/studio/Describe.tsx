import type { SubjectKind } from "../../lib/api";

const KIND_LABELS: Record<SubjectKind, string> = {
  animal: "Pet photo",
  human: "People photo",
  object: "Object photo",
  place: "Place photo",
};

export interface DescribeProps {
  text: string;
  kind: SubjectKind;
  onChange: (text: string) => void;
}

export function Describe({ text, kind, onChange }: DescribeProps) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label
          htmlFor="photo-describe"
          className="text-xs font-semibold text-text"
        >
          What&apos;s in the photo?
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
        value={text}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. My white Persian cat asleep on the arm of our grey sofa, one paw hanging down…"
        className="w-full resize-none rounded-xl border border-hairline bg-ground px-3 py-2 text-xs leading-relaxed text-text placeholder:text-muted"
      />
    </div>
  );
}
