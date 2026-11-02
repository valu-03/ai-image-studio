import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Settings } from "./Settings";
import type { SettingsPayload } from "../lib/api";

const baseSettings: SettingsPayload = {
  keys: {
    KIE_API_KEY: true,
    HIGGSFIELD_API_KEY_ID: false,
    HIGGSFIELD_API_KEY_SECRET: true,
    OPENROUTER_API_KEY: true,
  },
  provider: "kie",
  local_api: {
    enabled: true,
    running: true,
    error: "",
  },
};

describe("Settings sheet", () => {
  it("Settings never renders key values", () => {
    const html = renderToStaticMarkup(
      createElement(Settings, {
        open: true,
        settings: baseSettings,
        onClose: () => {},
        onSaveKey: async () => {},
        onChangeProvider: async () => {},
        onToggleLocalApi: async () => {},
      })
    );
    expect(html).toContain("set");
    expect(html).toContain("not set");
    expect(html).toContain('value=""');
    expect(html).not.toContain("sk-");
  });

  it("local api error text shown", () => {
    const html = renderToStaticMarkup(
      createElement(Settings, {
        open: true,
        settings: {
          ...baseSettings,
          local_api: {
            enabled: true,
            running: false,
            error: "Skit Studio connection couldn't start: port 8785 is in use",
          },
        },
        onClose: () => {},
        onSaveKey: async () => {},
        onChangeProvider: async () => {},
        onToggleLocalApi: async () => {},
      })
    );
    expect(html).toContain("Skit Studio connection couldn&#x27;t start: port 8785 is in use");
  });
});
