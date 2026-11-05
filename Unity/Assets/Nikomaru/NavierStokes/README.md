# Navier–Stokes vortex earring

A hanging, skinned earring based on the GPL-3.0-only `generate_vortex.py` Navier–Stokes vortex. The chain attaches to the vortex's top axial arrow; the FBX attachment origin is the top of the chain, not the pendant centre. All four original RGB-gradient materials use UV0 and ordinary lilToon `_MainTex` with white `_Color`; no custom vertex-colour shader is required.

## Requirements

Unity **2022.3.22f1**, VRChat SDK Avatars **3.10.6**, lilToon **2.4.1**, Modular Avatar **1.18.7**, and its NDMF **1.14.8** dependency were the integration targets. Install those packages before importing the earring. No avatar, SDK, lilToon, Modular Avatar, NDMF or other dependency package is included in the export.

## 日本語クイックスタート

1. Unity **2022.3.22f1** のアバタープロジェクトに、VRChat SDK Avatars **3.10.6**、lilToon **2.4.1**、Modular Avatar **1.18.7**（NDMF **1.14.8**）を先に導入し、本 unitypackage をインポートしてください。これらの依存パッケージやアバター本体は同梱していません。
2. 大きめの獣耳向けは **NavierStokes_Earring_Kemomimi**、通常の人耳向けは **NavierStokes_Earring_Human** を、耳ボーン（または耳・頭に追従するオブジェクト）の子に配置してください。Prefab の原点がチェーン上端です。耳の穴の位置へ移動・回転し、静止姿勢で下へ垂れるよう調整します。
3. Modular Avatar がメニューと FX を自動統合します。VRChat の **Navier-Stokes → Annotations** で「Inward Spiral / Axial Stretching」の説明文字と線だけを切り替えられます。**初期値は ON**、ワールド・アバター切替時には保存しません。複数個配置しても自動リネームにより個別に切り替えられます。
4. 物理揺れは参考アクセサリーの設定を踏襲し、人耳用は実際の Sio シーンの上書き値を使用しています。獣耳用は本体 100 mm＋チェーン 50 mm、人耳用は本体 46 mm＋チェーン 23 mm です。アバターごとの耳位置、干渉、照明下の見た目は実機で調整してください。

配布版には開発用の Build／Smoke スクリプトを含めず、Unity上部に **Nikomaru → Navier-Stokes** メニューを追加しません。Prefab・PhysBone・VRChat内のAnnotations切替には、これらの開発用スクリプトは不要です。旧版を導入済みの場合、新版のインポートだけでは古いファイルは削除されません。アバタープロジェクト内の `Assets/Nikomaru/NavierStokes/Editor/NavierStokesBuilder.cs` と `NavierStokesSmoke.cs` をUnityのProject欄から削除してください（他のNikomaru製品のファイルは削除しないでください）。

## Use

1. Import `Deliverables/navier-stokes-earring.unitypackage` into your avatar project after installing the dependencies.
2. Place **one** of `Prefabs/NavierStokes_Earring_Kemomimi.prefab` or `Prefabs/NavierStokes_Earring_Human.prefab` beneath the desired ear bone (or a transform following the ear/head). Move and rotate the prefab root to the piercing; keep the chain hanging down in the rest pose. The root starts at zero, rather than carrying avatar-specific reference coordinates. Adjust placement for your avatar: no particular avatar skeleton is bundled or required.
3. Modular Avatar installs a **Navier-Stokes → Annotations** menu toggle and FX controller automatically. Animation paths are relative to each prefab root, so nesting beneath arbitrary ear transforms is supported.
4. **Annotations are ON by default.** The bool is synchronized, costs one expression bit per instance and is **not saved** across avatar/world changes. Its source name is `Nikomaru/NavierStokes/Annotations`; MA **Auto Rename** is enabled so multiple earrings have independent bools and do not overwrite each other's animation targets. Each instance installs its own menu entry. Rename the menu submenu asset or configure each MA Menu Installer's target if you want left/right labels or a particular menu layout.

Do not separately merge the supplied expression-parameters asset when using MA: the prefab's MA Parameters already supplies the parameter. The native `Animations/NavierStokes_Parameters.asset` is provided for inspection/manual integration; without MA you must merge the FX/menu/parameter assets yourself, prefix relative animation paths with the actual root path, and assign distinct parameter names for multiple instances.

The fixed `EarAnchor` bone leads to `Chain_01 → Chain_02 → Chain_03 → Pendant → PendantEnd`. The PhysBone starts at `Chain_01`, leaving the ear anchor fixed. Labels/leader lines are skinned to the pendant and grouped under `Annotations`; the toggle does not hide the vortex or chain. The silver chain uses lilToon native reflection/specular (`_UseReflection=1`, metallic .85, smoothness .8); its appearance still depends on world lighting/reflection probes. Annotation material is deliberately white, unlit and double-sided for legibility rather than reproducing the Blender flat-material colour. The vortex/chain are also double-sided for dependable thin-ribbon visibility.

## Sizes and reference derivation

The two *named* sphere prefabs in the reference project are not evidence of different dimensions; their **scene overrides** establish the distinction:

- `Mafuyu_white-Heavy-Sphere/Assets/mafuyu_white.unity`, sphere prefab instance at lines 18043–18111, retains its pendant bone scale 1. Its reference sphere renderer root-bone AABB half-width is .023088075 m (diameter approximately **46.176 mm**). The chain AABB length is about **39.452 mm**; the reference armature also has avatar-specific positioning/rotation that is intentionally not copied.
- `Sio-autum_sphere/Assets/Sio_boy.unity`, lines 339–369, sets `Bone.004` (fileID 5354045180970678967) to uniform **.46**; it does **not** uniformly scale the whole earring. The reference sphere pendant diameter is therefore approximately **21.241 mm** in the reference model/ear scale. The chain bones remain otherwise unscaled. Scene placement is avatar-specific, not a reusable attachment origin.

This vortex is a different silhouette, so these are **reference-informed sizes, not a claim of identical geometry or sphere diameter**. The kemomimi vortex body is **100 mm tall**, plus a **50 mm chain**: approximately **150 mm total** below the piercing (metal link radii may extend slightly). The human variant scales the complete model uniformly by **.46**, giving a **46 mm body**, **23 mm chain**, approximately **69 mm total**. Uniform model scaling deliberately preserves the vortex/chain proportions and rig, unlike the reference's pendant-only change. Both prefab roots remain unit scale. The useful demonstration scene is `Scenes/NavierStokes_Demo.unity` and contains only our two earrings, a camera and light—no avatar.

The simplified chain requested for the final asset uses **four low-poly alternating oval links plus a minimal tip eyelet (480 triangles)**. Blender's authored vortex body has **19,770 triangles**; Unity's imported mesh reports **19,767**. The four annotation meshes together have **2,246 triangles**. Thus the actual Unity assets render **22,493 triangles total** with annotations visible, **20,247** without them (Blender source totals: 22,496 / 20,250). Hiding annotations suppresses their renderers; it does not remove their stored meshes from the package.

### PhysBone profiles

Both reference *prefabs* share the kemomimi/base values, but the **Sio scene overrides** change human-ear dynamics. These distinctions are preserved:

| Setting | Kemomimi | Human (Sio scene) |
|---|---:|---:|
| pull | .254 | .312 |
| spring | .013 | .899 |
| stiffness | .39 | .39 |
| gravity | .704 | .09 |
| gravity falloff | 0 | 0 |
| immobile | .304 | .216 |
| max angle X | 29° | 53.4° |
| max angle Z | 45° | 45° |

Shared: serialized version 1; integration type 0; immobile type 0; limit type 1; collision disabled/radius 0; grabbing and posing allowed; max stretch/squish/stretch motion 0. Human overrides are visible at `Sio_boy.unity:319–338`. The reference README explains the same native MA menu/FX distribution convention; this earring uses native MA components rather than a new runtime script.

## Rebuild and export

The complete corresponding GPL source is archived, import-safely, in `Source/NavierStokes_Source.zip`. Extract it into a project-root `Source/` folder to rebuild, including the GPL license, original generator, `build_earring.py`, Blender file and export contract. The project-root source is not a Unity-imported `.blend`, so Unity does not require Blender merely to use the FBX. The rebuild script's command line is documented in its header and `HANDOVER.md` alongside the project source. The exporter includes explicit source files only, not backup files or logs.

The distribution package contains no compiled C# scripts or developer-menu registrations. `NavierStokesBuilder.cs` and `NavierStokesSmoke.cs` remain only in the development project; the following Unity commands require that development checkout, not a normal package import. The source ZIP contains the Blender/model sources, not installed Unity editor tools. When upgrading from an older package, delete the two old scripts from `Assets/Nikomaru/NavierStokes/Editor` in the consumer project: importing the replacement package does not remove previously imported files.

Development project only: run these from its **Unity project root** after the Blender FBX/textures/export-contract exist (PowerShell):

```powershell
$unity = 'C:/Program Files/Unity/Hub/Editor/2022.3.22f1/Editor/Unity.exe'
& $unity -batchmode -projectPath . -executeMethod Nikomaru.NavierStokes.Editor.NavierStokesBuilder.Build -logFile Deliverables/unity-build.log
& $unity -batchmode -projectPath . -executeMethod Nikomaru.NavierStokes.Editor.NavierStokesBuilder.Validate -logFile Deliverables/unity-validate.log
& $unity -batchmode -projectPath . -executeMethod Nikomaru.NavierStokes.Editor.NavierStokesBuilder.Export -logFile Deliverables/unity-export.log
& $unity -batchmode -projectPath . -executeMethod Nikomaru.NavierStokes.Editor.NavierStokesSmoke.Run -logFile Deliverables/unity-runtime-smoke.log
```

Each entrypoint exits the batch process with 0 on success and 1 on its own failures. Do **not** pass `-quit` to the smoke entrypoint (it exits when the runtime sequence completes), and do **not** pass `-nographics` to rendering smoke. Other entrypoints may run without graphics. The same actions are available under **Nikomaru → Navier-Stokes** in the editor. Close an already-running Unity editor for this project before batch invocation.

Build configures the FBX importer, creates real `.mat`, `.anim`, `.controller`, menu/parameter assets and two `.prefab` files through Unity APIs, and writes the demo scene. Rebuilding preserves generated asset GUIDs. Export writes `Deliverables/navier-stokes-earring.unitypackage` and `package-assets.txt`; it excludes the development `Editor/` folder and C# scripts and uses **no IncludeDependencies**, preventing accidental bundling of external packages.

Validation also writes `Deliverables/unity-validation.json`, including imported skin-matrix-evaluated body/full heights in metres and per-part triangle counts for both prefabs. Runtime smoke writes both `result.txt` and structured `result.json` alongside the PNGs.

The runtime smoke constructs a temporary avatar with both sizes under different nested attachment paths, runs the installed **NDMF/MA build**, verifies distinct remapped menu bools and rewritten animation targets, then enters real Animator ON → independent OFF → both OFF → ON states. It checks actual skinned baked-vertex motion for the body, chain and four annotation meshes and renders PNG evidence. `Deliverables/runtime-smoke/result.txt` is the exercised result; PNGs show ON/OFF and moved-bone frames. This is a deterministic skinning/Animator/render integration smoke, **not a VRChat in-client PhysBone/grab/upload test**. A VRChat avatar upload and in-client fit/lighting/PhysBone check remain a user integration step. Never infer a passing run from the presence of these editor APIs alone.

## License

GPL-3.0-only, matching the original source license. The original generator and license are retained in the source archive. Third-party dependency licenses are not replaced by this license; obtain those packages separately. The package contains no reference sphere meshes, textures, avatars or dependency package files.
