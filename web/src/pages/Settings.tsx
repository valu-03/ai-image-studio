import { useState } from "react";
import { X, Check, AlertTriangle } from "lucide-react";
import type { KeyName, SettingsPayload } from "../lib/api";
import { Term } from "../components/Term";

interface KeyRowSpec {
  name: KeyName;
  label: string;
  purpose: string;
}

const KEY_ROWS: KeyRowSpec[] = [
  {
    name: "KIE_API_KEY",
    label: "Kie key (Nano Banana Pro)",
    purpose: "Makes photos and supports a reference photo to lock identity.",
  },
  {
    name: "OPENROUTER_API_KEY",
    label: "OpenRouter key (Picture check)",
    purpose: "Reads the finished picture and points out what gives it away.",
  },
  {
    name: "HIGGSFIELD_API_KEY_ID",
    label: "Higgsfield key ID (Soul)",
    purpose: "First half of the Higgsfield Soul login.",
  },
  {
    name: "HIGGSFIELD_API_KEY_SECRET",
    label: "Higgsfield key secret (Soul)",
    purpose: "Second half of the Higgsfield Soul login.",
  },
];

export interface SettingsProps {
  open: boolean;
  settings: SettingsPayload | null;
  onClose: () => void;
  onSaveKey: (name: KeyName, value: string) => Promise<void>;
  onChangeProvider: (provider: "kie" | "higgsfield") => Promise<void>;
  onToggleLocalApi: (enabled: boolean) => Promise<void>;
}

export function Settings({
  open,
  settings,
  onClose,
  onSaveKey,
  onChangeProvider,
  onToggleLocalApi,
}: SettingsProps) {
  const [drafts, setDrafts] = useState<Partial<Record<KeyName, string>>>({});
  const [saving, setSaving] = useState<KeyName | null>(null);
  const [error, setError] = useState<string>("");

  if (!open || !settings) return null;

  const handleSave = async (name: KeyName) => {
    const val = (drafts[name] ?? "").trim();
    setSaving(name);
    setError("");
    try {
      await onSaveKey(name, val);
      setDrafts((prev) => ({ ...prev, [name]: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save key.");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      onClick={onClose}
    >
      <aside
        className="flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-hairline bg-surface p-6 text-text shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-hairline pb-4">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="rounded-lg p-1.5 text-muted hover:bg-raised hover:text-text"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger"
          >
            {error}
          </div>
        )}

        <section className="mt-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            <Term
              word="Image maker"
              plain="The service that draws the photo from your description."
              example="Like choosing which photo lab prints your film roll."
            />
          </h3>
          <div className="mt-2.5 space-y-2">
            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-hairline bg-raised/60 p-3 hover:border-muted">
              <input
                type="radio"
                name="provider"
                checked={settings.provider === "kie"}
                onChange={() => void onChangeProvider("kie")}
                className="mt-1 accent-accent"
              />
              <span className="text-xs leading-relaxed">
                <span className="block font-semibold text-text">
                  Nano Banana Pro via Kie (recommended)
                </span>
                <span className="text-muted">
                  Uses your reference photo to keep the same pet or person across shots. About $0.12 per photo.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-hairline bg-raised/60 p-3 hover:border-muted">
              <input
                type="radio"
                name="provider"
                checked={settings.provider === "higgsfield"}
                onChange={() => void onChangeProvider("higgsfield")}
                className="mt-1 accent-accent"
              />
              <span className="text-xs leading-relaxed">
                <span className="block font-semibold text-text">Higgsfield Soul</span>
                <span className="text-muted">
                  Can&apos;t use a reference photo. Billed directly by Higgsfield (price not reported here).
                </span>
              </span>
            </label>
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            API keys
          </h3>
          <p className="mt-1 text-xs text-muted">
            Keys stay in your local <code>.env</code> file and are never shown on screen.
          </p>
          <div className="mt-3 space-y-3">
            {KEY_ROWS.map((row) => {
              const isSet = Boolean(settings.keys[row.name]);
              const draft = drafts[row.name] ?? "";
              return (
                <div
                  key={row.name}
                  className="rounded-xl border border-hairline bg-raised/40 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-text">{row.label}</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                        isSet
                          ? "bg-ok/15 text-ok"
                          : "bg-hairline text-muted"
                      }`}
                    >
                      {isSet ? (
                        <>
                          <Check className="h-3 w-3" /> set
                        </>
                      ) : (
                        "not set"
                      )}
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-muted">{row.purpose}</p>
                  <div className="mt-2 flex gap-2">
                    <input
                      type="password"
                      autoComplete="off"
                      value={draft}
                      onChange={(e) =>
                        setDrafts((prev) => ({ ...prev, [row.name]: e.target.value }))
                      }
                      placeholder={isSet ? "Paste a new key to replace…" : "Paste key…"}
                      aria-label={row.label}
                      className="flex-1 rounded-lg border border-hairline bg-ground px-2.5 py-1.5 text-xs text-text placeholder:text-muted"
                    />
                    <button
                      type="button"
                      disabled={saving === row.name || !draft.trim()}
                      onClick={() => void handleSave(row.name)}
                      className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-on-accent disabled:opacity-40"
                    >
                      Save
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
            <Term
              word="Skit Studio connection"
              plain="Lets Skit Studio ask this app to make still photos using the Look cards you picked here."
              example="Like leaving a side door unlocked so your video app can borrow your camera setup."
            />
          </h3>
          <div className="mt-2.5 rounded-xl border border-hairline bg-raised/40 p-3">
            <label className="flex cursor-pointer items-center justify-between gap-3">
              <span className="text-xs font-medium text-text">
                Share Look with Skit Studio (port 8785)
              </span>
              <input
                type="checkbox"
                checked={settings.local_api.enabled}
                onChange={(e) => void onToggleLocalApi(e.target.checked)}
                className="h-4 w-4 accent-accent"
              />
            </label>
            <p className="mt-1.5 text-xs text-muted">
              {settings.local_api.error ? (
                <span className="inline-flex items-center gap-1.5 text-danger">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  {settings.local_api.error}
                </span>
              ) : settings.local_api.running ? (
                <span className="text-ok">Running on 127.0.0.1:8785</span>
              ) : settings.local_api.enabled ? (
                "Enabled (starts when the desktop window opens)"
              ) : (
                "Turned off"
              )}
            </p>
          </div>
        </section>
      </aside>
    </div>
  );
}
