import { useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import { Term } from "../../components/Term";

export const MAX_REFERENCE_BYTES = 20 * 1024 * 1024;
const ALLOWED_MIME = new Set(["image/png", "image/jpeg", "image/webp"]);
const ALLOWED_EXT = /\.(png|jpe?g|webp)$/i;

export interface ReferenceFile {
  name: string;
  b64: string;
}

export function validateReferenceCandidate(file: {
  name: string;
  size: number;
  type?: string;
}): string | null {
  if (file.size > MAX_REFERENCE_BYTES) {
    return "That reference is bigger than 20 MB. Pick a smaller photo.";
  }
  const mimeOk = file.type ? ALLOWED_MIME.has(file.type.toLowerCase()) : false;
  const extOk = ALLOWED_EXT.test(file.name);
  if (!mimeOk && !extOk) {
    return "Pick a PNG, JPEG or WebP photo (HEIC and other formats aren't supported).";
  }
  return null;
}

export interface ReferenceProps {
  provider: "kie" | "higgsfield";
  reference: ReferenceFile | null;
  onChange: (ref: ReferenceFile | null) => void;
}

export function Reference({ provider, reference, onChange }: ReferenceProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string>("");
  const isSoul = provider === "higgsfield";

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const problem = validateReferenceCandidate(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const comma = result.indexOf(",");
      const b64 = comma >= 0 ? result.slice(comma + 1) : result;
      onChange({ name: file.name, b64 });
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="rounded-xl border border-hairline bg-raised/40 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-medium text-text">
          <Term
            word="Reference photo"
            plain="A real photo of the same pet or person so the app keeps their markings or face."
            example="Like showing a portrait painter a snapshot of your dog before they start."
          />{" "}
          <span className="text-[11px] font-normal text-muted">(optional)</span>
        </div>

        {isSoul ? (
          <span className="text-[11px] text-muted">Unavailable with Soul</span>
        ) : reference ? (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="max-w-[140px] truncate text-text" title={reference.name}>
              {reference.name}
            </span>
            <button
              type="button"
              onClick={() => onChange(null)}
              aria-label="Remove reference photo"
              className="rounded p-0.5 text-muted hover:bg-surface hover:text-text"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : (
          <>
            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(e) => handleFile(e.target.files?.[0])}
              className="sr-only"
              aria-label="Upload reference photo"
            />
            <button
              type="button"
              disabled={isSoul}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-1 rounded-lg border border-hairline bg-surface px-2.5 py-1 text-[11px] font-medium text-text hover:border-muted disabled:opacity-40"
            >
              <ImagePlus className="h-3.5 w-3.5 text-muted" />
              Add photo
            </button>
          </>
        )}
      </div>

      {isSoul && (
        <p className="mt-1 text-[11px] text-muted">
          Higgsfield Soul can&apos;t use a reference photo. Switch to Nano Banana Pro (Kie) in Settings to lock identity.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-1 text-[11px] text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
