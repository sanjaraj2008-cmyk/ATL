// =========================================================================
// METIC.STUDIO INSPIRED DESKTOP CLIENT LOGIC + THREE.JS 3D ENGINE
// Interactive Precision Loupe, PBR 3D Inspector, Theme, Audit Runner
// =========================================================================

let currentAuditResult = null;
let auditHistory = [];
let presetsList = [];

// Explicit Snapshot Source-Binding State (Fixes Stale Snapshot P0 Bug)
let activeSnapshot = {
  sourceUrl: null,
  html: null,
  contentHash: null,
  fetchedAt: null,
  isStale: false
};

function escapeHTML(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Three.js Metic 3D Magnifying Glass State
let stage, canvas, renderer, scene, camera, rig, head;
let isPickedUp = false;
let isDragging = false;
let isReturning = false;
let lastTapTime = 0;
let lastPointerX = 0, lastPointerY = 0;
let pointerX = 0, pointerY = 0;
let targetTiltX = 0, targetTiltY = 0;

const homePos = { x: 0.0, y: 0.15, z: 0.0 };
const homeRot = { x: -0.08, y: 0.04, z: -0.02 };
const headRot = { x: 0.02, y: -0.04, z: 0.03 };

document.addEventListener('DOMContentLoaded', async () => {
  lucide.createIcons();
  initTheme();
  initMetic3DMagnifyingGlass();
  await loadPresetsDropdown();
  loadHistoryFromStorage();

  // Attach listener to track URL edits against active snapshot
  const urlInput = document.getElementById('input-url');
  if (urlInput) {
    urlInput.addEventListener('input', handleURLInputChange);
  }
});

// =========================================================================
// 1. METIC.STUDIO 3D MAGNIFYING GLASS ENGINE
// Double-tap / double-click to pick up, move anywhere, release to spring back
// =========================================================================
function initMetic3DMagnifyingGlass() {
  stage = document.querySelector('#stage');
  canvas = document.querySelector('#scene');
  const lensCopy = document.querySelector('#lensCopy');
  const xrayLens = document.querySelector('#xrayLens');
  const scanStatus = document.querySelector('#scanStatus');
  const scanTarget = document.querySelector('#scanTarget');
  if (!stage || !canvas) return;

  const isMobile = window.innerWidth < 768;
  const width = stage.clientWidth || 480;
  const height = stage.clientHeight || 480;

  // WebGL Renderer with Alpha enabled to blend seamlessly with theme
  renderer = new THREE.WebGLRenderer({
    canvas: canvas,
    antialias: !isMobile, // Disable MSAA on mobile for silky smooth 60fps
    alpha: true,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2));
  renderer.setSize(width, height, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  if (!isMobile) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  } else {
    renderer.shadowMap.enabled = false;
  }

  // Scene & Camera
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 100);
  camera.position.set(0, 0, 8.4);

  // Lighting (PBR Studio Hemisphere + Directional Key/Fill/Rim)
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb7b5b2, 2.1));

  const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
  keyLight.position.set(-3.5, 5, 7);
  if (!isMobile) {
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.bias = -0.0002;
  }
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xffffff, 1.25);
  fillLight.position.set(4, 1, 5);
  scene.add(fillLight);

  const rimLight = new THREE.PointLight(0xffffff, 18, 12);
  rimLight.position.set(1.5, 2.2, 2.5);
  scene.add(rimLight);

  // Soft product shadow receiver ground plane
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.ShadowMaterial({ opacity: 0.16 })
  );
  ground.position.set(0, 0, -0.8);
  if (!isMobile) {
    ground.receiveShadow = true;
  }
  scene.add(ground);

  // 3D Assembly Rigs
  rig = new THREE.Group();
  scene.add(rig);

  head = new THREE.Group();
  rig.add(head);

  // Materials identical to metic-3d-magnifying-glass.html
  const black = new THREE.MeshPhysicalMaterial({
    color: 0x101114,
    metalness: 0.58,
    roughness: 0.28,
    clearcoat: 0.5,
    clearcoatRoughness: 0.22
  });
  const blackSoft = new THREE.MeshStandardMaterial({
    color: 0x18191c,
    metalness: 0.28,
    roughness: 0.48
  });
  const steel = new THREE.MeshStandardMaterial({
    color: 0xbfc2c5,
    metalness: 0.86,
    roughness: 0.24
  });
  const red = new THREE.MeshStandardMaterial({
    color: 0xff343d,
    metalness: 0.32,
    roughness: 0.25,
    emissive: 0x240305
  });
  const tickMat = new THREE.MeshStandardMaterial({
    color: 0xe0e0df,
    metalness: 0.25,
    roughness: 0.38
  });

  function torus(parent, radius, tube, material, z = 0, segments = 160) {
    const segs = isMobile ? 64 : segments;
    const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 16, segs), material);
    mesh.position.z = z;
    if (!isMobile) {
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    }
    parent.add(mesh);
    return mesh;
  }

  // 1. Layered outer rim and deep black bezel
  torus(head, 1.015, 0.070, steel, 0.015);
  torus(head, 0.986, 0.083, black, 0.075);
  torus(head, 0.921, 0.026, blackSoft, 0.125);

  // 2. Optical opening: crystal-clear transparent optical glass opening
  const lens = new THREE.Mesh(
    new THREE.CircleGeometry(0.875, 96),
    new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      metalness: 0.02,
      roughness: 0.03,
      transmission: 0.99,
      transparent: true,
      opacity: 0.03,
      clearcoat: 1.0,
      clearcoatRoughness: 0.04,
      side: THREE.DoubleSide
    })
  );
  lens.position.z = 0.12;
  head.add(lens);

  // 3. Fine red optical ring inside the bezel
  torus(head, 0.887, 0.008, red, 0.176, 192);
  torus(head, 0.858, 0.004, steel, 0.171, 192);

  // 4. Precision ticks around the circumference (120 ticks, major every 10, medium every 5)
  const ticks = new THREE.Group();
  head.add(ticks);
  for (let i = 0; i < 120; i++) {
    const a = (i / 120) * Math.PI * 2;
    const major = i % 10 === 0, medium = i % 5 === 0;
    const len = major ? 0.070 : (medium ? 0.050 : 0.027);
    const tick = new THREE.Mesh(new THREE.BoxGeometry(major ? 0.010 : 0.006, len, 0.006), tickMat);
    const r = 0.988 - len / 2 - 0.004;
    tick.position.set(Math.cos(a) * r, Math.sin(a) * r, 0.153);
    tick.rotation.z = a - Math.PI / 2;
    ticks.add(tick);
  }

  // 5. Breaks / highlights on outer metal lip
  for (let i = 0; i < 12; i++) {
    const a = i * Math.PI / 6;
    const mark = new THREE.Mesh(new THREE.BoxGeometry(0.018, 0.082, 0.012), steel);
    mark.position.set(Math.cos(a) * 1.016, Math.sin(a) * 1.016, 0.064);
    mark.rotation.z = a - Math.PI / 2;
    head.add(mark);
  }

  // 6. Handle assembly from tapered cylinders, red collar, grip rings, and end cap
  function cylinderBetween(parent, start, end, rTop, rBottom, material, radial = 48) {
    const A = new THREE.Vector3(...start), B = new THREE.Vector3(...end);
    const direction = new THREE.Vector3().subVectors(B, A);
    const mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(rTop, rBottom, direction.length(), isMobile ? 24 : radial, 1, false),
      material
    );
    mesh.position.copy(A).add(B).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    if (!isMobile) {
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    }
    parent.add(mesh);
    return mesh;
  }

  const p0 = [0.70, -0.72, 0.00], p1 = [0.88, -1.00, 0.00], p2 = [1.49, -2.00, 0.00], p3 = [1.57, -2.13, 0.00];
  cylinderBetween(rig, p0, p1, 0.145, 0.205, black, 48);
  cylinderBetween(rig, p1, p2, 0.205, 0.135, black, 48);
  cylinderBetween(rig, p1, p1.map((v, i) => i === 2 ? 0.02 : v), 0.20, 0.20, blackSoft, 48);
  // Red metallic ferrule around the neck
  cylinderBetween(rig, [0.84, -0.94, 0.018], [0.94, -1.10, 0.018], 0.207, 0.194, red, 48);
  cylinderBetween(rig, [0.91, -1.05, 0.02], [0.94, -1.10, 0.02], 0.196, 0.194, steel, 48);
  // Fine grip grooves
  const A = new THREE.Vector3(...p1), B = new THREE.Vector3(...p2);
  const axis = new THREE.Vector3().subVectors(B, A);
  for (let i = 1; i <= 5; i++) {
    const t = 0.22 + i * 0.125;
    const center = A.clone().add(axis.clone().multiplyScalar(t));
    const half = axis.clone().normalize().multiplyScalar(0.018);
    cylinderBetween(
      rig,
      center.clone().sub(half).toArray(),
      center.clone().add(half).toArray(),
      0.177 - t * 0.035,
      0.177 - t * 0.035,
      steel,
      32
    );
  }
  // End cap
  cylinderBetween(rig, [1.47, -1.97, 0.01], [1.56, -2.11, 0.01], 0.145, 0.122, blackSoft, 48);
  cylinderBetween(rig, [1.54, -2.08, 0.02], [1.60, -2.17, 0.02], 0.125, 0.092, steel, 48);
  cylinderBetween(rig, [1.59, -2.15, 0.02], [1.63, -2.20, 0.02], 0.095, 0.070, black, 48);

  // Set initial home position and rotation
  rig.position.set(homePos.x, homePos.y, homePos.z);
  rig.rotation.set(homeRot.x, homeRot.y, homeRot.z);
  head.rotation.set(headRot.x, headRot.y, headRot.z);

  // Helper to compute where the loupe rests in screen pixel coordinates
  function getHomeScreenCoords() {
    const placeholder = document.getElementById('stage-placeholder');
    if (!placeholder) {
      return { x: window.innerWidth * 0.745, y: window.innerHeight * 0.28 };
    }
    const r = placeholder.getBoundingClientRect();
    const halfH = 8.4 * Math.tan(THREE.MathUtils.degToRad(16));
    const offsetY = (homePos.y / halfH) * (r.height / 2);
    return {
      x: r.left + r.width / 2,
      y: (r.top + r.height / 2) - offsetY
    };
  }

  // Position stage over placeholder and align resting state (X-ray lens deactivated)
  function dockStageToPlaceholder() {
    const placeholder = document.getElementById('stage-placeholder');
    if (!placeholder || !stage) return;
    const r = placeholder.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;

    stage.style.position = 'absolute';
    stage.style.left = `${r.left + window.scrollX}px`;
    stage.style.top = `${r.top + window.scrollY}px`;
    stage.style.width = `${r.width}px`;
    stage.style.height = `${r.height}px`;
    stage.style.zIndex = '40';
    stage.style.pointerEvents = 'auto';
    stage.style.cursor = 'grab';

    // When resting / docked, X-Ray vision effect MUST BE DEACTIVATED
    if (xrayLens && !isPickedUp && !isReturning) {
      const home = getHomeScreenCoords();
      xrayLens.style.left = `${home.x}px`;
      xrayLens.style.top = `${home.y}px`;
      xrayLens.classList.remove('active');
      xrayLens.style.opacity = '0';
      xrayLens.style.visibility = 'hidden';
    }
    if (scanStatus && !isPickedUp && !isReturning) {
      scanStatus.classList.remove('active');
      scanStatus.style.opacity = '0';
      scanStatus.style.visibility = 'hidden';
    }

    onResize();
  }

  // Initial docking
  setTimeout(dockStageToPlaceholder, 50);
  window.addEventListener('scroll', () => {
    if (!isPickedUp && !isReturning) {
      dockStageToPlaceholder();
    }
  }, { passive: true });

  // Updates the 3D loupe position and X-ray blueprint lens synchronously
  function updateLoupe(clientX, clientY) {
    if (!xrayLens) return;

    // 1. Position the high-contrast X-ray lens exactly under cursor/finger
    xrayLens.style.left = `${clientX}px`;
    xrayLens.style.top = `${clientY}px`;
    xrayLens.classList.add('active');
    xrayLens.style.visibility = 'visible';
    xrayLens.style.opacity = '1';

    if (scanStatus) {
      scanStatus.classList.add('active');
      scanStatus.style.visibility = 'visible';
      scanStatus.style.opacity = '1';
    }

    // 2. Position 3D rig so the loupe head aligns with (clientX, clientY)
    const w = window.innerWidth;
    const h = window.innerHeight;
    const ndcX = (clientX / w) * 2 - 1;
    const ndcY = -(clientY / h) * 2 + 1;

    const halfH = camera.position.z * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const halfW = halfH * camera.aspect;

    rig.position.x = ndcX * halfW;
    rig.position.y = ndcY * halfH;
    rig.position.z = 0.35; // slightly lifted while dragging

    // 3. Scan telemetry: inspect element under the lens
    const hit = document.elementFromPoint(clientX, clientY);
    const target = hit?.closest?.('[data-scan]');

    if (target) {
      if (scanTarget) scanTarget.textContent = target.dataset.scan;
      document.querySelectorAll('.scan-hit').forEach(el => {
        if (el !== target) el.classList.remove('scan-hit');
      });
      target.classList.add('scan-hit');
    } else {
      document.querySelectorAll('.scan-hit').forEach(el => el.classList.remove('scan-hit'));
      if (scanTarget) {
        if (hit && hit !== document.body && hit !== document.documentElement && !hit.closest('#stage')) {
          const text = hit.textContent?.trim().slice(0, 24);
          scanTarget.textContent = text ? `${hit.tagName.toLowerCase()} · "${text}"` : 'page surface';
        } else {
          scanTarget.textContent = 'page surface';
        }
      }
    }
  }

  // Activates X-Ray vision effect and picks up the magnifying glass
  function triggerPickup(clientX, clientY) {
    if (isReturning) return;
    isPickedUp = true;
    isDragging = true;
    isReturning = false;
    lastPointerX = clientX;
    lastPointerY = clientY;

    if (lensCopy) {
      lensCopy.style.opacity = '0';
      lensCopy.style.transform = 'translate(-50%, -65%) scale(0.9)';
    }

    // Expand stage to fixed full-viewport canvas across the entire website
    stage.style.position = 'fixed';
    stage.style.left = '0';
    stage.style.top = '0';
    stage.style.width = '100vw';
    stage.style.height = '100vh';
    stage.style.zIndex = '9990';
    stage.style.pointerEvents = 'none';
    stage.style.cursor = 'grabbing';

    // ACTIVATE X-Ray vision
    if (xrayLens) {
      xrayLens.classList.add('active');
      xrayLens.style.visibility = 'visible';
      xrayLens.style.opacity = '1';
    }
    if (scanStatus) {
      scanStatus.classList.add('active');
      scanStatus.style.visibility = 'visible';
      scanStatus.style.opacity = '1';
    }

    onResize();
    updateLoupe(clientX, clientY);
  }

  // Deactivates X-Ray vision effect immediately and initiates smooth return
  function deactivateAndReturn() {
    if (!isPickedUp && !isDragging) return;
    isDragging = false;
    isReturning = true;

    // Immediately DEACTIVATE X-Ray vision effect on release
    if (xrayLens) {
      xrayLens.classList.remove('active');
      xrayLens.style.opacity = '0';
      xrayLens.style.visibility = 'hidden';
    }
    if (scanStatus) {
      scanStatus.classList.remove('active');
      scanStatus.style.opacity = '0';
      scanStatus.style.visibility = 'hidden';
    }
    document.querySelectorAll('.scan-hit').forEach(el => el.classList.remove('scan-hit'));
    if (scanTarget) scanTarget.textContent = 'page surface';
  }

  let longPressTimer = null;
  let touchStartPos = { x: 0, y: 0 };
  let isTouching = false;

  // 1. DESKTOP: Double-click on stage
  stage.addEventListener('dblclick', (e) => {
    e.preventDefault();
    triggerPickup(e.clientX, e.clientY);
  });

  // 2. DESKTOP: Rapid double pointer-down (mouse / stylus)
  stage.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
      const now = Date.now();
      if (now - lastTapTime < 350) {
        triggerPickup(e.clientX, e.clientY);
        lastTapTime = 0;
      } else {
        lastTapTime = now;
      }
    }
  });

  // 3. MOBILE: Long-press on magnifying glass (~420ms hold)
  stage.addEventListener('touchstart', (e) => {
    if (isPickedUp || isReturning) return;
    if (e.touches && e.touches.length === 1) {
      isTouching = true;
      const t = e.touches[0];
      touchStartPos = { x: t.clientX, y: t.clientY };

      if (longPressTimer) clearTimeout(longPressTimer);
      longPressTimer = setTimeout(() => {
        if (isTouching && !isPickedUp) {
          if (navigator.vibrate) {
            try { navigator.vibrate(50); } catch (_) {}
          }
          triggerPickup(touchStartPos.x, touchStartPos.y);
        }
        longPressTimer = null;
      }, 420);
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (e.touches && e.touches.length > 0) {
      const t = e.touches[0];
      // If finger moved > 10px before long-press timer finished, user is scrolling: cancel long press
      if (longPressTimer) {
        const dist = Math.hypot(t.clientX - touchStartPos.x, t.clientY - touchStartPos.y);
        if (dist > 10) {
          clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      }

      // If loupe is picked up and dragging: prevent page scrolling and track loupe
      if (isPickedUp && isDragging) {
        if (e.cancelable) e.preventDefault();
        handlePointerMove(t.clientX, t.clientY);
      }
    }
  }, { passive: false });

  window.addEventListener('touchend', () => {
    isTouching = false;
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
    if (isPickedUp && isDragging) {
      deactivateAndReturn();
    }
  });

  window.addEventListener('touchcancel', () => {
    isTouching = false;
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
    if (isPickedUp && isDragging) {
      deactivateAndReturn();
    }
  });

  // Universal move handler for active dragging and resting parallax
  function handlePointerMove(clientX, clientY) {
    if (isPickedUp && isDragging) {
      updateLoupe(clientX, clientY);

      const deltaX = clientX - lastPointerX;
      const deltaY = clientY - lastPointerY;
      targetTiltY = THREE.MathUtils.clamp(deltaX * 0.012, -0.35, 0.35);
      targetTiltX = THREE.MathUtils.clamp(deltaY * 0.012, -0.35, 0.35);

      lastPointerX = clientX;
      lastPointerY = clientY;
    } else if (!isPickedUp && !isReturning && stage) {
      const r = stage.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) {
        pointerX = ((clientX - r.left) / r.width - 0.5) * 2;
        pointerY = ((clientY - r.top) / r.height - 0.5) * 2;
      }
    }
  }

  window.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
      handlePointerMove(e.clientX, e.clientY);
    }
  });

  // Desktop release: pointerup anywhere on screen deactivates X-ray and returns
  window.addEventListener('pointerup', (e) => {
    if (e.pointerType === 'mouse' || e.pointerType === 'pen') {
      if (isPickedUp && isDragging) {
        deactivateAndReturn();
      }
    }
  });

  // Render loop with idle physics and spring return
  const clock = new THREE.Clock();
  let frameCount = 0;
  function animate() {
    requestAnimationFrame(animate);
    frameCount++;

    // Mobile thermal & battery optimization:
    // When resting idle on mobile, render at 30fps to keep device cool and eliminate lag
    if (isMobile && !isPickedUp && !isReturning && (frameCount % 2 !== 0)) {
      return;
    }

    const t = clock.getElapsedTime();

    if (isReturning) {
      // Elastic spring physics back to home position
      rig.position.x += (homePos.x - rig.position.x) * 0.16;
      rig.position.y += (homePos.y - rig.position.y) * 0.16;
      rig.position.z += (homePos.z - rig.position.z) * 0.16;

      rig.rotation.x += (homeRot.x - rig.rotation.x) * 0.16;
      rig.rotation.y += (homeRot.y - rig.rotation.y) * 0.16;
      rig.rotation.z += (homeRot.z - rig.rotation.z) * 0.16;

      // X-ray lens simultaneously stays deactivated during glide back
      if (xrayLens) {
        const home = getHomeScreenCoords();
        xrayLens.style.left = `${home.x}px`;
        xrayLens.style.top = `${home.y}px`;
        xrayLens.classList.remove('active');
        xrayLens.style.opacity = '0';
        xrayLens.style.visibility = 'hidden';
      }

      const d = Math.abs(rig.position.x - homePos.x) + Math.abs(rig.position.y - homePos.y) + Math.abs(rig.position.z - homePos.z);
      if (d < 0.015) {
        rig.position.set(homePos.x, homePos.y, homePos.z);
        rig.rotation.set(homeRot.x, homeRot.y, homeRot.z);
        if (xrayLens) {
          const home = getHomeScreenCoords();
          xrayLens.style.left = `${home.x}px`;
          xrayLens.style.top = `${home.y}px`;
          xrayLens.classList.remove('active');
          xrayLens.style.opacity = '0';
          xrayLens.style.visibility = 'hidden';
        }

        isReturning = false;
        isPickedUp = false;

        dockStageToPlaceholder();

        if (lensCopy) {
          lensCopy.style.opacity = '1';
          lensCopy.style.transform = 'translate(-50%, -50%) scale(1)';
        }
      }
    } else if (isPickedUp && isDragging) {
      // Inertial tilt while being carried
      rig.rotation.y += (targetTiltY - rig.rotation.y) * 0.15;
      rig.rotation.x += (targetTiltX - rig.rotation.x) * 0.15;
    } else {
      // Resting Metic Parallax and gentle organic breathing
      rig.rotation.y += (pointerX * 0.10 - rig.rotation.y) * 0.04;
      rig.rotation.x += (-pointerY * 0.055 - rig.rotation.x) * 0.04;
      rig.position.y += (homePos.y + Math.sin(t * 0.8) * 0.025 - rig.position.y) * 0.03;
    }

    renderer.render(scene, camera);
  }
  animate();

  // Resize handler
  function onResize() {
    if (!stage || !renderer || !camera) return;
    const w = stage.clientWidth || window.innerWidth;
    const h = stage.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();

    if (w < 700) {
      camera.position.z = 9.2;
    } else {
      camera.position.z = 8.4;
    }
  }
  window.addEventListener('resize', () => {
    if (!isPickedUp && !isReturning) dockStageToPlaceholder();
    else onResize();
  });
  onResize();
}

// =========================================================================
// 1B. DEDICATED MOBILE EVIDENCE LOUPE DEMO COMPONENT
// Lightweight, buttery-smooth 60fps CSS/DOM component for mobile devices
// =========================================================================
const mobileDemoScenarios = {
  duration: {
    claimText: '30-Day Free Trial',
    claimSub: 'No credit card required. Full team access.',
    status: 'CONTRADICTED',
    statusClass: 'status-contradicted',
    pageQuote: '“Start your 7-day trial. Credit card required for activation.”',
    domZone: 'HERO_SECTION',
    tag: 'h2.pricing-tier',
    fixText: 'Update ad to state “7-Day Trial” or honor advertised 30 days.'
  },
  pricing: {
    claimText: 'Free Forever Plan',
    claimSub: 'Manage contacts and deals at ₹0 per month.',
    status: 'SUPPORTED',
    statusClass: 'status-supported',
    pageQuote: '“Free Tools: Get started at ₹0/mo. No credit card required.”',
    domZone: 'HERO_SECTION',
    tag: 'div.pricing-cta > p',
    fixText: 'Message match verified against hero pricing table.'
  },
  discount: {
    claimText: 'Guaranteed 90% Off',
    claimSub: 'Unlock all pro features at a flat 90% discount.',
    status: 'NOT_FOUND',
    statusClass: 'status-not-found',
    pageQuote: '“Save up to 16% on annual billing.” (90% offer not found)',
    domZone: 'MAIN_BODY',
    tag: 'span.billing-toggle',
    fixText: 'Remove unsubstantiated 90% claim from ad creative.'
  }
};

function selectMobileLoupeScenario(key) {
  const sc = mobileDemoScenarios[key];
  if (!sc) return;

  const btnDuration = document.getElementById('mob-chip-duration');
  const btnPricing = document.getElementById('mob-chip-pricing');
  const btnDiscount = document.getElementById('mob-chip-discount');

  const chipInactive = "px-3 py-1 rounded-full text-[11px] font-mono border border-[var(--line-strong)] bg-[var(--paper)] text-[var(--ink-secondary)] transition cursor-pointer";
  const chipActive = "px-3 py-1 rounded-full text-[11px] font-mono border border-[var(--accent)] bg-[var(--surface-card)] text-[var(--accent)] font-bold shadow-sm transition cursor-pointer";

  if (btnDuration) btnDuration.className = key === 'duration' ? chipActive : chipInactive;
  if (btnPricing) btnPricing.className = key === 'pricing' ? chipActive : chipInactive;
  if (btnDiscount) btnDiscount.className = key === 'discount' ? chipActive : chipInactive;

  const claimTitle = document.getElementById('mob-claim-title');
  const claimSub = document.getElementById('mob-claim-sub');
  const statusPill = document.getElementById('mob-status-pill');
  const quoteElem = document.getElementById('mob-quote');
  const zoneElem = document.getElementById('mob-zone');
  const fixElem = document.getElementById('mob-fix');

  if (claimTitle) claimTitle.textContent = sc.claimText;
  if (claimSub) claimSub.textContent = sc.claimSub;
  if (statusPill) {
    statusPill.textContent = sc.status;
    statusPill.className = `status-pill ${sc.statusClass}`;
  }
  if (quoteElem) quoteElem.textContent = sc.pageQuote;
  if (zoneElem) zoneElem.textContent = `📍 DOM: ${sc.domZone} (${sc.tag})`;
  if (fixElem) fixElem.textContent = sc.fixText;

  lucide.createIcons();
}



// =========================================================================
// 3. THEME TOGGLER (METIC TONES)
// =========================================================================
function initTheme() {
  const saved = localStorage.getItem('auditor-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const target = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', target);
  localStorage.setItem('auditor-theme', target);
  updateThemeIcon(target);
}

function updateThemeIcon(theme) {
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.setAttribute('data-lucide', theme === 'dark' ? 'sun' : 'moon');
    lucide.createIcons();
  }
}

// =========================================================================
// 4. CHAPTER & VIEW NAVIGATION
// =========================================================================
function switchView(viewName) {
  document.getElementById('view-landing').classList.add('hidden');
  document.getElementById('view-workspace').classList.add('hidden');
  document.getElementById('view-history').classList.add('hidden');

  const btnLanding = document.getElementById('nav-landing');
  const btnWorkspace = document.getElementById('nav-workspace');
  const btnHistory = document.getElementById('nav-history');

  const inactiveClass = "px-5 py-1.5 rounded-full text-xs font-semibold tracking-wide transition text-[var(--ink-secondary)] hover:text-[var(--ink)]";
  const activeClass = "px-5 py-1.5 rounded-full text-xs font-semibold tracking-wide transition text-[var(--ink)] bg-[var(--paper)] shadow-sm";

  btnLanding.className = inactiveClass;
  btnWorkspace.className = inactiveClass;
  btnHistory.className = inactiveClass;

  if (viewName === 'landing') {
    document.getElementById('view-landing').classList.remove('hidden');
    btnLanding.className = activeClass;
    if (stage) stage.style.display = '';
    setTimeout(dockStageToPlaceholder, 60);
  } else if (viewName === 'workspace') {
    document.getElementById('view-workspace').classList.remove('hidden');
    btnWorkspace.className = activeClass;
    if (stage && !isPickedUp) stage.style.display = 'none';
  } else if (viewName === 'history') {
    document.getElementById('view-history').classList.remove('hidden');
    btnHistory.className = activeClass;
    if (stage && !isPickedUp) stage.style.display = 'none';
    renderHistory();
  }

  lucide.createIcons();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// =========================================================================
// 5. BENCHMARK PRESETS & DATASET AUDIT EXECUTION
// =========================================================================
async function loadPresetsDropdown() {
  try {
    let res = await fetch('/api/presets');
    if (res.status === 404) {
      res = await fetch('/presets');
    }
    presetsList = await res.json();
    const selector = document.getElementById('preset-selector');
    selector.innerHTML = '<option value="">Choose benchmark preset...</option>';
    presetsList.forEach((p, idx) => {
      const opt = document.createElement('option');
      opt.value = idx;
      opt.textContent = `${p.id || 'P' + (idx+1)}: ${p.title}`;
      selector.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load presets', err);
  }
}

let activeLandingTab = 'url';

function switchLandingInputTab(tab) {
  activeLandingTab = tab;
  const urlContainer = document.getElementById('landing-url-container');
  const htmlContainer = document.getElementById('landing-html-container');
  const tabBtnUrl = document.getElementById('tab-btn-url');
  const tabBtnHtml = document.getElementById('tab-btn-html');

  if (tab === 'url') {
    urlContainer.classList.remove('hidden');
    htmlContainer.classList.add('hidden');
    tabBtnUrl.className = "font-bold text-[var(--accent)] underline cursor-pointer";
    tabBtnHtml.className = "text-[var(--ink-secondary)] hover:text-[var(--ink)] cursor-pointer";
  } else {
    urlContainer.classList.add('hidden');
    htmlContainer.classList.remove('hidden');
    tabBtnUrl.className = "text-[var(--ink-secondary)] hover:text-[var(--ink)] cursor-pointer";
    tabBtnHtml.className = "font-bold text-[var(--accent)] underline cursor-pointer";
  }
}

function updateSnapshotBanner() {
  const banner = document.getElementById('snapshot-status-banner');
  if (!banner) return;
  if (!activeSnapshot.sourceUrl) {
    banner.classList.add('hidden');
    banner.innerHTML = '';
    return;
  }

  if (activeSnapshot.isStale) {
    banner.className = "text-xs font-mono p-2.5 rounded-lg border border-amber-400 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 flex items-center justify-between";
    banner.innerHTML = `
      <div class="flex items-center space-x-2">
        <i data-lucide="alert-circle" class="w-4 h-4 text-amber-600 shrink-0"></i>
        <span><strong>URL Changed:</strong> Snapshot was captured from <code class="px-1 py-0.5 bg-black/5 dark:bg-white/10 rounded">${escapeHTML(activeSnapshot.sourceUrl)}</code>. Re-fetch or verify live.</span>
      </div>
      <button type="button" onclick="fetchLiveURL()" class="ml-2 px-2.5 py-1 text-[11px] font-bold rounded bg-amber-600 text-white hover:bg-amber-700 transition">Re-Fetch</button>
    `;
    banner.classList.remove('hidden');
  } else {
    banner.className = "text-xs font-mono p-2.5 rounded-lg border border-emerald-400/50 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200 flex items-center justify-between";
    banner.innerHTML = `
      <div class="flex items-center space-x-2">
        <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-600 shrink-0"></i>
        <span>Snapshot bound to <code class="px-1 py-0.5 bg-black/5 dark:bg-white/10 rounded">${escapeHTML(activeSnapshot.sourceUrl)}</code> [Hash: ${activeSnapshot.contentHash || 'verified'}]</span>
      </div>
      <span class="text-[10px] text-[var(--ink-muted)]">${activeSnapshot.fetchedAt || ''}</span>
    `;
    banner.classList.remove('hidden');
  }
  lucide.createIcons();
}

function handleURLInputChange() {
  const urlInput = document.getElementById('input-url');
  if (!urlInput) return;
  const currentVal = urlInput.value.trim();
  if (activeSnapshot.sourceUrl && currentVal !== activeSnapshot.sourceUrl) {
    activeSnapshot.isStale = true;
  } else if (activeSnapshot.sourceUrl && currentVal === activeSnapshot.sourceUrl) {
    activeSnapshot.isStale = false;
  }
  updateSnapshotBanner();
}

async function fetchLiveURL() {
  const urlInput = document.getElementById('input-url');
  const statusEl = document.getElementById('fetch-status');
  const fetchBtn = document.getElementById('btn-fetch-url');
  const rawUrl = urlInput.value.trim();

  if (!rawUrl) {
    statusEl.innerHTML = '<span class="text-rose-500 font-bold">Please enter a valid URL.</span>';
    return;
  }

  fetchBtn.disabled = true;
  statusEl.innerHTML = '<span class="text-[var(--accent)] animate-pulse">Fetching live landing page HTML...</span>';

  try {
    let res = await fetch('/api/fetch-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: rawUrl })
    });

    if (res.status === 404) {
      res = await fetch('/fetch-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: rawUrl })
      });
    }

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to fetch URL');
    }

    document.getElementById('input-html').value = data.html;
    const meta = data.metadata || {};
    
    // Bind active snapshot to this exact URL and content hash
    activeSnapshot = {
      sourceUrl: rawUrl,
      html: data.html,
      contentHash: meta.content_hash || null,
      fetchedAt: new Date().toLocaleTimeString(),
      isStale: false
    };
    updateSnapshotBanner();

    statusEl.innerHTML = `
      <span class="text-emerald-600 dark:text-emerald-400 font-bold">✓ Fetched successfully!</span>
      <span class="text-[var(--ink-muted)]">Status: ${meta.status_code || 200} | ${meta.load_time_ms || 0}ms | ${Math.round(data.html.length / 1024)} KB</span>
    `;
  } catch (err) {
    statusEl.innerHTML = `
      <div class="space-y-1">
        <span class="text-rose-600 dark:text-rose-400 font-bold">Fetch Notice: ${err.message}</span>
        <div class="text-[10px] text-[var(--ink-muted)]">Tip: If this website blocks cloud scrapers, you can paste its HTML directly into the "Raw HTML" tab or upload a file.</div>
      </div>
    `;
  } finally {
    fetchBtn.disabled = false;
  }
}

function loadPreset(idx) {
  if (idx === "") return;
  const item = presetsList[idx];
  if (item) {
    document.getElementById('input-headline').value = item.ad_headline || '';
    document.getElementById('input-desc').value = item.ad_description || '';
    const inputCta = document.getElementById('input-cta');
    if (inputCta) inputCta.value = item.ad_call_to_action || '';
    const inputCampaign = document.getElementById('input-campaign');
    if (inputCampaign) inputCampaign.value = item.campaign_name || item.title || '';
    document.getElementById('input-html').value = item.html || '';
    if (item.html) {
      activeSnapshot = {
        sourceUrl: null,
        html: item.html,
        contentHash: null,
        fetchedAt: 'Preset Loaded',
        isStale: false
      };
      updateSnapshotBanner();
      switchLandingInputTab('html');
    }
  }
}

function loadBenchmarkDirect(idx) {
  switchView('workspace');
  setTimeout(() => {
    loadPreset(idx);
    document.getElementById('preset-selector').value = idx;
  }, 100);
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      document.getElementById('input-html').value = e.target.result;
      activeSnapshot = {
        sourceUrl: file.name,
        html: e.target.result,
        contentHash: null,
        fetchedAt: `File Upload (${file.name})`,
        isStale: false
      };
      updateSnapshotBanner();
      switchLandingInputTab('html');
    };
    reader.readAsText(file);
  }
}

async function executeAudit() {
  const headline = document.getElementById('input-headline').value.trim();
  const desc = document.getElementById('input-desc').value.trim();
  const ctaInput = document.getElementById('input-cta');
  const cta = ctaInput ? ctaInput.value.trim() : '';
  const campaignInput = document.getElementById('input-campaign');
  const campaign = campaignInput ? campaignInput.value.trim() : '';
  const html = document.getElementById('input-html').value.trim();
  const targetUrl = activeLandingTab === 'url'
    ? (document.getElementById('input-url') ? document.getElementById('input-url').value.trim() : '')
    : (activeSnapshot.sourceUrl || '');

  const runBtn = document.getElementById('btn-run-audit');
  runBtn.disabled = true;
  runBtn.innerHTML = `
    <span class="inline-block w-3.5 h-3.5 border-2 border-[var(--paper)] border-t-transparent rounded-full animate-spin"></span>
    <span class="font-mono text-xs">AUDITING DOM...</span>
  `;

  // CTA and Campaign are strictly optional; headline or description is sufficient
  if (!headline && !desc && !cta) {
    alert("Please enter at least an ad headline or description to verify.");
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <span>Verify Message Match</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256"><path d="M204,64V168a12,12,0,0,1-24,0V93L72.49,200.49a12,12,0,0,1-17-17L163,76H88a12,12,0,0,1,0-24H192A12,12,0,0,1,204,64Z"></path></svg>
    `;
    return;
  }

  const auditPayload = {
    ad_headline: headline || '',
    ad_description: desc || ''
  };
  if (cta) auditPayload.ad_call_to_action = cta;
  if (campaign) auditPayload.campaign_name = campaign;

  if (activeLandingTab === 'url') {
    const liveUrl = document.getElementById('input-url').value.trim();
    if (!liveUrl) {
      alert("Please enter a destination landing page URL.");
      runBtn.disabled = false;
      runBtn.innerHTML = `<span>Verify Message Match</span>`;
      return;
    }

    // Check for Stale Snapshot Mismatch
    if (activeSnapshot.sourceUrl && activeSnapshot.isStale) {
      const confirmProceed = confirm(
        `Warning: The landing page URL was changed to "${liveUrl}", but the captured HTML snapshot belongs to "${activeSnapshot.sourceUrl}".\n\nClick OK to fetch fresh content from "${liveUrl}", or Cancel to abort.`
      );
      if (!confirmProceed) {
        runBtn.disabled = false;
        runBtn.innerHTML = `<span>Verify Message Match</span>`;
        return;
      }
      // Re-fetch fresh URL first before running audit
      await fetchLiveURL();
      auditPayload.landing_page_html = document.getElementById('input-html').value.trim();
      auditPayload.landing_page_url = liveUrl;
    } else if (activeSnapshot.sourceUrl && activeSnapshot.sourceUrl === liveUrl && activeSnapshot.html) {
      // Use verified bound snapshot
      auditPayload.landing_page_html = activeSnapshot.html;
      auditPayload.landing_page_url = liveUrl;
      auditPayload.snapshot_source_url = activeSnapshot.sourceUrl;
      auditPayload.snapshot_hash = activeSnapshot.contentHash;
    } else {
      // Direct live URL audit requested
      auditPayload.landing_page_url = liveUrl;
      if (html && html.trim().length > 100) {
        auditPayload.landing_page_html = html;
        if (activeSnapshot.sourceUrl) {
          auditPayload.snapshot_source_url = activeSnapshot.sourceUrl;
          auditPayload.snapshot_hash = activeSnapshot.contentHash;
        }
      }
    }
  } else {
    if (!html || html.trim().length < 10) {
      alert("Please paste the destination landing page HTML or upload a file.");
      runBtn.disabled = false;
      runBtn.innerHTML = `<span>Verify Message Match</span>`;
      return;
    }
    auditPayload.landing_page_html = html;
    if (activeSnapshot.sourceUrl) {
      auditPayload.snapshot_source_url = activeSnapshot.sourceUrl;
      auditPayload.snapshot_hash = activeSnapshot.contentHash;
    }
  }

  try {
    let resp = await fetch('/api/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(auditPayload)
    });

    if (resp.status === 404) {
      resp = await fetch('/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(auditPayload)
      });
    }

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned status ${resp.status}`);
    }

    const data = await resp.json();
    currentAuditResult = data;

    // Check if there was a previous audit for this target URL to compute drift
    const prevAudit = targetUrl
      ? auditHistory.find(h => h.url && h.url.trim().toLowerCase() === targetUrl.trim().toLowerCase())
      : null;
    let diffInfo = null;
    if (prevAudit && prevAudit.score !== null && data.match_score !== null) {
      diffInfo = {
        prevScore: prevAudit.score,
        prevGrade: prevAudit.grade,
        scoreDelta: data.match_score - prevAudit.score,
        prevTimestamp: prevAudit.timestamp,
        prevCriticalCount: prevAudit.criticalCount || 0
      };
    }

    const historyItem = {
      id: 'audit_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
      timestamp: new Date().toLocaleString(),
      campaign: campaign || 'General Campaign',
      headline: headline,
      description: desc,
      cta: cta || '',
      url: targetUrl || activeSnapshot.sourceUrl || '',
      score: data.match_score,
      grade: data.grade,
      criticalCount: (data.findings || []).filter(f => f.severity === 'CRITICAL' || f.status === 'CONTRADICTED').length,
      hasLiability: data.has_critical_marketing_liability || false,
      diffInfo: diffInfo,
      data: data
    };

    auditHistory.unshift(historyItem);
    saveHistoryToStorage();
    const countBadge = document.getElementById('history-count');
    if (countBadge) countBadge.textContent = auditHistory.length;

    renderAuditResults(data, diffInfo);
    document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    alert('Audit execution error: ' + err.message);
  } finally {
    runBtn.disabled = false;
    runBtn.innerHTML = `
      <span>Verify Message Match</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 256 256"><path d="M204,64V168a12,12,0,0,1-24,0V93L72.49,200.49a12,12,0,0,1-17-17L163,76H88a12,12,0,0,1,0-24H192A12,12,0,0,1,204,64Z"></path></svg>
    `;
    lucide.createIcons();
  }
}

function renderAuditResults(data, diffInfo = null) {
  const container = document.getElementById('results-container');
  container.classList.remove('hidden');

  // Render Re-Audit Diff / Drift Banner if applicable
  const diffBanner = document.getElementById('reaudit-diff-banner');
  if (diffBanner) {
    if (diffInfo) {
      const deltaSign = diffInfo.scoreDelta >= 0 ? '+' : '';
      const isPositive = diffInfo.scoreDelta >= 0;
      const deltaBg = isPositive
        ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-400 text-emerald-800 dark:text-emerald-200'
        : 'bg-red-50 dark:bg-red-950/40 border-red-400 text-red-800 dark:text-red-200';
      const iconName = isPositive ? 'trending-up' : 'trending-down';
      diffBanner.className = `p-4 rounded-2xl border text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm ${deltaBg}`;
      diffBanner.innerHTML = `
        <div class="flex items-center space-x-3">
          <i data-lucide="${iconName}" class="w-5 h-5 shrink-0 ${isPositive ? 'text-emerald-600' : 'text-red-600'}"></i>
          <div>
            <div class="font-bold tracking-wide">RE-AUDIT COMPARISON VS PREVIOUS RUN</div>
            <div class="text-[11px] opacity-90 mt-0.5 font-sans">
              Score shifted from <b>${diffInfo.prevScore}/100</b> (${escapeHTML(diffInfo.prevGrade)}) to <b>${data.match_score}/100</b> (${escapeHTML(data.grade)}) ·
              Delta: <b class="text-sm font-mono">${deltaSign}${diffInfo.scoreDelta} pts</b> · Prior run: ${escapeHTML(diffInfo.prevTimestamp)}
            </div>
          </div>
        </div>
        <button type="button" onclick="switchView('history')" class="px-3 py-1 text-[11px] font-bold rounded-lg border border-current hover:bg-black/5 dark:hover:bg-white/10 transition self-start sm:self-center">
          View History
        </button>
      `;
      diffBanner.classList.remove('hidden');
    } else {
      diffBanner.classList.add('hidden');
      diffBanner.innerHTML = '';
    }
  }

  const liabilityBanner = document.getElementById('liability-banner');
  if (data.has_critical_marketing_liability) {
    liabilityBanner.classList.remove('hidden');
  } else {
    liabilityBanner.classList.add('hidden');
  }

  const unreadableBanner = document.getElementById('unreadable-banner');
  const isUnreadable = data.audit_state === "FAILED_UNREADABLE_INPUT" || data.match_score === null;

  if (isUnreadable) {
    unreadableBanner.classList.remove('hidden');
    const reasonText = data.scoring_unavailability_reason || "Unable to extract meaningful text content from destination page snapshot.";
    document.getElementById('unreadable-desc').textContent = reasonText;
    
    const meta = data.audit_metadata || {};
    const metaItems = [];
    if (meta.source_url) metaItems.push(`Target: ${escapeHTML(meta.source_url)}`);
    if (meta.http_status) metaItems.push(`HTTP ${meta.http_status}`);
    if (meta.load_time_ms) metaItems.push(`${meta.load_time_ms}ms`);
    if (data.audit_warnings && data.audit_warnings.length > 0) {
      metaItems.push(`Diagnostic: ${escapeHTML(data.audit_warnings[0])}`);
    }
    document.getElementById('unreadable-meta').innerHTML = metaItems.join(' · ');

    document.getElementById('res-score').textContent = "N/A";
    const gradeElem = document.getElementById('res-grade');
    gradeElem.textContent = data.grade || "Unable to Assess";
    gradeElem.className = "status-pill status-partial w-max";
    document.getElementById('res-coverage').textContent = "0%";
    document.getElementById('res-prominence').textContent = "N/A";
    document.getElementById('res-validity').textContent = "N/A";
  } else {
    unreadableBanner.classList.add('hidden');
    document.getElementById('res-score').textContent = `${data.match_score}/100`;
    const gradeElem = document.getElementById('res-grade');
    gradeElem.textContent = data.grade;

    if (data.match_score >= 85) {
      gradeElem.className = "status-pill status-supported w-max";
    } else if (data.match_score >= 60) {
      gradeElem.className = "status-pill status-partial w-max";
    } else {
      gradeElem.className = "status-pill status-contradicted w-max";
    }

    document.getElementById('res-coverage').textContent = `${data.evidence_coverage_index}%`;
    document.getElementById('res-prominence').textContent = data.evidence_prominence_index !== null ? `${data.evidence_prominence_index}%` : "N/A";
    document.getElementById('res-validity').textContent = data.evidence_validity_rate !== null ? `${data.evidence_validity_rate}%` : "N/A";
  }

  document.getElementById('findings-count').textContent = data.findings ? data.findings.length : 0;

  const list = document.getElementById('findings-list');
  list.innerHTML = '';

  data.findings.forEach((f, idx) => {
    let statusClass = "status-partial";
    if (f.status === "SUPPORTED") statusClass = "status-supported";
    else if (f.status === "CONTRADICTED") statusClass = "status-contradicted";
    else if (f.status === "NOT_FOUND" || f.status === "MISSING") statusClass = "status-not-found";
    else if (f.status === "PARTIALLY_SUPPORTED") statusClass = "status-partial";
    else if (f.status === "UNVERIFIABLE") statusClass = "status-partial";

    const isCritical = f.severity === "CRITICAL" || f.severity === "HIGH";
    const borderIndicator = isCritical ? "border-l-4 border-l-[var(--accent)]" : "border-l-4 border-l-[var(--line-strong)]";

    const card = document.createElement('div');
    card.className = `editorial-card p-7 rounded-2xl ${borderIndicator}`;

    let regulatoryHtml = '';
    if (f.regulatory_flag && f.regulatory_review_note) {
      regulatoryHtml = `
        <div class="mt-3.5 p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-xs">
          <div class="font-bold font-mono uppercase tracking-wider mb-1 flex items-center space-x-1.5">
            <i data-lucide="alert-triangle" class="w-3.5 h-3.5 text-amber-600 dark:text-amber-400"></i>
            <span>Potential Compliance / Disclosure Review</span>
          </div>
          <p class="leading-relaxed font-sans">${escapeHTML(f.regulatory_review_note)}</p>
        </div>
      `;
    }

    let evidenceHtml = '';
    if (f.primary_evidence && f.primary_evidence.quote) {
      const offsetsStr = (f.primary_evidence.source_start_offset !== null && f.primary_evidence.source_start_offset !== undefined) ? ` | Offsets: [${Number(f.primary_evidence.source_start_offset)}:${Number(f.primary_evidence.source_end_offset)}]` : '';
      const selectorStr = f.primary_evidence.selector_path ? ` | Selector: <code class="px-1 py-0.5 bg-black/5 dark:bg-white/10 rounded">${escapeHTML(f.primary_evidence.selector_path)}</code>` : '';
      const isVerified = Boolean(f.primary_evidence.is_verified);
      const isContradicted = f.status === "CONTRADICTED";
      
      let verificationBadge = '';
      let borderClass = '';

      if (isContradicted) {
        borderClass = 'border-l-rose-500 bg-rose-50/40 dark:bg-rose-950/20';
        verificationBadge = `
          <span class="font-bold text-rose-600 dark:text-rose-400 flex items-center space-x-1.5">
            <i data-lucide="x-circle" class="w-3.5 h-3.5"></i>
            <span>CONFLICTING EVIDENCE FOUND ON PAGE</span>
          </span>
        `;
      } else if (isVerified) {
        borderClass = 'border-l-emerald-600 dark:border-l-emerald-400 bg-emerald-50/30 dark:bg-emerald-950/20';
        verificationBadge = `
          <span class="font-bold text-emerald-700 dark:text-emerald-400 flex items-center space-x-1.5">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
            <span>VERIFIED IN SOURCE DOM</span>
          </span>
        `;
      } else {
        borderClass = 'border-l-amber-500 bg-amber-50/30 dark:bg-amber-950/20';
        verificationBadge = `
          <span class="font-bold text-amber-700 dark:text-amber-400 flex items-center space-x-1.5">
            <i data-lucide="alert-circle" class="w-3.5 h-3.5"></i>
            <span>UNVERIFIED / HEURISTIC MATCH</span>
          </span>
        `;
      }

      evidenceHtml = `
        <div class="mt-4 p-4 rounded-xl precision-border-l ${borderClass} border border-[var(--line-border)]">
          <div class="flex flex-wrap items-center justify-between text-xs font-mono text-[var(--ink-secondary)] mb-1.5">
            ${verificationBadge}
            <span>ZONE: <b class="text-[var(--ink)]">${escapeHTML(f.primary_evidence.dom_zone)}</b> (&lt;${escapeHTML(f.primary_evidence.tag_name)}&gt;, Block ${escapeHTML(f.primary_evidence.block_id)}${selectorStr})${offsetsStr}</span>
          </div>
          <p class="font-mono text-sm text-[var(--ink)] italic pl-1">"${escapeHTML(f.primary_evidence.quote)}"</p>
        </div>
      `;
    } else {
      evidenceHtml = `
        <div class="mt-4 p-3.5 rounded-xl border border-[var(--line-border)] bg-[var(--paper-subtle)] text-xs font-mono text-[var(--ink-muted)] flex items-center justify-between">
          <span class="flex items-center space-x-1.5">
            <i data-lucide="minus-circle" class="w-3.5 h-3.5 text-[var(--ink-muted)]"></i>
            <span>NO DIRECT EVIDENCE FOUND IN EXTRACTED PAGE TEXT</span>
          </span>
          <span class="text-[10px]">Zero page matches for this claim</span>
        </div>
      `;
    }

    let techDrawerHtml = '';
    if (f.mismatch_details) {
      techDrawerHtml = `
        <details class="mt-3.5 text-xs text-[var(--ink-secondary)] rounded-xl border border-[var(--line-border)] bg-[var(--paper)] overflow-hidden">
          <summary class="px-3.5 py-2.5 font-mono font-semibold text-[var(--ink)] cursor-pointer select-none hover:bg-[var(--paper-subtle)] flex items-center justify-between">
            <span class="flex items-center gap-1.5">
              <i data-lucide="layers" class="w-3.5 h-3.5 text-[var(--accent)]"></i>
              <span>🔬 Detailed Technical Audit Breakdown (Phase 5 Schema)</span>
            </span>
            <span class="text-[10px] text-[var(--ink-muted)]">Click to expand</span>
          </summary>
          <div class="p-4 border-t border-[var(--line-border)] space-y-2 font-mono text-[11px] leading-relaxed">
            <div><b class="text-[var(--ink)]">Ad Promise:</b> ${escapeHTML(f.mismatch_details.original_ad_claim)}</div>
            <div><b class="text-[var(--ink)]">Page Finding:</b> ${escapeHTML(f.mismatch_details.landing_page_finding)}</div>
            <div><b class="text-[var(--ink)]">Discrepancy:</b> ${escapeHTML(f.mismatch_details.discrepancy_description)}</div>
            <div><b class="text-[var(--ink)]">Significance:</b> ${escapeHTML(f.mismatch_details.practical_significance)}</div>
            <div><b class="text-[var(--ink)]">Conditions & Visibility:</b> ${escapeHTML(f.mismatch_details.conditions_and_visibility)}</div>
            <div><b class="text-[var(--ink)]">Audit Certainty:</b> ${escapeHTML(f.mismatch_details.certainty_level)}</div>
          </div>
        </details>
      `;
    }

    card.innerHTML = `
      <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div class="flex items-center space-x-2.5">
            <span class="status-pill ${statusClass}">${escapeHTML(f.status)}</span>
            <span class="text-[11px] font-mono text-[var(--ink-muted)]">CLAIM ${escapeHTML(f.claim_id)}</span>
          </div>
          <h4 class="editorial-title text-2xl text-[var(--ink)] mt-2">${escapeHTML(f.ad_claim_text)}</h4>
          
          <div class="mt-3 p-3.5 rounded-xl bg-[var(--paper-subtle)] border border-[var(--line-border)] flex items-start gap-2.5">
            <span class="text-base select-none">💡</span>
            <div>
              <div class="text-[11px] font-mono font-bold uppercase tracking-wider text-[var(--accent)] mb-0.5">Plain-English Explanation</div>
              <p class="text-sm text-[var(--ink)] font-normal leading-relaxed">${escapeHTML(f.plain_summary || f.explanation)}</p>
            </div>
          </div>
        </div>

        <div class="text-left md:text-right text-xs font-mono text-[var(--ink-muted)] shrink-0 space-y-0.5">
          <div>REASON: <b class="text-[var(--ink)]">${escapeHTML(f.reason_code)}</b></div>
          <div>SEVERITY: <b class="${isCritical ? 'text-[var(--accent)]' : 'text-[var(--ink)]'}">${escapeHTML(f.severity)}</b></div>
          <div>MATERIALITY: <b class="text-[var(--ink)]">${escapeHTML(f.claim_materiality)}</b></div>
        </div>
      </div>

      ${regulatoryHtml}
      ${evidenceHtml}
      ${techDrawerHtml}

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-4 precision-border-t text-xs">
        <div class="p-4 rounded-xl bg-[var(--paper)] border border-[var(--line-border)]">
          <div class="font-mono font-bold text-[var(--ink)] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
            <i data-lucide="edit-2" class="w-3.5 h-3.5 text-[var(--accent)]"></i>
            <span>Recommended Ad Adjustment:</span>
          </div>
          <p class="text-[var(--ink-secondary)] leading-relaxed">${escapeHTML(f.recommended_ad_fix)}</p>
        </div>

        <div class="p-4 rounded-xl bg-[var(--paper)] border border-[var(--line-border)]">
          <div class="font-mono font-bold text-[var(--ink)] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
            <i data-lucide="layout" class="w-3.5 h-3.5 text-[var(--accent)]"></i>
            <span>Recommended Page Adjustment:</span>
          </div>
          <p class="text-[var(--ink-secondary)] leading-relaxed">${escapeHTML(f.recommended_page_fix)}</p>
        </div>
      </div>
    `;

    list.appendChild(card);
  });

  lucide.createIcons();
}

function saveHistoryToStorage() {
  try {
    localStorage.setItem('atl_audit_history_v1', JSON.stringify(auditHistory.slice(0, 50)));
  } catch (e) {
    console.warn('Failed to save audit history to localStorage:', e);
  }
}

function loadHistoryFromStorage() {
  try {
    const raw = localStorage.getItem('atl_audit_history_v1');
    if (raw) {
      auditHistory = JSON.parse(raw);
    }
  } catch (e) {
    auditHistory = [];
  }
  const countBadge = document.getElementById('history-count');
  if (countBadge) countBadge.textContent = auditHistory.length;
}

function renderHistory() {
  const list = document.getElementById('history-list');
  if (!list) return;

  if (auditHistory.length === 0) {
    list.innerHTML = `
      <div class="p-10 text-center border border-dashed border-[var(--ink-secondary)]/30 rounded-2xl">
        <i data-lucide="history" class="w-8 h-8 text-[var(--ink-muted)] mx-auto mb-2 opacity-60"></i>
        <p class="text-[var(--ink-muted)] text-sm font-mono">No audits saved in your campaign archive yet.</p>
        <button onclick="switchView('workspace')" class="btn-metic-primary !text-xs !py-1.5 mt-4">Start New Audit</button>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  list.innerHTML = '';
  auditHistory.forEach(h => {
    const item = document.createElement('div');
    item.className = "editorial-card p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 transition hover:shadow-md";

    const scoreColorClass = h.score >= 85
      ? "text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-300"
      : (h.score >= 60
        ? "text-amber-700 bg-amber-50 dark:bg-amber-950/40 border-amber-300"
        : "text-red-700 bg-red-50 dark:bg-red-950/40 border-red-300");

    const criticalBadge = h.criticalCount > 0
      ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-red-100 text-red-700 border border-red-300">${h.criticalCount} Critical Issue${h.criticalCount > 1 ? 's' : ''}</span>`
      : `<span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-100 text-emerald-700 border border-emerald-300">0 Critical Issues</span>`;

    const deltaBadge = h.diffInfo
      ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold font-mono ${h.diffInfo.scoreDelta >= 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}">Delta: ${h.diffInfo.scoreDelta >= 0 ? '+' : ''}${h.diffInfo.scoreDelta} pts</span>`
      : '';

    const urlDisplay = h.url
      ? `<div class="text-xs font-mono text-[var(--ink-muted)] truncate max-w-md mt-1">
           <i data-lucide="link" class="w-3 h-3 inline mr-1 opacity-70"></i>
           <span title="${escapeHTML(h.url)}">${escapeHTML(h.url)}</span>
         </div>`
      : '';

    item.innerHTML = `
      <div class="space-y-1.5 flex-1 min-w-0">
        <div class="flex items-center space-x-2 flex-wrap gap-y-1">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[var(--paper)] border border-[var(--ink-secondary)]/30 text-[var(--ink)]">${escapeHTML(h.campaign || 'Campaign')}</span>
          ${criticalBadge}
          ${deltaBadge}
        </div>
        <h4 class="editorial-title text-xl text-[var(--ink)] truncate">${escapeHTML(h.headline)}</h4>
        ${urlDisplay}
        <div class="text-[11px] font-mono text-[var(--ink-muted)]">
          Captured: ${escapeHTML(h.timestamp)} · Grade: <b>${escapeHTML(h.grade || 'N/A')}</b>
        </div>
      </div>

      <div class="flex items-center space-x-4 shrink-0">
        <div class="text-center px-4 py-2 rounded-xl border ${scoreColorClass}">
          <div class="text-2xl font-black font-mono leading-none">${escapeHTML(h.score)}<span class="text-xs font-normal opacity-70">/100</span></div>
          <div class="text-[9px] font-mono uppercase tracking-wider mt-0.5">${escapeHTML(h.grade || 'Score')}</div>
        </div>

        <div class="flex flex-col space-y-1.5">
          <button type="button" onclick="viewReportFromHistory('${h.id}')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--paper)] hover:bg-[var(--paper-contrast)] border border-[var(--ink-secondary)]/30 text-[var(--ink)] flex items-center space-x-1.5 transition cursor-pointer">
            <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
            <span>View Report</span>
          </button>
          <button type="button" onclick="reAuditFromHistory('${h.id}')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--ink)] text-[var(--paper)] hover:opacity-90 flex items-center space-x-1.5 transition cursor-pointer">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
            <span>Re-Audit Page</span>
          </button>
        </div>

        <button type="button" onclick="deleteHistoryItem('${h.id}', event)" title="Delete audit record" class="p-2 rounded-lg text-[var(--ink-muted)] hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 transition cursor-pointer">
          <i data-lucide="trash" class="w-4 h-4"></i>
        </button>
      </div>
    `;

    list.appendChild(item);
  });

  lucide.createIcons();
}

function viewReportFromHistory(id) {
  const item = auditHistory.find(h => h.id === id);
  if (!item || !item.data) return;

  currentAuditResult = item.data;
  renderAuditResults(item.data, item.diffInfo);
  switchView('workspace');
  const resultsContainer = document.getElementById('results-container');
  if (resultsContainer) {
    resultsContainer.classList.remove('hidden');
    resultsContainer.scrollIntoView({ behavior: 'smooth' });
  }
}

function reAuditFromHistory(id) {
  const item = auditHistory.find(h => h.id === id);
  if (!item) return;

  switchView('workspace');

  const inputHeadline = document.getElementById('input-headline');
  const inputDesc = document.getElementById('input-desc');
  const inputCta = document.getElementById('input-cta');
  const inputCampaign = document.getElementById('input-campaign');
  const inputUrl = document.getElementById('input-url');

  if (inputHeadline) inputHeadline.value = item.headline || '';
  if (inputDesc) inputDesc.value = item.description || '';
  if (inputCta) inputCta.value = item.cta || '';
  if (inputCampaign) inputCampaign.value = item.campaign !== 'General Campaign' ? item.campaign : '';
  if (inputUrl && item.url) {
    inputUrl.value = item.url;
    switchLandingInputTab('url');
  }

  // Visual highlight to prompt immediate re-audit
  const formCard = document.querySelector('#view-workspace .editorial-card');
  if (formCard) {
    formCard.scrollIntoView({ behavior: 'smooth' });
    formCard.classList.add('ring-2', 'ring-[var(--accent)]');
    setTimeout(() => formCard.classList.remove('ring-2', 'ring-[var(--accent)]'), 2500);
  }
}

function deleteHistoryItem(id, event) {
  if (event) event.stopPropagation();
  auditHistory = auditHistory.filter(h => h.id !== id);
  saveHistoryToStorage();
  const countBadge = document.getElementById('history-count');
  if (countBadge) countBadge.textContent = auditHistory.length;
  renderHistory();
}

function clearHistory() {
  if (auditHistory.length === 0) return;
  if (!confirm('Are you sure you want to clear all audit history?')) return;
  auditHistory = [];
  saveHistoryToStorage();
  const countBadge = document.getElementById('history-count');
  if (countBadge) countBadge.textContent = '0';
  renderHistory();
}

function downloadReport(type) {
  if (!currentAuditResult) return;
  if (type === 'json') {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentAuditResult, null, 2));
    const dl = document.createElement('a');
    dl.setAttribute("href", dataStr);
    dl.setAttribute("download", "metic_audit_report.json");
    dl.click();
  } else if (type === 'csv') {
    let csv = "Claim ID,Ad Claim Text,Status,Reason Code,Materiality,Severity,Evidence Quote,DOM Zone,Ad Fix,Page Fix\n";
    currentAuditResult.findings.forEach(f => {
      const q = f.primary_evidence ? `"${f.primary_evidence.quote.replace(/"/g, '""')}"` : '""';
      const z = f.primary_evidence ? f.primary_evidence.dom_zone : '""';
      csv += `"${f.claim_id}","${f.ad_claim_text.replace(/"/g, '""')}","${f.status}","${f.reason_code}","${f.claim_materiality}","${f.severity}",${q},"${z}","${f.recommended_ad_fix.replace(/"/g, '""')}","${f.recommended_page_fix.replace(/"/g, '""')}"\n`;
    });
    const dataStr = "data:text/csv;charset=utf-8," + encodeURIComponent(csv);
    const dl = document.createElement('a');
    dl.setAttribute("href", dataStr);
    dl.setAttribute("download", "metic_audit_report.csv");
    dl.click();
  }
}
