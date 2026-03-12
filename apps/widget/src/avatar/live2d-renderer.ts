import type { AvatarRenderer } from "../types";

/**
 * Live2D avatar renderer stub.
 *
 * Full implementation requires:
 *   - pixi.js (v7)
 *   - pixi-live2d-display
 *   - Cubism SDK Core (proprietary, must be downloaded separately)
 *
 * This scaffold shows a placeholder canvas with loading state.
 * Replace with actual PixiJS + Live2D integration when model files are available.
 */
export class Live2DRenderer implements AvatarRenderer {
  private canvas: HTMLCanvasElement | null = null;
  private animFrame: number | null = null;

  constructor(private modelUrl: string) {}

  async mount(container: HTMLElement): Promise<void> {
    this.canvas = document.createElement("canvas");
    this.canvas.width = container.clientWidth || 380;
    this.canvas.height = 200;
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    container.appendChild(this.canvas);

    const ctx = this.canvas.getContext("2d");
    if (!ctx) return;

    // Placeholder: draw loading indicator
    let frame = 0;
    const draw = () => {
      if (!ctx || !this.canvas) return;
      const w = this.canvas.width;
      const h = this.canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = "#f1f5f9";
      ctx.fillRect(0, 0, w, h);

      // Breathing circle animation (simulates idle)
      const scale = 1 + Math.sin(frame * 0.03) * 0.08;
      const cx = w / 2;
      const cy = h / 2 - 10;
      const radius = 30 * scale;

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = "#94a3b8";
      ctx.fill();

      // Eyes
      ctx.fillStyle = "#fff";
      ctx.beginPath();
      ctx.arc(cx - 10, cy - 5, 5, 0, Math.PI * 2);
      ctx.arc(cx + 10, cy - 5, 5, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.fillStyle = "#64748b";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Live2D Avatar", cx, cy + radius + 20);
      ctx.fillText("(模型載入中...)", cx, cy + radius + 36);

      frame++;
      this.animFrame = requestAnimationFrame(draw);
    };
    draw();
  }

  dispose(): void {
    if (this.animFrame !== null) {
      cancelAnimationFrame(this.animFrame);
      this.animFrame = null;
    }
    if (this.canvas?.parentElement) {
      this.canvas.parentElement.removeChild(this.canvas);
    }
    this.canvas = null;
  }
}
