# C4D Personal Scripts

这里存放我个人使用的 Cinema 4D 脚本，主要用于整理模型、处理 SVG / Spline、辅助 CAD 到 C4D 的工作流，以及一些日常小工具。

**当前主要环境**: Cinema 4D 2024.5.1

## 使用方式

将脚本放入 Cinema 4D 的脚本目录：

```text
library/scripts
```

重启 Cinema 4D，或在脚本管理器里刷新后，即可在“扩展”菜单、脚本管理器或命令面板中运行。

## 脚本列表

脚本统一使用英文文件名，并通过前缀按用途分类。

| 分类 | 文件名 | 用途 |
| --- | --- | --- |
| Analyze | `Analyze_VisibilityScanner.py` | 通过多视角正交相机和临时 ID 材质检测对象外部可见性，并把对象分配到可见、边缘可见、疑似内部不可见等图层，适合清理 CAD / STEP / MoI 导入模型。 |
| Animate | `Animate_KeyframeSmoother.py` | 复制当前选中的对象，并在复制体上平滑 Position / Rotation / Scale 动画曲线，用于处理烘焙动画、反求相机、跟踪数据等轻微抖动。 |
| CleanUp | `CleanUp_DeleteEmptyNulls.py` | 递归清理场景中没有子对象、没有标签的 Null Object，用于保持对象层级整洁。 |
| CleanUp | `CleanUp_TinyFragmentCollector.py` | 使用 bounding box 尺寸检测场景中的微小碎片对象，并收集到备用图层中，方便确认后手动删除。 |
| Display | `Display_CycleViewportShading.py` | 在活动视图中循环切换不同的视图着色模式，例如 Gouraud 着色、Gouraud 着色线条、快速着色等。 |
| Display | `Display_ToggleEditorVisibility.py` | 快速切换所选对象在编辑器中的显示状态，在默认显示和隐藏之间切换。 |
| Group | `Group_SimilarMeshObjects.py` | 分组模式：未选择时扫描全场景，选择多个对象时扫描选中对象及其子级，将相似可见对象整理到 `Auto_Similar_Groups` 下。 |
| Import | `Import_BatchSVGAssets.py` | 批量导入指定文件夹中的 SVG 文件，并把导入结果整理到 `Imported_SVG_Assets` 组下；单个 SVG 生成多个对象时会自动包一层 Null。 |
| Material | `Material_SketchSplineColor.py` | 为选中的 Spline 或子级 Spline 创建同色 Sketch Material 和 Sketch Style Tag，读取 Display Color 作为线条颜色，并可在运行时输入统一线条厚度。 |
| Select | `Select_SimilarBBoxObjects.py` | 以当前唯一选中的对象为参考，按 bounding box 最长边倍数范围选择尺寸相近对象，适合批量选择小零件、小标识、小装饰物。 |
| Select | `Select_SimilarMeshObjects.py` | 单选模式：以当前唯一选中的 Polygon Object 为参考，选择场景中几何特征相似的可见对象，不创建 Null，不移动层级。 |
| Spline | `Spline_BuildSVGSweeps.py` | 将选中的 SVG Spline 批量转换为带厚度的 Sweep 对象，自动继承 Spline 显示颜色生成发光材质，并支持统一半径和随机 PSR 偏移。 |
| Transfer | `Transfer_MoIStepBBoxMetadata.py` | 基于包围盒匹配，将 STEP 参考模型的名称、材质标签、层级、图层等元数据迁移到 MoI 导入的高质量模型上。 |
| Transform | `Transform_ResetPSR.py` | 一键重置所选对象的 Position、Scale、Rotation。 |

## SimilarMesh 工具说明

`Select_SimilarMeshObjects.py` 和 `Group_SimilarMeshObjects.py` 是从旧版 `SimilarMesh Grouper.py` 拆分出的两个独立脚本。旧脚本已不再使用。

两个脚本都会尽量跳过不可见对象，包括：

- 对象自身或父级 `GetEditorMode() == c4d.MODE_OFF`；
- `obj.GetNBit(c4d.NBIT_EHIDE)`，用于覆盖 Object Solo 等导致的 editor effective hidden 状态；
- `obj.GetNBit(c4d.NBIT_OHIDE)`；
- Layer 隐藏；
- Layer Solo 导致的非 Solo Layer 不可见状态。

Layer 判断使用 `layer.GetLayerData(doc)`，因为它会考虑 Layer Solo 这类全局状态。该可见性过滤是面向选择/分组的保守实用判断，不应视为完整、稳定的最终 viewport 可见性 API。

## 维护说明

- 这个仓库主要作为个人脚本备份和同步使用。
- 新增脚本时，优先把脚本文件直接放在当前目录，并在上方“脚本列表”补一行说明。
- 脚本文件名使用英文，并优先采用用途前缀，例如 `Select_`、`CleanUp_`、`Display_`。
