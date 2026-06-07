import * as THREE from "three";

function clearGroup(group) {
  while (group.children.length > 0) {
    const child = group.children.pop();
    child.traverse?.((node) => {
      node.geometry?.dispose?.();
      if (Array.isArray(node.material)) {
        node.material.forEach((material) => material.dispose?.());
      } else {
        node.material?.dispose?.();
      }
    });
  }
}

function toVector3(values) {
  return new THREE.Vector3(values[0], values[1], values[2]);
}

function isNonZeroBox(box) {
  const size = new THREE.Vector3();
  box.getSize(size);
  return size.x > 0.001 && size.y > 0.001 && size.z > 0.001;
}

export class ProjectionAdapter {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#111820");
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    this.camera.position.set(7, 6, 8);
    this.camera.lookAt(0, 0.8, 0);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.container.appendChild(this.renderer.domElement);

    this.entityRoot = new THREE.Group();
    this.markerRoot = new THREE.Group();
    this.scene.add(this.entityRoot);
    this.scene.add(this.markerRoot);
    this.registry = new Map();
    this.unprojected = [];
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -1);
    this.lastState = null;

    const ambient = new THREE.HemisphereLight("#f3f7ff", "#4b5563", 2.2);
    const key = new THREE.DirectionalLight("#ffffff", 2.5);
    key.position.set(4, 8, 5);
    key.castShadow = true;
    this.scene.add(ambient, key);

    const grid = new THREE.GridHelper(12, 12, "#425466", "#25313f");
    grid.position.y = 0.105;
    this.scene.add(grid);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(this.container);
    this.resize();
    this.animate();
  }

  project(state) {
    this.lastState = state;
    clearGroup(this.entityRoot);
    clearGroup(this.markerRoot);
    this.registry.clear();
    this.unprojected = [];

    for (const entity of state.entities) {
      if (entity.state?.projection_disabled) {
        this.unprojected.push({
          entity_id: entity.entity_id,
          reason: entity.state?.verification_reason ?? "projection_object_absent",
          position: entity.transform.position
        });
        this.addUnconfirmedMarker(entity);
        continue;
      }
      this.addEntityMesh(entity);
    }
    this.renderer.render(this.scene, this.camera);
  }

  addEntityMesh(entity) {
    const color = entity.state?.verification === "not_verified" ? "#f2c94c" : entity.material.color;
    const material = new THREE.MeshStandardMaterial({
      color,
      transparent: entity.material.opacity < 1,
      opacity: entity.material.opacity,
      roughness: 0.58,
      metalness: 0.05
    });
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = entity.entity_id;
    mesh.userData.entityId = entity.entity_id;
    mesh.userData.selectable = Boolean(entity.state?.selectable);
    mesh.castShadow = entity.kind !== "surface";
    mesh.receiveShadow = true;
    mesh.position.copy(toVector3(entity.transform.position));
    mesh.rotation.set(entity.transform.rotation[0], entity.transform.rotation[1], entity.transform.rotation[2]);
    mesh.scale.copy(toVector3(entity.transform.scale));
    this.entityRoot.add(mesh);

    if (entity.state?.selected) {
      const outline = new THREE.BoxHelper(mesh, "#f7d154");
      outline.name = `${entity.entity_id}_outline`;
      this.entityRoot.add(outline);
    }

    const box = new THREE.Box3().setFromObject(mesh);
    this.registry.set(entity.entity_id, {
      entity_id: entity.entity_id,
      object: mesh,
      bounds_nonzero: isNonZeroBox(box),
      hit_testable: Boolean(entity.state?.selectable) && entity.material.opacity > 0,
      material_opacity: entity.material.opacity,
      position: [...entity.transform.position]
    });
  }

  addUnconfirmedMarker(entity) {
    const group = new THREE.Group();
    group.name = `${entity.entity_id}_unconfirmed_marker`;
    group.position.copy(toVector3(entity.transform.position));

    const ringMaterial = new THREE.MeshBasicMaterial({ color: "#f2c94c", side: THREE.DoubleSide });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.68, 0.035, 8, 48), ringMaterial);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.05;
    group.add(ring);

    const lineMaterial = new THREE.LineBasicMaterial({ color: "#f2c94c" });
    const points = [
      new THREE.Vector3(-0.55, 0.05, 0),
      new THREE.Vector3(0.55, 0.05, 0),
      new THREE.Vector3(0, 0.05, -0.55),
      new THREE.Vector3(0, 0.05, 0.55)
    ];
    const line = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), lineMaterial);
    group.add(line);
    this.markerRoot.add(group);
  }

  selectAt(clientX, clientY) {
    this.setPointer(clientX, clientY);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const selectableObjects = [...this.registry.values()].filter((item) => item.object.userData.selectable).map((item) => item.object);
    const hits = this.raycaster.intersectObjects(selectableObjects, false);
    return hits[0]?.object?.userData?.entityId ?? null;
  }

  groundPointAt(clientX, clientY) {
    this.setPointer(clientX, clientY);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const point = new THREE.Vector3();
    if (!this.raycaster.ray.intersectPlane(this.groundPlane, point)) {
      return null;
    }
    return [Number(point.x.toFixed(2)), 1, Number(point.z.toFixed(2))];
  }

  screenPointForEntity(entityId) {
    const item = this.registry.get(entityId);
    if (!item) {
      return null;
    }
    const rect = this.renderer.domElement.getBoundingClientRect();
    const point = item.object.position.clone().project(this.camera);
    return {
      clientX: rect.left + ((point.x + 1) / 2) * rect.width,
      clientY: rect.top + ((1 - point.y) / 2) * rect.height
    };
  }

  getSnapshot() {
    return {
      adapter: "threejs_web",
      projected_entities: [...this.registry.values()].map((item) => ({
        entity_id: item.entity_id,
        bounds_nonzero: item.bounds_nonzero,
        hit_testable: item.hit_testable,
        material_opacity: item.material_opacity,
        position: item.position
      })),
      unprojected_entities: this.unprojected.map((item) => ({ ...item }))
    };
  }

  setPointer(clientX, clientY) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  }

  resize() {
    const width = Math.max(1, this.container.clientWidth);
    const height = Math.max(1, this.container.clientHeight);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    this.renderer.render(this.scene, this.camera);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.renderer.render(this.scene, this.camera);
  }
}
