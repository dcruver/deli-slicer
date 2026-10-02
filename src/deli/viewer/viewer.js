// The viewer pane: the bed of the chosen printer and the part on it, placed as `deli slice`
// places it. It is a viewer only. It asks the server for /state twice a second and redraws
// when the version changes, so `deli scale`, `deli rotate` and edits to deli.toml show up here.

import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const info = document.getElementById('info');

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

scene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(-1, -2, 3);
scene.add(sun);

let bedGroup = null;
let partMesh = null;
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

  if (partMesh) { scene.remove(partMesh); partMesh.geometry.dispose(); partMesh = null; }
  if (nTriangles === 0) return;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeVertexNormals();
  partMesh = new THREE.Mesh(geometry, material);
  scene.add(partMesh);
}

const mm = n => Math.round(n * 100) / 100;
const pct = f => `${Math.round(f * 1000) / 10}%`;

function describe(state) {
  const lines = [];
  if (state.part) {
    lines.push(`<b>${state.part.file}</b>`);
    if (state.part.size) lines.push(state.part.size.map(mm).join(' × ') + ' mm');
    const s = state.part.scale, r = state.part.rotate;
    if (s.some(f => f !== 1)) lines.push(`<span class="dim">scale</span> ${s.every(f => f === s[0]) ? pct(s[0]) : s.map(pct).join(' × ')}`);
    const turns = ['x', 'y', 'z'].map((a, i) => r[i] ? `${r[i]}° about ${a}` : null).filter(Boolean);
    if (turns.length) lines.push(`<span class="dim">rotate</span> ${turns.join(', ')}`);
  } else {
    lines.push('No part yet. <span class="dim">deli add &lt;file&gt;</span>');
  }
  lines.push(state.printer ? `<span class="dim">printer</span> ${state.printer}`
                           : '<span class="dim">No printer chosen: deli printer &lt;name&gt;</span>');
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
      await drawPart();
    }
  } catch (err) {
    info.innerHTML = `<span class="error">${err.message || 'deli view has stopped'}</span>`;
  }
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
refresh();
setInterval(refresh, 500);
