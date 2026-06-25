import c4d
from c4d import gui


# -----------------------------
# Script Name:
# Select Similar Bounding Box Objects
# 相似包围盒选择器
#
# 功能：
# 根据当前唯一选中对象的 bounding box 最长边，
# 选择场景中 bounding box 最长边处于指定倍数范围内的对象。
# 默认范围：0x ~ 2x
# -----------------------------


ID_MIN_FACTOR = 1001
ID_MAX_FACTOR = 1002
ID_OK = 1003
ID_CANCEL = 1004


class FactorDialog(gui.GeDialog):
    def __init__(self):
        super().__init__()
        self.min_factor = 0.0
        self.max_factor = 2.0
        self.ok = False

    def CreateLayout(self):
        self.SetTitle("相似包围盒选择器")

        self.GroupBegin(2000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddStaticText(2001, c4d.BFH_LEFT, name="最小倍数：")
        self.AddEditNumberArrows(ID_MIN_FACTOR, c4d.BFH_SCALEFIT)

        self.AddStaticText(2002, c4d.BFH_LEFT, name="最大倍数：")
        self.AddEditNumberArrows(ID_MAX_FACTOR, c4d.BFH_SCALEFIT)
        self.GroupEnd()

        self.GroupBegin(2003, c4d.BFH_CENTER, 2, 1)
        self.AddButton(ID_OK, c4d.BFH_CENTER, name="确定")
        self.AddButton(ID_CANCEL, c4d.BFH_CENTER, name="取消")
        self.GroupEnd()

        return True

    def InitValues(self):
        self.SetFloat(ID_MIN_FACTOR, self.min_factor)
        self.SetFloat(ID_MAX_FACTOR, self.max_factor)
        return True

    def Command(self, cid, msg):
        if cid == ID_OK:
            self.min_factor = self.GetFloat(ID_MIN_FACTOR)
            self.max_factor = self.GetFloat(ID_MAX_FACTOR)
            self.ok = True
            self.Close()
            return True

        if cid == ID_CANCEL:
            self.ok = False
            self.Close()
            return True

        return True


def is_layer_visible(op, doc):
    layer = op.GetLayerObject(doc)
    if layer is None:
        return True

    try:
        data = layer.GetLayerData(doc)
        if "view" in data and data["view"] is False:
            return False
    except Exception:
        pass

    return True


def is_editor_visible(op, doc):
    """
    检查对象及其父级是否在编辑器中可见。
    忽略：
    1. 对象自身隐藏
    2. 父级隐藏
    3. Layer 视图隐藏
    """
    current = op

    while current:
        if current.GetEditorMode() == c4d.MODE_OFF:
            return False

        if not is_layer_visible(current, doc):
            return False

        current = current.GetUp()

    return True


def get_bbox_longest_side(op):
    """
    获取 bounding box 最长边。
    匹配盒按立方体处理：
    x / y / z 都视为最长边长度。
    所以只需要比较最长边。
    """
    rad = op.GetRad()

    size_x = rad.x * 2.0
    size_y = rad.y * 2.0
    size_z = rad.z * 2.0

    return max(size_x, size_y, size_z)


def iter_objects(op):
    while op:
        yield op

        child = op.GetDown()
        if child:
            for sub in iter_objects(child):
                yield sub

        op = op.GetNext()


def main():
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return

    selected = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)

    if len(selected) == 0:
        gui.MessageDialog("请先选择一个参考对象。")
        return

    if len(selected) > 1:
        gui.MessageDialog("只能选择一个参考对象，请不要同时选择多个对象。")
        return

    ref_obj = selected[0]
    ref_longest = get_bbox_longest_side(ref_obj)

    if ref_longest <= 0:
        gui.MessageDialog("当前选择对象的 bounding box 尺寸无效。")
        return

    dlg = FactorDialog()
    dlg.Open(c4d.DLG_TYPE_MODAL_RESIZEABLE, defaultw=320, defaulth=110)

    if not dlg.ok:
        return

    min_factor = dlg.min_factor
    max_factor = dlg.max_factor

    if min_factor < 0:
        gui.MessageDialog("最小倍数不能小于 0。")
        return

    if max_factor <= 0:
        gui.MessageDialog("最大倍数必须大于 0。")
        return

    if min_factor > max_factor:
        gui.MessageDialog("最小倍数不能大于最大倍数。")
        return

    min_side = ref_longest * min_factor
    max_side = ref_longest * max_factor

    matched = []

    root = doc.GetFirstObject()
    if root is None:
        return

    for op in iter_objects(root):
        if not is_editor_visible(op, doc):
            continue

        longest = get_bbox_longest_side(op)

        if longest <= 0:
            continue

        if min_side <= longest <= max_side:
            matched.append(op)

    doc.StartUndo()

    for op in doc.GetActiveObjects(0):
        doc.AddUndo(c4d.UNDOTYPE_BITS, op)
        op.DelBit(c4d.BIT_ACTIVE)

    for op in matched:
        doc.AddUndo(c4d.UNDOTYPE_BITS, op)
        op.SetBit(c4d.BIT_ACTIVE)

    doc.EndUndo()
    c4d.EventAdd()

    gui.MessageDialog(
        "完成。\n\n"
        "脚本：相似包围盒选择器\n"
        "参考对象：{}\n"
        "参考最长边：{:.3f}\n"
        "最小倍数：{:.3f}\n"
        "最大倍数：{:.3f}\n"
        "匹配对象数量：{}".format(
            ref_obj.GetName(),
            ref_longest,
            min_factor,
            max_factor,
            len(matched)
        )
    )


if __name__ == "__main__":
    main()