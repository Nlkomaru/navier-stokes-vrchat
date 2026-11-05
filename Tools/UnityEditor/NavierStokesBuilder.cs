// SPDX-License-Identifier: GPL-3.0-only
// Native Unity editor asset generation; requires VRC SDK Avatars, Modular Avatar and lilToon.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using nadena.dev.modular_avatar.core;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using VRC.SDK3.Avatars.Components;
using VRC.SDK3.Avatars.ScriptableObjects;
using VRC.SDK3.Dynamics.PhysBone.Components;
using Object = UnityEngine.Object;

namespace Nikomaru.NavierStokes.Editor
{
    public static class NavierStokesBuilder
    {
        public const string Root = "Assets/Nikomaru/NavierStokes";
        public const string ModelPath = Root + "/Models/NavierStokes_Earring.fbx";
        public const string Parameter = "Nikomaru/NavierStokes/Annotations";
        public const string ControllerPath = Root + "/Animations/NavierStokes_FX.controller";
        public const string DemoPath = Root + "/Scenes/NavierStokes_Demo.unity";
        public const string HumanPath = Root + "/Prefabs/NavierStokes_Earring_Human.prefab";
        public const string KemomimiPath = Root + "/Prefabs/NavierStokes_Earring_Kemomimi.prefab";
        public const float HumanScale = .46f;
        static readonly string[] LabelNames = { "Label_InwardSpiral", "Line_InwardSpiral", "Label_AxialStretching", "Line_AxialStretching" };
        static readonly string[] BoneNames = { "EarAnchor", "Chain_01", "Chain_02", "Chain_03", "Pendant", "PendantEnd" };
        static readonly Dictionary<string, string> GradientNames = new Dictionary<string, string>
        {
            { "InnerGold", "InnerGold_Gradient.png" }, { "MidBlueRibbon", "MidBlueRibbon_Gradient.png" },
            { "OuterCyan", "OuterCyan_Gradient.png" }, { "AxisWhite", "AxisWhite_Gradient.png" }
        };

        [MenuItem("Nikomaru/Navier-Stokes/Build assets")]
        public static void Build() { Run(BuildAssets); }
        [MenuItem("Nikomaru/Navier-Stokes/Validate assets")]
        public static void Validate() { Run(ValidateAssets); }
        [MenuItem("Nikomaru/Navier-Stokes/Export unitypackage")]
        public static void Export() { Run(ExportAssets); }

        static void Run(Action action)
        {
            try { action(); Debug.Log("Navier-Stokes: " + action.Method.Name + " succeeded."); if (Application.isBatchMode) EditorApplication.Exit(0); }
            catch (Exception e) { Debug.LogException(e); if (Application.isBatchMode) EditorApplication.Exit(1); else throw; }
        }
        public static void Require(bool value, string message) { if (!value) throw new InvalidOperationException(message); }
        static T Load<T>(string path) where T : Object
        {
            var asset = AssetDatabase.LoadAssetAtPath<T>(path);
            Require(asset != null, "Missing " + typeof(T).Name + ": " + path);
            return asset;
        }
        public static Transform Find(Transform root, string name)
        {
            var matches = root.GetComponentsInChildren<Transform>(true).Where(t => t.name == name).ToArray();
            Require(matches.Length == 1, "Expected exactly one " + name + ", found " + matches.Length);
            return matches[0];
        }
        static void Folder(string relative)
        {
            var parts = relative.Split('/'); var path = parts[0];
            for (int i = 1; i < parts.Length; i++) { if (!AssetDatabase.IsValidFolder(path + "/" + parts[i])) AssetDatabase.CreateFolder(path, parts[i]); path += "/" + parts[i]; }
        }
        static void SaveAsset(Object asset, string path)
        {
            var old = AssetDatabase.LoadMainAssetAtPath(path);
            if (old == null) AssetDatabase.CreateAsset(asset, path);
            else { Require(old.GetType() == asset.GetType(), "Asset type changed: " + path); EditorUtility.CopySerialized(asset, old); Object.DestroyImmediate(asset); EditorUtility.SetDirty(old); }
        }
        static void BuildAssets()
        {
            Require(File.Exists(ModelPath), "Run Source/build_earring.py with Blender before building Unity assets.");
            Require(File.Exists("Source/export-contract.json"), "Missing Blender Source/export-contract.json.");
            foreach (var folder in new[] { "Materials", "Animations", "Prefabs", "Scenes", "Source" }) Folder(Root + "/" + folder);
            PackageSource();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(ModelPath) as ModelImporter;
            Require(importer != null, "FBX has no ModelImporter.");
            importer.animationType = ModelImporterAnimationType.Generic;
            importer.importAnimation = false;
            importer.optimizeGameObjects = false;
            importer.isReadable = true;
            importer.globalScale = 1;
            importer.useFileScale = true;
            importer.bakeAxisConversion = true;
            importer.preserveHierarchy = true;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.SaveAndReimport();
            var model = Load<GameObject>(ModelPath);
            var temp = Object.Instantiate(model);
            try
            {
                temp.name = "Model";
                foreach (var importedAnimator in temp.GetComponentsInChildren<Animator>(true)) Object.DestroyImmediate(importedAnimator);
                var materials = BuildMaterials(temp);
                foreach (var renderer in temp.GetComponentsInChildren<Renderer>(true))
                {
                    renderer.sharedMaterials = renderer.sharedMaterials.Select(m => materials[CleanMaterialName(m.name)]).ToArray();
                    if (renderer is SkinnedMeshRenderer skin) skin.updateWhenOffscreen = true;
                }
                var annotations = temp.GetComponentsInChildren<Transform>(true).SingleOrDefault(t => t.name == "Annotations");
                if (annotations == null) { annotations = new GameObject("Annotations").transform; annotations.SetParent(temp.transform, false); }
                foreach (var name in LabelNames)
                {
                    var label = Find(temp.transform, name);
                    Require(label.GetComponent<Renderer>() != null, "Annotation has no mesh renderer: " + name);
                    if (!label.IsChildOf(annotations)) label.SetParent(annotations, true);
                }
                annotations.gameObject.SetActive(true);
                var root = new GameObject("NavierStokes_Earring");
                try
                {
                    temp.transform.SetParent(root.transform, false);
                    BuildAnimation(root.transform, annotations);
                    BuildMenus();
                    BuildPrefab(root, false);
                    BuildPrefab(root, true);
                }
                finally { Object.DestroyImmediate(root); temp = null; }
            }
            finally { if (temp != null) Object.DestroyImmediate(temp); }
            AssetDatabase.SaveAssets();
            BuildDemo();
            ValidateAssets();
        }
        static string CleanMaterialName(string name) { return name.Replace(" (Instance)", ""); }
        static Dictionary<string, Material> BuildMaterials(GameObject model)
        {
            var shader = Shader.Find("lilToon"); Require(shader != null, "Install lilToon before building.");
            var result = new Dictionary<string, Material>();
            foreach (var source in model.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Distinct())
            {
                Require(source != null, "FBX has an empty material slot.");
                var name = CleanMaterialName(source.name);
                if (result.ContainsKey(name)) continue;
                var mat = new Material(shader) { name = name };
                mat.SetColor("_Color", Color.white);
                if (GradientNames.TryGetValue(name, out var textureName))
                {
                    var path = Root + "/Textures/" + textureName;
                    var ti = AssetImporter.GetAtPath(path) as TextureImporter;
                    Require(ti != null, "Missing RGB gradient texture: " + path);
                    ti.sRGBTexture = true; ti.wrapMode = TextureWrapMode.Clamp; ti.mipmapEnabled = false; ti.filterMode = FilterMode.Bilinear;
                    ti.textureCompression = TextureImporterCompression.Uncompressed; ti.SaveAndReimport();
                    mat.SetTexture("_MainTex", Load<Texture2D>(path));
                }
                else
                {
                    Require(name == "ChainSilver" || name == "AnnotationTextMat" || name == "AnnotationLineMat", "Unknown FBX material " + name);
                    mat.SetColor("_Color", name == "ChainSilver" ? new Color(.72f, .77f, .85f) : Color.white);
                }
                mat.SetFloat("_Cull", (float)CullMode.Off);
                mat.SetFloat("_AsUnlit", name.StartsWith("Annotation", StringComparison.Ordinal) ? 1 : .35f);
                if (name == "ChainSilver")
                {
                    mat.SetFloat("_AsUnlit", 0);
                    mat.SetFloat("_UseReflection", 1); mat.SetFloat("_Metallic", .85f);
                    mat.SetFloat("_Smoothness", .8f); mat.SetFloat("_ApplySpecular", 1); mat.SetFloat("_SpecularToon", 0);
                }
                SaveAsset(mat, Root + "/Materials/" + name + ".mat");
                result[name] = Load<Material>(Root + "/Materials/" + name + ".mat");
            }
            foreach (var name in GradientNames.Keys) Require(result.ContainsKey(name), "Missing gradient material " + name);
            return result;
        }
        static void BuildAnimation(Transform root, Transform annotations)
        {
            var path = AnimationUtility.CalculateTransformPath(annotations, root);
            foreach (bool enabled in new[] { false, true })
            {
                var clip = new AnimationClip { name = enabled ? "Annotations_On" : "Annotations_Off", frameRate = 60 };
                AnimationUtility.SetEditorCurve(clip, EditorCurveBinding.FloatCurve(path, typeof(GameObject), "m_IsActive"), AnimationCurve.Constant(0, 1f / 60f, enabled ? 1 : 0));
                SaveAsset(clip, Root + "/Animations/" + clip.name + ".anim");
            }
            var controller = LoadOrCreateController();
            // Rebuild only this controller's generated subassets, keeping its GUID stable on repeat builds.
            foreach (var subasset in AssetDatabase.LoadAllAssetsAtPath(ControllerPath)) if (subasset != controller) Object.DestroyImmediate(subasset, true);
            controller.parameters = new[] { new AnimatorControllerParameter { name = Parameter, type = AnimatorControllerParameterType.Bool, defaultBool = true } };
            var machine = new AnimatorStateMachine { name = "Annotations" };
            AssetDatabase.AddObjectToAsset(machine, controller);
            controller.layers = new[] { new AnimatorControllerLayer { name = "Annotations", defaultWeight = 1, stateMachine = machine } };
            var on = machine.AddState("On"); on.motion = Load<AnimationClip>(Root + "/Animations/Annotations_On.anim"); on.writeDefaultValues = false;
            var off = machine.AddState("Off"); off.motion = Load<AnimationClip>(Root + "/Animations/Annotations_Off.anim"); off.writeDefaultValues = false;
            machine.defaultState = on;
            AddTransition(on, off, AnimatorConditionMode.IfNot);
            AddTransition(off, on, AnimatorConditionMode.If);
            EditorUtility.SetDirty(controller);
        }
        static AnimatorController LoadOrCreateController()
        {
            return AssetDatabase.LoadAssetAtPath<AnimatorController>(ControllerPath) ?? AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
        }
        static void AddTransition(AnimatorState from, AnimatorState to, AnimatorConditionMode condition)
        {
            var transition = from.AddTransition(to); transition.hasExitTime = false; transition.duration = 0;
            transition.AddCondition(condition, 0, Parameter);
        }
        static void BuildMenus()
        {
            var submenu = ScriptableObject.CreateInstance<VRCExpressionsMenu>(); submenu.name = "NavierStokes_SubMenu";
            submenu.controls.Add(new VRCExpressionsMenu.Control { name = "Annotations", type = VRCExpressionsMenu.Control.ControlType.Toggle, parameter = new VRCExpressionsMenu.Control.Parameter { name = Parameter }, value = 1 });
            SaveAsset(submenu, Root + "/Animations/NavierStokes_SubMenu.asset");
            var menu = ScriptableObject.CreateInstance<VRCExpressionsMenu>(); menu.name = "NavierStokes_Menu";
            menu.controls.Add(new VRCExpressionsMenu.Control { name = "Navier-Stokes", type = VRCExpressionsMenu.Control.ControlType.SubMenu, subMenu = Load<VRCExpressionsMenu>(Root + "/Animations/NavierStokes_SubMenu.asset") });
            SaveAsset(menu, Root + "/Animations/NavierStokes_Menu.asset");
            var parameters = ScriptableObject.CreateInstance<VRCExpressionParameters>(); parameters.name = "NavierStokes_Parameters";
            parameters.parameters = new[] { new VRCExpressionParameters.Parameter { name = Parameter, valueType = VRCExpressionParameters.ValueType.Bool, defaultValue = 1, saved = false, networkSynced = true } };
            SaveAsset(parameters, Root + "/Animations/NavierStokes_Parameters.asset");
        }
        static void BuildPrefab(GameObject root, bool human)
        {
            root.name = human ? "NavierStokes_Earring_Human" : "NavierStokes_Earring_Kemomimi";
            root.transform.localScale = Vector3.one;
            root.transform.Find("Model").localScale = Vector3.one * (human ? HumanScale : 1);
            var merge = root.GetComponent<ModularAvatarMergeAnimator>() ?? root.AddComponent<ModularAvatarMergeAnimator>();
            merge.animator = Load<AnimatorController>(ControllerPath); merge.layerType = VRCAvatarDescriptor.AnimLayerType.FX;
            merge.pathMode = MergeAnimatorPathMode.Relative; merge.deleteAttachedAnimator = true; merge.matchAvatarWriteDefaults = true;
            var menu = root.GetComponent<ModularAvatarMenuInstaller>() ?? root.AddComponent<ModularAvatarMenuInstaller>();
            menu.menuToAppend = Load<VRCExpressionsMenu>(Root + "/Animations/NavierStokes_Menu.asset");
            var parameters = root.GetComponent<ModularAvatarParameters>() ?? root.AddComponent<ModularAvatarParameters>();
            parameters.parameters = new List<ParameterConfig> { new ParameterConfig { nameOrPrefix = Parameter, internalParameter = true, syncType = ParameterSyncType.Bool, defaultValue = 1, hasExplicitDefaultValue = true, saved = false, localOnly = false } };
            var physics = root.GetComponent<VRCPhysBone>() ?? root.AddComponent<VRCPhysBone>();
            physics.rootTransform = Find(root.transform, "Chain_01");
            var serialized = new SerializedObject(physics);
            SetInt(serialized, "version", 1); SetInt(serialized, "integrationType", 0); SetInt(serialized, "immobileType", 0);
            SetInt(serialized, "multiChildType", 0); SetInt(serialized, "allowCollision", 0); SetInt(serialized, "limitType", 1);
            SetInt(serialized, "allowGrabbing", 1); SetInt(serialized, "allowPosing", 1);
            SetFloat(serialized, "pull", human ? .312f : .254f); SetFloat(serialized, "spring", human ? .899f : .013f);
            SetFloat(serialized, "stiffness", .39f); SetFloat(serialized, "gravity", human ? .09f : .704f);
            SetFloat(serialized, "gravityFalloff", 0); SetFloat(serialized, "immobile", human ? .216f : .304f);
            SetFloat(serialized, "radius", 0); SetFloat(serialized, "maxAngleX", human ? 53.4f : 29);
            SetFloat(serialized, "maxAngleZ", 45); SetFloat(serialized, "maxStretch", 0); SetFloat(serialized, "maxSquish", 0); SetFloat(serialized, "stretchMotion", 0);
            serialized.ApplyModifiedPropertiesWithoutUndo();
            PrefabUtility.SaveAsPrefabAsset(root, human ? HumanPath : KemomimiPath);
        }
        static SerializedProperty Property(SerializedObject obj, string name)
        {
            var prop = obj.FindProperty(name); Require(prop != null, "Installed SDK lacks PhysBone field " + name); return prop;
        }
        static void SetInt(SerializedObject obj, string name, int value) { Property(obj, name).intValue = value; }
        static void SetFloat(SerializedObject obj, string name, float value) { Property(obj, name).floatValue = value; }

        static void BuildDemo()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var large = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(KemomimiPath)); large.transform.position = new Vector3(-.09f, .15f, 0);
            var small = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(HumanPath)); small.transform.position = new Vector3(.09f, .15f, 0);
            var camera = new GameObject("Preview Camera").AddComponent<Camera>(); camera.transform.position = new Vector3(0, .07f, -.6f);
            camera.transform.LookAt(new Vector3(0, .07f, 0)); camera.orthographic = true; camera.orthographicSize = .17f;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(.035f, .045f, .065f);
            var light = new GameObject("Key Light").AddComponent<Light>(); light.type = LightType.Directional; light.intensity = 1.1f; light.transform.rotation = Quaternion.Euler(35, -30, 0);
            EditorSceneManager.SaveScene(scene, DemoPath);
        }
        public static void ValidateAssets()
        {
            var geometry = new List<GeometryReport>();
            Require(File.Exists(Root + "/Source/NavierStokes_Source.zip"), "Missing packaged corresponding source.");
            foreach (var path in new[] { KemomimiPath, HumanPath })
            {
                var root = Load<GameObject>(path);
                Require(root.GetComponentsInChildren<Component>(true).All(c => c != null), "Missing script on " + path);
                var bones = BoneNames.Select(n => Find(root.transform, n)).ToArray();
                for (int i = 1; i < bones.Length; i++) Require(bones[i].parent == bones[i - 1], "Incorrect bone hierarchy at " + bones[i].name);
                var body = Find(root.transform, "NavierStokes_OpenAI_Vortex").GetComponent<SkinnedMeshRenderer>();
                Require(body != null && body.sharedMesh != null && body.bones.Length > 0, "Body must be skinned.");
                var chain = Find(root.transform, "Chain").GetComponent<SkinnedMeshRenderer>();
                Require(chain != null && chain.bones.Length > 0, "Chain must be skinned.");
                Require(body.sharedMesh.uv.Length == body.sharedMesh.vertexCount, "Body is missing UV0.");
                var group = Find(root.transform, "Annotations"); Require(group.gameObject.activeSelf, "Annotations default must be ON.");
                foreach (var name in LabelNames) Require(Find(root.transform, name).IsChildOf(group), "Annotation is outside toggle group: " + name);
                foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
                    foreach (var material in renderer.sharedMaterials)
                        Require(material != null && material.shader != null && material.shader.name == "lilToon", "Non-lilToon material on " + renderer.name);
                foreach (var name in GradientNames.Keys) Require(Load<Material>(Root + "/Materials/" + name + ".mat").GetTexture("_MainTex") != null, "Missing RGB ramp on " + name);
                var merge = root.GetComponent<ModularAvatarMergeAnimator>();
                Require(merge != null && merge.pathMode == MergeAnimatorPathMode.Relative && merge.animator != null, "MA relative FX integration missing.");
                var expectedBinding = AnimationUtility.CalculateTransformPath(group, root.transform);
                foreach (var clip in merge.animator.animationClips.Distinct()) foreach (var binding in AnimationUtility.GetCurveBindings(clip))
                    Require(binding.path == expectedBinding, "Animation does not target prefab-relative annotation group: " + binding.path);
                Require(root.GetComponent<ModularAvatarMenuInstaller>().menuToAppend != null, "MA menu missing.");
                var parameter = root.GetComponent<ModularAvatarParameters>().parameters.Single();
                Require(parameter.nameOrPrefix == Parameter && parameter.internalParameter && parameter.syncType == ParameterSyncType.Bool && parameter.defaultValue == 1 && !parameter.saved, "MA parameter mismatch.");
                var human = path == HumanPath; var model = root.transform.Find("Model");
                Require(Mathf.Abs(model.localScale.x - (human ? HumanScale : 1)) < .0001f, "Size mismatch.");
                var pb = root.GetComponent<VRCPhysBone>(); Require(pb.rootTransform == bones[1], "PhysBone must start below fixed ear anchor.");
                var settings = new SerializedObject(pb);
                foreach (var pair in new Dictionary<string, float> { { "pull", human ? .312f : .254f }, { "spring", human ? .899f : .013f }, { "gravity", human ? .09f : .704f }, { "immobile", human ? .216f : .304f }, { "stiffness", .39f }, { "maxAngleX", human ? 53.4f : 29 }, { "maxAngleZ", 45 } })
                    Require(Mathf.Abs(Property(settings, pair.Key).floatValue - pair.Value) < .0001f, "PhysBone " + pair.Key + " mismatch.");
                Require(Mathf.Abs(root.transform.InverseTransformPoint(bones[0].position).y) < .001f, "EarAnchor must be at attachment origin.");
                Debug.Log(path + ": body local bounds=" + body.localBounds + ", model scale=" + model.localScale.x);
                geometry.Add(MeasureGeometry(root, human));
            }
            var controller = Load<AnimatorController>(ControllerPath);
            Require(controller.parameters.Length == 1 && controller.parameters[0].name == Parameter && controller.parameters[0].defaultBool, "Animator bool/default mismatch.");
            Directory.CreateDirectory("Deliverables");
            File.WriteAllText("Deliverables/unity-validation.json", JsonUtility.ToJson(new ValidationReport { unityVersion = Application.unityVersion, measured = geometry.ToArray() }, true));
        }
        [Serializable] class GeometryReport { public string prefab; public float bodyHeightMetres, fullHeightMetres; public int bodyTriangles, chainTriangles, annotationTriangles; }
        [Serializable] class ValidationReport { public string unityVersion; public bool passed = true; public GeometryReport[] measured; }
        static GeometryReport MeasureGeometry(GameObject prefab, bool human)
        {
            var instance = Object.Instantiate(prefab);
            try
            {
                foreach (var pb in instance.GetComponentsInChildren<VRCPhysBone>(true)) pb.enabled = false;
                var all = new List<Vector3>(); var body = Array.Empty<Vector3>();
                var report = new GeometryReport { prefab = prefab.name };
                foreach (var renderer in instance.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    // Evaluate imported skin matrices in root space; BakeMesh's optional scale handling
                    // otherwise applies parent model scale again when transformed to world space.
                    var mesh = renderer.sharedMesh;
                    var original = mesh.vertices; var weights = mesh.boneWeights; var bindposes = mesh.bindposes;
                    Require(weights.Length == original.Length, "Incomplete skin weights on " + renderer.name);
                    var matrices = renderer.bones.Select((bone, index) => instance.transform.worldToLocalMatrix * bone.localToWorldMatrix * bindposes[index]).ToArray();
                    var vertices = new Vector3[original.Length];
                    for (int i = 0; i < original.Length; i++)
                    {
                        var weight = weights[i]; var vertex = original[i];
                        if (weight.weight0 > 0) vertices[i] += matrices[weight.boneIndex0].MultiplyPoint3x4(vertex) * weight.weight0;
                        if (weight.weight1 > 0) vertices[i] += matrices[weight.boneIndex1].MultiplyPoint3x4(vertex) * weight.weight1;
                        if (weight.weight2 > 0) vertices[i] += matrices[weight.boneIndex2].MultiplyPoint3x4(vertex) * weight.weight2;
                        if (weight.weight3 > 0) vertices[i] += matrices[weight.boneIndex3].MultiplyPoint3x4(vertex) * weight.weight3;
                    }
                    all.AddRange(vertices);
                    var triangles = mesh.triangles.Length / 3;
                    if (renderer.name == "NavierStokes_OpenAI_Vortex") { body = vertices; report.bodyTriangles = triangles; }
                    else if (renderer.name == "Chain") report.chainTriangles = triangles;
                    else report.annotationTriangles += triangles;
                }
                Require(body.Length > 0 && all.Count > 0, "Cannot measure imported skinned geometry.");
                report.bodyHeightMetres = body.Max(v => v.y) - body.Min(v => v.y);
                report.fullHeightMetres = all.Max(v => v.y) - all.Min(v => v.y);
                var scale = human ? HumanScale : 1;
                Require(Mathf.Abs(report.bodyHeightMetres - .1f * scale) < .0005f, "Imported body scale/up-axis mismatch: " + report.bodyHeightMetres);
                Require(Mathf.Abs(report.fullHeightMetres - .15f * scale) < .001f, "Imported full-height mismatch: " + report.fullHeightMetres);
                Debug.Log(JsonUtility.ToJson(report));
                return report;
            }
            finally { Object.DestroyImmediate(instance); }
        }
        static void PackageSource()
        {
            foreach (var filename in new[] { "LICENSE", "generate_vortex.py", "build_earring.py", "export-contract.json" })
                Require(File.Exists("Source/" + filename), "Missing corresponding source: Source/" + filename);
            var archive = Root + "/Source/NavierStokes_Source.zip";
            if (File.Exists(archive)) File.Delete(archive);
            using (var zip = ZipFile.Open(archive, ZipArchiveMode.Create))
                foreach (var source in new[] { "LICENSE", "generate_vortex.py", "build_earring.py", "export-contract.json", "NavierStokes_Earring.blend", "HANDOVER.md" })
                {
                    Require(File.Exists("Source/" + source), "Missing corresponding source " + source);
                    zip.CreateEntryFromFile("Source/" + source, source, System.IO.Compression.CompressionLevel.Optimal);
                }
            AssetDatabase.ImportAsset(archive, ImportAssetOptions.ForceSynchronousImport);
        }
        static void ExportAssets()
        {
            ValidateAssets();
            var ownPaths = AssetDatabase.GetAllAssetPaths().Where(p => p.StartsWith(Root + "/", StringComparison.Ordinal)
                && !p.StartsWith(Root + "/Editor/", StringComparison.Ordinal)
                && !p.EndsWith(".cs", StringComparison.OrdinalIgnoreCase)
                && !AssetDatabase.IsValidFolder(p)).ToArray();
            Require(ownPaths.Contains(Root + "/Source/NavierStokes_Source.zip"), "Package needs original GPL corresponding source archive.");
            Directory.CreateDirectory("Deliverables");
            var package = Path.GetFullPath("Deliverables/navier-stokes-earring.unitypackage");
            // Deliberately no IncludeDependencies: MA, VRC SDK, lilToon and avatars are not ours to bundle.
            AssetDatabase.ExportPackage(ownPaths, package, ExportPackageOptions.Default);
            Require(File.Exists(package) && new FileInfo(package).Length > 0, "Unity package export failed.");
            File.WriteAllLines("Deliverables/package-assets.txt", ownPaths);
            Debug.Log("Exported " + package + " with " + ownPaths.Length + " own assets; external dependencies excluded.");
        }
    }
}
