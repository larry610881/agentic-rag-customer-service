import type { AvatarRenderer } from "../types";
import { loadScript } from "./cdn-loader";

/* Global declarations for CDN-loaded libraries */
declare const PIXI: any;

const CDN_PIXI = "https://cdn.jsdelivr.net/npm/pixi.js@7.4.2/dist/pixi.min.js";
const CDN_LIVE2D_DISPLAY =
  "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js";

/**
 * Live2D avatar renderer.
 *
 * Loads Cubism Core (self-hosted), pixi.js, and pixi-live2d-display from CDN,
 * then renders a Live2D model with idle motion.
 */
export class Live2DRenderer implements AvatarRenderer {
  private app: any = null;
  private container: HTMLElement | null = null;

  constructor(
    private modelUrl: string,
    private apiBase: string,
  ) {}

  async mount(container: HTMLElement): Promise<void> {
    this.container = container;

    try {
      // Load Cubism Core first (must be available before pixi-live2d-display)
      await loadScript(`${this.apiBase}/static/libs/live2dcubismcore.min.js`);
      // Then load pixi.js
      await loadScript(CDN_PIXI);
      // Then load pixi-live2d-display (depends on both PIXI and CubismCore)
      await loadScript(CDN_LIVE2D_DISPLAY);

      // pixi-live2d-display registers itself on PIXI.live2d
      const Live2DModel = PIXI.live2d?.Live2DModel;
      if (!Live2DModel) {
        throw new Error("Live2DModel not found on PIXI.live2d");
      }

      // Create PIXI Application
      const width = container.clientWidth || 380;
      const height = container.clientHeight || 180;

      this.app = new PIXI.Application({
        width,
        height,
        backgroundAlpha: 0,
        autoStart: true,
      });
      container.appendChild(this.app.view as HTMLCanvasElement);

      // Style the canvas to fill container
      const canvas = this.app.view as HTMLCanvasElement;
      canvas.style.width = "100%";
      canvas.style.height = "100%";

      // Resolve model URL relative to backend origin
      const fullModelUrl = this.modelUrl.startsWith("http")
        ? this.modelUrl
        : `${this.apiBase}${this.modelUrl}`;

      // Load model
      const model = await Live2DModel.from(fullModelUrl, {
        autoInteract: false,
      });

      // Scale model to fit container
      const scaleX = width / model.width;
      const scaleY = height / model.height;
      const scale = Math.min(scaleX, scaleY) * 0.85;
      model.scale.set(scale);

      // Center model
      model.x = (width - model.width * scale) / 2;
      model.y = (height - model.height * scale) / 2;

      this.app.stage.addChild(model);

      // Start idle motion if available
      try {
        model.motion("Idle");
      } catch {
        // Model may not have Idle motion group — that's fine
      }
    } catch (err) {
      console.error("[widget] Live2D load failed:", err);
      this.showFallback(container);
    }
  }

  dispose(): void {
    if (this.app) {
      this.app.destroy(true, { children: true, texture: true, baseTexture: true });
      this.app = null;
    }
    this.container = null;
  }

  private showFallback(container: HTMLElement): void {
    // Clean any partial rendering
    container.innerHTML = "";

    const fallback = document.createElement("div");
    fallback.style.cssText =
      "display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:#f1f5f9;color:#64748b;font:14px sans-serif;border-radius:8px;";
    fallback.textContent = "Avatar \u8F09\u5165\u5931\u6557";
    container.appendChild(fallback);
  }
}
