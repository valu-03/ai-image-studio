import { AlertCircle, Eye, Loader2 } from "lucide-react";
import type {
  GiveawayItem,
  PhotoJob,
  PriceEstimate,
  RecentPhoto,
} from "../../lib/api";
import { RealCheck } from "./RealCheck";

export interface PhotoPanelProps {
  job: PhotoJob | null;
  selectedRecent: RecentPhoto | null;
  recentCheck: {
    historyId: string;
    loading: boolean;
    giveaways: GiveawayItem[] | null;
    check_error: string;
  } | null;
  price: PriceEstimate | null;
  pending: boolean;
  onFix: (giveawayKey: string) => void;
  onCheckRecent: (historyId: string) => void;
}

export function PhotoPanel({
  job,
  selectedRecent,
  recentCheck,
  price,
  pending,
  onFix,
  onCheckRecent,
}: PhotoPanelProps) {
  const checkUsd = (price?.check?.usd ?? 0.01).toFixed(2);

  // Viewing a selected recent photo (when no new job is currently running)
  if (selectedRecent && (!job || job.state !== "running")) {
    const isApi = selectedRecent.source === "api";
    const matchingCheck =
      recentCheck && recentCheck.historyId === selectedRecent.history_id
        ? recentCheck
        : null;

    return (
      <div className="flex min-h-0 flex-1 flex-col justify-between overflow-y-auto p-5">
        <div className="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-photo-ground p-2">
          <img
            src={selectedRecent.file_url}
            alt="Selected recent photo"
            className="max-h-full max-w-full rounded-lg object-contain"
          />
        </div>

        <div className="mt-4 space-y-3">
          {isApi && !matchingCheck && (
            <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface p-3.5 text-xs">
              <span className="text-muted">
                Made through Skit Studio. Run the picture check if something looks off.
              </span>
              <button
                type="button"
                onClick={() => onCheckRecent(selectedRecent.history_id)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-on-accent hover:opacity-95"
              >
                <Eye className="h-3.5 w-3.5" />
                {`Check this photo · ~$${checkUsd}`}
              </button>
            </div>
          )}

          {matchingCheck?.loading && (
            <div className="flex items-center gap-2 rounded-xl border border-hairline bg-surface p-3.5 text-xs text-muted">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              Checking how real it looks…
            </div>
          )}

          {matchingCheck && !matchingCheck.loading && (
            <RealCheck
              giveaways={matchingCheck.giveaways}
              checkError={matchingCheck.check_error}
              price={price}
              pending={pending}
              canFix={false}
              onFix={onFix}
            />
          )}
        </div>
      </div>
    );
  }

  // Empty state
  if (!job) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md rounded-2xl border border-hairline bg-surface/70 p-6 text-center">
          <p className="text-sm leading-relaxed text-text">
            Describe what&apos;s in the photo on the left. The app makes it, then looks at it like a sceptical friend would and points out what gives it away.
          </p>
        </div>
      </div>
    );
  }

  // Generating state
  if (job.state === "running") {
    return (
      <div className="flex min-h-0 flex-1 flex-col justify-between overflow-y-auto p-5">
        {job.file_url ? (
          <div className="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-photo-ground p-2">
            <img
              src={job.file_url}
              alt="Generated photo"
              className="max-h-full max-w-full rounded-lg object-contain"
            />
          </div>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
            <Loader2 className="h-6 w-6 animate-spin text-accent" />
            <p className="text-sm font-medium text-text">
              {job.stage || "Making your photo…"}
            </p>
          </div>
        )}
      </div>
    );
  }

  // Error state
  if (job.state === "error") {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div
          role="alert"
          className="max-w-md rounded-2xl border border-danger/40 bg-surface p-6 text-left"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
            <div className="space-y-1.5">
              <h3 className="text-sm font-semibold text-text">
                Couldn&apos;t make the photo
              </h3>
              <p className="whitespace-pre-line text-xs leading-relaxed text-muted">
                {job.error}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Done state
  return (
    <div className="flex min-h-0 flex-1 flex-col justify-between overflow-y-auto p-5">
      <div className="flex min-h-0 flex-1 items-center justify-center rounded-2xl bg-photo-ground p-2">
        {job.file_url && (
          <img
            src={job.file_url}
            alt="Generated photo"
            className="max-h-full max-w-full rounded-lg object-contain"
          />
        )}
      </div>

      <div className="mt-4">
        <RealCheck
          giveaways={job.giveaways}
          checkError={job.check_error}
          price={price}
          pending={pending}
          canFix={true}
          onFix={onFix}
        />
      </div>
    </div>
  );
}
