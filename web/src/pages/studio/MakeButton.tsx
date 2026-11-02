import type { PriceEstimate } from "../../lib/api";

export function formatTotalPrice(price: PriceEstimate | null): string {
  if (!price || price.image.usd === null || price.image.usd === undefined) {
    return "price unknown";
  }
  const total = price.image.usd + (price.check?.usd ?? 0);
  return `~$${total.toFixed(2)}`;
}

export interface MakeButtonProps {
  pending: boolean;
  textEmpty: boolean;
  keyMissing: boolean;
  price: PriceEstimate | null;
  onMake: () => void;
  onOpenSettings?: () => void;
}

export function MakeButton({
  pending,
  textEmpty,
  keyMissing,
  price,
  onMake,
  onOpenSettings,
}: MakeButtonProps) {
  const disabled = pending || textEmpty || keyMissing;
  const priceTag = formatTotalPrice(price);

  return (
    <div className="space-y-1.5">
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!disabled) onMake();
        }}
        className="w-full rounded-xl bg-accent px-4 py-2.5 text-xs font-semibold text-on-accent shadow-sm transition-opacity hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {pending ? "Making photo…" : `Make photo · ${priceTag}`}
      </button>
      {keyMissing && (
        <div className="flex items-center justify-between text-[11px] text-danger">
          <span>Image API key is not set yet.</span>
          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="font-semibold underline hover:text-text"
            >
              Open Settings
            </button>
          )}
        </div>
      )}
    </div>
  );
}
