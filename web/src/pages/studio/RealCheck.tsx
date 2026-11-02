import { useRef } from "react";
import { AlertTriangle, CheckCircle2, Wrench } from "lucide-react";
import type { GiveawayItem, PriceEstimate } from "../../lib/api";
import { formatTotalPrice } from "./MakeButton";

export interface RealCheckProps {
  giveaways: GiveawayItem[] | null;
  checkError: string;
  price: PriceEstimate | null;
  pending: boolean;
  canFix: boolean;
  onFix: (giveawayKey: string) => void;
}

export function RealCheck({
  giveaways,
  checkError,
  price,
  pending,
  canFix,
  onFix,
}: RealCheckProps) {
  const clickedRef = useRef(false);
  const priceLabel = formatTotalPrice(price);

  const handleFixClick = (key: string) => {
    if (pending || clickedRef.current) return;
    clickedRef.current = true;
    try {
      onFix(key);
    } finally {
      setTimeout(() => {
        clickedRef.current = false;
      }, 300);
    }
  };

  if (checkError) {
    const cleanReason = checkError.replace(/^The picture check couldn't run:\s*/i, "");
    return (
      <div
        role="region"
        aria-label="Does this look real?"
        className="rounded-xl border border-hairline bg-surface p-3.5 text-xs"
      >
        <div className="flex items-start gap-2 text-muted">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <div>
            <p className="font-semibold text-text">
              The picture check couldn&apos;t run: {cleanReason}
            </p>
            <p className="mt-0.5 text-[11px] text-muted">
              Your photo is ready above. Add an OpenRouter key in Settings whenever you want the check to read it.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (giveaways === null) {
    return null;
  }

  if (giveaways.length === 0) {
    return (
      <div
        role="region"
        aria-label="Does this look real?"
        className="rounded-xl border border-hairline bg-surface p-3.5 text-xs"
      >
        <div className="flex items-center gap-2 text-text">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-ok" />
          <span className="font-medium">
            Nothing obvious gives it away. Still look closely: you&apos;re the final judge.
          </span>
        </div>
      </div>
    );
  }

  const countLabel =
    giveaways.length === 1
      ? "1 thing gives it away"
      : `${giveaways.length} things give it away`;

  return (
    <div
      role="region"
      aria-label="Does this look real?"
      className="space-y-2.5 rounded-xl border border-hairline bg-surface p-3.5 text-xs"
    >
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-text">Does this look real?</h3>
        <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] font-semibold text-accent">
          {countLabel}
        </span>
      </div>

      <ul className="space-y-2">
        {giveaways.map((item) => {
          const btnText = item.fixable
            ? `Fix · ${priceLabel}`
            : `Try again with a fix · ${priceLabel}`;
          return (
            <li
              key={item.key}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-hairline bg-raised/50 p-3"
            >
              <div className="min-w-0 flex-1 space-y-0.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-text">{item.label}</span>
                  {item.where && (
                    <span className="rounded bg-ground px-1.5 py-0.5 text-[11px] text-muted">
                      {item.where}
                    </span>
                  )}
                </div>
                <p className="text-[11px] leading-relaxed text-muted">{item.plain}</p>
              </div>

              {canFix && (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => handleFixClick(item.key)}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-on-accent hover:opacity-95 disabled:opacity-40"
                >
                  <Wrench className="h-3.5 w-3.5" />
                  {btnText}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
