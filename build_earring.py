# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Nlkomaru
"""Blender-only earring export. Run with blender-launcher.exe -b --python ... -- ..."""

import argparse
import json
import math
from pathlib import Path
import shutil
import sys
import traceback

import bpy
from mathutils import Vector


BODY_NAME = "NavierStokes_OpenAI_Vortex"
ANNOTATION_NAMES = (
    "Label_InwardSpiral", "Line_InwardSpiral",
    "Label_AxialStretching", "Line_AxialStretching",
)
BONE_NAMES = ("EarAnchor", "Chain_01", "Chain_02", "Chain_03", "Pendant", "PendantEnd")
BODY_HEIGHT = 0.10
CHAIN_LENGTH = 0.05
GRADIENT_WIDTH = 1024


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("D:/VR/Projects/openai-navier-stokes"))
    parser.add_argument("--validate", action="store_true", help="Check geometry, skinning, units and source synchronization")
    parser.add_argument("--smoke", action="store_true", help="Reopen saved blend and prove evaluated skin deformation; --render also writes posed preview")
    parser.add_argument("--render", action="store_true", help="Render Source/earring_preview.png, including all annotations")
    parser.add_argument("--close-up", action="store_true", help="Also render Source/earring_chain_closeup.png")
    parser.add_argument("--run-id", default="manual", help="Written into build-result.json for the asynchronous Store launcher")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def select_only(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def triangle_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def bake_gradient_textures(body, texture_dir):
    """Bake the *RGB ramp*, not the grayscale Col attribute, into UV0 textures.

    These materials depend only on a scalar, so a 1D lookup bake avoids UV
    packing, lighting dependence, and projection seams. Half-texel UVs map the
    original BYTE_COLOR Col factors to the exact corresponding ramp samples.
    """
    # Curve conversion already creates a UVMap. Replace it, rather than adding
    # UVMap.001: Unity's ordinary _MainTex samples the first channel (UV0).
    for layer in list(body.data.uv_layers):
        body.data.uv_layers.remove(layer)
    uv = body.data.uv_layers.new(name="UVMap")
    factors = body.data.color_attributes["Col"]
    materials = []
    for slot, material in enumerate(body.data.materials):
        nodes = material.node_tree.nodes
        ramp = next(node.color_ramp for node in nodes if node.type == "VALTORGB")
        filename = material.name + "_Gradient.png"
        # Byte image pixels are sRGB values, unlike the scene-linear ramp.
        # Encode explicitly so both Blender and Unity decode the same RGB.
        image = bpy.data.images.new(material.name + "_Gradient", width=GRADIENT_WIDTH, height=4, alpha=True)
        image.colorspace_settings.name = "sRGB"
        def srgb(value):
            return value * 12.92 if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
        row = [srgb(component) if channel < 3 else component
               for index in range(GRADIENT_WIDTH)
               for channel, component in enumerate(ramp.evaluate(index / (GRADIENT_WIDTH - 1)))]
        image.pixels.foreach_set(row * 4)
        image.filepath_raw = str(texture_dir / filename)
        image.file_format = "PNG"
        image.save()
        image.pack()
        texture = nodes.new("ShaderNodeTexImage")
        texture.name = "BakedRGBGradient"
        texture.image = image
        texture.interpolation = "Linear"
        texture.extension = "EXTEND"
        uv_node = nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = uv.name
        material.node_tree.links.new(uv_node.outputs["UV"], texture.inputs["Vector"])
        bsdf = nodes.get("Principled BSDF")
        material.node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        if "Emission Color" in bsdf.inputs:
            material.node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Emission Color"])
        # RGB is now supplied by UV texture in Blender and Unity alike.
        for node in list(nodes):
            if node.type in {"ATTRIBUTE", "VALTORGB"}:
                nodes.remove(node)
        for polygon in body.data.polygons:
            if polygon.material_index == slot:
                for loop in polygon.loop_indices:
                    factor = factors.data[loop].color[0]
                    uv.data[loop].uv = ((factor * (GRADIENT_WIDTH - 1) + 0.5) / GRADIENT_WIDTH, 0.5)
        materials.append({
            "name": material.name,
            "main_texture": "Assets/Nikomaru/NavierStokes/Textures/" + filename,
            "color": [1, 1, 1, 1],
            "srgb": True,
            "wrap": "Clamp",
            "filter": "Bilinear",
            "mipmaps": False,
            "compression": "None",
        })
    body["gradient_uv_factor_max_error"] = max(
        abs((value.uv.x * GRADIENT_WIDTH - 0.5) / (GRADIENT_WIDTH - 1) - factor.color[0])
        for value, factor in zip(uv.data, factors.data))
    assert body["gradient_uv_factor_max_error"] < 1e-6, "UV0 lost original gradient factors"
    # Do not leave the misleading grayscale attribute in the exported mesh.
    body.data.color_attributes.remove(factors)
    return materials


def transform_mesh(obj, scale, tip_height):
    # Bake all object transforms into coordinates; rig and meshes share origin.
    matrix = obj.matrix_world.copy()
    for vertex in obj.data.vertices:
        point = matrix @ vertex.co
        vertex.co = (point.x * scale, point.y * scale,
                     (point.z - tip_height) * scale - CHAIN_LENGTH)
    obj.matrix_world.identity()
    obj.data.update()


def build_chain():
    """Four simple interlinked low-poly oval rings plus a minimal tip eyelet."""
    vertices, faces, connector_vertices = [], [], []

    def ring(center_z, radius_x, radius_z, wire, turn, connector=False):
        start = len(vertices)
        segments, sides = 12, 4
        for segment in range(segments):
            angle = math.tau * segment / segments
            # Outward in-plane normal to an ellipse.
            normal = Vector((math.cos(angle) / radius_x, 0, math.sin(angle) / radius_z)).normalized()
            center = Vector((radius_x * math.cos(angle), 0, center_z + radius_z * math.sin(angle)))
            for side in range(sides):
                phi = math.tau * side / sides
                point = center + wire * (math.cos(phi) * normal + Vector((0, math.sin(phi), 0)))
                vertices.append((point.x * math.cos(turn) - point.y * math.sin(turn),
                                 point.x * math.sin(turn) + point.y * math.cos(turn), point.z))
                if connector:
                    connector_vertices.append(len(vertices) - 1)
        for segment in range(segments):
            for side in range(sides):
                a = start + segment * sides + side
                b = start + ((segment + 1) % segments) * sides + side
                c = start + ((segment + 1) % segments) * sides + (side + 1) % sides
                d = start + segment * sides + (side + 1) % sides
                faces.append((a, b, c, d))

    # 16mm outer height, 11.33mm center pitch: four alternating rings interlock.
    outer_half_height = 0.008
    wire = 0.0007
    pitch = (CHAIN_LENGTH - 2 * outer_half_height) / 3
    for link in range(4):
        ring(-outer_half_height - link * pitch, 0.0025,
             outer_half_height - wire, wire, (link % 2) * math.pi / 2)
    # The small eyelet overlaps both the lowest ring and the white arrow cone.
    # Its lower arc crosses the axis below the tip, not the vortex center.
    ring(-CHAIN_LENGTH + 0.00015, 0.00065, 0.00065, 0.00030, math.pi / 2, connector=True)
    mesh = bpy.data.meshes.new("ChainMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Chain", mesh)
    bpy.context.scene.collection.objects.link(obj)
    # Correct the winding consistently for the generated closed rings.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    material = bpy.data.materials.new("ChainSilver")
    material.use_nodes = True
    material.diffuse_color = (0.65, 0.70, 0.78, 1)
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = material.diffuse_color
    bsdf.inputs["Metallic"].default_value = 0.85
    bsdf.inputs["Roughness"].default_value = 0.24
    obj.data.materials.append(material)
    return obj, set(connector_vertices)


def build_rig():
    data = bpy.data.armatures.new("NavierStokesRig")
    obj = bpy.data.objects.new("NavierStokesRig", data)
    bpy.context.scene.collection.objects.link(obj)
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    positions = (0, 0, -CHAIN_LENGTH / 3, -CHAIN_LENGTH * 2 / 3,
                 -CHAIN_LENGTH, -CHAIN_LENGTH - BODY_HEIGHT)
    for index, name in enumerate(BONE_NAMES):
        bone = data.edit_bones.new(name)
        bone.head = (0, 0, positions[index])
        if index == 0:
            bone.tail = (0, 0, 0.002)
        elif index == len(BONE_NAMES) - 1:
            bone.tail = (0, 0, positions[index] - 0.005)
        else:
            bone.tail = (0, 0, positions[index + 1])
        if index:
            bone.parent = data.edit_bones[BONE_NAMES[index - 1]]
            bone.use_connect = index > 1
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.show_in_front = True
    data.display_type = "STICK"
    return obj


def skin_mesh(obj, rig, connector_vertices=None):
    groups = {name: obj.vertex_groups.new(name=name) for name in BONE_NAMES}
    if connector_vertices is None:
        groups["Pendant"].add(list(range(len(obj.data.vertices))), 1, "REPLACE")
    else:
        names = ("Chain_01", "Chain_02", "Chain_03", "Pendant")
        for vertex in obj.data.vertices:
            if vertex.index in connector_vertices:
                groups["Pendant"].add([vertex.index], 1, "REPLACE")
                continue
            depth = min(3.0, max(0.0, -vertex.co.z / CHAIN_LENGTH * 3))
            lower = min(2, int(depth))
            fraction = depth - lower
            if fraction < 1:
                groups[names[lower]].add([vertex.index], 1 - fraction, "REPLACE")
            if fraction > 0:
                groups[names[lower + 1]].add([vertex.index], fraction, "REPLACE")
    modifier = obj.modifiers.new("EarringSkin", "ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True
    # Parenting with identity transforms leaves the mesh at the attachment origin.
    if obj.parent is None:
        obj.parent = rig


def bounds(objects):
    points = [obj.matrix_world @ vertex.co for obj in objects for vertex in obj.data.vertices]
    return ([min(point[axis] for point in points) for axis in range(3)],
            [max(point[axis] for point in points) for axis in range(3)])


def setup_preview(scene, meshes, scale, tip_height):
    for obj in scene.objects:
        if obj.type == "LIGHT":
            obj.location = (obj.location.x * scale, obj.location.y * scale,
                            (obj.location.z - tip_height) * scale - CHAIN_LENGTH)
            obj.data.size *= scale
            obj.data.energy *= scale * scale
    camera = scene.camera
    camera.data.type = "ORTHO"
    camera.data.clip_start = 0.001
    camera.data.clip_end = 10
    minimum, maximum = bounds(meshes)
    center = Vector(((minimum[0] + maximum[0]) / 2, 0, (minimum[2] + maximum[2]) / 2))
    camera.location = center + Vector((0, -0.5, 0))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1400
    scene.render.resolution_percentage = 100
    camera.data.ortho_scale = max(maximum[2] - minimum[2],
                                  (maximum[0] - minimum[0]) * 1400 / 1200) * 1.20
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"


def validate_scene(body, chain, annotations, rig, source_texts):
    assert triangle_count(body) <= 20000, "Vortex body exceeds 20,000 triangles"
    minimum, maximum = bounds([body])
    assert abs(maximum[2] - minimum[2] - BODY_HEIGHT) < 1e-6, "Body height is not 0.10m"
    assert abs(maximum[2] + CHAIN_LENGTH) < 1e-6, "Chain is not attached at top white arrow"
    assert [bone.name for bone in rig.data.bones] == list(BONE_NAMES), "Unexpected bone hierarchy"
    for index, name in enumerate(BONE_NAMES):
        parent = rig.data.bones[name].parent
        assert (parent.name if parent else None) == (BONE_NAMES[index - 1] if index else None)
    for obj in [body, chain, *annotations]:
        assert obj.type == "MESH" and len(obj.data.vertices), obj.name
        assert any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers), obj.name
        for vertex in obj.data.vertices:
            weights = [entry.weight for entry in vertex.groups]
            assert weights and abs(sum(weights) - 1) < 1e-5, (obj.name, vertex.index, weights)
            if obj != chain:
                assert len(vertex.groups) == 1 and obj.vertex_groups[vertex.groups[0].group].name == "Pendant"
    assert len(annotations) == 4 and all(obj.parent.name == "Annotations" for obj in annotations)
    assert len(body.data.uv_layers) == 1 and body.data.uv_layers[0].name == "UVMap"
    assert body.data.uv_layers.active and "Col" not in body.data.color_attributes
    assert body["gradient_uv_factor_max_error"] < 1e-6
    for name, source in source_texts.items():
        assert bpy.data.texts[name].as_string() == source, "Unsynchronized source: " + name
    return {"body_triangles": triangle_count(body), "chain_triangles": triangle_count(chain),
            "annotations_triangles": sum(triangle_count(obj) for obj in annotations),
            "all_vertices_fully_weighted": True, "rigid_pendant_annotations": True,
            "gradient_uv_channels": 1,
            "gradient_uv_factor_max_error": body["gradient_uv_factor_max_error"],
            "source_text_synchronized": True}


def smoke_saved_blend(args, source_dir, output_dir):
    """Independent saved-file check; never save the temporary test pose."""
    blend = output_dir / "NavierStokes_Earring.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    body = bpy.data.objects[BODY_NAME]
    chain = bpy.data.objects["Chain"]
    rig = bpy.data.objects["NavierStokesRig"]
    annotations = [bpy.data.objects[name] for name in ANNOTATION_NAMES]
    meshes = [body, chain, *annotations]
    source_texts = {name: (source_dir / name).read_text(encoding="utf-8")
                    for name in ("generate_vortex.py", "build_earring.py")}
    stats = validate_scene(body, chain, annotations, rig, source_texts)
    assert bpy.data.texts["Text"].as_string() == source_texts["generate_vortex.py"]
    assert scene.unit_settings.scale_length == 1

    def evaluated_positions():
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        return {obj.name: [obj.matrix_world @ vertex.co for vertex in obj.evaluated_get(depsgraph).data.vertices]
                for obj in meshes}

    baseline = evaluated_positions()
    anchor_before = (rig.matrix_world @ rig.pose.bones["EarAnchor"].matrix).copy()
    bone = rig.pose.bones["Chain_02"]
    original_mode, original_basis = bone.rotation_mode, bone.matrix_basis.copy()
    bone.rotation_mode = "XYZ"
    bone.rotation_euler.z = math.radians(20)
    posed = evaluated_positions()
    anchor_after = rig.matrix_world @ rig.pose.bones["EarAnchor"].matrix
    anchor_delta = max(abs(anchor_before[row][col] - anchor_after[row][col])
                       for row in range(4) for col in range(4))
    movement = {name: max((after - before).length for before, after in zip(baseline[name], posed[name]))
                for name in baseline}
    tip_index = max(range(len(body.data.vertices)), key=lambda index: body.data.vertices[index].co.z)
    tip_error = (posed[body.name][tip_index] - rig.matrix_world @ rig.pose.bones["Pendant"].head).length
    assert anchor_delta < 1e-8, "EarAnchor moved during chain rotation"
    assert movement[body.name] > 0.005 and movement["Chain"] > 0.001, "Skinning did not deform evaluated geometry"
    assert all(movement[name] > 0.001 for name in ANNOTATION_NAMES), "Annotations did not follow pendant"
    assert tip_error < 1e-6, "Posed arrow tip detached from Pendant"
    render = None
    if args.render:
        render = str(output_dir / "earring_deformed.png")
        scene.render.filepath = render
        # Room for the temporary swing while preserving the saved rest camera.
        scene.camera.data.ortho_scale *= 1.25
        bpy.ops.render.render(write_still=True)
    bone.rotation_mode = original_mode
    bone.matrix_basis = original_basis
    restored = evaluated_positions()
    restoration_error = max((after - before).length for name in baseline
                            for before, after in zip(baseline[name], restored[name]))
    assert restoration_error < 1e-7, "Temporary pose was not restored"
    return {
        "status": "complete", "run_id": args.run_id, "saved_blend_reopened": str(blend),
        "statistics": stats, "bone_rotated": "Chain_02", "rotation_degrees_local_z": 20,
        "evaluated_max_displacement_m": movement, "ear_anchor_matrix_max_delta": anchor_delta,
        "posed_arrow_tip_to_pendant_head_error_m": tip_error,
        "restored_vertex_max_error_m": restoration_error,
        "deformed_render": render, "temporary_pose_saved": False,
    }


def build(args, source_dir, output_dir):
    model_dir = args.project / "Assets/Nikomaru/NavierStokes/Models"
    texture_dir = args.project / "Assets/Nikomaru/NavierStokes/Textures"
    for directory in (output_dir, model_dir, texture_dir):
        directory.mkdir(parents=True, exist_ok=True)
    generator = source_dir / "generate_vortex.py"
    source_texts = {"generate_vortex.py": generator.read_text(encoding="utf-8"),
                    "build_earring.py": Path(__file__).read_text(encoding="utf-8")}
    # Always regenerate from this checkout, never from an old .blend or G: copy.
    exec(compile(source_texts["generate_vortex.py"], str(generator), "exec"),
         {"__name__": "__vortex_generator__", "__file__": str(generator)})
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    body = bpy.data.objects[BODY_NAME]
    original_min, original_max = bounds([body])
    tip_height = original_max[2]
    # Guard the source contract: the highest body point must be the axis arrow.
    assert abs(tip_height - 4.92) < 1e-5, "Source white arrow tip changed; review attachment"
    scale = BODY_HEIGHT / (original_max[2] - original_min[2])
    materials = bake_gradient_textures(body, texture_dir)
    transform_mesh(body, scale, tip_height)
    annotations = []
    for name in ANNOTATION_NAMES:
        obj = bpy.data.objects[name]
        select_only([obj])
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.view_layer.objects.active
        transform_mesh(obj, scale, tip_height)
        annotations.append(obj)
    chain, connector_vertices = build_chain()
    rig = build_rig()
    annotation_root = bpy.data.objects.new("Annotations", None)
    scene.collection.objects.link(annotation_root)
    annotation_root.parent = rig
    for obj in annotations:
        obj.parent = annotation_root
    skin_mesh(body, rig)
    skin_mesh(chain, rig, connector_vertices)
    for obj in annotations:
        skin_mesh(obj, rig)
    meshes = [body, chain, *annotations]
    setup_preview(scene, meshes, scale, tip_height)
    for name, source in source_texts.items():
        text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
        text.clear()
        text.write(source)
    text = bpy.data.texts.get("Text") or bpy.data.texts.new("Text")
    text.clear()
    text.write(source_texts["generate_vortex.py"])
    for name in ("generate_vortex.py", "build_earring.py", "LICENSE"):
        source = source_dir / name
        destination = output_dir / name
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
    stats = {"body_triangles": triangle_count(body), "chain_triangles": triangle_count(chain),
             "annotations_triangles": sum(triangle_count(obj) for obj in annotations)}
    if args.validate:
        stats.update(validate_scene(body, chain, annotations, rig, source_texts))
    # The body budget is mandatory even when optional validation is disabled.
    if stats["body_triangles"] > 20000:
        raise RuntimeError("Vortex body exceeds 20,000 triangles")
    blend_path = output_dir / "NavierStokes_Earring.blend"
    scene.render.filepath = str(output_dir / "earring_preview.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    fbx_path = model_dir / "NavierStokes_Earring.fbx"
    select_only([rig, annotation_root, *meshes])
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path), use_selection=True, object_types={"ARMATURE", "MESH", "EMPTY"},
        global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z", axis_up="Y", use_space_transform=True, bake_space_transform=False,
        use_mesh_modifiers=True, mesh_smooth_type="FACE", use_triangles=True,
        add_leaf_bones=False, use_armature_deform_only=False,
        primary_bone_axis="Y", secondary_bone_axis="X", armature_nodetype="NULL",
        bake_anim=False, path_mode="RELATIVE", embed_textures=False,
    )
    minimum, maximum = bounds(meshes)
    material_contract = materials + [
        {"name": "ChainSilver", "main_texture": None, "color_linear": [0.65, 0.70, 0.78, 1],
         "metallic": 0.85, "roughness": 0.24},
        {"name": "AnnotationTextMat", "main_texture": None, "color_linear": [0.55, 0.58, 0.60, 1]},
        {"name": "AnnotationLineMat", "main_texture": None, "color_linear": [0.27, 0.29, 0.31, 1]},
    ]
    command = ('& "$env:LOCALAPPDATA\\Microsoft\\WindowsApps\\blender-launcher.exe" -b --python "'
               + str(source_dir / "build_earring.py") + '" -- --project "' + str(args.project)
               + '" --validate --render --close-up --run-id reviewed-export')
    contract = {
        "schema_version": 1, "status": "exported", "license": "GPL-3.0-only",
        "source_checkout": str(source_dir), "fbx": str(fbx_path), "blend": str(blend_path),
        "units": "meters", "blender_up": "+Z", "fbx_up": "+Y", "fbx_forward": "-Z",
        "unity_import": {"globalScale": 1, "useFileScale": True, "bakeAxisConversion": True,
                         "animationType": "Generic", "optimizeGameObjects": False,
                         "importAnimation": False, "preserveHierarchy": True},
        "attachment_origin": [0, 0, 0], "pendant_direction_unity": "-Y",
        "body_height_m": BODY_HEIGHT, "chain_length_m": CHAIN_LENGTH,
        "arrow_tip_unity_m": [0, -CHAIN_LENGTH, 0],
        "bounds_blender_m": {"min": minimum, "max": maximum},
        "expected_height_m": BODY_HEIGHT + CHAIN_LENGTH,
        "armature": "NavierStokesRig", "bones": [
            {"name": name, "parent": BONE_NAMES[index - 1] if index else None}
            for index, name in enumerate(BONE_NAMES)],
        "physbone": {"stationary_root": "EarAnchor", "recommended_root": "Chain_01",
                     "explicit_endpoint": "PendantEnd", "endpointPosition": [0, 0, 0]},
        "meshes": {BODY_NAME: {"weight": "Pendant:1", "triangle_budget": 20000},
                   "Chain": {"weight": "linear depth blend Chain_01/Chain_02/Chain_03/Pendant; eyelet Pendant:1",
                             "oval_links": 4, "tip_eyelets": 1},
                   "Annotations": {"type": "EMPTY", "children": list(ANNOTATION_NAMES),
                                   "weight": "each child Pendant:1", "external_fonts": False}},
        "color_encoding": "Actual RGB original ramps baked to sRGB PNG + UV0; no Col/vertex-color shader needed",
        "unity_material_shader": "lilToon", "main_texture_property": "_MainTex",
        "main_color_property": "_Color", "materials": material_contract,
        "triangle_budget_scope": "vortex body only; chain and four separate annotations additional",
        "statistics": stats, "optional_validation_executed": args.validate,
        "execution_command_powershell": command,
        "previews": ["earring_preview.png"] if args.render else [],
    }
    if args.render:
        bpy.ops.render.render(write_still=True)
    if args.close_up:
        camera = scene.camera
        old_location, old_rotation, old_scale = camera.location.copy(), camera.rotation_euler.copy(), camera.data.ortho_scale
        center = Vector((0, 0, -CHAIN_LENGTH / 2))
        camera.location = center + Vector((0.065, -0.3, 0.012))
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera.data.ortho_scale = CHAIN_LENGTH * 1.35
        scene.render.filepath = str(output_dir / "earring_chain_closeup.png")
        bpy.ops.render.render(write_still=True)
        camera.location, camera.rotation_euler, camera.data.ortho_scale = old_location, old_rotation, old_scale
        scene.render.filepath = str(output_dir / "earring_preview.png")
        contract["previews"].append("earring_chain_closeup.png")
    write_json(output_dir / "export-contract.json", contract)
    return {"status": "complete", "run_id": args.run_id, "fbx": str(fbx_path),
            "contract": str(output_dir / "export-contract.json"), "statistics": stats,
            "validation_executed": args.validate, "render_executed": args.render,
            "close_up_executed": args.close_up}


if __name__ == "__main__":
    options = arguments()
    source_directory = Path(__file__).resolve().parent
    output_directory = options.project / "Source"
    output_directory.mkdir(parents=True, exist_ok=True)
    result_path = output_directory / ("smoke-result.json" if options.smoke else "build-result.json")
    write_json(result_path, {"status": "running", "run_id": options.run_id})
    try:
        result = (smoke_saved_blend(options, source_directory, output_directory) if options.smoke
                  else build(options, source_directory, output_directory))
    except Exception:
        write_json(result_path, {"status": "failed", "run_id": options.run_id, "traceback": traceback.format_exc()})
        raise
    else:
        # Written last: wait for this status/run-id, not a stale .fbx or .png.
        write_json(result_path, result)
