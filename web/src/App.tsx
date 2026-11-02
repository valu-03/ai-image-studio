import { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import {
  getSettings,
  setKey,
  setSettings,
  type KeyName,
  type SettingsPayload,
} from "./lib/api";
import { Settings } from "./pages/Settings";

export function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettingsState] = useState<SettingsPayload | null>(null);

  useEffect(() => {
    void getSettings()
      .then(setSettingsState)
      .catch(() => {});
  }, []);

  const handleSaveKey = async (name: KeyName, value: string) => {
    await setKey(name, value);
    const updated = await getSettings();
    setSettingsState(updated);
  };

  const handleChangeProvider = async (provider: "kie" | "higgsfield") => {
    const updated = await setSettings({ provider });
    setSettingsState(updated);
  };

  const handleToggleLocalApi = async (enabled: boolean) => {
    const updated = await setSettings({ local_api_enabled: enabled });
    setSettingsState(updated);
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-ground text-text">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-hairline bg-surface px-5">
        <div className="flex items-center gap-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden="true" />
          <h1 className="text-sm font-semibold tracking-tight text-text">
            AI Image Studio
          </h1>
        </div>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          aria-label="Open settings"
          className="inline-flex items-center gap-1.5 rounded-lg border border-hairline bg-raised px-2.5 py-1.5 text-xs font-medium text-text hover:border-muted"
        >
          <SettingsIcon className="h-3.5 w-3.5 text-muted" />
          Settings
        </button>
      </header>

      <main className="flex min-h-0 flex-1 overflow-hidden">
        <section
          aria-label="Photo controls"
          className="flex h-full w-[min(440px,36%)] shrink-0 flex-col justify-between border-r border-hairline bg-surface p-4"
        />
        <section
          aria-label="Photo and check"
          className="flex min-w-0 flex-1 flex-col bg-photo-ground"
        />
      </main>

      <Settings
        open={settingsOpen}
        settings={settings}
        onClose={() => setSettingsOpen(false)}
        onSaveKey={handleSaveKey}
        onChangeProvider={handleChangeProvider}
        onToggleLocalApi={handleToggleLocalApi}
      />
    </div>
  );
}
