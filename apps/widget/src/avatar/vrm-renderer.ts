import type { AvatarRenderer } from "../types";

/**
 * VRM avatar renderer stub.
 *
 * Full implementation requires:
 *   - three (Three.js)
 *   - @pixiv/three-vrm
 *
 * This scaffold shows a placeholder canvas with loading state.
 * Replace with actual Three.js + VRM integration when model files are available.
 */
export class VRMRenderer implements AvatarRenderer {
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

    // Placeholder: draw 3D-style loading indicator
    let frame = 0;
    const draw = () => {
      if (!ctx || !this.canvas) return;
      const w = this.canvas.width;
      const h = this.canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Background
      ctx.fillStyle = "#f1f5f9";
      ctx.fillRect(0, 0, w, h);

      // Rotating cube wireframe (simulates 3D loading)
      const cx = w / 2;
      const cy = h / 2 - 10;
      const size = 25;
      const angle = frame * 0.02;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);

      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 2;

      // Front face
      const dx = size * cos;
      const dy = size * 0.5 * sin;
      ctx.strokeRect(cx - size + dx, cy - size + dy, size * 2, size * 2);

      // Back face offset
      ctx.globalAlpha = 0.4;
      ctx.strokeRect(cx - size - dx, cy - size - dy, size * 2, size * 2);
      ctx.globalAlpha = 1;

      // Label
      ctx.fillStyle = "#64748b";
      ctx.font = "12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("VRM Avatar", cx, cy + size + 30);
      ctx.fillText("(模型載入中...)", cx, cy + size + 46);

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
