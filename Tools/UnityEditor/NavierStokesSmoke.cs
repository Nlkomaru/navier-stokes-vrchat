// SPDX-License-Identifier: GPL-3.0-only
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using nadena.dev.ndmf;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using VRC.SDK3.Avatars.Components;
using VRC.SDK3.Avatars.ScriptableObjects;
using VRC.SDK3.Dynamics.PhysBone.Components;
using Object = UnityEngine.Object;

namespace Nikomaru.NavierStokes.Editor
{
    // Editor-only harness: it is never attached to distribution prefabs or uploaded to VRChat.
    [InitializeOnLoad]
    public static class NavierStokesSmoke
    {
        const string RunningKey = "Nikomaru.NavierStokes.Smoke";
        const string BatchKey = "Nikomaru.NavierStokes.SmokeBatch";
        static GameObject avatar;
        static Animator animator;
        static Transform[] annotations;
        static string[] parameters;
        static int phase, lastFrame;
        static double deadline;
        static Color32[] onPixels;
        static readonly List<string> Evidence = new List<string>();
        static NavierStokesSmoke()
        {
            EditorApplication.update += Tick;
            EditorApplication.playModeStateChanged += state =>
            {
                if (state == PlayModeStateChange.EnteredEditMode && SessionState.GetBool(RunningKey, false))
                    Finish(false, "Play mode ended before smoke completed.");
            };
        }
        [MenuItem("Nikomaru/Navier-Stokes/Runtime smoke (real rendering)")]
        public static void Run()
        {
            try
            {
                NavierStokesBuilder.Require(!EditorApplication.isPlayingOrWillChangePlaymode, "Smoke must start in edit mode.");
                NavierStokesBuilder.ValidateAssets();
                NavierStokesBuilder.Require(SystemInfo.graphicsDeviceType != UnityEngine.Rendering.GraphicsDeviceType.Null, "Runtime rendering smoke requires graphics; do not pass -nographics.");
                EditorSceneManager.OpenScene(NavierStokesBuilder.DemoPath);
                SessionState.SetBool(BatchKey, Application.isBatchMode);
                SessionState.SetBool(RunningKey, true);
                EditorApplication.EnterPlaymode();
            }
            catch (Exception e) { Debug.LogException(e); if (Application.isBatchMode) EditorApplication.Exit(1); else throw; }
        }
        static void Tick()
        {
            if (!SessionState.GetBool(RunningKey, false) || !EditorApplication.isPlaying || EditorApplication.isCompiling) return;
            try
            {
                if (avatar == null)
                {
                    deadline = EditorApplication.timeSinceStartup + 120;
                    Setup(); phase = 0; lastFrame = Time.frameCount; return;
                }
                NavierStokesBuilder.Require(EditorApplication.timeSinceStartup < deadline, "Smoke runtime timed out.");
                if (Time.frameCount - lastFrame < 6) return;
                lastFrame = Time.frameCount;
                switch (phase++)
                {
                    case 0:
                        AssertAnnotations(true, true);
                        onPixels = Capture("annotations-on.png");
                        animator.SetBool(parameters[0], false);
                        break;
                    case 1:
                        AssertAnnotations(false, true);
                        Evidence.Add("Independent instance toggle: first OFF leaves second ON.");
                        animator.SetBool(parameters[1], false);
                        break;
                    case 2:
                        AssertAnnotations(false, false);
                        var offPixels = Capture("annotations-off.png");
                        var changed = onPixels.Zip(offPixels, (a, b) => Math.Abs(a.r - b.r) + Math.Abs(a.g - b.g) + Math.Abs(a.b - b.b)).Count(d => d > 12);
                        NavierStokesBuilder.Require(changed > 4, "Annotations ON/OFF rendered images did not differ.");
                        Evidence.Add("Rendered ON/OFF changed pixels: " + changed);
                        animator.SetBool(parameters[0], true); animator.SetBool(parameters[1], true);
                        break;
                    case 3:
                        AssertAnnotations(true, true);
                        TestSkinning();
                        Capture("bone-motion.png");
                        Finish(true, "Merged MA controller, two nested differently sized instances, independent menu bools, runtime ON/OFF and skinned rendering passed.");
                        break;
                }
            }
            catch (Exception e) { Debug.LogException(e); Finish(false, e.ToString()); }
        }
        static void Setup()
        {
            Evidence.Clear(); Directory.CreateDirectory("Deliverables/runtime-smoke");
            // Remove demo instances only from the transient play scene, never from the saved demonstration scene.
            foreach (var root in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
                if (root.name.StartsWith("NavierStokes_Earring_", StringComparison.Ordinal)) Object.DestroyImmediate(root);
            avatar = new GameObject("NavierStokes_SmokeAvatar");
            animator = avatar.AddComponent<Animator>(); animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            var descriptor = avatar.AddComponent<VRCAvatarDescriptor>();
            descriptor.customizeAnimationLayers = true;
            descriptor.baseAnimationLayers = new[] { new VRCAvatarDescriptor.CustomAnimLayer { type = VRCAvatarDescriptor.AnimLayerType.FX, isDefault = true } };
            descriptor.customExpressions = true;
            descriptor.expressionsMenu = ScriptableObject.CreateInstance<VRCExpressionsMenu>();
            descriptor.expressionParameters = ScriptableObject.CreateInstance<VRCExpressionParameters>();
            descriptor.expressionParameters.parameters = Array.Empty<VRCExpressionParameters.Parameter>();
            var attachments = new GameObject("Attachments").transform; attachments.SetParent(avatar.transform, false);
            var paths = new[] { NavierStokesBuilder.KemomimiPath, NavierStokesBuilder.HumanPath };
            for (int i = 0; i < paths.Length; i++)
            {
                var ear = new GameObject(i == 0 ? "ArbitraryKemomimiEar" : "ArbitraryHumanEar").transform;
                ear.SetParent(attachments, false); ear.localPosition = new Vector3(i == 0 ? -.09f : .09f, .15f, 0);
                var instance = Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(paths[i]));
                instance.transform.SetParent(ear, false);
            }
            // Exercise the real installed NDMF/MA build, including parameter auto-renaming and relative-path rewriting.
            // Null directory keeps generated controllers in memory, not in the distributable asset tree.
            using (new OverrideTemporaryDirectoryScope(null)) AvatarProcessor.ProcessAvatar(avatar);
            descriptor = avatar.GetComponent<VRCAvatarDescriptor>();
            var fx = descriptor.baseAnimationLayers.Single(l => l.type == VRCAvatarDescriptor.AnimLayerType.FX).animatorController;
            NavierStokesBuilder.Require(fx != null, "MA did not produce an FX controller.");
            animator.runtimeAnimatorController = fx; animator.Rebind(); animator.Update(0);
            var toggles = MenuToggles(descriptor.expressionsMenu, new HashSet<VRCExpressionsMenu>()).Where(c => c.name == "Annotations").ToArray();
            NavierStokesBuilder.Require(toggles.Length == 2, "Expected one Annotations menu toggle per instance.");
            parameters = toggles.Select(t => t.parameter.name).ToArray();
            NavierStokesBuilder.Require(parameters.Distinct().Count() == 2, "MA did not namespace the two instance bools.");
            var controllerParameters = animator.parameters.Where(p => parameters.Contains(p.name)).ToArray();
            NavierStokesBuilder.Require(controllerParameters.Length == 2 && controllerParameters.All(p => p.type == AnimatorControllerParameterType.Bool && p.defaultBool), "Merged bool defaults/types mismatch.");
            foreach (var parameter in parameters)
            {
                var expression = descriptor.expressionParameters.parameters.Single(p => p.name == parameter);
                NavierStokesBuilder.Require(expression.valueType == VRCExpressionParameters.ValueType.Bool && expression.defaultValue == 1 && !expression.saved && expression.networkSynced, "Merged expression parameter mismatch.");
            }
            var controller = fx as AnimatorController;
            NavierStokesBuilder.Require(controller != null, "MA output is not an AnimatorController.");
            var bindings = controller.animationClips.SelectMany(AnimationUtility.GetCurveBindings).Where(b => b.propertyName == "m_IsActive" && b.path.EndsWith("/Annotations", StringComparison.Ordinal)).Select(b => b.path).Distinct().ToArray();
            NavierStokesBuilder.Require(bindings.Length == 2, "Merged annotation bindings do not address two distinct objects.");
            // Resolve by rewritten binding path, not menu traversal order; then align bools by controller conditions.
            annotations = bindings.Select(p => avatar.transform.Find(p)).ToArray();
            NavierStokesBuilder.Require(annotations.All(t => t != null), "A rewritten animation target does not exist.");
            parameters = bindings.Select(binding => FindParameterForBinding(controller, binding)).ToArray();
            foreach (var pb in avatar.GetComponentsInChildren<VRCPhysBone>(true)) pb.enabled = false;
            Evidence.Add("Unity " + Application.unityVersion + "; graphics " + SystemInfo.graphicsDeviceType + "/" + SystemInfo.graphicsDeviceName);
            Evidence.Add("Real NDMF/MA build: independent bools " + string.Join(", ", parameters));
            Evidence.Add("Rewritten bindings: " + string.Join(", ", bindings));
            Evidence.Add("PhysBone settings validated separately; deterministic bone mutation below tests skinning, not the VRChat in-client PhysBone solver.");
        }
        static IEnumerable<VRCExpressionsMenu.Control> MenuToggles(VRCExpressionsMenu menu, HashSet<VRCExpressionsMenu> visited)
        {
            if (menu == null || !visited.Add(menu)) yield break;
            foreach (var control in menu.controls)
            {
                if (control.type == VRCExpressionsMenu.Control.ControlType.Toggle) yield return control;
                if (control.subMenu != null) foreach (var nested in MenuToggles(control.subMenu, visited)) yield return nested;
            }
        }
        static string FindParameterForBinding(AnimatorController controller, string binding)
        {
            var matchingLayers = controller.layers.Where(l => States(l.stateMachine).Any(s => s.motion is AnimationClip clip && AnimationUtility.GetCurveBindings(clip).Any(b => b.path == binding))).ToArray();
            NavierStokesBuilder.Require(matchingLayers.Length == 1, "Cannot identify annotation controller layer for " + binding);
            var conditions = States(matchingLayers[0].stateMachine).SelectMany(s => s.transitions).SelectMany(t => t.conditions).Select(c => c.parameter).Where(p => parameters.Contains(p)).Distinct().ToArray();
            NavierStokesBuilder.Require(conditions.Length == 1, "Cannot identify annotation bool for " + binding);
            return conditions[0];
        }
        static IEnumerable<AnimatorState> States(AnimatorStateMachine machine)
        {
            foreach (var state in machine.states) yield return state.state;
            foreach (var child in machine.stateMachines) foreach (var state in States(child.stateMachine)) yield return state;
        }
        static void AssertAnnotations(bool first, bool second)
        {
            NavierStokesBuilder.Require(annotations[0].gameObject.activeSelf == first && annotations[1].gameObject.activeSelf == second, "Runtime Animator did not set annotation groups to " + first + "/" + second);
            Evidence.Add("Runtime Animator annotation activeSelf=" + first + "/" + second + " at frame " + Time.frameCount);
        }
        static void TestSkinning()
        {
            foreach (var group in annotations)
            {
                var model = group.parent;
                while (model != null && model.name != "Model") model = model.parent;
                NavierStokesBuilder.Require(model != null, "Annotation group has no model ancestor.");
                var bone = NavierStokesBuilder.Find(model, "Chain_01");
                foreach (var name in new[] { "NavierStokes_OpenAI_Vortex", "Chain", "Label_InwardSpiral", "Line_InwardSpiral", "Label_AxialStretching", "Line_AxialStretching" })
                {
                    var renderer = NavierStokesBuilder.Find(model, name).GetComponent<SkinnedMeshRenderer>();
                    NavierStokesBuilder.Require(renderer != null && renderer.bones.Length > 0, "Expected skinned " + name);
                    var before = new Mesh(); var after = new Mesh();
                    var original = bone.localRotation;
                    try
                    {
                        renderer.BakeMesh(before); bone.localRotation = original * Quaternion.Euler(0, 0, 18);
                        renderer.BakeMesh(after);
                        var a = before.vertices; var b = after.vertices;
                        NavierStokesBuilder.Require(a.Length == b.Length && a.Length > 0, "Empty baked mesh " + name);
                        var delta = a.Zip(b, (x, y) => Vector3.Distance(x, y)).Max();
                        NavierStokesBuilder.Require(delta > .000001f, "Bone motion did not deform " + name);
                        Evidence.Add(model.parent.name + "/" + name + " baked vertex delta=" + delta.ToString("G9"));
                    }
                    finally { bone.localRotation = original; Object.DestroyImmediate(before); Object.DestroyImmediate(after); }
                }
                bone.localRotation *= Quaternion.Euler(0, 0, 18);
            }
        }
        static Color32[] Capture(string filename)
        {
            var camera = Object.FindObjectsOfType<Camera>().Single(c => c.name == "Preview Camera");
            var target = new RenderTexture(1024, 1024, 24, RenderTextureFormat.ARGB32);
            var image = new Texture2D(1024, 1024, TextureFormat.RGB24, false);
            var oldTarget = camera.targetTexture; var oldActive = RenderTexture.active;
            try
            {
                camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
                image.ReadPixels(new Rect(0, 0, 1024, 1024), 0, 0); image.Apply();
                var pixels = image.GetPixels32(); var background = pixels[0];
                var visible = pixels.Count(p => Math.Abs(p.r - background.r) + Math.Abs(p.g - background.g) + Math.Abs(p.b - background.b) > 30);
                NavierStokesBuilder.Require(visible > 100, "Rendered frame is empty: " + filename);
                File.WriteAllBytes("Deliverables/runtime-smoke/" + filename, image.EncodeToPNG());
                Evidence.Add(filename + ": foreground pixels=" + visible); return pixels;
            }
            finally { camera.targetTexture = oldTarget; RenderTexture.active = oldActive; target.Release(); Object.DestroyImmediate(target); Object.DestroyImmediate(image); }
        }
        [Serializable] class SmokeReport { public bool passed; public string utc, unityVersion, message; public string[] evidence; }
        static void Finish(bool success, string message)
        {
            var batch = SessionState.GetBool(BatchKey, false);
            SessionState.SetBool(RunningKey, false);
            Directory.CreateDirectory("Deliverables/runtime-smoke");
            File.WriteAllLines("Deliverables/runtime-smoke/result.txt", new[] { success ? "PASS" : "FAIL", DateTime.UtcNow.ToString("O"), message }.Concat(Evidence));
            File.WriteAllText("Deliverables/runtime-smoke/result.json", JsonUtility.ToJson(new SmokeReport { passed = success, utc = DateTime.UtcNow.ToString("O"), unityVersion = Application.unityVersion, message = message, evidence = Evidence.ToArray() }, true));
            if (success) Debug.Log("Navier-Stokes smoke PASS: " + message); else Debug.LogError("Navier-Stokes smoke FAIL: " + message);
            if (batch) EditorApplication.Exit(success ? 0 : 1); else EditorApplication.ExitPlaymode();
        }
    }
}
