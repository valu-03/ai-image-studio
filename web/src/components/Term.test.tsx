import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Term, nextTermOpenState } from "./Term";

describe("Term popover", () => {
  it("renders a dotted-underline button with aria-expanded=false when closed", () => {
    const html = renderToStaticMarkup(
      createElement(Term, {
        word: "Aperture",
        plain: "How wide the lens opens to let light in.",
        example: "Like the pupil of your eye widening in a dim room.",
      })
    );
    expect(html).toContain("Aperture");
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain("In plain words:");
  });

  it("renders the Feynman plain explanation and example when open", () => {
    const html = renderToStaticMarkup(
      createElement(Term, {
        word: "Aperture",
        plain: "How wide the lens opens to let light in.",
        example: "Like the pupil of your eye widening in a dim room.",
        defaultOpen: true,
      })
    );
    expect(html).toContain('aria-expanded="true"');
    expect(html).toContain("In plain words:");
    expect(html).toContain("How wide the lens opens to let light in.");
    expect(html).toContain("Like:");
    expect(html).toContain("Like the pupil of your eye widening in a dim room.");
  });

  it("Term opens and closes with keyboard", () => {
    let open = false;
    open = nextTermOpenState(open, "Enter");
    expect(open).toBe(true);
    open = nextTermOpenState(open, "Escape");
    expect(open).toBe(false);
    open = nextTermOpenState(open, " ");
    expect(open).toBe(true);
    open = nextTermOpenState(open, "Escape");
    expect(open).toBe(false);
  });
});
