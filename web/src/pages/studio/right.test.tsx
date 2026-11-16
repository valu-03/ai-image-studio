import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PhotoPanel } from "./PhotoPanel";
import { RealCheck } from "./RealCheck";
import { RecentStrip } from "./RecentStrip";
import type { PriceEstimate, RecentPhoto } from "../../lib/api";

const samplePrice: PriceEstimate = {
  image: { credits: 24, usd: 0.12, confidence: "estimated" },
  check: { usd: 0.01, confidence: "estimated" },
  label: "about $0.12",
};

describe("Right column: PhotoPanel, RealCheck, RecentStrip", () => {
  it('zero giveaways never says "real"', () => {
    const html = renderToStaticMarkup(
      createElement(RealCheck, {
        giveaways: [],
        checkError: "",
        price: samplePrice,
        pending: false,
        canFix: true,
        onFix: () => {},
      })
    );
    const textOnly = html.replace(/<[^>]+>/g, " ");
    expect(textOnly).not.toMatch(/looks real|undetectable|passes/i);
    expect(textOnly).toContain("Nothing obvious gives it away");
  });

  it("check error shows reason and keeps photo", () => {
    const html = renderToStaticMarkup(
      createElement(PhotoPanel, {
        job: {
          state: "done",
          stage: "Done",
          error: "",
          file_url: "/files/cat-1.png",
          history_id: "h-1",
          giveaways: null,
          check_error: "OPENROUTER_API_KEY is not set in .env",
        },
        selectedRecent: null,
        recentCheck: null,
        price: samplePrice,
        pending: false,
        onFix: () => {},
        onCheckRecent: () => {},
      })
    );
    expect(html).toContain('/files/cat-1.png');
    expect(html).toContain("The picture check couldn&#x27;t run:");
    expect(html).toContain("OPENROUTER_API_KEY is not set in .env");
  });

  it("fix button shows price and disables while pending to prevent double submission", () => {
    const readyHtml = renderToStaticMarkup(
      createElement(RealCheck, {
        giveaways: [
          {
            key: "studio_light",
            label: "Light too perfect",
            plain: "The light is soft and flattering everywhere.",
            where: "on the sofa",
            fixable: true,
          },
        ],
        checkError: "",
        price: samplePrice,
        pending: false,
        canFix: true,
        onFix: () => {},
      })
    );
    expect(readyHtml).toContain("Fix · ~$0.13");

    const pendingHtml = renderToStaticMarkup(
      createElement(RealCheck, {
        giveaways: [
          {
            key: "studio_light",
            label: "Light too perfect",
            plain: "The light is soft and flattering everywhere.",
            where: "on the sofa",
            fixable: true,
          },
        ],
        checkError: "",
        price: samplePrice,
        pending: true,
        canFix: true,
        onFix: () => {},
      })
    );
    expect(pendingHtml).toContain("disabled");
  });

  it("api photo shows check button, page photo does not", () => {
    const apiPhoto: RecentPhoto = {
      history_id: "h-api",
      file_url: "/files/api-1.png",
      note: "Local API",
      rating: null,
      source: "api",
    };
    const pagePhoto: RecentPhoto = {
      history_id: "h-page",
      file_url: "/files/page-1.png",
      note: "Studio",
      rating: null,
      source: "page",
    };

    const apiHtml = renderToStaticMarkup(
      createElement(PhotoPanel, {
        job: null,
        selectedRecent: apiPhoto,
        recentCheck: null,
        price: samplePrice,
        pending: false,
        onFix: () => {},
        onCheckRecent: () => {},
      })
    );
    expect(apiHtml).toContain("Check this photo · ~$0.01");

    const pageHtml = renderToStaticMarkup(
      createElement(PhotoPanel, {
        job: null,
        selectedRecent: pagePhoto,
        recentCheck: null,
        price: samplePrice,
        pending: false,
        onFix: () => {},
        onCheckRecent: () => {},
      })
    );
    expect(pageHtml).not.toContain("Check this photo");
  });

  it("thumb toggles aria-pressed", () => {
    const items: RecentPhoto[] = [
      {
        history_id: "h-up",
        file_url: "/files/up.png",
        note: "Studio",
        rating: 5,
        source: "page",
      },
      {
        history_id: "h-down",
        file_url: "/files/down.png",
        note: "Local API",
        rating: 1,
        source: "api",
      },
    ];
    const html = renderToStaticMarkup(
      createElement(RecentStrip, {
        items,
        activeHistoryId: "h-up",
        onSelect: () => {},
        onRate: () => {},
      })
    );
    expect(html).toContain('aria-label="Thumb up" aria-pressed="true"');
    expect(html).toContain('aria-label="Thumb down" aria-pressed="true"');
    expect(html).toContain(">API<");
  });
});
