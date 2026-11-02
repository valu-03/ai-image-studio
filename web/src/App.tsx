import { useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { useStudio } from "./lib/studio";
import { Settings } from "./pages/Settings";
import { Describe } from "./pages/studio/Describe";
import { Reference } from "./pages/studio/Reference";
import { LookCards } from "./pages/studio/LookCards";
import { MakeButton } from "./pages/studio/MakeButton";

export function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const studio = useStudio();

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
          className="flex h-full w-[min(440px,36%)] shrink-0 flex-col justify-between overflow-y-auto border-r border-hairline bg-surface p-4"
        >
          <div className="space-y-3">
            <Describe
              text={studio.text}
              kind={studio.kind}
              onChange={studio.setText}
            />
            <Reference
              provider={studio.provider}
              reference={studio.reference}
              onChange={studio.setReference}
            />
            <LookCards
              cards={studio.cards}
              selected={studio.look.cards}
              touched={studio.look.touched}
              onSelectOption={(cardId, optionKey) =>
                void studio.selectCardOption(cardId, optionKey)
              }
            />
          </div>

          <div className="pt-2">
            <MakeButton
              pending={studio.pending}
              textEmpty={!studio.text.trim()}
              keyMissing={studio.keyMissing}
              price={studio.price}
              onMake={() => void studio.make()}
              onOpenSettings={() => setSettingsOpen(true)}
            />
          </div>
        </section>

        <section
          aria-label="Photo and check"
          className="flex min-w-0 flex-1 flex-col bg-photo-ground"
        />
      </main>

      <Settings
        open={settingsOpen}
        settings={studio.settings}
        onClose={() => setSettingsOpen(false)}
        onSaveKey={studio.saveApiKey}
        onChangeProvider={studio.changeProvider}
        onToggleLocalApi={studio.toggleLocalApi}
      />
    </div>
  );
}
