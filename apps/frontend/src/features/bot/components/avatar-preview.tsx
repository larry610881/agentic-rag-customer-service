import { useEffect, useRef } from "react";
import type { RendererHandle } from "@/features/chat/lib/live2d-renderer";

interface AvatarPreviewProps {
  avatarType: "none" | "live2d" | "vrm";
  avatarModelUrl: string;
}

/** Wait until element has non-zero dimensions (tab switch / layout settle) */
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

export function AvatarPreview({ avatarType, avatarModelUrl }: AvatarPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<RendererHandle | null>(null);

  useEffect(() => {
    if (!avatarType || avatarType === "none" || !avatarModelUrl) return;

    const container = containerRef.current;
    if (!container) return;

    const abortController = new AbortController();

    const init = async () => {
      // Wait until container is visible and has dimensions
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
        console.warn("[AvatarPreview] Failed to initialize renderer:", err);
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

  if (!avatarType || avatarType === "none" || !avatarModelUrl) return null;

  return (
    <div
      data-testid="avatar-preview"
      ref={containerRef}
      className="h-[200px] w-[200px] shrink-0 overflow-hidden rounded-lg"
    />
  );
}
