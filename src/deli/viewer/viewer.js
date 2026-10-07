// The viewer pane: the bed of the chosen printer and the parts on it, placed as `deli slice`
// places them, and, while the G-code `deli slice` wrote is still the print's, every extrusion
// in it, supports included, coloured by what it is for; the model is then drawn faint over it,
// or hidden. One view, so every tool works on whatever is there. It changes a print only by
// running deli's own commands through the server (Apply). It asks the server for /state twice
// a second and redraws when the version changes, so `deli scale`, `deli rotate`, `deli slice`
// and edits to deli.toml show up here.

import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const info = document.getElementById('info');
const layerBar = document.getElementById('layers');
const layerSlider = document.getElementById('layer');
const layerLabel = document.getElementById('layerLabel');
const pauseTicks = document.getElementById('pauseTicks');
const onlyLayerBox = document.getElementById('onlyLayerBox');
const pauseHere = document.getElementById('pauseHere');
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
let partRanges = [];
let placed = null;
let overhang = null;  // from /state: the slope below which supports hold a face up
let showOverhangs = false;
let modelTop = 0;
let paths = null;  // the sliced print: what is drawn, and where each layer ends in it
let framed = false;
let version = null;
// Cutting: what is above the slider's height (the ceiling) is not drawn, and with "only this
// layer" what is below the layer (the floor); where the part is cut open its inside shows dark.
const NO_CUT = 1e6;
const ceiling = new THREE.Plane(new THREE.Vector3(0, 0, -1), NO_CUT);
const floor = new THREE.Plane(new THREE.Vector3(0, 0, 1), NO_CUT);
renderer.localClippingEnabled = true;
const MODEL_COLOUR = 0xf28c28;
const material = new THREE.MeshStandardMaterial({ color: MODEL_COLOUR, roughness: 0.6, metalness: 0.05, clippingPlanes: [ceiling, floor] });
const insideMaterial = new THREE.MeshBasicMaterial({ color: 0x5c3510, side: THREE.BackSide, clippingPlanes: [ceiling, floor] });
const overhangMaterial = new THREE.MeshBasicMaterial({ color: 0xe5484d, clippingPlanes: [ceiling, floor],  // unlit: they face away from the light
  polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });

// The model is shown whenever there is no G-code to show, or a tool that works on it is in
// use; over the G-code it is faint. Clicking Model in the legend overrules that until the
// print is sliced again or its G-code goes out of date.
let modelChoice = null;
const modelVisible = () => modelChoice ?? (!paths || mode === 'move' || mode === 'flat' || showOverhangs);
function showModel() {
  if (!partMesh) return;
  const visible = modelVisible(), faint = Boolean(paths);
  partMesh.visible = visible;
  partExtras[0].visible = visible && !faint;  // the inside
  overhangMesh.visible = visible && showOverhangs;
  if (material.transparent !== faint) {
    Object.assign(material, { transparent: faint, opacity: faint ? 0.3 : 1, depthWrite: !faint });
    material.needsUpdate = true;
  }
}

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

async function drawPart(parts) {
  const response = await fetch(`/mesh?plate=${plate}`);
  if (!response.ok) throw new Error(await response.text());
  const data = await response.arrayBuffer();
  const [nVertices, nTriangles, nCopies] = new Uint32Array(data, 0, 3);
  const vertices = new Float32Array(data, 12, nVertices * 3);
  const indices = new Uint32Array(data, 12 + nVertices * 12, nTriangles * 3);
  const counts = new Uint32Array(data, 12 + nVertices * 12 + nTriangles * 12, nCopies * 4);
  // Which vertices and triangles are each copy's, of which part, for the tools that act on one.
  partRanges = [];
  for (let i = 0, vertex = 0, triangle = 0; i < nCopies; i++) {
    const [index, copy, nv, nt] = counts.subarray(i * 4, i * 4 + 4);
    partRanges.push({ part: parts[index], copy, vertex, vertices: nv, triangle, triangles: nt });
    vertex += nv;
    triangle += nt;
  }
  placed = vertices.slice();  // where the parts are, before a drag moves one

  clearModel();
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
  modelTop = 0;
  for (let i = 2; i < vertices.length; i += 3) modelTop = Math.max(modelTop, vertices[i]);
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

function clearModel() {
  if (!partMesh) return;
  scene.remove(partMesh, ...partExtras);
  partMesh.geometry.dispose();
  overhangMesh.geometry.dispose();
  partMesh = overhangMesh = null;
  partExtras = [];
}

function clearPaths() {
  if (!paths) return;
  scene.remove(paths.mesh, paths.travel);
  for (const drawn of [paths.mesh, paths.travel]) { drawn.geometry.dispose(); drawn.material.dispose(); }
  paths.mesh.dispose();
  paths = null;
}

// The slider at the bottom: the layers of the G-code, cutting the model at the same height,
// or, with no G-code, a height to cut the model at.
function setUpSlider() {
  layerBar.hidden = !paths && !partMesh;
  onlyLayerBox.hidden = pauseHere.hidden = !paths;
  if (paths) {
    Object.assign(layerSlider, { min: 1, step: 1, max: paths.ends.length });
    layerSlider.setAttribute('list', 'pauseTicks');
    pauseTicks.innerHTML = paths.pauses.map(after => `<option value="${after}"></option>`).join('');
  } else {
    Object.assign(layerSlider, { min: 0, step: 0.1, max: Math.ceil(modelTop * 10) / 10 });
    layerSlider.removeAttribute('list');
  }
  layerSlider.value = layerSlider.max;
  showLayers();
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

function duration(seconds) {
  if (seconds >= 3600) return `${Math.floor(seconds / 3600)} h ${String(Math.round(seconds % 3600 / 60)).padStart(2, '0')} min`;
  return seconds >= 60 ? `${Math.round(seconds / 60)} min` : `${Math.round(seconds)} s`;
}

// The sliced print: one box per extrusion, as wide and as high as the line it lays down, in
// printing order, so that drawing the first so many of them shows the print up to a layer.
// Travel moves are thin lines, shown when asked for. After each pause the colours change,
// lighter and back again, as a change of filament there would show.
async function drawToolpaths(roles, pauses) {
  const response = await fetch(`/toolpaths?plate=${plate}`);
  if (!response.ok) throw new Error(await response.text());
  const data = await response.arrayBuffer();
  const n = new Uint32Array(data, 0, 1)[0];
  const segments = new Float32Array(data, 4, n * 8);
  const rates = new Float32Array(data, 4 + n * 32, n * 2);
  const layers = new Uint32Array(data, 4 + n * 40, n);
  const roleOf = new Uint8Array(data, 4 + n * 44, n);
  const times = n ? JSON.parse(new TextDecoder().decode(new Uint8Array(data, 4 + n * 45))) : null;
  const travelRole = roles.indexOf('Travel');

  clearPaths();
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

  showRoles();
  colourPaths();
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
    + (partMesh ? `<div class="role${modelVisible() ? '' : ' off'}" data-role="Model" title="Click to ${modelVisible() ? 'hide' : 'show'} the model">`
        + `<span class="swatch" style="background: #${new THREE.Color(MODEL_COLOUR).getHexString()}"></span><span class="name">Model</span></div>` : '')
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

// Whether any part or copy was moved, or kept to a plate, so that arranging would change something.
const handPlaced = () => (lastState?.parts ?? []).some(part => part.at.some(Boolean) || part.kept.some(Boolean));

function options() {
  return '<div class="options">'
    + (partMesh && overhang ? `<div id="overhangNote" class="dim"${showOverhangs ? '' : ' hidden'}>Red: faces that look down at less than `
        + `${Math.round(overhang.angle)}° from level, which supports hold up${overhang.auto ? ' (the automatic angle: half a wall\'s width per layer)' : ''}</div>` : '')
    // Arrange is there also when the parts cannot be drawn, as when one was moved off the bed.
    + (partMesh || handPlaced() ? '<div class="tools">'
        + (partMesh ? `<button type="button" id="overhangs" title="Show overhangs" aria-pressed="${showOverhangs}">Overhangs</button>` : '')
        + (handPlaced() ? '<button type="button" id="arrange" title="Arrange every part again, as before any was moved">Arrange</button>' : '')
        + '</div>' : '')
    + '<div class="tools">'
    + Object.entries(TOOLS).filter(([, tool]) => partMesh || !tool.needsPart).map(([name, tool]) =>
        `<button type="button" data-tool="${name}" title="${tool.title}" aria-pressed="${mode === name}">${tool.label}</button>`).join('')
    + `<span class="units">${Object.keys(UNITS).map(name =>
        `<button type="button" data-units="${name}" aria-pressed="${name === units}">${name}</button>`).join('')}</span></div></div>`;
}

function showLayers() {
  const at = Number(layerSlider.value), top = at >= Number(layerSlider.max);
  if (!paths) {
    ceiling.constant = top ? NO_CUT : at;
    floor.constant = NO_CUT;
    layerLabel.textContent = top ? 'no section' : `cut at ${mm(at)} mm`;
    return;
  }
  const layer = at;
  paths.mesh.count = paths.ends[layer - 1];
  paths.travel.geometry.setDrawRange(0, paths.travelEnds[layer - 1] * 2);
  ceiling.constant = top ? NO_CUT : paths.tops[layer - 1] + 0.001;  // the model cut where the print has got to
  floor.constant = onlyLayer && layer > 1 ? -(paths.tops[layer - 2] + 0.001) : NO_CUT;
  layerLabel.textContent = `layer ${layer} of ${paths.ends.length}, ${mm(paths.tops[layer - 1])} mm, `
    + duration(paths.layerTimes[layer - 1] ?? 0) + (paths.pauses.includes(layer) ? ', then a pause' : '');
}
layerSlider.addEventListener('input', showLayers);
document.getElementById('onlyLayer').addEventListener('change', event => {
  onlyLayer = event.target.checked;
  showLayers();
});
// The info box is rewritten on every redraw, so the box listens for its buttons and rows.
info.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (button?.dataset.plate) {
    plate = Number(button.dataset.plate);
    return lastState && redraw(lastState);
  }
  if (button?.dataset.tool) return setMode(mode === button.dataset.tool ? null : button.dataset.tool);
  if (button?.id === 'sliceNow') return startSlice(button);
  if (button?.id === 'arrange') return showCommand('deli arrange', 'to arrange every part again', [['arrange']]);
  if (button?.id === 'overhangs') {
    showOverhangs = !showOverhangs;
    button.setAttribute('aria-pressed', showOverhangs);
    document.getElementById('overhangNote').hidden = !showOverhangs;
    showModel();
    if (paths) redrawLegend();
    return;
  }
  if (button?.dataset.units) return setUnits(button.dataset.units);
  const row = event.target.closest('[data-role]');
  if (!row || !paths) return;
  const name = row.dataset.role;
  if (name === 'Model') {
    modelChoice = !modelVisible();
    showModel();
    return redrawLegend();
  }
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

// The tools a click on the view is for, one at a time: measuring, moving a part, or laying a
// face of one flat on the bed. The last two write the command that does it, to apply or copy,
// and need a part.
const TOOLS = {
  measure: { label: 'Measure', title: 'Measure between two points (M)' },
  move: { label: 'Move', title: 'Drag a part to where it should go', needsPart: true },
  flat: { label: 'Lay flat', title: 'Click the face of a part to lay on the bed', needsPart: true },
};
let mode = null;

// Measuring: a click on the part or on the sliced print pins one end of a line, which then
// follows the pointer over what is drawn until a second click pins the other, and the line is
// labelled with its length and how far apart its ends are along each axis, in millimetres or
// inches. On the part, an end snaps to a corner of the triangle under the pointer when one is
// within a few pixels. A third click starts again; Esc clears; a right-click clears and puts
// the tool down. The points are dropped when the print changes, since what they were on may
// have moved.
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

// The point on what is drawn under the pointer, the nearest of the model and the extrusions
// shown, or null.
const uncut = point => ceiling.distanceToPoint(point) >= 0 && floor.distanceToPoint(point) >= 0;
function pickAt(x, y) {
  const targets = [partMesh?.visible && partMesh, paths?.mesh].filter(Boolean);
  if (!targets.length) return null;
  raycaster.setFromCamera(new THREE.Vector2(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2), camera);
  const hit = raycaster.intersectObjects(targets, false).find(hit => uncut(hit.point)
    && (hit.object === partMesh || !hiddenRoles.has(paths.roles[paths.boxRole[hit.instanceId]])));
  if (!hit) return null;
  if (hit.object !== partMesh) return hit.point;
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

function setMode(name) {
  if (mode === 'measure' && name !== 'measure') clearMeasurement();
  mode = name;
  renderer.domElement.style.cursor = { measure: 'crosshair', move: 'grab', flat: 'pointer' }[name] ?? '';
  for (const button of info.querySelectorAll('[data-tool]')) button.setAttribute('aria-pressed', button.dataset.tool === name);
  showModel();  // Move and Lay flat bring the model up
  if (paths) redrawLegend();
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

// A click marks a point, or picks a face to lay flat, and a right-click puts the tool down; a
// drag, with either button, still turns or moves the view, except a part dragged to move it.
let pressedAt = null;
renderer.domElement.addEventListener('pointerdown', event => {
  pressedAt = [event.clientX, event.clientY];
  if (mode === 'move' && event.button === 0) startDrag(event);
}, { capture: true });  // before the view's controls, so that a drag on a part does not turn the view too
renderer.domElement.addEventListener('pointerup', event => {
  if (dragging) return endDrag();
  if (!mode || !pressedAt || Math.hypot(event.clientX - pressedAt[0], event.clientY - pressedAt[1]) > 4) return;
  if (event.button === 2) return setMode(null);
  if (event.button !== 0) return;
  if (mode === 'flat') return layFlat(event.clientX, event.clientY);
  if (mode !== 'measure') return;
  const point = pickAt(event.clientX, event.clientY);
  if (!point) return;
  if (picks.length === 2) picks.length = 0;
  picks.push(point.clone());
  loose = pointer = null;
  drawMeasurement();
});
renderer.domElement.addEventListener('pointermove', event => {
  if (dragging) return drag(event);
  if (mode === 'measure' && picks.length === 1 && !event.buttons) pointer = [event.clientX, event.clientY];
});
renderer.domElement.addEventListener('pointerleave', () => {
  if (!loose) return;
  loose = pointer = null;
  drawMeasurement();
});
addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === 'm' || event.key === 'M') setMode(mode === 'measure' ? null : 'measure');
  else if (event.key === 'Escape') {
    clearMeasurement();
    putBack();
    commandRan = false;
    hideCommand();
  }
});

// The command a tool has written: Apply runs it here, through the viewer, as the shell would
// (the page changes a print only so, and shows what it ran); Copy is for running it yourself.
// Only the page at the address `deli view` printed has the token that lets it run commands.
const commandBox = document.getElementById('command');
const token = new URLSearchParams(location.search).get('t');
let commandRuns = null;  // the commands Apply runs, each as its arguments
let commandRan = false;  // the panel shows what was run, which a redraw leaves up
function showCommand(text, note = '', runs = null) {
  commandBox.hidden = false;
  commandRan = false;
  commandRuns = runs;
  document.getElementById('commandText').textContent = text ?? '';
  document.getElementById('commandText').hidden = !text;
  document.getElementById('copyCommand').hidden = !text;
  document.getElementById('copyCommand').textContent = 'Copy';
  document.getElementById('applyCommand').hidden = !(runs && token);
  // With commands to run, the note says what for ("to move it there"); else it is the whole note.
  document.getElementById('commandNote').textContent = !runs ? note
    : token ? `Apply, or run in the print's directory, ${note}:`
    : `Run in the print's directory ${note} (the address deli view printed can apply it from here):`;
  document.getElementById('commandOutput').hidden = true;
}
function hideCommand() {
  if (!commandRan) commandBox.hidden = true;
}
document.getElementById('applyCommand').addEventListener('click', async event => {
  const runs = commandRuns, output = document.getElementById('commandOutput');
  event.target.disabled = true;
  let printed = '', failed = false;
  try {
    for (const args of runs) {
      const response = await fetch('/run', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Deli-Token': token },
                                             body: JSON.stringify({ args }) });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      printed += result.output;
      if (result.code !== 0) { failed = true; break; }
    }
  } catch (err) {
    printed += err instanceof TypeError ? 'The viewer has stopped. Run deli view again.' : err.message;
    failed = true;
  }
  event.target.disabled = false;
  putBack();  // the print, redrawn from deli.toml, shows where the part is now
  showRan(printed, failed);
});
// The panel, once a command has run: what it printed. It stays up through redraws.
function showRan(printed, failed) {
  const output = document.getElementById('commandOutput');
  commandBox.hidden = false;
  commandRan = true;
  commandRuns = null;
  document.getElementById('applyCommand').hidden = true;
  document.getElementById('copyCommand').hidden = true;
  document.getElementById('commandNote').textContent = failed ? 'Ran, and it did not work:' : 'Ran:';
  output.textContent = printed.trim();
  output.classList.toggle('error', failed);
  output.hidden = !printed.trim();
}

// Slice: `deli slice`, which the server runs in a process of its own; /state says how it is
// getting on, and the G-code shows up by itself once it is written.
let followingSlice = false;
async function startSlice(button) {
  button.replaceWith(Object.assign(document.createElement('span'), { className: 'dim', textContent: 'slicing…' }));
  showCommand('deli slice', 'Slicing…');
  document.getElementById('copyCommand').hidden = true;
  commandRan = true;  // stays up while the page redraws
  try {
    const response = await fetch('/slice', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Deli-Token': token }, body: '{}' });
    if (response.ok || response.status === 409) followingSlice = true;  // 409: one already running, which is followed instead
    else showRan(await response.text(), true);
  } catch (err) {
    showRan(err instanceof TypeError ? 'The viewer has stopped. Run deli view again.' : err.message, true);
  }
}
function followSlice(slicing) {
  if (!followingSlice || !slicing) return;
  if (slicing.running) {
    document.getElementById('commandNote').textContent = `Slicing… ${slicing.seconds} s`;
    return;
  }
  followingSlice = false;
  document.getElementById('commandText').textContent = 'deli slice';
  showRan(slicing.output, slicing.code !== 0);
}
document.getElementById('copyCommand').addEventListener('click', async event => {
  try {
    await navigator.clipboard.writeText(document.getElementById('commandText').textContent);
    event.target.textContent = 'Copied';
  } catch {
    getSelection().selectAllChildren(document.getElementById('commandText'));  // to copy by hand
  }
});
document.getElementById('closeCommand').addEventListener('click', () => { putBack(); commandRan = false; hideCommand(); });

// How a part is named on the command line: its file, without the extension, quoted if needed.
function partName(part) {
  const name = part.file.replace(/\.[^./]+$/, '');
  return /^[\w.\/@%+=:,-]+$/.test(name) ? name : `'${name.replaceAll("'", "'\\''")}'`;
}
const number = n => String(Math.round(n * 100) / 100);

function rangeOf(faceIndex) {
  return partRanges.find(range => faceIndex >= range.triangle && faceIndex < range.triangle + range.triangles);
}
function partHit(x, y) {
  if (!partMesh) return null;
  raycaster.setFromCamera(new THREE.Vector2(x / innerWidth * 2 - 1, 1 - y / innerHeight * 2), camera);
  return raycaster.intersectObject(partMesh, false).find(hit => uncut(hit.point)) ?? null;
}

// Move: a part dragged over the bed, level, shows where it would go and gives the
// `deli move` that puts its middle there. The print itself changes only when that is run.
let dragging = null;
function startDrag(event) {
  const hit = partHit(event.clientX, event.clientY);
  if (!hit) return;
  const range = rangeOf(hit.faceIndex);
  controls.enabled = false;
  renderer.domElement.style.cursor = 'grabbing';
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let v = range.vertex; v < range.vertex + range.vertices; v++) {
    minX = Math.min(minX, placed[v * 3]); maxX = Math.max(maxX, placed[v * 3]);
    minY = Math.min(minY, placed[v * 3 + 1]); maxY = Math.max(maxY, placed[v * 3 + 1]);
  }
  dragging = { range, plane: new THREE.Plane(new THREE.Vector3(0, 0, 1), -hit.point.z), from: hit.point.clone(),
               middle: [(minX + maxX) / 2, (minY + maxY) / 2], by: new THREE.Vector3() };
  putBack(range);  // another part moved before goes back where it is
}
function drag(event) {
  raycaster.setFromCamera(new THREE.Vector2(event.clientX / innerWidth * 2 - 1, 1 - event.clientY / innerHeight * 2), camera);
  const to = raycaster.ray.intersectPlane(dragging.plane, new THREE.Vector3());
  if (!to) return;
  dragging.by.subVectors(to, dragging.from).setZ(0);
  const { range, by } = dragging, position = partMesh.geometry.attributes.position;
  for (let v = range.vertex; v < range.vertex + range.vertices; v++) {
    position.array[v * 3] = placed[v * 3] + by.x;
    position.array[v * 3 + 1] = placed[v * 3 + 1] + by.y;
  }
  position.needsUpdate = true;
  const [x, y] = [dragging.middle[0] + by.x, dragging.middle[1] + by.y];
  // A place is on the copy's own plate, so a copy only arranged onto this one is kept to it.
  const { part, copy } = range, which = part.count > 1 ? ['--copy', String(copy)] : [];
  const steps = [...(plate > 1 && part.kept[copy - 1] !== plate ? [['plate', String(plate)]] : []), [number(x), number(y)]];
  showCommand(steps.map(step => `deli move ${partName(part)} ${[...which, ...step].join(' ')}`).join(' && '),
    `to move ${part.count > 1 ? `copy ${copy}` : 'it'} there`, steps.map(step => ['move', part.file, ...which, ...step]));
}
function endDrag() {
  controls.enabled = true;
  renderer.domElement.style.cursor = 'grab';
  partMesh.geometry.computeBoundingSphere();
  partMesh.geometry.computeBoundingBox();
  dragging = null;
}
// Every part back where the print has it, but the one given.
function putBack(except) {
  if (!partMesh || !placed) return;
  const position = partMesh.geometry.attributes.position;
  for (const range of partRanges) {
    if (range === except) continue;
    position.array.set(placed.subarray(range.vertex * 3, (range.vertex + range.vertices) * 3), range.vertex * 3);
  }
  position.needsUpdate = true;
  partMesh.geometry.computeBoundingSphere();
}

// Lay flat: the `deli rotate` that turns the part so the clicked face lies on the bed. The
// engine scales a part, then turns it about x, y and z in that order, all as recorded, not
// added to what it has; so the face's direction is taken back to the file's own, and new x
// and y angles found that point it straight down, keeping the turn about z.
function layFlat(x, y) {
  const hit = partHit(x, y);
  if (!hit) return;
  const range = rangeOf(hit.faceIndex), [rx, ry, rz] = range.part.rotate;
  const toRadians = Math.PI / 180;
  const turned = new THREE.Matrix4().makeRotationZ(rz * toRadians)
    .multiply(new THREE.Matrix4().makeRotationY(ry * toRadians)).multiply(new THREE.Matrix4().makeRotationX(rx * toRadians));
  const m = hit.face.normal.clone().applyMatrix4(turned.transpose()).normalize();  // the face's direction as in the file
  const r = Math.hypot(m.y, m.z);
  const angle = radians => {
    const degrees = Math.round(radians / toRadians * 100) / 100;
    return degrees <= -180 ? degrees + 360 : degrees === -0 ? 0 : degrees;
  };
  const ax = angle(Math.atan2(-m.y, -m.z)), ay = angle(Math.atan2(m.x, r));
  const name = partName(range.part);
  const steps = [['x', ax, rx], ['y', ay, ry]].filter(([, to, from]) => Math.abs(to - from) > 0.01);
  if (!steps.length) return showCommand(null, 'That face already lies on the bed.');
  showCommand(steps.map(([axis, to]) => `deli rotate ${name} ${axis} ${number(to)}`).join(' && '),
    'to lay that face on the bed',
    steps.map(([axis, to]) => ['rotate', range.part.file, axis, number(to)]));
}

// Pause: the `deli pause` for the layer on the slider, or the one that takes it away.
document.getElementById('pauseHere').addEventListener('click', () => {
  if (!paths) return;
  const layer = Number(layerSlider.value);
  const off = paths.pauses.includes(layer);
  const which = plate > 1 ? ['--plate', String(plate)] : [];  // the first plate's are the print's own
  const args = [...(off ? ['pause', 'off', String(layer)] : ['pause', String(layer)]), ...which];
  showCommand(`deli ${args.join(' ')}`, off ? 'to stop pausing after this layer' : 'to pause after this layer', [args]);
});

const mm = n => Math.round(n * 100) / 100;
const pct = f => `${Math.round(f * 1000) / 10}%`;

// The copies of a part on a plate, as `deli slice` arranges them.
const copiesOn = (part, n) => (part.on ?? []).filter(p => p === n).length;

function describe(state) {
  const lines = [];
  if (state.plates > 1)
    lines.push('<div class="plates">' + Array.from({ length: state.plates }, (_, i) => i + 1).map(n =>
      `<button type="button" data-plate="${n}" aria-pressed="${n === plate}">Plate ${n}</button>`).join('') + '</div>');
  for (const part of state.parts) {
    if (state.plates > 1 && !copiesOn(part, plate)) continue;
    const count = state.plates > 1 ? copiesOn(part, plate) : part.count;
    lines.push(`<b>${part.file}</b>${count > 1 ? ` × ${count}` : ''}`
      + (state.plates > 1 && count < part.count ? ` <span class="dim">of ${part.count}</span>` : ''));
    if (part.size) lines.push(part.size.map(mm).join(' × ') + ' mm');
    const s = part.scale, r = part.rotate;
    if (s.some(f => f !== 1)) lines.push(`<span class="dim">scale</span> ${s.every(f => f === s[0]) ? pct(s[0]) : s.map(pct).join(' × ')}`);
    const turns = ['x', 'y', 'z'].map((a, i) => r[i] ? `${r[i]}° about ${a}` : null).filter(Boolean);
    if (turns.length) lines.push(`<span class="dim">rotate</span> ${turns.join(', ')}`);
    if (part.plate) lines.push(`<span class="dim">kept to plate</span> ${part.plate}`);
    // Where the copies on this plate were moved to, or kept to it on their own.
    part.at.forEach((at, i) => {
      if ((part.on?.[i] ?? 1) !== plate) return;
      const own = part.kept[i] !== part.plate ? part.kept[i] : null;
      if (!at && !own) return;
      const which = part.count > 1 ? `copy ${i + 1} ` : '';
      lines.push(`<span class="dim">${which}${at ? 'at' : 'kept to plate'}</span> ${at ? `${at.map(mm).join(', ')} mm` : own}`);
    });
    if (part.z) lines.push(`<span class="dim">${part.z < 0 ? 'sunk' : 'raised'}</span> ${mm(Math.abs(part.z))} mm`);
  }
  if (!state.parts.length) lines.push('No part yet. <span class="dim">deli add &lt;file&gt;</span>');
  else if (state.plates > 1 && !state.parts.some(part => copiesOn(part, plate))) lines.push('<span class="dim">Nothing on this plate.</span>');
  lines.push(state.printer ? `<span class="dim">printer</span> ${state.printer}`
                           : '<span class="dim">No printer chosen: deli printer &lt;name&gt;</span>');
  if (state.filament) lines.push(`<span class="dim">filament</span> ${state.filament}`);
  const pauses = state.pauses[plate] ?? [];
  if (pauses.length) lines.push(`<span class="dim">pauses after layer</span> ${pauses.join(', ')}`);
  if (state.gcode?.[plate]) lines.push(`<span class="dim">sliced</span> ${state.gcode[plate]}`);
  else if (state.gcode) {}  // sliced, with nothing on this plate
  else if (state.parts.length) {
    const slice = state.slicing?.running ? '<span class="dim">slicing…</span>'
      : token ? '<button type="button" id="sliceNow" title="deli slice">Slice</button>' : 'deli slice';
    lines.push(`<span class="dim">${state.stale ? 'The print has changed since it was sliced:' : 'Not sliced yet:'}</span> ${slice}`);
  }
  if (state.error) lines.push(`<span class="error">${state.error}</span>`);
  info.innerHTML = lines.join('<br>');
}

let sliced = null;  // which slicing made the G-code shown, if any
let plate = 1;  // the plate shown, of a print with several
let lastState = null;  // what was drawn, to draw again for another plate

async function refresh() {
  try {
    const state = await (await fetch('/state')).json();
    followSlice(state.slicing);
    if (state.version !== version) {
      version = state.version;
      await redraw(state);
    }
  } catch (err) {
    // A fetch that cannot reach the server at all fails with a TypeError: the viewer has gone.
    info.innerHTML = `<span class="error">${err instanceof TypeError ? 'The viewer has stopped. Run <b>deli view</b> again.' : err.message}</span>`;
  }
}

async function redraw(state) {
  lastState = state;
  plate = Math.min(plate, state.plates ?? 1);
  if ((state.sliced ?? null) !== sliced) modelChoice = null;  // sliced again, or out of date: the model as it should be shown
  sliced = state.sliced ?? null;
  overhang = state.overhang ?? null;
  clearMeasurement();
  hideCommand();
  if (dragging) endDrag();
  drawBed(state.bed, state.height);
  describe(state);
  let problem = null;
  try {
    await drawPart(state.parts);
  } catch (err) {  // the parts cannot be placed; the G-code, if there is one, can still be shown
    clearModel();
    problem = err;
  }
  if (state.gcode?.[plate]) await drawToolpaths(state.roles, state.pauses[plate] ?? []);
  else clearPaths();
  if (TOOLS[mode]?.needsPart && !partMesh) setMode(null);
  showModel();
  setUpSlider();
  if (problem && problem.message !== state.error) info.innerHTML += `<div class="error">${problem.message}</div>`;
  info.innerHTML += options();
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
