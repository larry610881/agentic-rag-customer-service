import type { AvatarRenderer } from "../types";
import { loadScript } from "./cdn-loader";

/* Global declarations for CDN-loaded libraries */
declare const THREE: any;

/**
 * CDN URL for Three.js core (UMD global build).
 *
 * GLTFLoader is NOT available as a UMD script in r160+,
 * so we implement a minimal inline GLTF/GLB loader using
 * Three.js core APIs directly (BufferGeometry + Mesh).
 *
 * For full GLTF feature support, the VRM renderer is preferred.
 * This renderer handles simple GLB models (single mesh, embedded textures).
 */
const CDN_THREE =
  "https://cdn.jsdelivr.net/npm/three@0.150.0/build/three.min.js";

/**
 * Minimal GLB loader using Three.js core only (no GLTFLoader dependency).
 * Parses the binary GLB container, extracts JSON + binary buffer,
 * and builds a Three.js scene from the GLTF data.
 */
async function loadGLB(url: string): Promise<{ scene: any; animations: any[] }> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to fetch GLB: ${response.status}`);
  const arrayBuffer = await response.arrayBuffer();
  const dataView = new DataView(arrayBuffer);

  // GLB header: magic(4) + version(4) + length(4)
  const magic = dataView.getUint32(0, true);
  if (magic !== 0x46546C67) throw new Error("Not a valid GLB file");

  // Parse chunks
  let offset = 12;
  let jsonChunk = "";
  let binChunk: ArrayBuffer | null = null;

  while (offset < arrayBuffer.byteLength) {
    const chunkLength = dataView.getUint32(offset, true);
    const chunkType = dataView.getUint32(offset + 4, true);
    offset += 8;

    if (chunkType === 0x4E4F534A) {
      // JSON chunk
      const decoder = new TextDecoder();
      jsonChunk = decoder.decode(new Uint8Array(arrayBuffer, offset, chunkLength));
    } else if (chunkType === 0x004E4942) {
      // BIN chunk
      binChunk = arrayBuffer.slice(offset, offset + chunkLength);
    }
    offset += chunkLength;
  }

  const gltf = JSON.parse(jsonChunk);
  const scene = new THREE.Group();

  // Parse buffer views
  const bufferViews = gltf.bufferViews || [];

  // Parse accessors
  function getAccessorData(accessorIdx: number) {
    const accessor = gltf.accessors[accessorIdx];
    const bv = bufferViews[accessor.bufferView];
    const byteOffset = (bv.byteOffset || 0) + (accessor.byteOffset || 0);

    const componentTypes: Record<number, any> = {
      5120: Int8Array, 5121: Uint8Array, 5122: Int16Array,
      5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array,
    };
    const typeSizes: Record<string, number> = {
      SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16,
    };

    const TypedArray = componentTypes[accessor.componentType] || Float32Array;
    const numComponents = typeSizes[accessor.type] || 1;
    const count = accessor.count * numComponents;
    return new TypedArray(binChunk!, byteOffset, count);
  }

  // Parse images/textures (embedded in buffer)
  const textures: any[] = [];
  if (gltf.images) {
    for (const image of gltf.images) {
      if (image.bufferView !== undefined && binChunk) {
        const bv = bufferViews[image.bufferView];
        const blob = new Blob(
          [new Uint8Array(binChunk, bv.byteOffset || 0, bv.byteLength)],
          { type: image.mimeType || "image/png" },
        );
        const url = URL.createObjectURL(blob);
        const tex = new THREE.TextureLoader().load(url, () => URL.revokeObjectURL(url));
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.flipY = false;
        textures.push(tex);
      } else {
        textures.push(null);
      }
    }
  }

  // Parse materials
  const materials: any[] = [];
  if (gltf.materials) {
    for (const mat of gltf.materials) {
      const pbr = mat.pbrMetallicRoughness || {};
      const params: any = {
        side: mat.doubleSided ? THREE.DoubleSide : THREE.FrontSide,
      };

      if (pbr.baseColorFactor) {
        params.color = new THREE.Color(
          pbr.baseColorFactor[0], pbr.baseColorFactor[1], pbr.baseColorFactor[2],
        );
        if (pbr.baseColorFactor[3] < 1) {
          params.transparent = true;
          params.opacity = pbr.baseColorFactor[3];
        }
      }

      if (pbr.baseColorTexture && gltf.textures) {
        const texInfo = gltf.textures[pbr.baseColorTexture.index];
        if (texInfo && textures[texInfo.source]) {
          params.map = textures[texInfo.source];
        }
      }

      // Fallback: if no color and no texture, apply warm default
      if (!params.color && !params.map) {
        params.color = new THREE.Color(0xf5a623);
      }

      materials.push(new THREE.MeshStandardMaterial(params));
    }
  }

  // Fallback material (warm orange for untextured models)
  if (materials.length === 0) {
    materials.push(new THREE.MeshStandardMaterial({ color: 0xf5a623 }));
  }

  // Parse meshes
  if (gltf.meshes) {
    for (const mesh of gltf.meshes) {
      for (const prim of mesh.primitives) {
        const geom = new THREE.BufferGeometry();

        if (prim.attributes.POSITION !== undefined) {
          const pos = getAccessorData(prim.attributes.POSITION);
          geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
        }
        if (prim.attributes.NORMAL !== undefined) {
          const norm = getAccessorData(prim.attributes.NORMAL);
          geom.setAttribute("normal", new THREE.BufferAttribute(norm, 3));
        } else {
          geom.computeVertexNormals();
        }
        if (prim.attributes.TEXCOORD_0 !== undefined) {
          const uv = getAccessorData(prim.attributes.TEXCOORD_0);
          geom.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
        }
        if (prim.indices !== undefined) {
          const idx = getAccessorData(prim.indices);
          geom.setIndex(new THREE.BufferAttribute(idx, 1));
        }

        const matIdx = prim.material ?? 0;
        const mat = materials[matIdx] || materials[0];
        const mesh3d = new THREE.Mesh(geom, mat);
        scene.add(mesh3d);
      }
    }
  }

  return { scene, animations: [] };
}

/**
 * GLB avatar renderer.
 *
 * Uses a minimal inline GLB parser (no GLTFLoader CDN dependency).
 * Renders with turntable rotation and warm fallback material for untextured models.
 */
export class GLBRenderer implements AvatarRenderer {
  private renderer: any = null;
  private scene: any = null;
  private camera: any = null;
  private model: any = null;
  private clock: any = null;
  private animFrame: number | null = null;
  private container: HTMLElement | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private mixer: any = null;

  constructor(
    private modelUrl: string,
    private apiBase: string,
  ) {}

  async mount(container: HTMLElement): Promise<void> {
    this.container = container;

    try {
      const testCanvas = document.createElement("canvas");
      const gl = testCanvas.getContext("webgl2") || testCanvas.getContext("webgl");
      if (!gl) throw new Error("WebGL not supported");

      // Load Three.js core only (no GLTFLoader needed)
      await loadScript(CDN_THREE);

      const width = container.clientWidth || 380;
      const height = container.clientHeight || 180;

      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      this.renderer.setSize(width, height);
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      this.renderer.outputColorSpace = THREE.SRGBColorSpace;
      container.appendChild(this.renderer.domElement);
      this.renderer.domElement.style.width = "100%";
      this.renderer.domElement.style.height = "100%";

      this.scene = new THREE.Scene();

      this.camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
      this.camera.position.set(0, 1, 3);
      this.camera.lookAt(0, 0.5, 0);

      this.scene.add(new THREE.AmbientLight(0xffffff, 0.8));
      const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
      dirLight.position.set(2, 3, 1);
      this.scene.add(dirLight);

      this.clock = new THREE.Clock();

      const fullModelUrl = this.modelUrl.startsWith("http")
        ? this.modelUrl
        : `${this.apiBase}${this.modelUrl}`;

      const gltf = await loadGLB(fullModelUrl);
      this.model = gltf.scene;

      // Auto-center and scale
      const box = new THREE.Box3().setFromObject(this.model);
      const size = new THREE.Vector3();
      const center = new THREE.Vector3();
      box.getSize(size);
      box.getCenter(center);

      const maxDim = Math.max(size.x, size.y, size.z);
      const scale = 1.5 / maxDim;
      this.model.scale.setScalar(scale);

      box.setFromObject(this.model);
      box.getCenter(center);
      this.model.position.sub(center);
      this.model.position.y += size.y * scale * 0.5;

      this.scene.add(this.model);

      this.resizeObserver = new ResizeObserver(() => this.handleResize());
      this.resizeObserver.observe(container);
      this.animate();
    } catch (err) {
      console.error("[widget] GLB load failed:", err);
      this.showFallback(container);
    }
  }

  dispose(): void {
    if (this.animFrame !== null) cancelAnimationFrame(this.animFrame);
    this.resizeObserver?.disconnect();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement?.parentElement?.removeChild(this.renderer.domElement);
    }
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.model = null;
    this.mixer = null;
    this.clock = null;
    this.container = null;
    this.resizeObserver = null;
    this.animFrame = null;
  }

  private animate(): void {
    this.animFrame = requestAnimationFrame(() => this.animate());
    const delta = this.clock?.getDelta() ?? 0;
    if (this.mixer) this.mixer.update(delta);
    if (this.model) this.model.rotation.y += 0.005;
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
