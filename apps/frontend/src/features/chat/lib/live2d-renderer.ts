export interface RendererHandle {
  dispose: () => void;
}

export async function createLive2DRenderer(
  container: HTMLElement,
  modelUrl: string,
): Promise<RendererHandle> {
  const { Application } = await import("pixi.js");
  // pixi-live2d-display registers on PIXI global
  const PIXI = await import("pixi.js");
  (window as unknown as Record<string, unknown>).PIXI = PIXI;
  const { Live2DModel } = await import("pixi-live2d-display/cubism4");

  const app = new Application({
    view: document.createElement("canvas"),
    backgroundAlpha: 0,
    autoStart: true,
    resizeTo: container,
  });
  container.appendChild(app.view as HTMLCanvasElement);

  try {
    const model = await Live2DModel.from(modelUrl);
    const scale =
      Math.min(
        container.clientWidth / model.width,
        container.clientHeight / model.height,
      ) * 0.8;
    model.scale.set(scale);
    model.x = (container.clientWidth - model.width * scale) / 2;
    model.y = (container.clientHeight - model.height * scale) / 2;
    app.stage.addChild(model as never);
    model.motion("Idle");
  } catch (err) {
    console.warn("[AvatarPanel] Failed to load Live2D model:", err);
  }

  return {
    dispose: () => {
      app.destroy(true, { children: true, texture: true });
    },
  };
}
