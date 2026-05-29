# C4D Personal Scripts

这些是我个人使用的 Cinema 4D 脚本，主要由 AI 辅助编写，用于提高日常工作效率。

**当前环境**: Cinema 4D 2024.5.1

## 脚本列表

### 1. 切换视图隐藏显示 (`切换视图隐藏显示.py`)
- **功能**: 快速切换所选对象在编辑器中的显示状态（在“默认”和“隐藏”之间切换）。

### 2. 切换线框显示 (`切换线框显示.py`)
- **功能**: 在活动视图中循环切换不同的着色模式，如 Gouraud 着色、Gouraud 着色（线条）、快速着色等。

### 3. 删除所有没有子对象的空对象 (`删除所有没有子对象的空对象.py`)
- **功能**: 递归清理场景中所有既没有子对象也没有标签的空对象（Null Object），保持场景整洁。

### 4. MoI / STEP BBox Metadata Transfer (`moi_step_bbox_transfer.py`)
- **功能**: 基于包围盒（BBox）匹配，将 STEP 参考模型的元数据（名称、材质标签、层级、图层）自动迁移到 MoI 导入的高质量模型上。适用于工业设计工作流。

### 5. ResetPSR (`ResetPSR.py`)
- **功能**: 一键重置所选对象的坐标（Position）、缩放（Scale）和旋转（Rotation）为默认值。

### 6. C4D Visibility Scanner (`c4d_visibility_scanner.py`)
- **功能**: 用于 Cinema 4D 的模型可见性检测脚本，主要用于清理从 Rhino、STEP、MoI 等 CAD 流程导入的产品模型。脚本会自动为场景中的多边形对象和 C4D 基础对象分配临时纯色 ID 材质，创建多个正交相机从不同方向渲染检测，并统计每个对象是否在外部视角中出现；检测完成后，它会自动将对象分配到可见、边缘可见、疑似内部不可见三个 Layer 中，方便用户人工复查、隐藏或删除内部零件，从而减少场景复杂度并提升模型整理效率。

## 使用说明
将脚本放入 C4D 的脚本目录（`library/scripts`）即可在“扩展”菜单或命令面板中找到。
以后我让 AI 写的代码脚本都放到这里，这样可以通过 GitHub 备份和存储。

svg_spline_sweep_builder.py
将选中的 SVG 样条线批量转换为带厚度的 Sweep 对象，并自动继承样条颜色生成纯发光材质，同时支持统一半径控制和随机 PSR 偏移。

sketch_spline_color.py
为选中的 C4D spline 或其子级 spline 批量创建 Sketch Style Tag 和对应 Sketch Material，自动读取 spline 的 Display Color 作为线条颜色，并在运行时输入统一线条厚度，用于生成不随透视距离明显变粗变细的彩色 Sketch 线条。