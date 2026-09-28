extends SceneTree
## Fixed geometry preview for a snapshot already checked by asset_inspect.
## The generated GLTF scene is never attached; only static meshes are copied.

const PREVIEW_SIZE := Vector2i(512, 512)
const MATERIAL_COLOR := Color(0.56, 0.56, 0.56, 1.0)
const NORMALIZED_LONGEST_AXIS := 2.2
const FRAMING_MARGIN := 1.22
const MAX_GEOMETRY_VERTICES := 1000000
const MAX_SCENE_NODES := 16384

var _mesh_count := 0
var _surface_count := 0
var _vertex_count := 0
var _triangle_count := 0
var _nondegenerate_triangle_count := 0
var _bounds := AABB()
var _have_bounds := false


func _initialize() -> void:
	call_deferred("_run")


func _fail(message: String) -> void:
	printerr("ASSET_RENDER_FAILED: ", message)
	quit(2)


func _finite_transform(value: Transform3D) -> bool:
	return value.origin.is_finite() and value.basis.x.is_finite() \
		and value.basis.y.is_finite() and value.basis.z.is_finite()


func _neutral_material() -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = MATERIAL_COLOR
	material.roughness = 1.0
	material.metallic = 0.0
	return material


func _inspect_surface(mesh: Mesh, surface: int, transform: Transform3D) -> String:
	if mesh.surface_get_primitive_type(surface) != Mesh.PRIMITIVE_TRIANGLES:
		return "only triangle mesh surfaces are supported"
	var arrays := mesh.surface_get_arrays(surface)
	if arrays.size() != Mesh.ARRAY_MAX or not arrays[Mesh.ARRAY_VERTEX] is PackedVector3Array:
		return "surface has no readable position array"
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	if vertices.size() < 3 or _vertex_count + vertices.size() > MAX_GEOMETRY_VERTICES:
		return "surface is empty or exceeds the geometry vertex limit"
	var indices := PackedInt32Array()
	if arrays[Mesh.ARRAY_INDEX] != null:
		if not arrays[Mesh.ARRAY_INDEX] is PackedInt32Array:
			return "surface has an invalid index array"
		indices = arrays[Mesh.ARRAY_INDEX]
	var element_count := indices.size() if not indices.is_empty() else vertices.size()
	if element_count < 3 or element_count % 3 != 0:
		return "triangle element count must be a positive multiple of three"
	for index: int in indices:
		if index < 0 or index >= vertices.size():
			return "triangle index is outside the position array"
	# Validate every actual position, including unused vertices. Importer AABBs
	# alone cannot establish that decoded mesh data is finite.
	for index in vertices.size():
		if not vertices[index].is_finite():
			return "mesh contains a non-finite position"
		vertices[index] = transform * vertices[index]
		if not vertices[index].is_finite():
			return "mesh transform produced a non-finite position"
		_bounds = _bounds.expand(vertices[index]) if _have_bounds else AABB(vertices[index], Vector3.ZERO)
		_have_bounds = true
	for element in range(0, element_count, 3):
		var first := indices[element] if not indices.is_empty() else element
		var second := indices[element + 1] if not indices.is_empty() else element + 1
		var third := indices[element + 2] if not indices.is_empty() else element + 2
		var area := (vertices[second] - vertices[first]).cross(vertices[third] - vertices[first])
		if not area.is_finite():
			return "triangle area is non-finite"
		if area != Vector3.ZERO:
			_nondegenerate_triangle_count += 1
	_vertex_count += vertices.size()
	_triangle_count += element_count / 3
	_surface_count += 1
	return ""


func _copy_meshes(source: Node, target: Node3D) -> String:
	var pending: Array[Dictionary] = [{"node": source, "transform": Transform3D.IDENTITY}]
	var visited := 0
	var material := _neutral_material()
	while not pending.is_empty():
		visited += 1
		if visited > MAX_SCENE_NODES:
			return "imported scene exceeds the node limit"
		var entry: Dictionary = pending.pop_back()
		var node: Node = entry["node"]
		var combined: Transform3D = entry["transform"]
		if node is Node3D:
			combined = combined * node.transform
		if not _finite_transform(combined):
			return "scene contains a non-finite static transform"
		if node is MeshInstance3D:
			var original: MeshInstance3D = node
			if original.mesh == null or original.mesh.get_surface_count() == 0:
				return "mesh instance has no surfaces"
			if original.skin != null or original.mesh.get_blend_shape_count() != 0:
				return "skinning and morph targets are unsupported"
			for surface in original.mesh.get_surface_count():
				var problem := _inspect_surface(original.mesh, surface, combined)
				if not problem.is_empty():
					return problem
			var copy := MeshInstance3D.new()
			copy.mesh = original.mesh
			copy.transform = combined
			copy.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			copy.material_override = material
			target.add_child(copy)
			_mesh_count += 1
		for child: Node in node.get_children():
			pending.append({"node": child, "transform": combined})
	return ""


func _viewport() -> SubViewport:
	var viewport := SubViewport.new()
	viewport.size = PREVIEW_SIZE
	viewport.transparent_bg = true
	viewport.own_world_3d = true
	viewport.msaa_3d = Viewport.MSAA_4X
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
	root.add_child(viewport)
	return viewport


func _capture(viewport: SubViewport) -> Image:
	await process_frame
	await RenderingServer.frame_post_draw
	await process_frame
	await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	if image != null and not image.is_empty():
		image.convert(Image.FORMAT_RGBA8)
	viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	return image


func _array(vector: Vector3) -> Array[float]:
	return [vector.x, vector.y, vector.z]


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 3:
		_fail("expected ABS_SNAPSHOT_GLB ABS_PREVIEW_PNG ABS_RENDERING_JSON")
		return
	for path: String in args:
		if not path.is_absolute_path():
			_fail("input and output paths must be absolute")
			return
	var input_path: String = args[0].simplify_path()
	var preview_path: String = args[1].simplify_path()
	var receipt_path: String = args[2].simplify_path()
	if input_path == preview_path or input_path == receipt_path or preview_path == receipt_path:
		_fail("input, preview and receipt paths must be distinct")
		return
	for output_path: String in [preview_path, receipt_path]:
		if FileAccess.file_exists(output_path) or DirAccess.dir_exists_absolute(output_path):
			_fail("output already exists; refusing to overwrite")
			return
		if not DirAccess.dir_exists_absolute(output_path.get_base_dir()):
			_fail("output parent must be the runner's existing run directory")
			return
	var display := DisplayServer.get_name()
	var renderer := RenderingServer.get_video_adapter_name().strip_edges()
	if display.to_lower() in ["headless", "dummy"] or renderer.is_empty() or "dummy" in renderer.to_lower():
		_fail("capture requires a real graphics display; headless/dummy rendering is disabled")
		return
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	var load_error := document.append_from_file(input_path, state)
	if load_error != OK:
		_fail("GLB import failed: %s" % load_error)
		return
	var imported := document.generate_scene(state)
	if imported == null:
		_fail("GLB scene generation failed")
		return
	var model := Node3D.new()
	var geometry_problem := _copy_meshes(imported, model)
	imported.free()
	if not geometry_problem.is_empty():
		model.free()
		_fail(geometry_problem)
		return
	if not _have_bounds or _mesh_count == 0 or _nondegenerate_triangle_count == 0:
		model.free()
		_fail("expected nonempty, nondegenerate triangle geometry")
		return
	var longest_axis := maxf(_bounds.size.x, maxf(_bounds.size.y, _bounds.size.z))
	if not _bounds.position.is_finite() or not _bounds.size.is_finite() or longest_axis <= 0.0:
		model.free()
		_fail("mesh bounds are non-finite or empty")
		return
	var normalizing_scale := NORMALIZED_LONGEST_AXIS / longest_axis
	if not is_finite(normalizing_scale) or normalizing_scale <= 0.0:
		model.free()
		_fail("mesh bounds cannot be normalized")
		return
	var viewport := _viewport()
	model.scale = Vector3.ONE * normalizing_scale
	model.position = -_bounds.get_center() * normalizing_scale
	if not model.position.is_finite():
		model.free()
		_fail("normalized model position is non-finite")
		return
	viewport.add_child(model)
	var camera := Camera3D.new()
	viewport.add_child(camera)
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.position = Vector3(5.0, 3.0, 7.0)
	camera.look_at(Vector3.ZERO, Vector3.UP)
	camera.near = 0.01
	camera.far = 100.0
	var half_extents := _bounds.size * (normalizing_scale * 0.5)
	var projected_width := 2.0 * camera.basis.x.abs().dot(half_extents)
	var projected_height := 2.0 * camera.basis.y.abs().dot(half_extents)
	camera.size = maxf(projected_width, projected_height) * FRAMING_MARGIN
	if not is_finite(camera.size) or camera.size <= 0.0:
		_fail("camera cannot frame the normalized bounds")
		return
	camera.current = true
	var image := await _capture(viewport)
	if image == null or image.is_empty() or image.get_size() != PREVIEW_SIZE:
		_fail("renderer returned an empty or incorrectly sized image")
		return
	var save_error := image.save_png(preview_path)
	if save_error != OK:
		_fail("PNG write failed: %s" % save_error)
		return
	var receipt: Dictionary = {
		"schema": "agent_bridge.asset_render.v1",
		"status": "rendered_geometry_preview",
		"input_path": input_path,
		"input_sha256": FileAccess.get_sha256(input_path),
		"preview_sha256": FileAccess.get_sha256(preview_path),
		"godot_version": Engine.get_version_info().string,
		"renderer": renderer,
		"rendering_method": RenderingServer.get_current_rendering_method(),
		"rendering_driver": RenderingServer.get_current_rendering_driver_name(),
		"display_server": display,
		"adapter_vendor": RenderingServer.get_video_adapter_vendor(),
		"width": PREVIEW_SIZE.x,
		"height": PREVIEW_SIZE.y,
		"mesh_count": _mesh_count,
		"surface_count": _surface_count,
		"vertex_count_summed_per_surface": _vertex_count,
		"triangle_count": _triangle_count,
		"nondegenerate_triangle_count": _nondegenerate_triangle_count,
		"source_bounds": {"position": _array(_bounds.position), "size": _array(_bounds.size)},
		"normalization_scale": normalizing_scale,
		"normalized_longest_axis": NORMALIZED_LONGEST_AXIS,
		"camera": {
			"projection": "orthographic", "position": _array(camera.position),
			"target": [0, 0, 0], "size": camera.size,
			"projected_bounds_width": projected_width,
			"projected_bounds_height": projected_height, "framing_margin": FRAMING_MARGIN,
		},
		"material_policy": "neutral_geometry",
		"material_shading": "opaque unshaded, double-sided; no textures or lighting",
		"material_color_rgba": [MATERIAL_COLOR.r, MATERIAL_COLOR.g, MATERIAL_COLOR.b, MATERIAL_COLOR.a],
		"original_material_fidelity_preserved": false,
		"visual_quality_reviewed": false,
		"geometry_limits": {"vertices_summed_per_surface": MAX_GEOMETRY_VERTICES, "scene_nodes": MAX_SCENE_NODES},
	}
	var receipt_file := FileAccess.open(receipt_path, FileAccess.WRITE)
	if receipt_file == null:
		_fail("rendering receipt could not be opened")
		return
	receipt_file.store_string(JSON.stringify(receipt, "\t") + "\n")
	receipt_file.flush()
	var receipt_error := receipt_file.get_error()
	receipt_file.close()
	if receipt_error != OK:
		_fail("rendering receipt write failed: %s" % receipt_error)
		return
	print("ASSET_RENDER_OK: ", preview_path)
	quit(0)
