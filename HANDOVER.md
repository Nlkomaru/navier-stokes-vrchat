# OpenAI Navier-Stokes 3Dモデル再現 引き継ぎ資料 (Handover Guide)

## 1. プロジェクトの目的・要件
OpenAIの流体方程式（Navier-Stokes blowup）解説ページの3D流線イラストをBlenderのPythonスクリプトでプロシージャルに再現するプロジェクトです。

公開名は **navier-stokes-vrchat**。コードとモデルは **GPL-3.0-only** で配布します（[LICENSE](LICENSE)）。参照画像は同梱せず、その権利は各権利者に帰属します。OpenAI・VRChatの公式プロジェクトではありません。

- **参照画像URL**:
  `https://images.ctfassets.net/kftzwdyauwt9/38fsDDtQmNLBW3F74od13W/7f0213895c06edc97709dc82d7905bc3/navier-stokes-dark-master.png?w=1920&q=80&fm=webp`
- **ポリゴン数制限**:
  VRChat等での利用を想定し、渦メッシュ本体（`NavierStokes_OpenAI_Vortex`）は **厳密に 20,000 Tris（三角ポリゴン）以下** に収めること（現在の実測は **14,778 Tris**、超過時は生成スクリプトが例外で停止）。
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
  - `generate_vortex.py`: **最新の生成スクリプト**（14,778 Tris。曲線の点数を維持したまま流線数を削減し、旧19,770 Tris版から約25.3%軽量化）。
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

---

## 4. ポリゴン数（Tris）の計算式とバジェット管理
`build_curve_obj` は `POLY` スプライン（`resolution_u = 1`, キャップなし）に3頂点断面（`prof_tube` および3頂点化した `prof_ribbon`）をベベル適用しています。
- **1本あたりの四角ポリゴン（Quads）数** = `3 × (n_pts - 1)`
- **1本あたりの三角ポリゴン（Tris）数** = `6 × (n_pts - 1)`
  - 例：`n_pts = 21` の場合、1本あたり `6 × 20 = 120 Tris`
  - 例：`n_pts = 23` の場合、1本あたり `6 × 22 = 132 Tris`
- **カクつき防止のコツ**:
  `OuterCyan` は21点で約0.28〜0.50回転を基本にし、急な折れを抑えます。`InnerGold` と `MidBlueRibbon` は角度を `t` に比例させ、始点付近の角度変化の集中を避けています。3頂点断面・低ポリゴンのため、曲率の高い部分にはまだ角張りが残ります。
- **現在の配分**: InnerGold = 24本×25点（3,456 Tris）、MidBlueRibbon = 28本×29点（4,704 Tris）、OuterCyan = 42本×21点（5,040 Tris）、ArchStream = 10本×27点（1,560 Tris）、白軸＋矢印 = 18 Tris。合計14,778 Tris。
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
7. 軽量化で流線数を合計140本から104本へ削減。各曲線の点数・断面は維持し、密度を抑える代わりに曲線の分割を粗くしない方針です。実測14,778 Tris・7,710頂点（旧19,770 Tris・10,314頂点）。保存済み `.blend` は454,349 bytesから373,540 bytesへ縮小しました。
8. 軽量版も注釈OFF/ONを実レンダリングし、保存後のText一致、4注釈オブジェクトの分離、外部フォント未同梱、画面端から3%以上の余白を確認しました。VRChat上のFPSやメモリ使用量は未計測です。

参照画像とは流線の密度・細部形状に差があり、画像の完全一致ではありません。FBX出力・Unity/VRChatでのマテリアル表示は未検証です。
