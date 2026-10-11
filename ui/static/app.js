// =========================================================================
// METIC.STUDIO INSPIRED DESKTOP CLIENT LOGIC + THREE.JS 3D ENGINE
// Interactive Precision Loupe, PBR 3D Inspector, Theme, Audit Runner
// =========================================================================

let currentAuditResult = null;
let auditHistory = [];
let presetsList = [];

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

  const width = stage.clientWidth || 480;
  const height = stage.clientHeight || 480;

  // WebGL Renderer with Alpha enabled to blend seamlessly with theme
  renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height, false);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // Scene & Camera
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 100);
  camera.position.set(0, 0, 8.4);

  // Lighting (PBR Studio Hemisphere + Directional Key/Fill/Rim)
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb7b5b2, 2.1));

  const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
  keyLight.position.set(-3.5, 5, 7);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  keyLight.shadow.bias = -0.0002;
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
  ground.receiveShadow = true;
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
    const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, tube, 16, segments), material);
    mesh.position.z = z;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
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
      new THREE.CylinderGeometry(rTop, rBottom, direction.length(), radial, 1, false),
      material
    );
    mesh.position.copy(A).add(B).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    mesh.castShadow = true;
    mesh.receiveShadow = true;
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

  // Position stage over placeholder and align resting X-ray lens
  function dockStageToPlaceholder() {
    const placeholder = document.getElementById('stage-placeholder');
    if (!placeholder || !stage) return;
    const r = placeholder.getBoundingClientRect();
    stage.style.position = 'absolute';
    stage.style.left = `${r.left + window.scrollX}px`;
    stage.style.top = `${r.top + window.scrollY}px`;
    stage.style.width = `${r.width}px`;
    stage.style.height = `${r.height}px`;
    stage.style.zIndex = '40';
    stage.style.pointerEvents = 'auto';
    stage.style.cursor = 'grab';

    if (xrayLens && !isPickedUp && !isReturning) {
      const home = getHomeScreenCoords();
      xrayLens.style.left = `${home.x}px`;
      xrayLens.style.top = `${home.y}px`;
      xrayLens.style.opacity = '1';
    }

    onResize();
  }

  // Initial docking
  setTimeout(dockStageToPlaceholder, 50);
  window.addEventListener('scroll', () => {
    if (!isPickedUp && !isReturning) {
      dockStageToPlaceholder();
    }
  });

  // Updates the 3D loupe position and X-ray blueprint lens synchronously
  function updateLoupe(clientX, clientY) {
    if (!xrayLens) return;

    // 1. Position the high-contrast X-ray lens exactly under cursor
    xrayLens.style.left = `${clientX}px`;
    xrayLens.style.top = `${clientY}px`;
    xrayLens.style.opacity = '1';

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

  // Double-click or double-tap triggers pickup across the whole website
  function triggerPickup(e) {
    if (isReturning) return;
    isPickedUp = true;
    isDragging = true;
    isReturning = false;
    lastPointerX = e.clientX;
    lastPointerY = e.clientY;

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

    onResize();
    updateLoupe(e.clientX, e.clientY);
  }

  // Double-click listener on stage
  stage.addEventListener('dblclick', (e) => {
    e.preventDefault();
    triggerPickup(e);
  });

  // Touch double-tap detection for trackpads/mobile
  stage.addEventListener('pointerdown', (e) => {
    const now = Date.now();
    if (now - lastTapTime < 350) {
      triggerPickup(e);
    }
    lastTapTime = now;
  });

  // Clicking "Pick me up" prompt directly activates pickup
  if (lensCopy) {
    lensCopy.style.pointerEvents = 'auto';
    lensCopy.style.cursor = 'grab';
    lensCopy.addEventListener('click', (e) => {
      e.stopPropagation();
      triggerPickup(e);
    });
  }

  // Pointer move: tracks drag when picked up across the ENTIRE website
  window.addEventListener('pointermove', (e) => {
    if (isPickedUp && isDragging) {
      updateLoupe(e.clientX, e.clientY);

      const deltaX = e.clientX - lastPointerX;
      const deltaY = e.clientY - lastPointerY;
      targetTiltY = THREE.MathUtils.clamp(deltaX * 0.012, -0.35, 0.35);
      targetTiltX = THREE.MathUtils.clamp(deltaY * 0.012, -0.35, 0.35);

      lastPointerX = e.clientX;
      lastPointerY = e.clientY;
    } else if (!isPickedUp && !isReturning) {
      const r = stage.getBoundingClientRect();
      pointerX = ((e.clientX - r.left) / r.width - 0.5) * 2;
      pointerY = ((e.clientY - r.top) / r.height - 0.5) * 2;
    }
  });

  // Release mouse anywhere on the screen: springs smoothly back to original position
  window.addEventListener('pointerup', () => {
    if (isPickedUp && isDragging) {
      isDragging = false;
      isReturning = true;
      document.querySelectorAll('.scan-hit').forEach(el => el.classList.remove('scan-hit'));
      if (scanTarget) scanTarget.textContent = 'page surface';
    }
  });

  // Render loop with idle physics and spring return
  const clock = new THREE.Clock();
  function animate() {
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    if (isReturning) {
      // Elastic spring physics back to home position
      rig.position.x += (homePos.x - rig.position.x) * 0.14;
      rig.position.y += (homePos.y - rig.position.y) * 0.14;
      rig.position.z += (homePos.z - rig.position.z) * 0.14;

      rig.rotation.x += (homeRot.x - rig.rotation.x) * 0.14;
      rig.rotation.y += (homeRot.y - rig.rotation.y) * 0.14;
      rig.rotation.z += (homeRot.z - rig.rotation.z) * 0.14;

      // X-ray lens simultaneously glides back smoothly to home screen coords
      if (xrayLens) {
        const home = getHomeScreenCoords();
        const currentLensX = parseFloat(xrayLens.style.left) || home.x;
        const currentLensY = parseFloat(xrayLens.style.top) || home.y;

        const nextLensX = currentLensX + (home.x - currentLensX) * 0.14;
        const nextLensY = currentLensY + (home.y - currentLensY) * 0.14;

        xrayLens.style.left = `${nextLensX}px`;
        xrayLens.style.top = `${nextLensY}px`;
      }

      const d = Math.abs(rig.position.x - homePos.x) + Math.abs(rig.position.y - homePos.y) + Math.abs(rig.position.z - homePos.z);
      if (d < 0.015) {
        rig.position.set(homePos.x, homePos.y, homePos.z);
        rig.rotation.set(homeRot.x, homeRot.y, homeRot.z);
        if (xrayLens) {
          const home = getHomeScreenCoords();
          xrayLens.style.left = `${home.x}px`;
          xrayLens.style.top = `${home.y}px`;
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
    const w = stage.clientWidth;
    const h = stage.clientHeight;
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
    if (!isPickedUp) dockStageToPlaceholder();
    else onResize();
  });
  onResize();
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
  } else if (viewName === 'workspace') {
    document.getElementById('view-workspace').classList.remove('hidden');
    btnWorkspace.className = activeClass;
  } else if (viewName === 'history') {
    document.getElementById('view-history').classList.remove('hidden');
    btnHistory.className = activeClass;
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
    const res = await fetch('/api/presets');
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

function loadPreset(idx) {
  if (idx === "") return;
  const item = presetsList[idx];
  if (item) {
    document.getElementById('input-headline').value = item.ad_headline;
    document.getElementById('input-desc').value = item.ad_description;
    document.getElementById('input-html').value = item.html;
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
    };
    reader.readAsText(file);
  }
}

async function executeAudit() {
  const headline = document.getElementById('input-headline').value.trim();
  const desc = document.getElementById('input-desc').value.trim();
  const html = document.getElementById('input-html').value.trim();

  const runBtn = document.getElementById('btn-run-audit');
  runBtn.disabled = true;
  runBtn.innerHTML = `
    <span class="inline-block w-3.5 h-3.5 border-2 border-[var(--paper)] border-t-transparent rounded-full animate-spin"></span>
    <span class="font-mono text-xs">AUDITING DOM...</span>
  `;

  try {
    const resp = await fetch('/api/audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ad_headline: headline,
        ad_description: desc,
        landing_page_html: html
      })
    });

    if (!resp.ok) {
      throw new Error(`Server returned status ${resp.status}`);
    }

    const data = await resp.json();
    currentAuditResult = data;

    auditHistory.unshift({
      timestamp: new Date().toLocaleTimeString(),
      headline: headline,
      score: data.match_score,
      grade: data.grade,
      data: data
    });
    document.getElementById('history-count').textContent = auditHistory.length;

    renderAuditResults(data);
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

function renderAuditResults(data) {
  const container = document.getElementById('results-container');
  container.classList.remove('hidden');

  const liabilityBanner = document.getElementById('liability-banner');
  if (data.has_critical_marketing_liability) {
    liabilityBanner.classList.remove('hidden');
  } else {
    liabilityBanner.classList.add('hidden');
  }

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

  document.getElementById('findings-count').textContent = data.findings.length;

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
          <p class="leading-relaxed font-sans">${f.regulatory_review_note}</p>
        </div>
      `;
    }

    let evidenceHtml = '';
    if (f.primary_evidence) {
      const offsetsStr = f.primary_evidence.source_start_offset !== null && f.primary_evidence.source_start_offset !== undefined ? ` | Offsets: [${f.primary_evidence.source_start_offset}:${f.primary_evidence.source_end_offset}]` : '';
      const selectorStr = f.primary_evidence.selector_path ? ` | Selector: <code>${f.primary_evidence.selector_path}</code>` : '';
      evidenceHtml = `
        <div class="mt-4 p-4 rounded-xl bg-[var(--paper)] precision-border-l border-l-[var(--accent)] border border-[var(--line-border)]">
          <div class="flex flex-wrap items-center justify-between text-xs font-mono text-[var(--ink-secondary)] mb-1.5">
            <span class="font-bold text-[var(--accent)] flex items-center space-x-1.5">
              <i data-lucide="check" class="w-3.5 h-3.5"></i>
              <span>VERIFIED IN SOURCE DOM</span>
            </span>
            <span>ZONE: <b class="text-[var(--ink)]">${f.primary_evidence.dom_zone}</b> (&lt;${f.primary_evidence.tag_name}&gt;, Block ${f.primary_evidence.block_id}${selectorStr})${offsetsStr}</span>
          </div>
          <p class="font-mono text-sm text-[var(--ink)] italic pl-1">"${f.primary_evidence.quote}"</p>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <div class="flex items-center space-x-2.5">
            <span class="status-pill ${statusClass}">${f.status}</span>
            <span class="text-[11px] font-mono text-[var(--ink-muted)]">CLAIM ${f.claim_id}</span>
          </div>
          <h4 class="editorial-title text-2xl text-[var(--ink)] mt-2">${f.ad_claim_text}</h4>
          <p class="text-xs text-[var(--ink-secondary)] mt-1.5 leading-relaxed font-sans">${f.explanation}</p>
        </div>

        <div class="text-left md:text-right text-xs font-mono text-[var(--ink-muted)] shrink-0 space-y-0.5">
          <div>REASON: <b class="text-[var(--ink)]">${f.reason_code}</b></div>
          <div>SEVERITY: <b class="${isCritical ? 'text-[var(--accent)]' : 'text-[var(--ink)]'}">${f.severity}</b></div>
          <div>MATERIALITY: <b class="text-[var(--ink)]">${f.claim_materiality}</b></div>
        </div>
      </div>

      ${regulatoryHtml}
      ${evidenceHtml}

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 pt-4 precision-border-t text-xs">
        <div class="p-4 rounded-xl bg-[var(--paper)] border border-[var(--line-border)]">
          <div class="font-mono font-bold text-[var(--ink)] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
            <i data-lucide="edit-2" class="w-3.5 h-3.5 text-[var(--accent)]"></i>
            <span>Recommended Ad Adjustment:</span>
          </div>
          <p class="text-[var(--ink-secondary)] leading-relaxed">${f.recommended_ad_fix}</p>
        </div>

        <div class="p-4 rounded-xl bg-[var(--paper)] border border-[var(--line-border)]">
          <div class="font-mono font-bold text-[var(--ink)] uppercase tracking-wider mb-1 flex items-center space-x-1.5">
            <i data-lucide="layout" class="w-3.5 h-3.5 text-[var(--accent)]"></i>
            <span>Recommended Page Adjustment:</span>
          </div>
          <p class="text-[var(--ink-secondary)] leading-relaxed">${f.recommended_page_fix}</p>
        </div>
      </div>
    `;

    list.appendChild(card);
  });

  lucide.createIcons();
}

function renderHistory() {
  const list = document.getElementById('history-list');
  if (auditHistory.length === 0) {
    list.innerHTML = '<p class="text-[var(--ink-muted)] text-sm font-mono italic">No audits performed in this session yet.</p>';
    return;
  }
  list.innerHTML = '';
  auditHistory.forEach(h => {
    const item = document.createElement('div');
    item.className = "editorial-card p-5 rounded-2xl flex items-center justify-between";
    item.innerHTML = `
      <div>
        <h4 class="editorial-title text-xl text-[var(--ink)]">${h.headline}</h4>
        <span class="text-xs font-mono text-[var(--ink-muted)]">Timestamp: ${h.timestamp} · Grade: <b>${h.grade}</b></span>
      </div>
      <div class="text-3xl editorial-title text-[var(--accent)]">${h.score}/100</div>
    `;
    list.appendChild(item);
  });
}

function clearHistory() {
  auditHistory = [];
  document.getElementById('history-count').textContent = '0';
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
