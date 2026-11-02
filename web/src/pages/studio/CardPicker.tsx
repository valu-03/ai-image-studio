import { X, Check } from "lucide-react";
import type { LookCard } from "../../lib/api";

export interface CardPickerProps {
  card: LookCard | null;
  selectedOptionKey: string;
  onSelect: (cardId: string, optionKey: string) => void;
  onClose: () => void;
}

export function CardPicker({
  card,
  selectedOptionKey,
  onSelect,
  onClose,
}: CardPickerProps) {
  if (!card) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`${card.title} options`}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-hairline bg-surface p-5 text-text shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-hairline pb-3">
          <div>
            <h3 className="text-sm font-semibold text-text">{card.title}</h3>
            <p className="mt-0.5 text-xs text-muted">{card.plain}</p>
            <p className="mt-1 text-[11px] text-muted">
              <span className="font-semibold text-text">Like: </span>
              {card.example}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={`Close ${card.title}`}
            className="rounded-lg p-1 text-muted hover:bg-raised hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 max-h-[60vh] space-y-2 overflow-y-auto pr-1">
          {card.options.map((opt) => {
            const active = opt.key === selectedOptionKey;
            return (
              <button
                key={opt.key}
                type="button"
                aria-pressed={active}
                onClick={() => {
                  onSelect(card.id, opt.key);
                  onClose();
                }}
                className={`w-full rounded-xl border p-3 text-left transition-colors ${
                  active
                    ? "border-accent bg-raised"
                    : "border-hairline bg-ground/60 hover:border-muted"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-text">{opt.label}</span>
                  {active && <Check className="h-3.5 w-3.5 text-accent" />}
                </div>
                <p className="mt-1 text-xs text-text">{opt.plain}</p>
                <p className="mt-1 text-[11px] text-muted">
                  <span className="font-medium text-text">Like: </span>
                  {opt.example}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
