import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/use-chat-store";
import type { RendererHandle } from "@/features/chat/lib/live2d-renderer";

export function AvatarPanel() {
  const avatarType = useChatStore((s) => s.avatarType);
  const avatarModelUrl = useChatStore((s) => s.avatarModelUrl);
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<RendererHandle | null>(null);

  useEffect(() => {
    if (!avatarType || avatarType === "none" || !avatarModelUrl) return;

    const container = containerRef.current;
    if (!container) return;

    let cancelled = false;

    const init = async () => {
      try {
        let handle: RendererHandle;
        if (avatarType === "live2d") {
          const { createLive2DRenderer } = await import(
            "@/features/chat/lib/live2d-renderer"
          );
          handle = await createLive2DRenderer(container, avatarModelUrl);
        } else {
          const { createVRMRenderer } = await import(
            "@/features/chat/lib/vrm-renderer"
          );
          handle = await createVRMRenderer(container, avatarModelUrl);
        }

        if (cancelled) {
          handle.dispose();
          return;
        }
        rendererRef.current = handle;
      } catch (err) {
        console.warn("[AvatarPanel] Failed to initialize renderer:", err);
      }
    };

    init();

    return () => {
      cancelled = true;
      rendererRef.current?.dispose();
      rendererRef.current = null;
      while (container.firstChild) {
        container.removeChild(container.firstChild);
      }
    };
  }, [avatarType, avatarModelUrl]);

  if (!avatarType || avatarType === "none") return null;

  return (
    <div
      data-testid="avatar-panel"
      ref={containerRef}
      className="h-[200px] w-full overflow-hidden rounded-lg bg-muted/30"
    />
  );
}
