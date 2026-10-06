// The viewer pane: the bed of the chosen printer and the parts on it, placed as `deli slice`
// places them, or, once `deli slice` has run and until the print changes again, what it wrote:
// every extrusion in the G-code, supports included, coloured by what it is for. It is a viewer
// only, though it can measure what it shows. It asks the server for /state twice a second and redraws when the version changes, so
// `deli scale`, `deli rotate`, `deli slice` and edits to deli.toml show up here.

import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const info = document.getElementById('info');
const layerBar = document.getElementById('layers');
const layerSlider = document.getElementById('layer');
const layerLabel = document.getElementById('layerLabel');
const pauseTicks = document.getElementById('pauseTicks');
const sectionBar = document.getElementById('section');
const cutSlider = document.getElementById('cut');
const cutLabel = document.getElementById('cutLabel');
const measurement = document.getElementById('measurement');

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
let partExtras = [];  // drawn with the part: its inside, where a section cuts it open, and its overhangs
let overhangMesh = null;
let overhang = null;  // from /state: the slope below which supports hold a face up
let showOverhangs = false;
let paths = null;  // the sliced print: what is drawn, and where each layer ends in it
let framed = false;
let version = null;
// A section: what is above the cut is not drawn, and the part's inside shows dark.
const NO_CUT = 1e6;
const ceiling = new THREE.Plane(new THREE.Vector3(0, 0, -1), NO_CUT);
const material = new THREE.MeshStandardMaterial({ color: 0xf28c28, roughness: 0.6, metalness: 0.05, clippingPlanes: [ceiling] });
const insideMaterial = new THREE.MeshBasicMaterial({ color: 0x5c3510, side: THREE.BackSide, clippingPlanes: [ceiling] });
const overhangMaterial = new THREE.MeshBasicMaterial({ color: 0xe5484d, clippingPlanes: [ceiling],  // unlit: they face away from the light
  polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });

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
  overhangMesh = new THREE.Mesh(overhangs(geometry), overhangMaterial);
  overhangMesh.visible = showOverhangs;
  partExtras = [new THREE.Mesh(geometry, insideMaterial), overhangMesh];
  scene.add(partMesh, ...partExtras);

  let top = 0;
  for (let i = 2; i < vertices.length; i += 3) top = Math.max(top, vertices[i]);
  cutSlider.max = Math.ceil(top * 10) / 10;
  cutSlider.value = cutSlider.max;
  sectionBar.hidden = false;
  showSection();
}

// The triangles that look down at less than the overhang angle from level, so that supports
// would hold them up; not those on the bed, nor below it.
function overhangs(geometry) {
  const position = geometry.attributes.position.array, index = geometry.index.array;
  const limit = Math.cos((overhang?.angle ?? 45) * Math.PI / 180);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), normal = new THREE.Vector3();
  const picked = [];
  for (let t = 0; t < index.length; t += 3) {
    a.fromArray(position, index[t] * 3);
    b.fromArray(position, index[t + 1] * 3);
    c.fromArray(position, index[t + 2] * 3);
    if (Math.max(a.z, b.z, c.z) <= 0.01) continue;
    normal.subVectors(c, b).cross(a.sub(b)).normalize();  // as three.js finds a face's normal
    if (-normal.z > limit) picked.push(index[t], index[t + 1], index[t + 2]);
  }
  const shown = new THREE.BufferGeometry();
  shown.setAttribute('position', geometry.attributes.position);
  shown.setIndex(picked);
  return shown;
}

function showSection() {
  const at = Number(cutSlider.value), top = Number(cutSlider.max);
  ceiling.constant = at >= top ? NO_CUT : at;
  cutLabel.textContent = at >= top ? 'no section' : `cut at ${mm(at)} mm`;
}
cutSlider.addEventListener('input', showSection);

function clearPrint() {
  if (partMesh) {
    scene.remove(partMesh, ...partExtras);
    partMesh.geometry.dispose();
    overhangMesh.geometry.dispose();
    partMesh = overhangMesh = null;
    partExtras = [];
  }
  sectionBar.hidden = true;
  ceiling.constant = NO_CUT;
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
  'Custom': '#5ed194', 'Travel': '#8a9099',
};
const roleColour = name => ROLE_COLOURS[name] || '#e6b3b3';

// What the sliced print can be coloured by: what each extrusion is for, or one of these, on
// PrusaSlicer's scale from blue for the least to red for the most.
const MEASURES = {
  role: { name: 'Feature' },
  speed: { name: 'Speed', unit: 'mm/s', of: (p, i) => p.boxSpeed[i] },
  flow: { name: 'Flow', unit: 'mm³/s', of: (p, i) => p.boxFlow[i] },
  layerTime: { name: 'Layer time', unit: 's', of: (p, i) => p.layerTimes[p.boxLayer[i]] },
};
const SCALE = ['#0b2c7a', '#135985', '#1c8891', '#04d60f', '#aaf200', '#fcf903', '#f5ce0a', '#d16830', '#c2523c', '#942616']
  .map(c => new THREE.Color(c));
function onScale(f, out) {
  const x = Math.min(Math.max(f, 0), 1) * (SCALE.length - 1), i = Math.min(Math.floor(x), SCALE.length - 2);
  return out.copy(SCALE[i]).lerp(SCALE[i + 1], x - i);
}
let colourBy = 'role';
try { if (MEASURES[localStorage.getItem('colourBy')]) colourBy = localStorage.getItem('colourBy'); } catch {}
const hiddenRoles = new Set(['Travel']);  // by name, so they stay hidden when the print is sliced again
let onlyLayer = false;

// Hiding a role: each extrusion carries its role, and the vertex shader puts those of a
// hidden role outside the view, so nothing has to be rebuilt.
const hiddenMask = { value: 0 };
function withHiddenRoles(material) {
  material.onBeforeCompile = shader => {
    shader.uniforms.hiddenRoles = hiddenMask;
    shader.vertexShader = 'attribute float role;\nuniform uint hiddenRoles;\n' + shader.vertexShader.replace('#include <project_vertex>',
      '#include <project_vertex>\n  if (((hiddenRoles >> uint(role)) & 1u) == 1u) gl_Position = vec4(0.0, 0.0, 2.0, 1.0);');
  };
  return material;
}
// Only this layer: what is below it is cut away.
const floor = new THREE.Plane(new THREE.Vector3(0, 0, 1), NO_CUT);
renderer.localClippingEnabled = true;

function duration(seconds) {
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)} h ${String(Math.round(seconds % 3600 / 60)).padStart(2, '0')} min`;
  return seconds >= 60 ? `${Math.round(seconds / 60)} min` : `${Math.round(seconds)} s`;
}

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
  const rates = new Float32Array(data, 4 + n * 32, n * 2);
  const layers = new Uint32Array(data, 4 + n * 40, n);
  const roleOf = new Uint8Array(data, 4 + n * 44, n);
  const times = n ? JSON.parse(new TextDecoder().decode(new Uint8Array(data, 4 + n * 45))) : null;
  const travelRole = roles.indexOf('Travel');

  clearPrint();
  if (n === 0) return;
  let travels = 0;
  for (let i = 0; i < n; i++) if (roleOf[i] === travelRole) travels++;
  const count = n - travels;
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1),
    withHiddenRoles(new THREE.MeshLambertMaterial({ clippingPlanes: [floor] })), count);
  mesh.frustumCulled = false;
  const travelPoints = new Float32Array(travels * 6);
  const boxRole = new Uint8Array(count), boxLayer = new Uint32Array(count), lighter = new Uint8Array(count);
  const boxSpeed = new Float32Array(count), boxFlow = new Float32Array(count);
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
    lighter[boxes] = pauses.filter(after => after <= layer).length % 2;
    boxRole[boxes] = roleOf[i];
    boxLayer[boxes] = layer;
    boxSpeed[boxes] = rates[i * 2];
    boxFlow[boxes] = rates[i * 2 + 1];
    used.add(roleOf[i]);
    ends[layer] = ++boxes;
    tops[layer] = z1;
  }
  for (let layer = 0; layer < ends.length; layer++) {  // a layer with nothing in it ends where the one before did
    ends[layer] ??= ends[layer - 1] ?? 0;
    travelEnds[layer] ??= travelEnds[layer - 1] ?? 0;
    tops[layer] ??= tops[layer - 1] ?? 0;
  }
  mesh.geometry.setAttribute('role', new THREE.InstancedBufferAttribute(Float32Array.from(boxRole), 1));
  mesh.setColorAt(0, new THREE.Color());  // makes the colour buffer, filled by colourPaths
  mesh.computeBoundingSphere();  // around every extrusion, before the slider hides some, for picking points on them
  const travelGeometry = new THREE.BufferGeometry();
  travelGeometry.setAttribute('position', new THREE.BufferAttribute(travelPoints, 3));
  const travel = new THREE.LineSegments(travelGeometry, new THREE.LineBasicMaterial({ color: ROLE_COLOURS.Travel, clippingPlanes: [floor] }));
  travel.frustumCulled = false;
  scene.add(mesh, travel);
  if (travels) used.add(travelRole);
  paths = { mesh, travel, ends, travelEnds, tops, pauses, roles, used, boxRole, boxLayer, boxSpeed, boxFlow, lighter,
            roleTimes: times.roles, layerTimes: times.layers };

  layerSlider.max = ends.length;
  layerSlider.value = ends.length;
  pauseTicks.innerHTML = pauses.map(after => `<option value="${after}"></option>`).join('');
  layerBar.hidden = false;
  showRoles();
  colourPaths();
  showLayers();
  info.innerHTML += `<div id="legend">${legend()}</div>`;
}

// Colours every extrusion by what it is for, or by where its measure falls between the least
// and the most among the roles shown.
function colourPaths() {
  const { mesh } = paths, measure = MEASURES[colourBy], colour = new THREE.Color();
  if (!measure.of) {
    const colours = paths.roles.map(name => new THREE.Color(roleColour(name)));
    const lighter = colours.map(c => c.clone().lerp(new THREE.Color(0xffffff), 0.55));
    for (let i = 0; i < paths.boxRole.length; i++) mesh.setColorAt(i, (paths.lighter[i] ? lighter : colours)[paths.boxRole[i]]);
  } else {
    let least = Infinity, most = -Infinity;
    for (let i = 0; i < paths.boxRole.length; i++) {
      if (hiddenRoles.has(paths.roles[paths.boxRole[i]])) continue;
      const value = measure.of(paths, i);
      least = Math.min(least, value);
      most = Math.max(most, value);
    }
    paths.range = [least, most];
    for (let i = 0; i < paths.boxRole.length; i++)
      mesh.setColorAt(i, onScale(most > least ? (measure.of(paths, i) - least) / (most - least) : 0.5, colour));
  }
  mesh.instanceColor.needsUpdate = true;
}

function showRoles() {
  hiddenMask.value = paths.roles.reduce((mask, name, role) => hiddenRoles.has(name) ? mask | (1 << role) : mask, 0);
  paths.travel.visible = !hiddenRoles.has('Travel');
}

// The roles in the print, each with the time it takes, to click to hide or show; and the
// scale, when the print is coloured by a measure.
function legend() {
  const measure = MEASURES[colourBy], total = paths.roleTimes.reduce((a, b) => a + b, 0);
  const rows = paths.roles.map((name, role) => paths.used.has(role) ? { name, role, time: paths.roleTimes[role] } : null)
    .filter(Boolean).sort((a, b) => b.time - a.time);
  const other = paths.roleTimes[paths.roles.length];
  return `<div class="colour-by">Colour by <select id="colourBy">${Object.entries(MEASURES).map(([key, m]) =>
      `<option value="${key}"${key === colourBy ? ' selected' : ''}>${m.name}</option>`).join('')}</select></div>`
    + (measure.of ? `<div class="scale" style="background: linear-gradient(to right, ${SCALE.map(c => '#' + c.getHexString()).join(', ')})"></div>`
        + `<div class="range"><span>${round(paths.range[0])}</span><span>${measure.unit}</span><span>${round(paths.range[1])}</span></div>` : '')
    + rows.map(({ name, time }) => `<div class="role${hiddenRoles.has(name) ? ' off' : ''}" data-role="${name}" title="Click to ${hiddenRoles.has(name) ? 'show' : 'hide'}">`
        + `<span class="swatch" style="background: ${roleColour(name)}"></span><span class="name">${name}</span>`
        + `<span class="time">${duration(time)}</span><span class="share">${Math.round(time / total * 100)}%</span></div>`).join('')
    + (other >= 1 ? `<div class="role fixed" title="Retracting, waiting, moving only up"><span class="swatch"></span><span class="name dim">Other moves</span>`
        + `<span class="time">${duration(other)}</span><span class="share">${Math.round(other / total * 100)}%</span></div>` : '')
    + `<div class="role fixed total"><span class="swatch"></span><span class="name">Total</span><span class="time">${duration(total)}</span><span class="share"></span></div>`
    + (paths.pauses.length && !measure.of ? '<div class="dim">lighter between one pause and the next</div>' : '');
}
const round = n => n >= 100 ? Math.round(n) : Math.round(n * 10) / 10;
function redrawLegend() {
  const box = document.getElementById('legend');
  if (box) box.innerHTML = legend();
}

function options() {
  return '<div class="options">'
    + (partMesh && overhang ? `<div id="overhangNote" class="dim"${showOverhangs ? '' : ' hidden'}>Red: faces that look down at less than `
        + `${Math.round(overhang.angle)}° from level, which supports hold up${overhang.auto ? ' (the automatic angle: half a wall\'s width per layer)' : ''}</div>` : '')
    + '<div class="tools">'
    + (partMesh ? `<button type="button" id="overhangs" title="Show overhangs" aria-pressed="${showOverhangs}">Overhangs</button>` : '')
    + `<button type="button" id="measuring" title="Measure (M)" aria-pressed="${measuring}">Measure</button>`
    + `<span class="units">${Object.keys(UNITS).map(name =>
        `<button type="button" data-units="${name}" aria-pressed="${name === units}">${name}</button>`).join('')}</span></div></div>`;
}

function showLayers() {
  const layer = Number(layerSlider.value);
  paths.mesh.count = paths.ends[layer - 1];
  paths.travel.geometry.setDrawRange(0, paths.travelEnds[layer - 1] * 2);
  floor.constant = onlyLayer && layer > 1 ? -(paths.tops[layer - 2] + 0.001) : NO_CUT;
  layerLabel.textContent = `layer ${layer} of ${paths.ends.length}, ${mm(paths.tops[layer - 1])} mm, `
    + duration(paths.layerTimes[layer - 1] ?? 0) + (paths.pauses.includes(layer) ? ', then a pause' : '');
}
layerSlider.addEventListener('input', showLayers);
document.getElementById('onlyLayer').addEventListener('change', event => {
  onlyLayer = event.target.checked;
  if (paths) showLayers();
});
// The info box is rewritten on every redraw, so the box listens for its buttons and rows.
info.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (button?.id === 'measuring') return setMeasuring(!measuring);
  if (button?.id === 'overhangs') {
    showOverhangs = !showOverhangs;
    button.setAttribute('aria-pressed', showOverhangs);
    document.getElementById('overhangNote').hidden = !showOverhangs;
    if (overhangMesh) overhangMesh.visible = showOverhangs;
    return;
  }
  if (button?.dataset.units) return setUnits(button.dataset.units);
  const row = event.target.closest('[data-role]');
  if (!row || !paths) return;
  const name = row.dataset.role;
  if (!hiddenRoles.delete(name)) hiddenRoles.add(name);
  showRoles();
  if (MEASURES[colourBy].of) colourPaths();  // the scale spans the roles shown
  redrawLegend();
});
info.addEventListener('change', event => {
  if (event.target.id !== 'colourBy' || !paths) return;
  colourBy = event.target.value;
  try { localStorage.setItem('colourBy', colourBy); } catch {}
  colourPaths();
  redrawLegend();
});

// Measuring: while it is on, a click on the part or on the sliced print pins one end of a line,
// which then follows the pointer over what is drawn until a second click pins the other, and
// the line is labelled with its length and how far apart its ends are along each axis, in
// millimetres or inches. On the part, an end snaps to a corner of the triangle under the
// pointer when one is within a few pixels. A third click starts again; Esc clears; a right-click
// clears and turns measuring off. The points
// are dropped when the print changes, since what they were on may have moved.
let measuring = false;
const picks = [];
let loose = null;  // where the free end of the line is, between the first click and the second
let pointer = null;  // where the pointer has moved to since the free end last followed it
const UNITS = { mm: { per: 1, places: 2 }, in: { per: 25.4, places: 3 } };
let units = 'mm';
try { units = UNITS[localStorage.getItem('units')] ? localStorage.getItem('units') : 'mm'; } catch {}
const length = n => { const { per, places } = UNITS[units]; return (n / per).toFixed(places).replace(/\.?0+$/, ''); };
const SNAP_PIXELS = 10;
const raycaster = new THREE.Raycaster();
const measured = new THREE.Group();
scene.add(measured);
const dot = (() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 32;
  const ctx = canvas.getContext('2d');
  ctx.arc(16, 16, 12, 0, 2 * Math.PI);
  ctx.fillStyle = '#fff';
  ctx.fill();
  ctx.lineWidth = 4;
  ctx.strokeStyle = '#1b1e23';
  ctx.stroke();
  return new THREE.PointsMaterial({ map: new THREE.CanvasTexture(canvas), size: 12, sizeAttenuation: false,
                                    transparent: true, depthTest: false });
})();
const ruler = new THREE.LineBasicMaterial({ color: 0xffffff, depthTest: false });

function onScreen(point) {
  const p = point.clone().project(camera);
  return { x: (p.x + 1) / 2 * innerWidth, y: (1 - p.y) / 2 * innerHeight, behind: p.z > 1 };
}

// The point on what is drawn under the pointer, or null.
function pickAt(x, y) {
  const target = partMesh ?? paths?.mesh;
  if (!target) return null;
  raycaster.setFromCamera(new THREE.Vector2(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2), camera);
  const hit = raycaster.intersectObject(target, false).find(hit => target === partMesh
    ? ceiling.distanceToPoint(hit.point) >= 0
    : (!hiddenRoles.has(paths.roles[paths.boxRole[hit.instanceId]]) && floor.distanceToPoint(hit.point) >= 0));
  if (!hit) return null;
  if (target !== partMesh) return hit.point;
  const position = partMesh.geometry.attributes.position;
  let best = hit.point, nearest = SNAP_PIXELS;
  for (const index of [hit.face.a, hit.face.b, hit.face.c]) {
    const corner = new THREE.Vector3().fromBufferAttribute(position, index);
    const s = onScreen(corner), away = Math.hypot(s.x - x, s.y - y);
    if (away < nearest) { best = corner; nearest = away; }
  }
  return best;
}

function drawMeasurement() {
  for (const drawn of measured.children) drawn.geometry.dispose();
  measured.clear();
  const ends = loose ? [picks[0], loose] : picks;
  measurement.hidden = !ends.length;
  if (!ends.length) return;
  const geometry = new THREE.BufferGeometry().setFromPoints(ends);
  const shown = [new THREE.Points(geometry, dot)];
  if (ends.length === 2) shown.push(new THREE.Line(geometry.clone(), ruler));
  for (const drawn of shown) { drawn.renderOrder = 1; measured.add(drawn); }  // over the part, so never hidden by it
  const [a, b] = ends;
  measurement.innerHTML = b
    ? `<b>${length(a.distanceTo(b))} ${units}</b><br>` + ['x', 'y', 'z'].map(axis =>
        `<span class="dim">Δ${axis}</span> ${length(Math.abs(b[axis] - a[axis]))}`).join(' ')
    : ['x', 'y', 'z'].map(axis => `<span class="dim">${axis}</span> ${length(a[axis])}`).join(' ') + ` ${units}`;
  placeMeasurement();
}

function placeMeasurement() {  // beside the middle of the line, or the one point, wherever the camera has gone
  const ends = loose ? [picks[0], loose] : picks;
  if (!ends.length) return;
  const s = onScreen(ends.length === 2 ? ends[0].clone().lerp(ends[1], 0.5) : ends[0]);
  measurement.hidden = s.behind;
  measurement.style.left = `${s.x}px`;
  measurement.style.top = `${s.y}px`;
}

function clearMeasurement() {
  picks.length = 0;
  loose = null;
  drawMeasurement();
}

function setMeasuring(on) {
  measuring = on;
  renderer.domElement.style.cursor = on ? 'crosshair' : '';
  document.getElementById('measuring')?.setAttribute('aria-pressed', on);
  if (!on) clearMeasurement();
}

function setUnits(name) {
  units = name;
  try { localStorage.setItem('units', name); } catch {}
  for (const button of info.querySelectorAll('[data-units]')) button.setAttribute('aria-pressed', button.dataset.units === name);
  drawMeasurement();
}

// Once a frame at most, since picking among a large print's extrusions takes a while.
function followPointer() {
  if (!pointer) return;
  loose = pickAt(...pointer);
  pointer = null;
  drawMeasurement();
}

// A click marks a point and a right-click stops measuring; a drag, with either button, still
// turns or moves the view.
let pressedAt = null;
renderer.domElement.addEventListener('pointerdown', event => {
  pressedAt = [event.clientX, event.clientY];
});
renderer.domElement.addEventListener('pointerup', event => {
  if (!measuring || !pressedAt || Math.hypot(event.clientX - pressedAt[0], event.clientY - pressedAt[1]) > 4) return;
  if (event.button === 2) return setMeasuring(false);
  if (event.button !== 0) return;
  const point = pickAt(event.clientX, event.clientY);
  if (!point) return;
  if (picks.length === 2) picks.length = 0;
  picks.push(point.clone());
  loose = pointer = null;
  drawMeasurement();
});
renderer.domElement.addEventListener('pointermove', event => {
  if (measuring && picks.length === 1 && !event.buttons) pointer = [event.clientX, event.clientY];
});
renderer.domElement.addEventListener('pointerleave', () => {
  if (!loose) return;
  loose = pointer = null;
  drawMeasurement();
});
addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === 'm' || event.key === 'M') setMeasuring(!measuring);
  else if (event.key === 'Escape') clearMeasurement();
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
      overhang = state.overhang ?? null;
      clearMeasurement();
      drawBed(state.bed, state.height);
      describe(state);
      await (state.gcode ? drawToolpaths(state.roles, state.pauses) : drawPart());
      info.innerHTML += options();
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

renderer.setAnimationLoop(() => { controls.update(); followPointer(); placeMeasurement(); renderer.render(scene, camera); });
refresh();
setInterval(refresh, 500);
