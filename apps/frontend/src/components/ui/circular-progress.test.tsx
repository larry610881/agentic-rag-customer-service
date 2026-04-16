import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { CircularProgress } from "@/components/ui/circular-progress";

describe("CircularProgress", () => {
  it("renders 0% with correct aria attributes", () => {
    render(<CircularProgress value={0} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "0");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveTextContent("0%");
  });

  it("renders 50% value and label", () => {
    render(<CircularProgress value={50} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "50");
    expect(bar).toHaveTextContent("50%");
  });

  it("clamps value above 100", () => {
    render(<CircularProgress value={150} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
    expect(bar).toHaveTextContent("100%");
  });

  it("clamps negative value to 0", () => {
    render(<CircularProgress value={-10} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "0");
  });

  it("shows success icon when status='success'", () => {
    render(<CircularProgress value={100} status="success" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("data-status", "success");
    expect(screen.getByLabelText("上傳成功")).toBeInTheDocument();
    // 沒有百分比文字
    expect(bar).not.toHaveTextContent("%");
  });

  it("shows error icon when status='error'", () => {
    render(<CircularProgress value={42} status="error" />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("data-status", "error");
    expect(screen.getByLabelText("上傳失敗")).toBeInTheDocument();
  });

  it("forwards aria-label to progressbar", () => {
    render(<CircularProgress value={30} ariaLabel="上傳中：spec.pdf" />);
    expect(
      screen.getByRole("progressbar", { name: "上傳中：spec.pdf" }),
    ).toBeInTheDocument();
  });

  it("applies size prop to the container", () => {
    render(<CircularProgress value={10} size={96} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveStyle({ width: "96px", height: "96px" });
  });
});
