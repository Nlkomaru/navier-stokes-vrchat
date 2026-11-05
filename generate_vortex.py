# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Nlkomaru

import bpy
import bmesh
import numpy as np
import math

# ==============================================================================
# ★ 調整パラメータ（シルエット・線の太さ・文字ラベルの表示ON/OFFをここで一括調整可能）
# ==============================================================================
OVERALL_WIDTH_SCALE  = 1.0   # 渦全体の横幅スケール
LINE_THICKNESS_SCALE = 1.0   # 1本1本の線の太さスケール
SHOW_ANNOTATIONS     = True  # "inward spiral" / "axial stretching" の文字と引き出し線を表示するか

# 1. シーンの安全な初期化
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh, do_unlink=True)
for curve in list(bpy.data.curves):
    bpy.data.curves.remove(curve, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)
for world in list(bpy.data.worlds):
    bpy.data.worlds.remove(world, do_unlink=True)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)

scene = bpy.context.scene
main_collection = scene.collection

# 2. 断面プロファイルの作成（3角断面チューブ ＆ 平たい3角リボン）
def create_profile_curve(name, coords):
    prof_curve = bpy.data.curves.new(name=name, type='CURVE')
    prof_curve.dimensions = '2D'
    spline = prof_curve.splines.new('POLY')
    spline.use_cyclic_u = True
    spline.points.add(len(coords) - 1)
    for i, co in enumerate(coords):
        spline.points[i].co = (co[0], co[1], 0.0, 1.0)
    prof_obj = bpy.data.objects.new(name, prof_curve)
    main_collection.objects.link(prof_obj)
    return prof_obj

# 丸チューブ用（3頂点・スムーズシェーディングで丸チューブに見える）
tri_angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]
prof_tube = create_profile_curve("TubeProfile", [(math.cos(a), math.sin(a)) for a in tri_angles])

# リボン用（平たいきしめん状断面・3頂点）
prof_ribbon = create_profile_curve("RibbonProfile", [(2.15, 0.0), (-2.15, 0.34), (-2.15, -0.34)])

# 3. ストリームライン生成関数
def build_curve_obj(pts, radii, tilts, name, prof_obj, mat):
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.resolution_u = 1
    curve_data.use_fill_caps = False
    curve_data.bevel_mode = 'OBJECT'
    curve_data.bevel_object = prof_obj

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(pts) - 1)
    spline.use_smooth = True

    for i, pt in enumerate(pts):
        spline.points[i].co = (pt[0] * OVERALL_WIDTH_SCALE, pt[1] * OVERALL_WIDTH_SCALE, pt[2], 1.0)
        spline.points[i].radius = radii[i] * LINE_THICKNESS_SCALE
        spline.points[i].tilt = tilts[i]

    obj = bpy.data.objects.new(name, curve_data)
    main_collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj

# 4. マテリアル設定（OpenAI画像の深みのある高彩度カラーパレット）
def create_gradient_material(name, color_stops, viewport_rgba, roughness=0.32, metallic=0.08, emission=0.35):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.diffuse_color = viewport_rgba
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    
    attr_node = nodes.new(type="ShaderNodeAttribute")
    attr_node.attribute_name = "Col"
    
    ramp = nodes.new(type="ShaderNodeValToRGB")
    elems = ramp.color_ramp.elements
    elems[0].position = color_stops[0][0]
    elems[0].color = color_stops[0][1]
    elems[1].position = color_stops[1][0]
    elems[1].color = color_stops[1][1]
    for pos, col in color_stops[2:]:
        e = elems.new(pos)
        e.color = col
        
    links.new(attr_node.outputs["Fac"], ramp.inputs["Fac"])
    if bsdf:
        links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.20
        if "Emission Color" in bsdf.inputs:
            links.new(ramp.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = emission
    return mat

# 1. InnerGold: ブロンズアンバー〜鮮やかなゴールデンオレンジ
mat_inner = create_gradient_material(
    "InnerGold",
    [(0.0, (0.34, 0.12, 0.025, 1.0)), (0.45, (0.72, 0.30, 0.055, 1.0)), (1.0, (1.0, 0.50, 0.12, 1.0))],
    (0.92, 0.50, 0.12, 1.0), roughness=0.35, emission=0.20
)
# 2. MidBlueRibbon: ラベンダースレート〜濃厚なコバルトブルー〜鮮やかなアジュールブルー
mat_mid = create_gradient_material(
    "MidBlueRibbon",
    [(0.0, (0.20, 0.16, 0.29, 1.0)), (0.30, (0.025, 0.10, 0.48, 1.0)), (0.70, (0.02, 0.24, 0.68, 1.0)), (1.0, (0.025, 0.40, 0.82, 1.0))],
    (0.04, 0.26, 0.75, 1.0), roughness=0.32, emission=0.14
)
# 3. OuterCyan: アジュールブルー（内側）〜ターコイズシアン〜鮮やかなエメラルドグリーン（外側穂先）
mat_outer = create_gradient_material(
    "OuterCyan",
    [(0.0, (0.02, 0.24, 0.65, 1.0)), (0.35, (0.025, 0.52, 0.68, 1.0)), (0.72, (0.045, 0.72, 0.60, 1.0)), (1.0, (0.12, 0.82, 0.46, 1.0))],
    (0.06, 0.72, 0.60, 1.0), roughness=0.30, emission=0.18
)
# 4. AxisWhite: 中心の白い軸
mat_white = create_gradient_material(
    "AxisWhite",
    [(0.0, (0.80, 0.84, 0.88, 1.0)), (1.0, (0.98, 0.99, 1.0, 1.0))],
    (0.95, 0.95, 0.95, 1.0), roughness=0.15, emission=0.55
)

all_materials = [mat_inner, mat_mid, mat_outer, mat_white]

np.random.seed(42)
curve_objects = []

# ==============================================================================
# 5. OpenAI Navier-Stokes 3層ストリームライン構造（合計 14,778 Tris < 20,000）
# ==============================================================================

# 【パーツA】InnerGold (Axial Stretching): 24本 × 25点 (3,456 Tris)
# 中心軸の周りを螺旋で昇り降りし、上下端で斜めの毛束（右上・左下）としてスッと伸びる
for i in range(24):
    sign_z = 1.0 if i < 12 else -1.0
    theta0 = np.random.uniform(0, 2 * math.pi)
    r_base = np.random.uniform(0.18, 0.58)
    z_start = sign_z * np.random.uniform(-0.40, 0.40)
    z_end   = sign_z * np.random.uniform(2.85, 4.38)
    
    n_pts = 25
    t_vals = np.linspace(0, 1, n_pts)
    turns = np.random.uniform(0.85, 1.45) * 2 * math.pi
    
    pts, radii, tilts = [], [], []
    use_rib = (i % 3 == 0)
    thick = np.random.uniform(0.024, 0.038) if use_rib else np.random.uniform(0.020, 0.032)
    
    drift_x = sign_z * np.random.uniform(0.08, 0.38)
    
    for t in t_vals:
        flare = 0.26 * (max(0.0, t - 0.65) / 0.35) ** 2.0
        r = r_base * (1.0 - 0.35 * t) + flare
        theta = theta0 + turns * t
        z = z_start + (z_end - z_start) * (t ** 1.12)
        
        x = r * math.cos(theta) + drift_x * (t ** 1.5)
        y = r * math.sin(theta)
        pts.append((x, y, z))
        
        taper = (math.sin(t * math.pi) ** 0.40) * (1.0 - 0.18 * t)
        radii.append(max(0.0008, thick * taper))
        tilts.append(theta * 0.4)
        
    prof = prof_ribbon if use_rib else prof_tube
    obj = build_curve_obj(pts, radii, tilts, f"InnerGold_{i}", prof, mat_inner)
    curve_objects.append((obj, 0))

# 【パーツB】MidBlueRibbon: 28本 × 29点 (4,704 Tris)
# オレンジ柱の周りを斜めに巻き上がる平たい青〜紫スレートのリボンとチューブ。
for i in range(28):
    sign_z = 1.0 if i < 14 else -1.0
    theta0 = np.random.uniform(0, 2 * math.pi)
    
    r_start = np.random.uniform(1.08, 1.88)
    r_end   = np.random.uniform(0.36, 0.88)
    z_start = np.random.uniform(-0.95, 0.95)
    z_end   = sign_z * np.random.uniform(1.85, 4.18)
    
    n_pts = 29
    t_vals = np.linspace(0, 1, n_pts)
    turns = np.random.uniform(0.85, 1.35) * 2 * math.pi
    
    pts, radii, tilts = [], [], []
    use_rib = (i % 3 != 0)
    thick = np.random.uniform(0.026, 0.042) if use_rib else np.random.uniform(0.024, 0.036)
    
    drift_x = sign_z * np.random.uniform(0.05, 0.42)
    
    for t in t_vals:
        r = r_start * ((1.0 - t) ** 0.82) + r_end * (t ** 0.82)
        if t > 0.72 and (i % 3 == 0):
            r += 0.35 * ((t - 0.72) / 0.28) ** 1.7
        theta = theta0 + turns * t
        z = z_start * (1.0 - t) + z_end * (t ** 1.15)
        
        x_raw = r * math.cos(theta)
        tilt_z = -0.15 * x_raw * (1.0 - 0.5 * t)
        x = x_raw + drift_x * (t ** 1.5)
        y = r * math.sin(theta)
        pts.append((x, y, z + tilt_z))
        
        taper = math.sin(t * math.pi) ** 0.36
        radii.append(max(0.0008, thick * taper))
        tilts.append(math.pi * 0.38 + 0.45 * t)
        
    prof = prof_ribbon if use_rib else prof_tube
    obj = build_curve_obj(pts, radii, tilts, f"MidBlue_{i}", prof, mat_mid)
    curve_objects.append((obj, 1))

# 【パーツC】OuterCyan (Inward Spiral): 42本 × 21点 (5,040 Tris)
# ★ 左右のウイングがそのまま正面下寄りのボウル弧へシームレスにつながり、中央の青いネストとオレンジ柱を露出させる設計
for i in range(42):
    n_pts = 21
    t_vals = np.linspace(0, 1, n_pts)
    pts, radii, tilts = [], [], []
    
    if i < 19:
        # 【C1: 左ウイング → 正面ボウルへ巻き込むストリーム（19本）】
        theta_tip = math.pi + np.random.uniform(-0.30, 0.25)
        turns = np.random.uniform(0.28, 0.50) * 2 * math.pi
        
        r_tip  = np.random.uniform(2.35, 3.88)
        r_core = np.random.uniform(1.05, 1.65)
        
        z_core = np.random.uniform(-0.90, 0.30)
        curl_up = np.random.uniform(0.55, 1.80)
        dip_z   = np.random.uniform(-0.50, -0.15)
        
        thick   = np.random.uniform(0.028, 0.045)
        use_rib = (i % 5 == 0)
        
        for t in t_vals:
            r = r_tip * ((1.0 - t) ** 1.18) + r_core * (t ** 0.88)
            theta = theta_tip + turns * (t ** 1.05)
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = z_core + curl_up * ((1.0 - t) ** 4.0) + dip_z * math.sin(t * math.pi)
            pts.append((x, y, z))
            if t < 0.28:
                taper = (t / 0.28) ** 0.80
            else:
                taper = ((1.0 - t) / 0.72) ** 0.45
            radii.append(max(0.0006, thick * taper))
            tilts.append(0.35 * t)
            
    elif i < 38:
        # 【C2: 右上アーチ → 右ウイングへ放射状に広がるストリーム（19本）】
        theta_tip = np.random.uniform(-0.24 * math.pi, 0.16 * math.pi)
        turns = np.random.uniform(0.28, 0.48) * 2 * math.pi
        
        r_tip  = np.random.uniform(2.35, 3.92)
        r_core = np.random.uniform(1.05, 1.65)
        
        z_core = np.random.uniform(0.0, 1.25)
        z_tip  = z_core - np.random.uniform(0.40, 1.55)
        arch_z = np.random.uniform(0.25, 0.75)
        
        thick   = np.random.uniform(0.028, 0.045)
        use_rib = (i % 5 == 0)
        
        for t in t_vals:
            r = r_tip * ((1.0 - t) ** 1.18) + r_core * (t ** 0.88)
            theta = theta_tip + turns * (t ** 1.05)
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = z_tip * ((1.0 - t) ** 1.25) + z_core * (t ** 0.9) + arch_z * math.sin(t * math.pi)
            pts.append((x, y, z))
            if t < 0.28:
                taper = (t / 0.28) ** 0.80
            else:
                taper = ((1.0 - t) / 0.72) ** 0.45
            radii.append(max(0.0006, thick * taper))
            tilts.append(0.35 * t)
            
    else:
        # 【C3: 左から手前下寄りを通って右へ抜けるボウル・ブリッジ（4本）】
        theta_start = math.pi + np.random.uniform(-0.15, 0.20)
        turns = np.random.uniform(0.45, 0.60) * 2 * math.pi
        r_mid = np.random.uniform(1.45, 2.05)
        r_end = np.random.uniform(1.05, 1.48)
        z_base = np.random.uniform(-0.95, -0.35)
        tilt_slope = np.random.uniform(-0.12, 0.02)
        
        thick   = np.random.uniform(0.028, 0.040)
        use_rib = (i % 2 == 0)
        
        for t in t_vals:
            arch = math.sin(t * math.pi) ** 0.75
            r = r_mid * arch + r_end * (1.0 - arch)
            theta = theta_start + turns * t
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            z = z_base + tilt_slope * x - 0.15 * math.sin(t * math.pi)
            pts.append((x, y, z))
            taper = math.sin(t * math.pi) ** 0.45
            radii.append(max(0.0008, thick * taper))
            tilts.append(math.pi * 0.40)
            
    prof = prof_ribbon if use_rib else prof_tube
    obj = build_curve_obj(pts, radii, tilts, f"OuterCyan_{i}", prof, mat_outer)
    curve_objects.append((obj, 2))

# 【パーツD】下部左側のスムーズな大弧 ＆ 上部右寄りのアーチ（10本 × 27点 = 1,560 Tris）
for i in range(10):
    sign_z = -1.0 if i < 6 else 1.0
    if sign_z < 0:
        theta0 = np.random.uniform(0.68 * math.pi, 1.15 * math.pi)
        r_mid = np.random.uniform(1.45, 2.25)
        r_end = np.random.uniform(0.28, 0.72)
        z_start = np.random.uniform(-0.2, 0.4)
        z_end   = -np.random.uniform(2.3, 3.95)
        turns   = np.random.uniform(0.28, 0.46) * 2 * math.pi
    else:
        theta0 = np.random.uniform(-0.32 * math.pi, 0.42 * math.pi)
        r_mid = np.random.uniform(1.25, 1.95)
        r_end = np.random.uniform(0.25, 0.65)
        z_start = np.random.uniform(-0.3, 0.3)
        z_end   = np.random.uniform(2.4, 3.95)
        turns   = np.random.uniform(0.30, 0.48) * 2 * math.pi
        
    n_pts = 27
    t_vals = np.linspace(0, 1, n_pts)
    
    pts, radii, tilts = [], [], []
    thick = np.random.uniform(0.026, 0.042)
    for t in t_vals:
        arch = math.sin(t * math.pi) ** 0.78
        r = r_mid * arch + r_end * (1.0 - arch * 0.72)
        theta = theta0 + turns * (t ** 0.9)
        z = z_start * (1.0 - t) + z_end * (t ** 1.15)
        pts.append((r * math.cos(theta), r * math.sin(theta), z))
        taper = math.sin(t * math.pi) ** 0.42
        radii.append(max(0.0008, thick * taper))
        tilts.append(0.3 * t)
        
    mat_choice = mat_outer if (i % 2 == 0) else mat_mid
    mat_idx = 2 if (i % 2 == 0) else 1
    obj = build_curve_obj(pts, radii, tilts, f"ArchStream_{i}", prof_tube, mat_choice)
    curve_objects.append((obj, mat_idx))

# 6. 中心を貫く白い矢印（Z = -4.55 〜 +4.92）
axis_pts = [np.array([0.0, 0.0, -4.55]), np.array([0.0, 0.0, 4.65])]
axis_curve = bpy.data.curves.new(name="AxisCurve", type='CURVE')
axis_curve.dimensions = '3D'
axis_curve.bevel_depth = 0.018
axis_curve.bevel_resolution = 1
spline = axis_curve.splines.new('POLY')
spline.points.add(1)
for i, pt in enumerate(axis_pts):
    spline.points[i].co = (pt[0], pt[1], pt[2], 1.0)
axis_obj = bpy.data.objects.new("AxisWhiteObj", axis_curve)
main_collection.objects.link(axis_obj)
curve_objects.append((axis_obj, 3))

arrow_pts = [(0, 0, 4.60), (0, 0, 4.92)]
arrow_obj = build_curve_obj(arrow_pts, [0.075, 0.0], [0.0, 0.0], "AxisArrowHead", prof_tube, mat_white)
curve_objects.append((arrow_obj, 3))

# 7. bmeshで全オブジェクトを1つのメッシュに結合（厳密に 20,000 Tris 以下）
depsgraph = bpy.context.evaluated_depsgraph_get()
bm = bmesh.new()

for obj, mat_idx in curve_objects:
    eval_obj = obj.evaluated_get(depsgraph)
    temp_mesh = bpy.data.meshes.new_from_object(eval_obj)
    for poly in temp_mesh.polygons:
        poly.material_index = mat_idx
        poly.use_smooth = True
    bm.from_mesh(temp_mesh)
    bpy.data.meshes.remove(temp_mesh)

for obj, _ in curve_objects:
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.data.objects.remove(prof_tube, do_unlink=True)
bpy.data.objects.remove(prof_ribbon, do_unlink=True)

final_mesh = bpy.data.meshes.new("NavierStokes_OpenAI_Mesh")
bm.to_mesh(final_mesh)
bm.free()

final_mesh.calc_loop_triangles()
if len(final_mesh.loop_triangles) > 20000:
    raise RuntimeError(f"Vortex exceeds 20,000 Tris: {len(final_mesh.loop_triangles)}")

final_obj = bpy.data.objects.new("NavierStokes_OpenAI_Vortex", final_mesh)
main_collection.objects.link(final_obj)

for mat in all_materials:
    final_obj.data.materials.append(mat)

# 頂点カラー属性（Col）にグラデーション係数を格納
color_attr = final_mesh.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')
for poly in final_mesh.polygons:
    for loop_idx in poly.loop_indices:
        v_idx = final_mesh.loops[loop_idx].vertex_index
        co = final_mesh.vertices[v_idx].co
        r_val = math.sqrt(co.x**2 + co.y**2) / max(0.1, OVERALL_WIDTH_SCALE)
        if poly.material_index == 2:
            fac = min(1.0, max(0.0, (r_val - 1.25) / 2.05))
        elif poly.material_index == 1:
            fac = min(1.0, max(0.0, (r_val - 0.38) / 1.15))
        else:
            fac = min(1.0, max(0.0, abs(co.z) / 3.6))
        color_attr.data[loop_idx].color = (fac, fac, fac, 1.0)

# ==============================================================================
# 8. 【別コレクション管理】文字ラベル & 引き出し線 ("Annotations")
# アウトライナーの目のアイコン/カメラアイコン、または SHOW_ANNOTATIONS で一発ON/OFF可能！
# ==============================================================================
annot_collection = bpy.data.collections.new("Annotations")
scene.collection.children.link(annot_collection)
annot_collection.hide_viewport = not SHOW_ANNOTATIONS
annot_collection.hide_render   = not SHOW_ANNOTATIONS

# ラベル用の発光マテリアル（照明に左右されずOpenAI画像と同じくっきりしたオフホワイト/グレーで表示）
def create_unlit_material(name, rgba, strength=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.diffuse_color = rgba
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = 1.0
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = rgba
            bsdf.inputs["Emission Strength"].default_value = strength
    return mat

mat_annot_text = create_unlit_material("AnnotationTextMat", (0.55, 0.58, 0.60, 1.0), strength=0.8)
mat_annot_line = create_unlit_material("AnnotationLineMat", (0.27, 0.29, 0.31, 1.0), strength=0.8)

def create_annotation_text(name, body_text, location, size=0.44):
    font_curve = bpy.data.curves.new(type="FONT", name=name)
    font_curve.body = body_text
    font_curve.size = size
    font_curve.space_line = 0.95
    font_curve.align_x = 'LEFT'
    font_curve.align_y = 'TOP'
    # Blender内蔵フォントを使用し、OS付属フォントの埋め込み・再配布を避ける。
    text_obj = bpy.data.objects.new(name, font_curve)
    text_obj.location = location
    text_obj.rotation_euler = (math.radians(90), 0, 0)
    text_obj.data.materials.append(mat_annot_text)
    annot_collection.objects.link(text_obj)
    return text_obj

def create_leader_line(name, pt_start, pt_end, thickness=0.012):
    line_curve = bpy.data.curves.new(name=name, type='CURVE')
    line_curve.dimensions = '3D'
    line_curve.bevel_depth = thickness
    line_curve.bevel_resolution = 1
    spline = line_curve.splines.new('POLY')
    spline.points.add(1)
    spline.points[0].co = (pt_start[0], pt_start[1], pt_start[2], 1.0)
    spline.points[1].co = (pt_end[0], pt_end[1], pt_end[2], 1.0)
    line_obj = bpy.data.objects.new(name, line_curve)
    line_obj.data.materials.append(mat_annot_line)
    annot_collection.objects.link(line_obj)
    return line_obj

# (1) "inward\nspiral" ラベルと引き出し線（左上から左ウイングのシアン穂先を指す）
create_annotation_text("Label_InwardSpiral", "inward\nspiral", location=(-4.35, -0.5, 3.50), size=0.52)
create_leader_line("Line_InwardSpiral", pt_start=(-3.65, -0.5, 2.30), pt_end=(-2.85, -0.5, 0.75), thickness=0.008)

# (2) "axial\nstretching" ラベルと引き出し線（右上から中心部のオレンジ/青の軸方向ストレッチを指す）
create_annotation_text("Label_AxialStretching", "axial\nstretching", location=(1.55, -0.5, 4.85), size=0.52)
create_leader_line("Line_AxialStretching", pt_start=(1.58, -0.5, 3.48), pt_end=(0.45, -0.5, 3.20), thickness=0.008)

# ==============================================================================
# 9. ワールド背景・ライト・カメラ設定
# ==============================================================================
world = bpy.data.worlds.new("BlackWorld")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs["Color"].default_value = (0.004, 0.004, 0.006, 1.0)

light1_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light1_data.energy = 380
light1_data.size = 8.5
light1_obj = bpy.data.objects.new(name="KeyLight", object_data=light1_data)
light1_obj.location = (6.0, -7.5, 5.5)
light1_obj.rotation_euler = (math.radians(45), 0, math.radians(35))
main_collection.objects.link(light1_obj)

light2_data = bpy.data.lights.new(name="FillLight", type='AREA')
light2_data.energy = 200
light2_data.size = 7.5
light2_obj = bpy.data.objects.new(name="FillLight", object_data=light2_data)
light2_obj.location = (-6.5, -6.0, -4.0)
light2_obj.rotation_euler = (math.radians(120), 0, math.radians(-40))
main_collection.objects.link(light2_obj)

light3_data = bpy.data.lights.new(name="RimLight", type='AREA')
light3_data.energy = 240
light3_data.size = 6.0
light3_obj = bpy.data.objects.new(name="RimLight", object_data=light3_data)
light3_obj.location = (0.0, 5.5, 3.0)
light3_obj.rotation_euler = (math.radians(-60), 0, 0)
main_collection.objects.link(light3_obj)

# カメラを全体が余裕をもって収まる距離（Y=-15.0）に配置
cam_data = bpy.data.cameras.new(name="MainCamera")
cam_data.lens = 50.0
cam_obj = bpy.data.objects.new(name="MainCamera", object_data=cam_data)
cam_obj.location = (0, -15.0, 0.12)
cam_obj.rotation_euler = (math.radians(90), 0, 0)
main_collection.objects.link(cam_obj)
scene.camera = cam_obj

scene.render.resolution_x = 1200
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'None'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# 10. ビューポートをマテリアルプレビューに切り替え
if bpy.context.screen:
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'MATERIAL'
