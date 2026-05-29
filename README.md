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

| 脚本 | 文件名 | 用途 |
| --- | --- | --- |
| 切换视图隐藏显示 | `切换视图隐藏显示.py` | 快速切换所选对象在编辑器中的显示状态，在默认显示和隐藏之间切换。 |
| 切换线框显示 | `切换线框显示.py` | 在活动视图中循环切换不同的视图着色模式，例如 Gouraud 着色、Gouraud 着色线条、快速着色等。 |
| 删除空对象 | `删除所有没有子对象的空对象.py` | 递归清理场景中没有子对象、没有标签的 Null Object，用于保持对象层级整洁。 |
| Reset PSR | `ResetPSR.py` | 一键重置所选对象的 Position、Scale、Rotation。 |
| MoI / STEP BBox Metadata Transfer | `moi_step_bbox_transfer.py` | 基于包围盒匹配，将 STEP 参考模型的名称、材质标签、层级、图层等元数据迁移到 MoI 导入的高质量模型上。 |
| C4D Visibility Scanner | `c4d_visibility_scanner.py` | 通过多视角正交相机和临时 ID 材质检测对象外部可见性，并把对象分配到可见、边缘可见、疑似内部不可见等图层，适合清理 CAD / STEP / MoI 导入模型。 |
| Batch Import SVG Assets | `Batch_Import_SVG_Assets.py` | 批量导入指定文件夹中的 SVG 文件，并把导入结果整理到 `Imported_SVG_Assets` 组下；单个 SVG 生成多个对象时会自动包一层 Null。 |
| SVG Spline Sweep Builder | `SVG Spline Sweep Builder.py` | 将选中的 SVG Spline 批量转换为带厚度的 Sweep 对象，自动继承 Spline 显示颜色生成发光材质，并支持统一半径和随机 PSR 偏移。 |
| Sketch Spline Color | `sketch_spline_color.py` | 为选中的 Spline 或子级 Spline 创建同色 Sketch Material 和 Sketch Style Tag，读取 Display Color 作为线条颜色，并可在运行时输入统一线条厚度。 |
| SimilarMesh Grouper | `SimilarMesh Grouper.py` | 根据对象的包围盒尺寸比例、点数、面数等几何特征识别重复或相似模型，并自动整理到同一个 Null 组下，适合清理 CAD / STEP / FBX 导入后的重复零件层级。 |

## 维护说明

- 这个仓库主要作为个人脚本备份和同步使用。
- 新增脚本时，优先把脚本文件直接放在当前目录，并在上方“脚本列表”补一行说明。
- `.tif` 文件是部分旧脚本对应的 Cinema 4D 图标资源。
