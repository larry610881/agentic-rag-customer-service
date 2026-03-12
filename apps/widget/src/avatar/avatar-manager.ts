import type { AvatarRenderer, WidgetConfig } from "../types";

/**
 * Dynamically loads the appropriate avatar renderer based on config.
 * Returns null if avatar_type is "none" or missing.
 */
export async function loadAvatar(
  config: WidgetConfig,
): Promise<AvatarRenderer | null> {
  if (!config.avatar_type || config.avatar_type === "none") {
    return null;
  }

  const modelUrl = config.avatar_model_url || "";

  if (config.avatar_type === "live2d") {
    const { Live2DRenderer } = await import("./live2d-renderer");
    return new Live2DRenderer(modelUrl);
  }

  if (config.avatar_type === "vrm") {
    const { VRMRenderer } = await import("./vrm-renderer");
    return new VRMRenderer(modelUrl);
  }

  console.warn(`[widget] Unknown avatar_type: ${config.avatar_type}`);
  return null;
}
