import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AvatarPreview } from "./avatar-preview";

const mockLive2DDispose = vi.fn();
const mockVRMDispose = vi.fn();

vi.mock("@/features/chat/lib/live2d-renderer", () => ({
  createLive2DRenderer: vi.fn().mockResolvedValue({ dispose: mockLive2DDispose }),
}));

vi.mock("@/features/chat/lib/vrm-renderer", () => ({
  createVRMRenderer: vi.fn().mockResolvedValue({ dispose: mockVRMDispose }),
}));

// Mock ResizeObserver — jsdom doesn't support it.
// Immediately call the callback with non-zero dimensions to simulate visible container.
class MockResizeObserver {
  private callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  observe(target: Element) {
    // Simulate non-zero layout on next microtask
    Promise.resolve().then(() => {
      this.callback(
        [{ contentRect: { width: 200, height: 200 } } as ResizeObserverEntry],
        this,
      );
    });
  }
  unobserve() {}
  disconnect() {}
}

vi.stubGlobal("ResizeObserver", MockResizeObserver);

describe("AvatarPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nothing when avatarType is none", () => {
    const { container } = render(
      <AvatarPreview avatarType="none" avatarModelUrl="" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing when avatarModelUrl is empty", () => {
    const { container } = render(
      <AvatarPreview avatarType="live2d" avatarModelUrl="" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("calls createLive2DRenderer for live2d type", async () => {
    const { createLive2DRenderer } = await import(
      "@/features/chat/lib/live2d-renderer"
    );

    render(
      <AvatarPreview
        avatarType="live2d"
        avatarModelUrl="https://example.com/model.json"
      />,
    );

    expect(screen.getByTestId("avatar-preview")).toBeInTheDocument();

    await vi.waitFor(() => {
      expect(createLive2DRenderer).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        "https://example.com/model.json",
      );
    });
  });

  it("calls createVRMRenderer for vrm type", async () => {
    const { createVRMRenderer } = await import(
      "@/features/chat/lib/vrm-renderer"
    );

    render(
      <AvatarPreview
        avatarType="vrm"
        avatarModelUrl="https://example.com/model.vrm"
      />,
    );

    expect(screen.getByTestId("avatar-preview")).toBeInTheDocument();

    await vi.waitFor(() => {
      expect(createVRMRenderer).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        "https://example.com/model.vrm",
      );
    });
  });

  it("disposes old renderer when switching avatar type", async () => {
    const { createLive2DRenderer } = await import(
      "@/features/chat/lib/live2d-renderer"
    );

    const { rerender } = render(
      <AvatarPreview
        avatarType="live2d"
        avatarModelUrl="https://example.com/model.json"
      />,
    );

    await vi.waitFor(() => {
      expect(createLive2DRenderer).toHaveBeenCalled();
    });

    // Switch to VRM — should dispose old renderer
    rerender(
      <AvatarPreview
        avatarType="vrm"
        avatarModelUrl="https://example.com/model.vrm"
      />,
    );

    await vi.waitFor(() => {
      expect(mockLive2DDispose).toHaveBeenCalled();
    });
  });
});
