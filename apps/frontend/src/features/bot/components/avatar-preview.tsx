import { useEffect, useRef } from "react";
import type { RendererHandle } from "@/features/chat/lib/live2d-renderer";

interface AvatarPreviewProps {
  avatarType: "none" | "live2d" | "vrm";
  avatarModelUrl: string;
}

export function AvatarPreview({ avatarType, avatarModelUrl }: AvatarPreviewProps) {
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
        console.warn("[AvatarPreview] Failed to initialize renderer:", err);
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

  if (!avatarType || avatarType === "none" || !avatarModelUrl) return null;

  return (
    <div
      data-testid="avatar-preview"
      ref={containerRef}
      className="h-[200px] w-full overflow-hidden rounded-lg border bg-muted/30"
    />
  );
}
