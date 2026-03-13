import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/use-chat-store";
import type { RendererHandle } from "@/features/chat/lib/live2d-renderer";

/** Wait until element has non-zero dimensions (layout settle) */
function waitForLayout(el: HTMLElement, signal: AbortSignal): Promise<boolean> {
  if (el.clientWidth > 0 && el.clientHeight > 0) return Promise.resolve(true);
  return new Promise((resolve) => {
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          ro.disconnect();
          resolve(true);
          return;
        }
      }
    });
    signal.addEventListener("abort", () => {
      ro.disconnect();
      resolve(false);
    });
    ro.observe(el);
  });
}

export function AvatarPanel() {
  const avatarType = useChatStore((s) => s.avatarType);
  const avatarModelUrl = useChatStore((s) => s.avatarModelUrl);
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<RendererHandle | null>(null);

  useEffect(() => {
    if (!avatarType || avatarType === "none" || !avatarModelUrl) return;

    const container = containerRef.current;
    if (!container) return;

    const abortController = new AbortController();

    const init = async () => {
      const ready = await waitForLayout(container, abortController.signal);
      if (!ready || abortController.signal.aborted) return;

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

        if (abortController.signal.aborted) {
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
      abortController.abort();
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
