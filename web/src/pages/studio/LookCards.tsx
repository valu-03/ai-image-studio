import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { LookCard, LookPart } from "../../lib/api";
import { Term } from "../../components/Term";
import { CardPicker } from "./CardPicker";

export interface LookCardsProps {
  cards: LookCard[];
  selected: Record<string, string>;
  touched: string[];
  overrides?: Record<string, string>;
  onSelectOption: (cardId: string, optionKey: string) => void;
  onOpenLookTab?: (part?: LookPart) => void;
}

export function LookCards({
  cards,
  selected,
  touched,
  overrides = {},
  onSelectOption,
  onOpenLookTab,
}: LookCardsProps) {
  const [openCardId, setOpenCardId] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeCard = cards.find((c) => c.id === openCardId) ?? null;
  const touchedSet = new Set(touched);
  const overrideCount = Object.keys(overrides).length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text">
          <Term
            word="Look cards"
            plain="Six everyday camera choices that keep a photo from looking computer-made."
            example="Like picking which room light is on and where you stand before clicking the shutter."
          />
        </span>
        <span className="text-[11px] text-muted">
          Sensible defaults set · click a card to change
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {cards.map((card) => {
          const currentKey = selected[card.id] ?? card.options[0]?.key ?? "";
          const currentOpt =
            card.options.find((o) => o.key === currentKey) ?? card.options[0];
          const isTouched = touchedSet.has(card.id);
          return (
            <div
              key={card.id}
              data-testid={`look-card-${card.id}`}
              onClick={() => setOpenCardId(card.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenCardId(card.id);
                }
              }}
              role="button"
              tabIndex={0}
              aria-label={`${card.title}: ${currentOpt?.label ?? ""}. Click to change.`}
              className={`cursor-pointer rounded-xl border p-2.5 text-left transition-colors ${
                isTouched
                  ? "border-accent/60 bg-raised"
                  : "border-hairline bg-raised/50 hover:border-muted"
              }`}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="text-[11px] font-medium text-muted">
                  <Term
                    word={card.title}
                    plain={card.plain}
                    example={card.example}
                  />
                </span>
                {isTouched && (
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" title="You chose this" />
                )}
              </div>
              <div className="mt-0.5 truncate text-xs font-semibold text-text">
                {currentOpt?.label ?? "Default"}
              </div>
              <p className="mt-0.5 line-clamp-1 text-[11px] text-muted">
                {currentOpt?.plain ?? card.plain}
              </p>
            </div>
          );
        })}
      </div>

      <div>
        <div className="flex items-center justify-between">
          <button
            type="button"
            aria-expanded={advancedOpen}
            onClick={() => setAdvancedOpen((v) => !v)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-muted hover:text-text"
          >
            {advancedOpen ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            More controls
          </button>
          {onOpenLookTab && (
            <button
              type="button"
              onClick={() => onOpenLookTab("lighting")}
              className="text-[11px] font-medium text-accent hover:underline"
            >
              {overrideCount > 0
                ? `Look tab (${overrideCount} applied) →`
                : "Open Look tab →"}
            </button>
          )}
        </div>
        {advancedOpen && (
          <div className="mt-1.5 space-y-2 rounded-xl border border-hairline bg-ground/60 p-2.5 text-[11px] leading-relaxed text-muted">
            <p>
              Cards with a gold dot are shared with Skit Studio while this window is open. Untouched cards stay on realistic defaults that vary naturally between photos.
            </p>
            {onOpenLookTab && (
              <div className="flex flex-wrap gap-1 pt-0.5">
                {(
                  [
                    ["lighting", "Lighting"],
                    ["composition", "Composition"],
                    ["camera", "Camera"],
                    ["color", "Color"],
                    ["posing", "Posing"],
                    ["style", "Style"],
                    ["capture", "Capture"],
                    ["evidence", "Evidence"],
                  ] as [LookPart, string][]
                ).map(([part, label]) => (
                  <button
                    key={part}
                    type="button"
                    onClick={() => onOpenLookTab(part)}
                    className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                      overrides[part]
                        ? "border-accent/60 bg-raised text-text"
                        : "border-hairline bg-surface text-muted hover:text-text"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <CardPicker
        card={activeCard}
        selectedOptionKey={activeCard ? selected[activeCard.id] ?? "" : ""}
        onSelect={onSelectOption}
        onClose={() => setOpenCardId(null)}
      />
    </div>
  );
}
