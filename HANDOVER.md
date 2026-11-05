# OpenAI Navier-Stokes 3Dモデル再現 引き継ぎ資料 (Handover Guide)
> **公開配布の入口:** 導入者向け手順・現行リポジトリ配置は [README.md](README.md) を参照してください。旧環境のパスやコマンドを含む以下の開発記録は履歴資料であり、公開版の手順ではありません。現行の公開構成は `Deliverables/`（unitypackage）、`Unity/Assets/Nikomaru/NavierStokes/`（編集用Unityアセット）、`Tools/UnityEditor/`（開発専用ツール）、`Source/`（Blenderソース）です。


## 1. プロジェクトの目的・要件
OpenAIの流体方程式（Navier-Stokes blowup）解説ページの3D流線イラストをBlenderのPythonスクリプトでプロシージャルに再現するプロジェクトです。

公開名は **navier-stokes-vrchat**。コードとモデルは **GPL-3.0-only** で配布します（[LICENSE](LICENSE)）。参照画像は同梱せず、その権利は各権利者に帰属します。OpenAI・VRChatの公式プロジェクトではありません。

- **参照画像URL**:
  `https://images.ctfassets.net/kftzwdyauwt9/38fsDDtQmNLBW3F74od13W/7f0213895c06edc97709dc82d7905bc3/navier-stokes-dark-master.png?w=1920&q=80&fm=webp`
- **ポリゴン数制限**:
  VRChat等での利用を想定し、渦メッシュ本体（`NavierStokes_OpenAI_Vortex`）は **厳密に 20,000 Tris（三角ポリゴン）以下** に収めること（現在の実測は **19,770 Tris**、超過時は生成スクリプトが例外で停止）。
- **シルエット・構造要件**:
  1. **`InnerGold` (axial stretching)**: 中心軸のすぐ近くを螺旋状に昇り降りし、上下端で斜めの毛束（右上・左下）としてスッと伸びるゴールデンオレンジのフィラメント群。
  2. **`MidBlueRibbon`**: オレンジ柱の周囲を斜めに巻き上がる、平たいきしめん状断面のリボン＆チューブ螺旋（ラベンダースレート〜鮮やかなコバルト/アジュールブルー）。
  3. **`OuterCyan` (inward spiral)**: 赤道〜中腹付近から左右に大きく張り出し、内側のコアへ巻き込むシアン〜エメラルドグリーンの流線群（左側は上向きにカールする穂先、右側は右上アーチから斜め右下へ扇状に広がる穂先、手前は下寄りのボウル弧で中央の青とオレンジを隠さない構造）。
  4. **`AxisWhite`**: 中心を貫く白い垂直軸と上端の矢印ヘッド。
- **文字・引き出し線の要件（重要）**:
  - 参照画像にある **`inward spiral`** と **`axial stretching`** の文字および引き出し線（リーダーライン）を、**簡単に表示/非表示（ON/OFF）切り替えられるよう別コレクション（`Annotations`）＆別オブジェクトとして分離管理**すること（メインの `NavierStokes_OpenAI_Vortex` メッシュには結合しない）。
- **カメラ要件**:
  - 上下の先端や文字ラベルまで全体が余裕をもって収まる距離（例：`Y = -15.0`, 解像度 `1200x1200`）に配置すること。

---

## 2. ワークスペース内のファイル構成
- **作業ディレクトリ**: `D:\Programming\vrchat\openai-navier-stokes`
  - `Untitled.blend`: 調整済みシーン。内部の `Text` データブロックは `generate_vortex.py` と同期済み。注釈はBlender内蔵フォントを使用し、外部フォントは埋め込みません。
  - `generate_vortex.py`: **最新の生成スクリプト**（19,770 Tris、ラベル位置・引き出し線・曲線サンプル数・色味・左ウイングのカールを調整済み）。
  - `render_preview.png`: 保存済み `.blend` を再読込してレンダリングした注釈ON画像（1200×1200）。
  - `render_no_annotations.png`: `SHOW_ANNOTATIONS = False` で生成した注釈OFF画像。
  - `stats.json`: ローカル検証結果（Git管理対象外）。メッシュ統計、Text同期、注釈ON/OFF、外部フォント未同梱、カメラ内への収まりを確認できます。

---

## 3. Blender CLI + Vision 反復ワークフローの実行手順（重要ノウハウ）

### ⚠️ Windows Store版 Blender の注意点
この環境のBlenderは Microsoft Store (WindowsApps) 版です：
- 直接 `C:\Program Files\WindowsApps\...\blender.exe` を叩くと `Access is denied` になります。
- **必ずアプリ実行エイリアス `$env:LOCALAPPDATA\Microsoft\WindowsApps\blender-launcher.exe` を使用してください。**
- `blender-launcher.exe` は非同期ランチャーのため、標準出力（`stdout`）がパイプに返ってきません。またプロセス完了を待たずに制御が戻るため、**統計情報（Tris数など）はファイルに書き出し、レンダリング画像が出力されるまで `while (-not (Test-Path $render))` で待機する**のが確実です。

### ワンライナー実行＆レンダリングコマンド（PowerShell）
```powershell
$script = "D:\Programming\vrchat\openai-navier-stokes\generate_vortex.py"
$blend  = "D:\Programming\vrchat\openai-navier-stokes\Untitled.blend"
$stats  = "D:\Programming\vrchat\openai-navier-stokes\stats.json"
$render = "D:\Programming\vrchat\openai-navier-stokes\render_preview.png"

if (Test-Path $render) { Remove-Item $render }
if (Test-Path $stats)  { Remove-Item $stats }

& "$env:LOCALAPPDATA\Microsoft\WindowsApps\blender-launcher.exe" -b $blend --python $script --python-expr "import bpy, json; mesh = bpy.data.objects['NavierStokes_OpenAI_Vortex'].data; mesh.calc_loop_triangles(); open(r'$stats', 'w').write(json.dumps({'verts': len(mesh.vertices), 'polys': len(mesh.polygons), 'tris': len(mesh.loop_triangles)})); bpy.context.scene.render.filepath = r'$render'; bpy.ops.render.render(write_still=True)"

while (-not (Test-Path $render)) { Start-Sleep -Seconds 1 }
Get-Content $stats
```
出力された `render_preview.png` をエージェントの画像読み取りツール（`read_file` / Vision）で読み込み、参照画像と見比べながら `generate_vortex.py` を調整してください。

### `.blend` ファイルへの保存方法
調整が完了したら、`bpy.data.texts["Text"]` を最新の `generate_vortex.py` で上書きし、`bpy.ops.wm.save_as_mainfile(filepath=...)` で保存してください。注釈はBlender内蔵フォントを使います。Windows付属フォント等を埋め込む場合は別途再配布権を確認する必要があります。生成スクリプト単体ではText同期・保存を行いません。保存後は `.blend` を再読込し、Textの一致とレンダーを確認してください（※ユーザーがBlender GUIで `Untitled.blend` を開いている最中は上書き競合に注意し、必要に応じて別名保存してください）。

### イヤリング用 Blender / FBX 出力（2026-11-05）

- 最新ソースは `C:\Users\nikom\orca\workspaces\openai-navier-stokes\silverside`。旧Gドライブの同名プロジェクトではありません。
- `build_earring.py` は隣の `generate_vortex.py` をそのまま実行し、元のシルエット・RGBグラデーション・白矢印・内蔵フォント注釈を保持してイヤリング化します。元の `Untitled.blend` は変更しません。
- 基準サイズは渦本体高さ **0.10m**、交互に90度回した **4個の簡素な楕円チェーンリンクで0.05m**、白矢印の上端に最小限の接続アイレットを追加。リンク断面は4角・周方向12分割で装飾を増やしません。原点はチェーン上端、Unityではペンダントが **-Y** に下がります。サイズ違いはUnity側で全体を等倍スケールします。
- `NavierStokesRig` の骨階層は `EarAnchor > Chain_01 > Chain_02 > Chain_03 > Pendant > PendantEnd`。PhysBoneの推奨rootは `Chain_01`、固定親は `EarAnchor`、明示的な末端は `PendantEnd`。本体と注釈は `Pendant` へ剛体ウェイト、チェーンは深さに応じてチェーン骨間を補間し、接続アイレットは `Pendant` へ固定します。
- 実測は本体 **19,770 Tris**、チェーン＋接続部 **480 Tris**、注釈4個合計 **2,246 Tris**（全体22,496 Tris）。本体の **20,000 Tris以下** は引き続き必須。チェーンと注釈メッシュは別予算であり、イヤリング全体が20,000 Tris以下という意味ではありません。
- `Annotations` 空オブジェクト配下に4個の名前付き注釈メッシュを保持します。本体には結合せず、外部フォントは不要です。
- 元のグレースケール `Col` はRGBではありません。実際のマテリアルのColor Rampを `InnerGold_Gradient.png` / `MidBlueRibbon_Gradient.png` / `OuterCyan_Gradient.png` / `AxisWhite_Gradient.png` に焼き、UV0で参照します。Unityは通常の **lilToon `_MainTex` + 白い `_Color`** を使用し、カスタム頂点カラーシェーダーは不要です。PNGはsRGB・Clamp・Bilinear・MipMapなし・非圧縮。`ChainSilver` / `AnnotationTextMat` / `AnnotationLineMat` は単色です。
- ベイクはscene-linearのColor Rampを明示的にsRGBエンコードします。元のカーブ由来UVは削除し、唯一の `UVMap`（UV0）に係数を保存して、Blenderノードも明示的に同じUVを参照します。これにより、Blenderだけが `UVMap.001` を読みUnityが旧UV0を読む不一致を防ぎます。
- 出力先は `D:\VR\Projects\openai-navier-stokes`：
  - `Source\NavierStokes_Earring.blend`（`generate_vortex.py` / `build_earring.py` のText同期済み）
  - `Source\generate_vortex.py` / `Source\build_earring.py` / `Source\LICENSE`
  - `Source\export-contract.json`（階層、単位、マテリアル、寸法、統計、実行コマンド）
  - `Source\build-result.json`（非同期起動用の実行IDと成功／失敗）
  - `Assets\Nikomaru\NavierStokes\Models\NavierStokes_Earring.fbx`
  - `Assets\Nikomaru\NavierStokes\Textures\*_Gradient.png`
- `.blend` はUnityの `Assets` 外に置き、FBXと二重インポートしません。FBXはメートル・Y-up / -Z-forward、追加leaf boneなし、アニメーションなし。Unityではファイル単位を使用、Scale Factor 1、Bake Axis Conversion ON、Generic、Optimize Game Objects OFF、Preserve Hierarchy ONとします。

以下は**生成・検証・レンダリング用コマンド**です。実行済み結果は `Source\build-result.json` と `Source\smoke-result.json`、同一照明／カメラでのRGBベイク比較は `Source\gradient-diagnostic.json` に保存しています。

```powershell
$script = "C:\Users\nikom\orca\workspaces\openai-navier-stokes\silverside\build_earring.py"
$project = "D:\VR\Projects\openai-navier-stokes"
$run = [guid]::NewGuid().ToString()
$result = Join-Path $project "Source\build-result.json"
& "$env:LOCALAPPDATA\Microsoft\WindowsApps\blender-launcher.exe" -b --python $script -- --project $project --validate --render --close-up --run-id $run
# Store launcherは非同期。古いFBX/画像の存在を完了判定に使わないこと。
$deadline = (Get-Date).AddMinutes(10)
do {
    Start-Sleep -Seconds 1
    $status = $null
    if (Test-Path $result) {
        try { $status = Get-Content $result -Raw | ConvertFrom-Json } catch {}
    }
    if ((Get-Date) -gt $deadline) { throw "Blender completion timed out: $run" }
} until ($status.run_id -eq $run -and $status.status -in @("complete", "failed"))
if ($status.status -eq "failed") { throw $status.traceback }
$status
```

`--validate` は本体ポリゴン数・実寸・接続位置・骨階層・全頂点の正規化済みウェイト・注釈分離・ソースText同期を確認します。`--render` は注釈込みの全体像 `Source\earring_preview.png`、`--close-up` はチェーンと白矢印の接続部 `Source\earring_chain_closeup.png` を保存します。生成だけならこれら3オプションを省略できます。本体のポリゴン制限はオプションに関係なく適用されます。FBXのUnity実寸・スキニング・PhysBone挙動・マテリアル表示とレンダーの視覚確認は、実行後に統合担当側で行います。

保存済み `.blend` の再読込と実際のスキニング変形は別プロセスで確認できます。生成コマンドの後に実行し、上記と同じ実行ID付きの待機処理を `Source\smoke-result.json` に対して使用します。

```powershell
$run = [guid]::NewGuid().ToString()
$result = Join-Path $project "Source\smoke-result.json"
& "$env:LOCALAPPDATA\Microsoft\WindowsApps\blender-launcher.exe" -b --python $script -- --project $project --smoke --render --run-id $run
```

再読込検証ではText同期・実寸・全ウェイト・唯一のUV0を再確認し、`Chain_02` をローカルZ軸で20度回して評価済みメッシュの移動を測定します。実測は本体最大移動0.046306m、チェーン0.011854m、全注釈も追従、`EarAnchor` 行列変化0、白矢印先端と `Pendant` の距離誤差0、復元後頂点誤差0でした。変形画像は `Source\earring_deformed.png`、テスト姿勢は `.blend` に保存しません。

RGBベイク前後の同一条件レンダーは `Source\gradient_reference.png` / `Source\gradient_baked.png`。画像全チャンネル平均絶対差0.00002135、最大0.007843、0.02超のチャンネル0、UV係数の最大誤差2.97e-8でした。旧UVを誤計測した最大誤差1.00049は、UVMap/UVMap.001二重化という実際のUV0不具合を特定して修正済みです。

---

## 4. ポリゴン数（Tris）の計算式とバジェット管理
`build_curve_obj` は `POLY` スプライン（`resolution_u = 1`, キャップなし）に3頂点断面（`prof_tube` および3頂点化した `prof_ribbon`）をベベル適用しています。
- **1本あたりの四角ポリゴン（Quads）数** = `3 × (n_pts - 1)`
- **1本あたりの三角ポリゴン（Tris）数** = `6 × (n_pts - 1)`
  - 例：`n_pts = 21` の場合、1本あたり `6 × 20 = 120 Tris`
  - 例：`n_pts = 23` の場合、1本あたり `6 × 22 = 132 Tris`
- **カクつき防止のコツ**:
  `OuterCyan` は21点で約0.28〜0.50回転を基本にし、急な折れを抑えます。`InnerGold` と `MidBlueRibbon` は角度を `t` に比例させ、始点付近の角度変化の集中を避けています。3頂点断面・低ポリゴンのため、曲率の高い部分にはまだ角張りが残ります。
- **現在の配分**: InnerGold = 30本×25点（4,320 Tris）、MidBlueRibbon = 36本×29点（6,048 Tris）、OuterCyan = 60本×21点（7,200 Tris）、ArchStream = 14本×27点（2,184 Tris）、白軸＋矢印 = 18 Tris。合計19,770 Tris。
- **色管理**: `Standard` / `None`、露出0、ガンマ1、解像度100%をスクリプトで指定し、元ファイルのAgX設定による色味の差をなくしています。

---

## 5. 文字・引き出し線（`Annotations` コレクション）の仕組みと調整方法
`generate_vortex.py` のセクション8で以下のように実装済みです：
1. **コレクション分離**:
   - `bpy.data.collections.new("Annotations")` を作成し、以下の4オブジェクトを格納しています：
     - `Label_InwardSpiral` (`FONT` オブジェクト: `"inward\nspiral"`)
     - `Line_InwardSpiral` (`CURVE` オブジェクト: 左上のテキスト下からシアン穂先への引き出し線)
     - `Label_AxialStretching` (`FONT` オブジェクト: `"axial\nstretching"`)
     - `Line_AxialStretching` (`CURVE` オブジェクト: 右上のテキスト下から上部の軸ストレッチ部への引き出し線)
2. **表示/非表示の切り替え方法**:
   - **スクリプト上**: ファイル先頭の `SHOW_ANNOTATIONS = True / False` を切り替えるだけで、`annot_collection.hide_viewport` と `annot_collection.hide_render` が一括で切り替わります。
   - **Blender GUI上**: アウトライナー（Outliner）上の `Annotations` コレクションの「目のアイコン（ビューポート表示）」「カメラアイコン（レンダー表示）」、またはチェックボックス（ビューレイヤー除外）を1クリックするだけで出し入れ可能です。
   - **VRChat出力時**: `NavierStokes_OpenAI_Vortex` 単体を選択してFBXエクスポートすれば文字なしになり、`Annotations` 内のオブジェクトをメッシュ変換（`bpy.ops.object.convert(target='MESH')`）して含めれば文字ありになります。

---

## 6. 再開作業の実施結果（2026-11-05）
1. 初回レンダーを参照画像と比較。旧スクリプトの実測は19,074 Trisで、旧資料の19,098 Trisとは差がありました。
2. 左ラベルを上へ移動、両ラベルを拡大、行間とリーダーラインの位置・太さ・明度を調整しました。
3. 螺旋の本数と点数を再配分し、青・オレンジ・シアンの色分けと左の上向きカールを調整しました。カメラはY=-15.0を維持しています。
4. Blender 5.2.3 LTS / Eeveeで注釈OFFとONを実レンダリング。注釈4オブジェクトの分離、19,770 Tris、Textと外部スクリプトの完全一致、保存後の再読込を確認しました。
5. 本体・注釈の実頂点をカメラへ投影し、全てが画像の各端から3%以上内側に収まることを確認しました。
6. 公開準備時にArialの埋め込みを除去し、注釈をBlender内蔵フォントに変更。外部アセット未同梱、注釈ON/OFFの再レンダー、保存後のText一致、画面内の余白を再確認しました。`.blend1`・一時スクリプト・検証JSONは公開対象外です。

参照画像とは流線の密度・細部形状に差があり、画像の完全一致ではありません。上記1〜6は元の渦モデルのレンダー検証時点の記録です。その後、セクション3のイヤリング用FBX出力、保存済み `.blend` の再読込・ソース同期・実寸・ウェイト・評価済みスキニング変形、およびRGBベイク前後の画像比較まで実行済みです。Unity/VRChatでの最終インポート・マテリアル表示・PhysBone統合の検証結果は、別担当のUnity側証跡を参照してください。
