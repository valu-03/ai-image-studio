import { ThumbsDown, ThumbsUp } from "lucide-react";
import type { RecentPhoto } from "../../lib/api";

export interface RecentStripProps {
  items: RecentPhoto[];
  activeHistoryId: string | null;
  onSelect: (item: RecentPhoto) => void;
  onRate: (historyId: string, thumb: "up" | "down") => void;
}

export function RecentStrip({
  items,
  activeHistoryId,
  onSelect,
  onRate,
}: RecentStripProps) {
  if (items.length === 0) return null;

  return (
    <div
      aria-label="Recent photos"
      className="border-t border-hairline bg-surface px-4 py-2.5"
    >
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted">
          Recent photos
        </span>
        <span className="text-[11px] text-muted">
          Thumbs teach the app which Look choices work best for you
        </span>
      </div>

      <div className="flex gap-2.5 overflow-x-auto pb-1">
        {items.map((item) => {
          const isActive = item.history_id === activeHistoryId;
          const isUp = item.rating !== null && item.rating >= 4;
          const isDown = item.rating !== null && item.rating <= 2;

          return (
            <div
              key={item.history_id}
              className={`group relative flex shrink-0 flex-col overflow-hidden rounded-xl border bg-raised/50 transition-colors ${
                isActive ? "border-accent" : "border-hairline hover:border-muted"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(item)}
                className="relative block h-16 w-24 overflow-hidden bg-photo-ground text-left"
              >
                <img
                  src={item.file_url}
                  alt={item.note || "Recent generated photo"}
                  className="h-full w-full object-cover"
                />
                {item.source === "api" && (
                  <span className="absolute left-1 top-1 rounded bg-ground/85 px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                    Skit Studio
                  </span>
                )}
              </button>

              <div className="flex items-center justify-center gap-1 border-t border-hairline bg-surface px-1.5 py-1">
                <button
                  type="button"
                  aria-label="Thumb up"
                  aria-pressed={isUp}
                  onClick={() => onRate(item.history_id, "up")}
                  className={`rounded p-1 transition-colors ${
                    isUp
                      ? "bg-ok/20 text-ok"
                      : "text-muted hover:bg-raised hover:text-text"
                  }`}
                >
                  <ThumbsUp className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  aria-label="Thumb down"
                  aria-pressed={isDown}
                  onClick={() => onRate(item.history_id, "down")}
                  className={`rounded p-1 transition-colors ${
                    isDown
                      ? "bg-danger/20 text-danger"
                      : "text-muted hover:bg-raised hover:text-text"
                  }`}
                >
                  <ThumbsDown className="h-3 w-3" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
