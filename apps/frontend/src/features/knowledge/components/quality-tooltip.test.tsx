import { beforeAll, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QualityTooltip } from "./quality-tooltip";

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("QualityTooltip", () => {
  it("renders children without tooltip when no issues", () => {
    render(
      <QualityTooltip issues={[]}>
        <span>Score</span>
      </QualityTooltip>,
    );
    expect(screen.getByText("Score")).toBeInTheDocument();
  });

  it("shows tooltip with suggestions on hover when issues present", async () => {
    const user = userEvent.setup();
    render(
      <QualityTooltip issues={["too_short"]}>
        <button>Score</button>
      </QualityTooltip>,
    );

    await user.hover(screen.getByText("Score"));

    const tooltip = await screen.findByTestId("quality-tooltip");
    expect(tooltip).toHaveTextContent("chunk_size");
  });

  it("shows multiple suggestions for multiple issues", async () => {
    const user = userEvent.setup();
    render(
      <QualityTooltip issues={["too_short", "mid_sentence_break"]}>
        <button>Score</button>
      </QualityTooltip>,
    );

    await user.hover(screen.getByText("Score"));

    const tooltip = await screen.findByTestId("quality-tooltip");
    expect(tooltip).toHaveTextContent("chunk_size");
    expect(tooltip).toHaveTextContent("chunk_overlap");
  });
});
