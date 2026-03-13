export interface RendererHandle {
  dispose: () => void;
}

/** Dynamically load a script (deduplicates by URL) */
const loadedScripts = new Set<string>();
function loadScript(url: string): Promise<void> {
  if (loadedScripts.has(url)) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onload = () => {
      loadedScripts.add(url);
      resolve();
    };
    script.onerror = () => reject(new Error(`Failed to load: ${url}`));
    document.head.appendChild(script);
  });
}

/* CDN versions matching pixi-live2d-display compatibility */
const CDN_PIXI = "https://cdn.jsdelivr.net/npm/pixi.js@7.4.2/dist/pixi.min.js";
const CDN_LIVE2D_DISPLAY =
  "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/cubism4.min.js";

declare const PIXI: any;

export async function createLive2DRenderer(
  container: HTMLElement,
  modelUrl: string,
): Promise<RendererHandle> {
  // Load all dependencies via CDN <script> tags (same strategy as Widget)
  // This avoids Vite bundling version conflicts between pixi.js and pixi-live2d-display
  await loadScript("/static/libs/live2dcubismcore.min.js");
  await loadScript(CDN_PIXI);
  await loadScript(CDN_LIVE2D_DISPLAY);

  const Live2DModel = PIXI.live2d?.Live2DModel;
  if (!Live2DModel) {
    throw new Error("Live2DModel not found on PIXI.live2d");
  }

  const width = container.clientWidth || 380;
  const height = container.clientHeight || 200;

  const app = new PIXI.Application({
    width,
    height,
    backgroundAlpha: 0,
    autoStart: true,
  });
  container.appendChild(app.view as HTMLCanvasElement);

  // Style canvas to fill container
  const canvas = app.view as HTMLCanvasElement;
  canvas.style.width = "100%";
  canvas.style.height = "100%";

  try {
    const model = await Live2DModel.from(modelUrl, { autoInteract: false });
    const scaleX = width / model.width;
    const scaleY = height / model.height;
    const scale = Math.min(scaleX, scaleY) * 0.8;
    model.scale.set(scale);
    model.x = (width - model.width * scale) / 2;
    model.y = (height - model.height * scale) / 2;
    app.stage.addChild(model);

    try {
      model.motion("Idle");
    } catch {
      // Model may not have Idle motion group
    }
  } catch (err) {
    console.warn("[Live2D] Failed to load model:", err);
  }

  return {
    dispose: () => {
      app.destroy(true, { children: true, texture: true, baseTexture: true });
    },
  };
}
