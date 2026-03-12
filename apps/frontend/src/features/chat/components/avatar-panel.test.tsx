import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { useChatStore } from "@/stores/use-chat-store";

// Mock the renderer modules
const mockDispose = vi.fn();
const mockCreateLive2D = vi.fn().mockResolvedValue({ dispose: mockDispose });
const mockCreateVRM = vi.fn().mockResolvedValue({ dispose: mockDispose });

vi.mock("@/features/chat/lib/live2d-renderer", () => ({
  createLive2DRenderer: mockCreateLive2D,
}));

vi.mock("@/features/chat/lib/vrm-renderer", () => ({
  createVRMRenderer: mockCreateVRM,
}));

// Import after mocks
import { AvatarPanel } from "./avatar-panel";

describe("AvatarPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.setState({
      avatarType: null,
      avatarModelUrl: null,
    });
  });

  afterEach(cleanup);

  it('avatarType 為 "none" 時不渲染任何內容', () => {
    useChatStore.setState({ avatarType: "none" });
    const { container } = render(<AvatarPanel />);
    expect(container.innerHTML).toBe("");
  });

  it("avatarType 為 null 時不渲染任何內容", () => {
    useChatStore.setState({ avatarType: null });
    const { container } = render(<AvatarPanel />);
    expect(container.innerHTML).toBe("");
  });

  it('avatarType 為 "live2d" 時渲染 avatar 容器', () => {
    useChatStore.setState({
      avatarType: "live2d",
      avatarModelUrl: "/static/models/live2d/hiyori/hiyori_free_t08.model3.json",
    });
    render(<AvatarPanel />);
    expect(screen.getByTestId("avatar-panel")).toBeInTheDocument();
  });

  it('avatarType 為 "vrm" 時渲染 avatar 容器', () => {
    useChatStore.setState({
      avatarType: "vrm",
      avatarModelUrl: "/static/models/vrm/default.vrm",
    });
    render(<AvatarPanel />);
    expect(screen.getByTestId("avatar-panel")).toBeInTheDocument();
  });

  it("unmount 時呼叫 renderer dispose", async () => {
    useChatStore.setState({
      avatarType: "live2d",
      avatarModelUrl: "/test.model3.json",
    });
    const { unmount } = render(<AvatarPanel />);
    // Wait for the async renderer to initialize
    await vi.waitFor(() => {
      expect(mockCreateLive2D).toHaveBeenCalled();
    });
    unmount();
    expect(mockDispose).toHaveBeenCalled();
  });
});
