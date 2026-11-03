import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { App } from "../../App";
import { LOOK_SUB_BUILDERS, LookTab } from "./LookTab";

describe("Compose & Look tabs", () => {
  it("App renders both Compose and Look tabs in the header", () => {
    const html = renderToStaticMarkup(createElement(App));
    expect(html).toContain('data-testid="main-tab-compose"');
    expect(html).toContain('data-testid="main-tab-look"');
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
