export interface RendererHandle {
  dispose: () => void;
}

export async function createVRMRenderer(
  container: HTMLElement,
  modelUrl: string,
): Promise<RendererHandle> {
  const THREE = await import("three");
  const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js");
  const { VRMLoaderPlugin, VRMUtils } = await import("@pixiv/three-vrm");

  const width = container.clientWidth || 380;
  const height = container.clientHeight || 200;

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 20);
  camera.position.set(0, 1.2, -1.5);
  camera.lookAt(0, 1, 0);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambientLight);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(1, 2, -1);
  scene.add(dirLight);

  const clock = new THREE.Clock();
  let vrm: { update: (delta: number) => void } | null = null;
  let frameId: number | null = null;

  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));

  try {
    const gltf = await loader.loadAsync(modelUrl);
    vrm = gltf.userData.vrm;
    if (vrm) {
      VRMUtils.removeUnnecessaryJoints(gltf.scene);
      scene.add(gltf.scene);
    }
  } catch (err) {
    console.warn("[AvatarPanel] Failed to load VRM model:", err);
  }

  function animate() {
    frameId = requestAnimationFrame(animate);
    const delta = clock.getDelta();
    if (vrm) vrm.update(delta);
    renderer.render(scene, camera);
  }
  animate();

  return {
    dispose: () => {
      if (frameId !== null) cancelAnimationFrame(frameId);
      renderer.dispose();
      if (renderer.domElement.parentElement) {
        renderer.domElement.parentElement.removeChild(renderer.domElement);
      }
    },
  };
}
