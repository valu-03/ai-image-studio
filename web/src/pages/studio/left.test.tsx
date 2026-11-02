import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MakeButton } from "./MakeButton";
import { Reference, validateReferenceCandidate } from "./Reference";
import { LookCards } from "./LookCards";
import type { LookCard, PriceEstimate } from "../../lib/api";

const samplePrice: PriceEstimate = {
  image: { credits: 24, usd: 0.12, confidence: "estimated" },
  check: { usd: 0.01, confidence: "estimated" },
  label: "about $0.12",
};

const sampleCards: LookCard[] = [
  {
    id: "light",
    title: "Light",
    plain: "Where the room or outdoor light falls from.",
    example: "Like a table lamp on in the corner while day fades outside.",
    options: [
      {
        key: "practical_mixed",
        label: "Everyday mixed room light",
        plain: "A real lamp in the room mixed with window light and dull corners.",
        example: "Like a living room at 5 pm with one floor lamp switched on.",
        look: {},
      },
    ],
    advanced_part: "lighting",
  },
  {
    id: "camera",
    title: "Camera",
    plain: "What kind of camera took the shot.",
    example: "Like grabbing your phone out of your pocket.",
    options: [
      {
        key: "plain_phone_lens",
        label: "Everyday phone camera",
        plain: "Normal phone lens with almost everything in focus.",
        example: "Like a quick snapshot sent in a family chat.",
        look: {},
      },
    ],
    advanced_part: "camera",
  },
  {
    id: "framing",
    title: "Framing",
    plain: "Where the subject sits inside the rectangle.",
    example: "Like catching a dog slightly off to one side as it turns.",
    options: [
      {
        key: "off_centre_candid",
        label: "Off-centre, caught mid-moment",
        plain: "Not dead-centre; framed like a real person aimed quickly.",
        example: "Like snapping before your cat walks out of the room.",
        look: {},
      },
    ],
    advanced_part: "composition",
  },
  {
    id: "colour",
    title: "Colour",
    plain: "How warm, cool or muted the colours feel.",
    example: "Like honest daylight vs a warm evening bulb.",
    options: [
      {
        key: "muted_natural",
        label: "True-to-life, unboosted colour",
        plain: "Calm everyday colour without extra saturation.",
        example: "Like what your eyes see in an ordinary room.",
        look: {},
      },
    ],
    advanced_part: "color",
  },
  {
    id: "pose",
    title: "Pose",
    plain: "What the pet or person is doing with their body and eyes.",
    example: "Like looking at a toy instead of staring into the camera.",
    options: [
      {
        key: "mid_moment",
        label: "Doing their own thing",
        plain: "Not posing for the lens; caught in the middle of an action.",
        example: "Like a cat sniffing a mug on the table.",
        look: {},
      },
    ],
    advanced_part: "posing",
  },
  {
    id: "details",
    title: "Lived-in details",
    plain: "Tiny textures that prove a real camera was there.",
    example: "Like stray hairs, creases in a sleeve, or a scuffed baseboard.",
    options: [
      {
        key: "whiskers_and_nose",
        label: "Clumped fur & stray whiskers",
        plain: "Slightly uneven coat with individual hairs catching light.",
        example: "Like a cat right after waking up from a nap.",
        look: {},
      },
    ],
    advanced_part: "evidence",
  },
];

describe("Left column studio controls", () => {
  it("MakeButton disabled while pending", () => {
    const html = renderToStaticMarkup(
      createElement(MakeButton, {
        pending: true,
        textEmpty: false,
        keyMissing: false,
        price: samplePrice,
        onMake: () => {},
      })
    );
    expect(html).toContain("disabled");
    expect(html).toContain("Making photo");
  });

  it("MakeButton re-enables after error", () => {
    const html = renderToStaticMarkup(
      createElement(MakeButton, {
        pending: false,
        textEmpty: false,
        keyMissing: false,
        price: samplePrice,
        onMake: () => {},
      })
    );
    expect(html).not.toContain('disabled=""');
    expect(html).toContain("Make photo");
  });

  it("MakeButton shows price incl. check", () => {
    const html = renderToStaticMarkup(
      createElement(MakeButton, {
        pending: false,
        textEmpty: false,
        keyMissing: false,
        price: samplePrice,
        onMake: () => {},
      })
    );
    expect(html).toContain("0.13");
  });

  it("Soul disables reference with reason", () => {
    const html = renderToStaticMarkup(
      createElement(Reference, {
        provider: "higgsfield",
        reference: null,
        onChange: () => {},
      })
    );
    expect(html).toContain("Unavailable with Soul");
    expect(html).toContain("can&#x27;t use a reference photo");
  });

  it("reference over 20 MB rejected without request", () => {
    const err = validateReferenceCandidate({
      name: "huge.png",
      size: 21 * 1024 * 1024,
      type: "image/png",
    });
    expect(err).toContain("20 MB");
  });

  it("six cards render with plain line", () => {
    const html = renderToStaticMarkup(
      createElement(LookCards, {
        cards: sampleCards,
        selected: {
          light: "practical_mixed",
          camera: "plain_phone_lens",
          framing: "off_centre_candid",
          colour: "muted_natural",
          pose: "mid_moment",
          details: "whiskers_and_nose",
        },
        touched: ["light"],
        onSelectOption: () => {},
      })
    );
    for (const card of sampleCards) {
      expect(html).toContain(`data-testid="look-card-${card.id}"`);
      expect(html).toContain(card.options[0].plain);
    }
  });
});
