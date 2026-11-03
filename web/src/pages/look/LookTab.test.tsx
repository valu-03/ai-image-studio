import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { App } from "../../App";
import { LOOK_SUB_BUILDERS, LookTab } from "./LookTab";

describe("Compose & Look tabs", () => {
  it("App renders both Compose and Look tabs plus the 5 Compose spec sub-tabs (Purpose, Subject, Scene, Identity, More)", () => {
    const html = renderToStaticMarkup(createElement(App));
    expect(html).toContain('data-testid="main-tab-compose"');
    expect(html).toContain('data-testid="main-tab-look"');
    for (const sub of ["purpose", "subject", "scene", "identity", "more"]) {
      expect(html).toContain(`data-testid="compose-subtab-${sub}"`);
    }
    expect(html).toContain("Subject");
    expect(html).toContain("Wardrobe");
    expect(html).toContain("Action");
    expect(html).toContain("Posing");
    expect(html).toContain("Mood");
    expect(html).toContain('data-testid="prompt-panel"');
    expect(html).toContain('data-testid="copy-prompt-button"');
    expect(html).not.toContain("RECENT PHOTOS");
  });

  it("LookTab exposes all 8 Look sub-builders as tabs and applies to Compose", () => {
    expect(LOOK_SUB_BUILDERS.map((b) => b.id)).toEqual([
      "lighting",
      "composition",
      "camera",
      "color",
      "posing",
      "style",
      "capture",
      "evidence",
    ]);

    const html = renderToStaticMarkup(
      createElement(LookTab, {
        look: {
          kind: "animal",
          cards: {},
          touched: [],
          overrides: { lighting: "soft window light from the left" },
        },
        kind: "animal",
        onLookUpdated: () => {},
        onGoToCompose: () => {},
      })
    );

    for (const sub of LOOK_SUB_BUILDERS) {
      expect(html).toContain(`data-testid="look-subtab-${sub.id}"`);
    }
    expect(html).toContain("Apply to Compose");
    expect(html).toContain("Back to Compose tab");
    expect(html).toContain("soft window light from the left");
  });
});
