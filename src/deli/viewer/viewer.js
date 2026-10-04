// The viewer pane: the bed of the chosen printer and the parts on it, placed as `deli slice`
// places them, or, once `deli slice` has run and until the print changes again, what it wrote:
// every extrusion in the G-code, supports included, coloured by what it is for. It is a viewer
// only. It asks the server for /state twice a second and redraws when the version changes, so
// `deli scale`, `deli rotate`, `deli slice` and edits to deli.toml show up here.

import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const info = document.getElementById('info');
const layerBar = document.getElementById('layers');
const layerSlider = document.getElementById('layer');
const layerLabel = document.getElementById('layerLabel');
const pauseTicks = document.getElementById('pauseTicks');

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1b1e23);
const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 1, 5000);
camera.up.set(0, 0, 1); // printers are z-up
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(devicePixelRatio);
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.zoomToCursor = true;  // towards what is under the pointer, not the middle of the bed

scene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(-1, -2, 3);
scene.add(sun);

let bedGroup = null;
let partMesh = null;
let paths = null;  // the sliced print: what is drawn, and where each layer ends in it
let showTravel = false;
let framed = false;
let version = null;
const material = new THREE.MeshStandardMaterial({ color: 0xf28c28, roughness: 0.6, metalness: 0.05 });

function bounds(points) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}

// The bed outline, a 10 mm grid over its extent, and the edges of the print volume.
function drawBed(points, height) {
  if (bedGroup) scene.remove(bedGroup);
  bedGroup = new THREE.Group();
  const b = bounds(points);

  const shape = new THREE.Shape(points.map(p => new THREE.Vector2(p[0], p[1])));
  const plate = new THREE.Mesh(new THREE.ShapeGeometry(shape),
    new THREE.MeshBasicMaterial({ color: 0x262a31, side: THREE.DoubleSide }));
  plate.position.z = -0.05;
  bedGroup.add(plate);

  const grid = [];
  for (let x = Math.ceil(b.minX / 10) * 10; x <= b.maxX; x += 10) grid.push(x, b.minY, 0, x, b.maxY, 0);
  for (let y = Math.ceil(b.minY / 10) * 10; y <= b.maxY; y += 10) grid.push(b.minX, y, 0, b.maxX, y, 0);
  const gridGeometry = new THREE.BufferGeometry();
  gridGeometry.setAttribute('position', new THREE.Float32BufferAttribute(grid, 3));
  bedGroup.add(new THREE.LineSegments(gridGeometry, new THREE.LineBasicMaterial({ color: 0x3a3f48 })));

  const outline = new THREE.BufferGeometry().setFromPoints(points.map(p => new THREE.Vector3(p[0], p[1], 0.01)));
  bedGroup.add(new THREE.LineLoop(outline, new THREE.LineBasicMaterial({ color: 0x8a9099 })));

  if (height > 0) {
    const top = points.map(p => new THREE.Vector3(p[0], p[1], height));
    const posts = [];
    points.forEach((p, i) => posts.push(new THREE.Vector3(p[0], p[1], 0), top[i]));
    const faint = new THREE.LineBasicMaterial({ color: 0x3a3f48 });
    bedGroup.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(top), faint));
    bedGroup.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(posts), faint));
  }
  scene.add(bedGroup);

  if (!framed) {
    const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2, span = Math.max(b.maxX - b.minX, b.maxY - b.minY);
    controls.target.set(cx, cy, span * 0.15);
    camera.position.set(cx + span * 0.9, cy - span * 1.1, span * 0.8);
    controls.update();
    framed = true;
  }
}

async function drawPart() {
  const response = await fetch('/mesh');
  if (!response.ok) throw new Error(await response.text());
  const data = await response.arrayBuffer();
  const [nVertices, nTriangles] = new Uint32Array(data, 0, 2);
  const vertices = new Float32Array(data, 8, nVertices * 3);
  const indices = new Uint32Array(data, 8 + nVertices * 12, nTriangles * 3);

  clearPrint();
  if (nTriangles === 0) return;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeVertexNormals();
  partMesh = new THREE.Mesh(geometry, material);
  scene.add(partMesh);
}

function clearPrint() {
  if (partMesh) { scene.remove(partMesh); partMesh.geometry.dispose(); partMesh = null; }
  if (paths) {
    scene.remove(paths.mesh, paths.travel);
    for (const drawn of [paths.mesh, paths.travel]) { drawn.geometry.dispose(); drawn.material.dispose(); }
    paths.mesh.dispose();
    paths = null;
  }
  layerBar.hidden = true;
}

// PrusaSlicer's preview colours, by its names for what an extrusion is for.
const ROLE_COLOURS = {
  'Perimeter': '#ffe64d', 'External perimeter': '#ff7d38', 'Overhang perimeter': '#1f1fff',
  'Internal infill': '#b03029', 'Solid infill': '#9654cc', 'Top solid infill': '#f04040',
  'Ironing': '#ff8c69', 'Bridge infill': '#4d80ba', 'Gap fill': '#ffffff', 'Skirt/Brim': '#00876e',
  'Support material': '#00ff00', 'Support material interface': '#008000', 'Wipe tower': '#b3e3ab',
  'Custom': '#5ed194',
};
const roleColour = name => ROLE_COLOURS[name] || '#e6b3b3';

// The sliced print: one box per extrusion, as wide and as high as the line it lays down, in
// printing order, so that drawing the first so many of them shows the print up to a layer.
// Travel moves are thin lines, shown when asked for. After each pause the colours change,
// lighter and back again, as a change of filament there would show.
async function drawToolpaths(roles, pauses) {
  const response = await fetch('/toolpaths');
  if (!response.ok) throw new Error(await response.text());
  const data = await response.arrayBuffer();
  const n = new Uint32Array(data, 0, 1)[0];
  const segments = new Float32Array(data, 4, n * 8);
  const layers = new Uint32Array(data, 4 + n * 32, n);
  const roleOf = new Uint8Array(data, 4 + n * 36, n);
  const travelRole = roles.indexOf('Travel');

  clearPrint();
  if (n === 0) return;
  let travels = 0;
  for (let i = 0; i < n; i++) if (roleOf[i] === travelRole) travels++;
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshLambertMaterial(), n - travels);
  mesh.frustumCulled = false;
  const travelPoints = new Float32Array(travels * 6);
  const colours = roles.map(name => new THREE.Color(roleColour(name)));
  const lighter = colours.map(colour => colour.clone().lerp(new THREE.Color(0xffffff), 0.55));
  const from = new THREE.Vector3(), along = new THREE.Vector3(), middle = new THREE.Vector3();
  const turn = new THREE.Quaternion(), size = new THREE.Vector3(), matrix = new THREE.Matrix4();
  const xAxis = new THREE.Vector3(1, 0, 0);
  // Per layer: how many extrusions and travel moves there are by its end, and its height.
  const ends = [], travelEnds = [], tops = [], used = new Set();
  let boxes = 0, lines = 0;
  for (let i = 0; i < n; i++) {
    const [x0, y0, z0, x1, y1, z1, width, height] = segments.subarray(i * 8, i * 8 + 8);
    const layer = layers[i];
    if (roleOf[i] === travelRole) {
      travelPoints.set([x0, y0, z0, x1, y1, z1], lines++ * 6);
      travelEnds[layer] = lines;
      continue;
    }
    from.set(x0, y0, z0);
    along.set(x1, y1, z1).sub(from);
    const length = along.length();
    middle.copy(from).addScaledVector(along, 0.5);
    middle.z -= height / 2;  // the nozzle rides on top of the line
    turn.setFromUnitVectors(xAxis, along.divideScalar(length));
    matrix.compose(middle, turn, size.set(length + width / 2, width, height));  // a little long, to close the corners
    mesh.setMatrixAt(boxes, matrix);
    // A pause after layer 30 comes before the layer numbered 30 here, where they count from 0.
    const pausesBelow = pauses.filter(after => after <= layer).length;
    mesh.setColorAt(boxes, (pausesBelow % 2 ? lighter : colours)[roleOf[i]]);
    used.add(roleOf[i]);
    ends[layer] = ++boxes;
    tops[layer] = z1;
  }
  for (let layer = 0; layer < ends.length; layer++) {  // a layer with nothing in it ends where the one before did
    ends[layer] ??= ends[layer - 1] ?? 0;
    travelEnds[layer] ??= travelEnds[layer - 1] ?? 0;
    tops[layer] ??= tops[layer - 1] ?? 0;
  }
  const travelGeometry = new THREE.BufferGeometry();
  travelGeometry.setAttribute('position', new THREE.BufferAttribute(travelPoints, 3));
  const travel = new THREE.LineSegments(travelGeometry, new THREE.LineBasicMaterial({ color: 0x8a9099 }));
  travel.frustumCulled = false;
  travel.visible = showTravel;
  scene.add(mesh, travel);
  paths = { mesh, travel, ends, travelEnds, tops, pauses };

  layerSlider.max = ends.length;
  layerSlider.value = ends.length;
  pauseTicks.innerHTML = pauses.map(after => `<option value="${after}"></option>`).join('');
  layerBar.hidden = false;
  showLayers();
  info.innerHTML += '<br>' + roles.map((name, role) => used.has(role)
    ? `<br><span class="swatch" style="background: ${roleColour(name)}"></span>${name}` : '').join('')
    + (pauses.length ? '<br><span class="dim">lighter between one pause and the next</span>' : '')
    + `<div class="options"><label><input type="checkbox" id="travel"${showTravel ? ' checked' : ''}> Show travel moves</label></div>`;
}

function showLayers() {
  const layer = Number(layerSlider.value);
  paths.mesh.count = paths.ends[layer - 1];
  paths.travel.geometry.setDrawRange(0, paths.travelEnds[layer - 1] * 2);
  layerLabel.textContent = `layer ${layer} of ${paths.ends.length}, ${mm(paths.tops[layer - 1])} mm`
    + (paths.pauses.includes(layer) ? ', then a pause' : '');
}
layerSlider.addEventListener('input', showLayers);
info.addEventListener('change', event => {  // the info box is rewritten on every redraw, so the box listens for its checkbox
  if (event.target.id !== 'travel') return;
  showTravel = event.target.checked;
  if (paths) paths.travel.visible = showTravel;
});

const mm = n => Math.round(n * 100) / 100;
const pct = f => `${Math.round(f * 1000) / 10}%`;

function describe(state) {
  const lines = [];
  for (const part of state.parts) {
    lines.push(`<b>${part.file}</b>${part.count > 1 ? ` × ${part.count}` : ''}`);
    if (part.size) lines.push(part.size.map(mm).join(' × ') + ' mm');
    const s = part.scale, r = part.rotate;
    if (s.some(f => f !== 1)) lines.push(`<span class="dim">scale</span> ${s.every(f => f === s[0]) ? pct(s[0]) : s.map(pct).join(' × ')}`);
    const turns = ['x', 'y', 'z'].map((a, i) => r[i] ? `${r[i]}° about ${a}` : null).filter(Boolean);
    if (turns.length) lines.push(`<span class="dim">rotate</span> ${turns.join(', ')}`);
    if (part.at) lines.push(`<span class="dim">at</span> ${part.at.map(mm).join(', ')} mm`);
    if (part.z) lines.push(`<span class="dim">${part.z < 0 ? 'sunk' : 'raised'}</span> ${mm(Math.abs(part.z))} mm`);
  }
  if (!state.parts.length) lines.push('No part yet. <span class="dim">deli add &lt;file&gt;</span>');
  lines.push(state.printer ? `<span class="dim">printer</span> ${state.printer}`
                           : '<span class="dim">No printer chosen: deli printer &lt;name&gt;</span>');
  if (state.filament) lines.push(`<span class="dim">filament</span> ${state.filament}`);
  if (state.pauses.length) lines.push(`<span class="dim">pauses after layer</span> ${state.pauses.join(', ')}`);
  if (state.gcode) lines.push(`<span class="dim">sliced</span> ${state.gcode}`);
  if (state.error) lines.push(`<span class="error">${state.error}</span>`);
  info.innerHTML = lines.join('<br>');
}

async function refresh() {
  try {
    const state = await (await fetch('/state')).json();
    if (state.version !== version) {
      version = state.version;
      drawBed(state.bed, state.height);
      describe(state);
      await (state.gcode ? drawToolpaths(state.roles, state.pauses) : drawPart());
    }
  } catch (err) {
    // A fetch that cannot reach the server at all fails with a TypeError: the viewer has gone.
    info.innerHTML = `<span class="error">${err instanceof TypeError ? 'The viewer has stopped. Run <b>deli view</b> again.' : err.message}</span>`;
  }
}

// The axes at the bed's origin, lying on the plate: x red, y green, z blue, the convention
// three.js, Blender and most CAD tools share.
const AXES_SIZE = 20;  // mm of arrow per unit below
function letter(text, color) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.font = 'bold 44px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = color;
  ctx.fillText(text, 32, 34);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas) }));
  sprite.scale.set(0.55, 0.55, 1);
  return sprite;
}
function arrow(direction, color) {
  // A solid shaft and head, so the arrow has some width at any screen density.
  const material = new THREE.MeshBasicMaterial({ color });
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.78, 12), material);
  shaft.position.y = 0.39;
  const head = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.26, 16), material);
  head.position.y = 0.78 + 0.13;
  const group = new THREE.Group();
  group.add(shaft, head);
  group.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);  // the cylinder's axis is y
  return group;
}
const axes = new THREE.Group();
axes.add(new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12), new THREE.MeshBasicMaterial({ color: 0x9aa0a8 })));
for (const [name, color, dir] of [['x', '#e5484d', [1, 0, 0]], ['y', '#46a758', [0, 1, 0]], ['z', '#3e8fd9', [0, 0, 1]]]) {
  const direction = new THREE.Vector3(...dir);
  axes.add(arrow(direction, color));
  const label = letter(name, color);
  label.center.set(0.5, 0);  // standing on its point, so the plate does not cut it
  label.position.copy(direction).multiplyScalar(name === 'z' ? 1.1 : 1.38);
  axes.add(label);
}
axes.scale.setScalar(AXES_SIZE);
scene.add(axes);

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
refresh();
setInterval(refresh, 500);
