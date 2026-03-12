import type { AvatarRenderer } from "../types";
import { loadScript } from "./cdn-loader";

/* Global declarations for CDN-loaded libraries */
declare const THREE: any;

/**
 * CDN URLs for Three.js stack.
 *
 * Using three@0.160.1 because it is the last version that ships
 * `examples/js/loaders/GLTFLoader.js` as a script-tag-compatible global.
 * Newer versions (0.161+) only provide ESM addons, which cannot be loaded
 * via <script> tags in our IIFE widget context.
 */
const CDN_THREE =
  "https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.min.js";
const CDN_GLTF_LOADER =
  "https://cdn.jsdelivr.net/npm/three@0.160.1/examples/js/loaders/GLTFLoader.js";
const CDN_THREE_VRM =
  "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.3.3/lib/three-vrm.min.js";

/**
 * VRM avatar renderer.
 *
 * Loads Three.js, GLTFLoader, and @pixiv/three-vrm from CDN, then renders
 * a VRM model with idle animation (breathing + blink).
 */
export class VRMRenderer implements AvatarRenderer {
  private renderer: any = null;
  private scene: any = null;
  private camera: any = null;
  private vrm: any = null;
  private clock: any = null;
  private animFrame: number | null = null;
  private container: HTMLElement | null = null;
  private resizeObserver: ResizeObserver | null = null;

  constructor(
    private modelUrl: string,
    private apiBase: string,
  ) {}

  async mount(container: HTMLElement): Promise<void> {
    this.container = container;

    try {
      // Check WebGL support
      const testCanvas = document.createElement("canvas");
      const gl =
        testCanvas.getContext("webgl2") || testCanvas.getContext("webgl");
      if (!gl) {
        throw new Error("WebGL not supported");
      }

      // Load Three.js core first
      await loadScript(CDN_THREE);
      // GLTFLoader registers itself on THREE.GLTFLoader
      await loadScript(CDN_GLTF_LOADER);
      // @pixiv/three-vrm UMD exposes THREEVRM global
      await loadScript(CDN_THREE_VRM);

      const THREEVRM = (window as any).THREEVRM;
      if (!THREEVRM) {
        throw new Error("THREEVRM not found on window");
      }

      const width = container.clientWidth || 380;
      const height = container.clientHeight || 180;

      // Renderer
      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      this.renderer.setSize(width, height);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      container.appendChild(this.renderer.domElement);

      this.renderer.domElement.style.width = "100%";
      this.renderer.domElement.style.height = "100%";

      // Scene
      this.scene = new THREE.Scene();

      // Camera — upper body framing
      this.camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 20);
      this.camera.position.set(0, 1.2, -1.5);
      this.camera.lookAt(0, 1, 0);

      // Lights
      const ambient = new THREE.AmbientLight(0xffffff, 0.6);
      this.scene.add(ambient);

      const directional = new THREE.DirectionalLight(0xffffff, 0.8);
      directional.position.set(1, 2, -1);
      this.scene.add(directional);

      // Clock for animation
      this.clock = new THREE.Clock();

      // Resolve model URL relative to backend origin
      const fullModelUrl = this.modelUrl.startsWith("http")
        ? this.modelUrl
        : `${this.apiBase}${this.modelUrl}`;

      // Load VRM via GLTFLoader + VRMLoaderPlugin
      const loader = new THREE.GLTFLoader();
      loader.register(
        (parser: any) => new THREEVRM.VRMLoaderPlugin(parser),
      );

      const gltf = await new Promise<any>((resolve, reject) => {
        loader.load(fullModelUrl, resolve, undefined, reject);
      });

      const vrm = gltf.userData.vrm;
      if (!vrm) {
        throw new Error("No VRM data found in GLTF");
      }

      // Optimize: remove unnecessary joints
      if (THREEVRM.VRMUtils?.removeUnnecessaryJoints) {
        THREEVRM.VRMUtils.removeUnnecessaryJoints(gltf.scene);
      }

      // Rotate VRM0 model to face camera if needed
      if (THREEVRM.VRMUtils?.rotateVRM0) {
        THREEVRM.VRMUtils.rotateVRM0(vrm);
      }

      this.scene.add(vrm.scene);
      this.vrm = vrm;

      // Handle resize
      this.resizeObserver = new ResizeObserver(() => this.handleResize());
      this.resizeObserver.observe(container);

      // Start animation loop
      this.animate();
    } catch (err) {
      console.error("[widget] VRM load failed:", err);
      this.showFallback(container);
    }
  }

  dispose(): void {
    if (this.animFrame !== null) {
      cancelAnimationFrame(this.animFrame);
      this.animFrame = null;
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
    if (this.renderer) {
      this.renderer.dispose();
      if (this.renderer.domElement?.parentElement) {
        this.renderer.domElement.parentElement.removeChild(
          this.renderer.domElement,
        );
      }
      this.renderer = null;
    }
    this.scene = null;
    this.camera = null;
    this.vrm = null;
    this.clock = null;
    this.container = null;
  }

  private animate(): void {
    this.animFrame = requestAnimationFrame(() => this.animate());

    const delta = this.clock?.getDelta() ?? 0;

    if (this.vrm) {
      // Update VRM (spring bones, expression, etc.)
      this.vrm.update(delta);

      // Subtle breathing — move hips slightly up/down
      const hips = this.vrm.humanoid?.getNormalizedBoneNode("hips");
      if (hips) {
        const t = this.clock?.elapsedTime ?? 0;
        hips.position.y += Math.sin(t * 1.5) * 0.0008;
      }

      // Blink animation — close eyes briefly every ~4 seconds
      const blink = this.vrm.expressionManager;
      if (blink) {
        const t = this.clock?.elapsedTime ?? 0;
        const blinkCycle = t % 4;
        if (blinkCycle > 3.8 && blinkCycle < 4.0) {
          const blinkWeight = Math.sin(
            ((blinkCycle - 3.8) / 0.2) * Math.PI,
          );
          blink.setValue("blink", blinkWeight);
        } else {
          blink.setValue("blink", 0);
        }
      }
    }

    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  private handleResize(): void {
    if (!this.container || !this.renderer || !this.camera) return;

    const width = this.container.clientWidth;
    const height = this.container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  private showFallback(container: HTMLElement): void {
    container.innerHTML = "";

    const fallback = document.createElement("div");
    fallback.style.cssText =
      "display:flex;align-items:center;justify-content:center;width:100%;height:100%;background:#f1f5f9;color:#64748b;font:14px sans-serif;border-radius:8px;";
    fallback.textContent = "Avatar \u8F09\u5165\u5931\u6557";
    container.appendChild(fallback);
  }
}
