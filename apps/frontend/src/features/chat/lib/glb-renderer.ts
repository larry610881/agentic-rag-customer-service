import type { RendererHandle } from "./vrm-renderer";

export async function createGLBRenderer(
  container: HTMLElement,
  modelUrl: string,
): Promise<RendererHandle> {
  const THREE = await import("three");
  const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js");

  const width = container.clientWidth || 380;
  const height = container.clientHeight || 200;

  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
  camera.position.set(0, 1, 3);
  camera.lookAt(0, 0.5, 0);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
  scene.add(ambientLight);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
  dirLight.position.set(2, 3, 1);
  scene.add(dirLight);

  const clock = new THREE.Clock();
  let mixer: THREE.AnimationMixer | null = null;
  let model: THREE.Group | null = null;
  let frameId: number | null = null;

  const loader = new GLTFLoader();

  try {
    const gltf = await loader.loadAsync(modelUrl);
    model = gltf.scene;

    // Auto-center and scale to fit
    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 1.5 / maxDim;
    model.scale.setScalar(scale);

    // Re-center after scaling
    box.setFromObject(model);
    box.getCenter(center);
    model.position.sub(center);
    model.position.y += size.y * scale * 0.5;

    scene.add(model);

    // Play animations if available
    if (gltf.animations.length > 0) {
      mixer = new THREE.AnimationMixer(model);
      for (const clip of gltf.animations) {
        mixer.clipAction(clip).play();
      }
    }
  } catch (err) {
    console.warn("[AvatarPanel] Failed to load GLB model:", err);
  }

  function animate() {
    frameId = requestAnimationFrame(animate);
    const delta = clock.getDelta();
    if (mixer) mixer.update(delta);
    if (model) model.rotation.y += 0.005;
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
