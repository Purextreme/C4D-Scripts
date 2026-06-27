# Tiny Fragment Collector / 微碎片收集器
# 根据对象 bounding box 的最大边长、表面积和体积筛选极小碎片。
# 阈值单位请按当前 C4D Project Unit 输入，例如工程为 mm 时就按 mm 输入。
# 匹配对象只会被放入 Tiny_Fragments_To_Check Layer，不改变原始层级。

import c4d
from c4d import gui


LAYER_NAME = "Tiny_Fragments_To_Check"


class TinyFragmentDialog(gui.GeDialog):
    ID_MAX_SIDE = 1001
    ID_MAX_SURFACE = 1002
    ID_MAX_VOLUME = 1003

    def __init__(self):
        super().__init__()

        self.max_side = 0.02
        self.max_surface = 0.0008
        self.max_volume = 0.000001
        self.cancelled = True

    def CreateLayout(self):
        self.SetTitle("Tiny Fragment Collector / 微碎片收集器")

        self.GroupBegin(2000, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)
        self.GroupBorderSpace(18, 14, 18, 14)
        self.GroupSpace(0, 10)

        # 说明区
        self.GroupBegin(2100, c4d.BFH_SCALEFIT, 1, 0, "说明")
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(12, 10, 12, 10)
        self.GroupSpace(0, 5)

        self.AddStaticText(
            2101,
            c4d.BFH_SCALEFIT,
            initw=700,
            inith=0,
            name="用途：收集场景中极小的碎片对象，放入单独 Layer，方便检查后删除。"
        )

        self.AddStaticText(
            2102,
            c4d.BFH_SCALEFIT,
            initw=700,
            inith=0,
            name="判断方式：最大边长 <= 阈值，并且 表面积 <= 阈值 或 体积 <= 阈值。"
        )

        self.AddStaticText(
            2103,
            c4d.BFH_SCALEFIT,
            initw=700,
            inith=0,
            name="注意：薄片对象的体积可能接近 0，所以这里同时使用 bounding box 表面积判断。"
        )

        self.AddStaticText(
            2104,
            c4d.BFH_SCALEFIT,
            initw=700,
            inith=0,
            name="结果：匹配对象不会移动层级，只会放入 Tiny_Fragments_To_Check Layer，并自动选中。"
        )

        self.GroupEnd()

        # 阈值区
        self.GroupBegin(2200, c4d.BFH_SCALEFIT, 2, 0, "Thresholds / 阈值")
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(12, 10, 12, 10)
        self.GroupSpace(10, 8)

        self.AddStaticText(
            2201,
            c4d.BFH_LEFT | c4d.BFV_CENTER,
            initw=260,
            inith=0,
            name="Max side length / 最大边长 cm"
        )
        self.AddEditText(
            self.ID_MAX_SIDE,
            c4d.BFH_SCALEFIT,
            initw=380,
            inith=20
        )

        self.AddStaticText(
            2202,
            c4d.BFH_LEFT | c4d.BFV_CENTER,
            initw=260,
            inith=0,
            name="Max surface area / 最大表面积 cm^2"
        )
        self.AddEditText(
            self.ID_MAX_SURFACE,
            c4d.BFH_SCALEFIT,
            initw=380,
            inith=20
        )

        self.AddStaticText(
            2203,
            c4d.BFH_LEFT | c4d.BFV_CENTER,
            initw=260,
            inith=0,
            name="Max volume / 最大体积 cm^3"
        )
        self.AddEditText(
            self.ID_MAX_VOLUME,
            c4d.BFH_SCALEFIT,
            initw=380,
            inith=20
        )

        self.GroupEnd()

        self.AddDlgGroup(c4d.DLG_OK | c4d.DLG_CANCEL)

        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetString(self.ID_MAX_SIDE, "0.02")
        self.SetString(self.ID_MAX_SURFACE, "0.0008")
        self.SetString(self.ID_MAX_VOLUME, "0.000001")
        return True

    def _parse_positive_float(self, text, label):
        text = text.strip()

        if not text:
            raise ValueError("{} 不能为空。".format(label))

        try:
            value = float(text)
        except Exception:
            raise ValueError("{} 必须是数字，例如 0.000001 或 1e-6。".format(label))

        if value <= 0.0:
            raise ValueError("{} 必须大于 0。".format(label))

        return value

    def _confirm(self):
        try:
            self.max_side = self._parse_positive_float(
                self.GetString(self.ID_MAX_SIDE),
                "Max side length"
            )

            self.max_surface = self._parse_positive_float(
                self.GetString(self.ID_MAX_SURFACE),
                "Max surface area"
            )

            self.max_volume = self._parse_positive_float(
                self.GetString(self.ID_MAX_VOLUME),
                "Max volume"
            )

        except ValueError as e:
            gui.MessageDialog(str(e))
            return

        self.cancelled = False
        self.Close()

    def Command(self, cid, msg):
        if cid == c4d.DLG_OK:
            self._confirm()
            return True

        if cid == c4d.DLG_CANCEL:
            self.cancelled = True
            self.Close()
            return True

        return True


def iter_objects(op):
    """递归遍历对象层级。"""
    while op:
        yield op

        child = op.GetDown()
        if child:
            for sub in iter_objects(child):
                yield sub

        op = op.GetNext()


def is_geometry_candidate(obj):
    """
    只处理常见几何对象，避免 Null / Camera / Light 等 0 尺寸对象被误收集。
    如果需要处理生成器、Cloner、Instance，建议先 Current State to Object。
    """
    return obj.CheckType(c4d.Opolygon) or obj.CheckType(c4d.Ospline)


def get_world_scale_from_matrix(mg):
    """从全局矩阵估算对象缩放。"""
    sx = mg.v1.GetLength()
    sy = mg.v2.GetLength()
    sz = mg.v3.GetLength()

    return c4d.Vector(abs(sx), abs(sy), abs(sz))


def get_bbox_size(obj):
    """
    获取对象 bounding box 尺寸。
    GetRad() 返回半径，所以需要乘以 2。
    """
    rad = obj.GetRad()
    mg = obj.GetMg()
    scale = get_world_scale_from_matrix(mg)

    return c4d.Vector(
        rad.x * 2.0 * scale.x,
        rad.y * 2.0 * scale.y,
        rad.z * 2.0 * scale.z
    )


def find_or_create_layer(doc, name):
    """查找同名 Layer；如果不存在则创建。"""
    layer_root = doc.GetLayerObjectRoot()
    layer = layer_root.GetDown()

    while layer:
        if layer.GetName() == name:
            return layer
        layer = layer.GetNext()

    new_layer = c4d.documents.LayerObject()
    new_layer.SetName(name)
    new_layer.InsertUnder(layer_root)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, new_layer)

    return new_layer


def main():
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return

    root = doc.GetFirstObject()
    if root is None:
        gui.MessageDialog("当前场景没有对象。")
        return

    dlg = TinyFragmentDialog()

    opened = dlg.Open(
        c4d.DLG_TYPE_MODAL_RESIZEABLE,
        xpos=-2,
        ypos=-2,
        defaultw=780,
        defaulth=430
    )

    if not opened:
        gui.MessageDialog("对话框打开失败。")
        return

    if dlg.cancelled:
        return

    max_side = dlg.max_side
    max_surface = dlg.max_surface
    max_volume = dlg.max_volume

    c4d.StopAllThreads()

    doc.StartUndo()

    tiny_layer = find_or_create_layer(doc, LAYER_NAME)

    matched = []

    all_objects = list(iter_objects(root))

    for obj in all_objects:
        if not is_geometry_candidate(obj):
            continue

        size = get_bbox_size(obj)

        x = abs(size.x)
        y = abs(size.y)
        z = abs(size.z)

        actual_max_side = max(x, y, z)
        surface_area = 2.0 * (x * y + x * z + y * z)
        volume = x * y * z

        is_tiny = (
            actual_max_side <= max_side
            and (
                surface_area <= max_surface
                or volume <= max_volume
            )
        )

        if is_tiny:
            matched.append((obj, size, surface_area, volume))

    # 取消当前选择，然后选择匹配对象
    doc.SetActiveObject(None, c4d.SELECTION_NEW)

    for obj, size, surface_area, volume in matched:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

        # 只设置 Layer，不移动对象层级
        obj[c4d.ID_LAYER_LINK] = tiny_layer

        doc.SetActiveObject(obj, c4d.SELECTION_ADD)

    doc.EndUndo()
    c4d.EventAdd()

    result_msg = (
        "Tiny Fragment Collector finished.\n\n"
        "Matched objects: {}\n\n"
        "Output:\n"
        "Objects were assigned to Layer:\n"
        "{}\n\n"
        "No hierarchy was changed.\n\n"
        "Thresholds:\n"
        "Max side length: {} cm\n"
        "Max surface area: {} cm^2\n"
        "Max volume: {} cm^3\n\n"
        "Condition:\n"
        "Actual max side <= Max side length\n"
        "and\n"
        "(Surface area <= Max surface area or Volume <= Max volume)"
    ).format(
        len(matched),
        LAYER_NAME,
        max_side,
        max_surface,
        max_volume
    )

    gui.MessageDialog(result_msg)


if __name__ == "__main__":
    main()