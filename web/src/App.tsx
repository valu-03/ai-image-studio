import { useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import type { LookPart } from "./lib/api";
import { useStudio } from "./lib/studio";
import { LookTab } from "./pages/look/LookTab";
import { Settings } from "./pages/Settings";
import { ComposeEditor } from "./pages/studio/ComposeEditor";
import { MakeButton } from "./pages/studio/MakeButton";
import { PhotoPanel } from "./pages/studio/PhotoPanel";
import { PromptPanel } from "./pages/studio/PromptPanel";

export type MainTab = "compose" | "look";

export function App() {
  const initialTab =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("tab") === "look"
      ? "look"
      : "compose";
  const [activeTab, setActiveTab] = useState<MainTab>(initialTab);
  const [lookSubPart, setLookSubPart] = useState<LookPart>("lighting");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const studio = useStudio();

  const overrideCount = Object.keys(studio.look.overrides ?? {}).length;

  const openLookPart = (part: LookPart = "lighting") => {
    setLookSubPart(part);
    setActiveTab("look");
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-ground text-text">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-hairline bg-surface px-5">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <svg
              viewBox="0 0 256 256"
              className="h-5 w-5 shrink-0 text-accent"
              fill="currentColor"
              fillRule="evenodd"
              aria-hidden="true"
            >
              <path d="M 60.00 24.00 H 100.00 V 50.00 H 65.00 A 15.00 15.00 0 0 0 50.00 65.00 V 100.00 H 24.00 V 60.00 A 36.00 36.00 0 0 1 60.00 24.00 Z M 156.00 24.00 H 196.00 A 36.00 36.00 0 0 1 232.00 60.00 V 100.00 H 206.00 V 65.00 A 15.00 15.00 0 0 0 191.00 50.00 H 156.00 V 24.00 Z M 206.00 156.00 H 232.00 V 196.00 A 36.00 36.00 0 0 1 196.00 232.00 H 156.00 V 206.00 H 191.00 A 15.00 15.00 0 0 0 206.00 191.00 V 156.00 Z M 24.00 156.00 H 50.00 V 191.00 A 15.00 15.00 0 0 0 65.00 206.00 H 100.00 V 232.00 H 60.00 A 36.00 36.00 0 0 1 24.00 196.00 V 156.00 Z M 113.50 108.00 A 34.50 34.50 0 1 1 182.50 108.00 A 34.50 34.50 0 1 1 113.50 108.00 Z" />
            </svg>
            <h1 className="text-sm font-semibold tracking-tight text-text">
              AI Image Studio
            </h1>
          </div>

          <nav
            role="tablist"
            aria-label="Main sections"
            className="flex items-center gap-1 rounded-xl border border-hairline bg-ground p-1"
          >
            <button
              role="tab"
              type="button"
              aria-selected={activeTab === "compose"}
              data-testid="main-tab-compose"
              onClick={() => setActiveTab("compose")}
              className={`rounded-lg px-3.5 py-1 text-xs font-semibold transition-colors ${
                activeTab === "compose"
                  ? "bg-raised text-text shadow-sm"
                  : "text-muted hover:text-text"
              }`}
            >
              Compose
            </button>
            <button
              role="tab"
              type="button"
              aria-selected={activeTab === "look"}
              data-testid="main-tab-look"
              onClick={() => setActiveTab("look")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1 text-xs font-semibold transition-colors ${
                activeTab === "look"
                  ? "bg-raised text-text shadow-sm"
                  : "text-muted hover:text-text"
              }`}
            >
              <span>Look</span>
              {overrideCount > 0 && (
                <span className="rounded-full bg-accent px-1.5 py-0.2 text-[10px] font-bold text-on-accent">
                  {overrideCount}
                </span>
              )}
            </button>
          </nav>
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

      {activeTab === "compose" ? (
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <section
            aria-label="Photo controls"
            className="flex h-full w-[min(460px,38%)] shrink-0 flex-col justify-between overflow-hidden border-r border-hairline bg-surface p-4"
          >
            <ComposeEditor
              form={studio.composeForm}
              options={studio.composeOptions}
              preview={studio.composePreview}
              kind={studio.kind}
              provider={studio.provider}
              reference={studio.reference}
              cards={studio.cards}
              selectedCards={studio.look.cards}
              touchedCards={studio.look.touched}
              overrides={studio.look.overrides}
              onUpdateField={studio.updateComposeField}
              onReferenceChange={studio.setReference}
              onSelectCardOption={(cardId, optionKey) =>
                void studio.selectCardOption(cardId, optionKey)
              }
              onOpenLookTab={openLookPart}
            />

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
          >
            <PhotoPanel
              job={studio.job}
              selectedRecent={studio.selectedRecent}
              recentCheck={studio.recentCheck}
              price={studio.price}
              pending={studio.pending}
              onFix={(key) => void studio.fix(key)}
              onCheckRecent={(historyId) => void studio.runCheckOnRecent(historyId)}
            />
            <PromptPanel
              form={studio.composeForm}
              preview={studio.composePreview}
              onUpdateField={studio.updateComposeField}
            />
          </section>
        </main>
      ) : (
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <LookTab
            look={studio.look}
            kind={studio.kind}
            initialPart={lookSubPart}
            onLookUpdated={studio.setLook}
            onGoToCompose={() => setActiveTab("compose")}
          />
        </main>
      )}

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
