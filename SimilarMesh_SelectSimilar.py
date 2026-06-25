import c4d
from c4d import documents


SIZE_TOLERANCE = 0.08
POLY_TOLERANCE = 0.05
POINT_TOLERANCE = 0.05

ONLY_POLYGON_OBJECTS = True
SKIP_HIDDEN_OBJECTS = True


def collect_scene_objects(doc):
    result = []

    def walk(obj):
        while obj:
            result.append(obj)
            child = obj.GetDown()
            if child:
                walk(child)
            obj = obj.GetNext()

    first = doc.GetFirstObject()
    if first:
        walk(first)
    return result


def is_valid_mesh(obj):
    if ONLY_POLYGON_OBJECTS:
        return obj.CheckType(c4d.Opolygon)
    return hasattr(obj, "GetPointCount") and obj.GetPointCount() > 0


def get_nbit(obj, bit):
    method = getattr(obj, "GetNBit", None)
    if method is None:
        return False
    try:
        return bool(method(bit))
    except Exception:
        return False


def is_layer_visible(layer, doc):
    while layer:
        try:
            data = layer.GetLayerData(doc)
        except Exception:
            data = None

        if data:
            if not data.get("view", True):
                return False
            if not data.get("manager", True):
                return False
        else:
            try:
                if not bool(layer[c4d.ID_LAYER_VIEW]):
                    return False
            except Exception:
                pass
            try:
                if not bool(layer[c4d.ID_LAYER_MANAGER]):
                    return False
            except Exception:
                pass

        layer = layer.GetUp()

    return True


def is_object_hidden_in_hierarchy(obj, doc):
    current = obj
    while current:
        try:
            if current.GetEditorMode() == c4d.MODE_OFF:
                return True
        except Exception:
            pass

        if get_nbit(current, c4d.NBIT_EHIDE):
            return True

        if get_nbit(current, c4d.NBIT_OHIDE):
            return True

        try:
            layer = current.GetLayerObject(doc)
            if layer and not is_layer_visible(layer, doc):
                return True
        except Exception:
            pass

        current = current.GetUp()

    return False


def should_process_object(obj, doc):
    if SKIP_HIDDEN_OBJECTS and is_object_hidden_in_hierarchy(obj, doc):
        return False
    return is_valid_mesh(obj)


def get_world_scale_from_matrix(mg):
    return c4d.Vector(mg.v1.GetLength(), mg.v2.GetLength(), mg.v3.GetLength())


def get_object_signature(obj):
    if not obj.CheckType(c4d.Opolygon):
        return None

    rad = obj.GetRad() * 2.0
    scale = get_world_scale_from_matrix(obj.GetMg())
    size = c4d.Vector(
        abs(rad.x * scale.x),
        abs(rad.y * scale.y),
        abs(rad.z * scale.z),
    )

    poly_count = obj.GetPolygonCount()
    point_count = obj.GetPointCount()
    if poly_count <= 0 or point_count <= 0:
        return None

    return {
        "size": sorted([size.x, size.y, size.z]),
        "poly_count": poly_count,
        "point_count": point_count,
    }


def relative_close(a, b, tolerance):
    if a == 0 and b == 0:
        return True
    base = max(abs(a), abs(b), 0.000001)
    return abs(a - b) / base <= tolerance


def signatures_similar(sig_a, sig_b):
    for a, b in zip(sig_a["size"], sig_b["size"]):
        if not relative_close(a, b, SIZE_TOLERANCE):
            return False

    if not relative_close(sig_a["poly_count"], sig_b["poly_count"], POLY_TOLERANCE):
        return False

    if not relative_close(sig_a["point_count"], sig_b["point_count"], POINT_TOLERANCE):
        return False

    return True


def select_objects(doc, objects):
    doc.SetActiveObject(None, c4d.SELECTION_NEW)
    first = True
    for obj in objects:
        mode = c4d.SELECTION_NEW if first else c4d.SELECTION_ADD
        doc.SetActiveObject(obj, mode)
        first = False


def main():
    doc = documents.GetActiveDocument()
    if doc is None:
        return

    selected = doc.GetActiveObjects(0)
    if len(selected) != 1:
        c4d.gui.MessageDialog("请只选择 1 个 Polygon Object 作为参考对象。")
        return

    target_obj = selected[0]
    if not should_process_object(target_obj, doc):
        c4d.gui.MessageDialog(
            "当前选中的对象不可作为参考对象。\n"
            "可能原因：不是 Polygon Object、对象被隐藏、父级隐藏，或在隐藏 Layer 中。"
        )
        return

    target_sig = get_object_signature(target_obj)
    if target_sig is None:
        c4d.gui.MessageDialog("当前选中的对象无法生成有效特征。")
        return

    similar_objects = []
    for obj in collect_scene_objects(doc):
        if not should_process_object(obj, doc):
            continue
        sig = get_object_signature(obj)
        if sig and signatures_similar(target_sig, sig):
            similar_objects.append(obj)

    if not similar_objects:
        c4d.gui.MessageDialog("没有找到相似对象。")
        return

    select_objects(doc, similar_objects)
    c4d.EventAdd()
    c4d.gui.MessageDialog(
        f"选择相似对象完成：已选中 {len(similar_objects)} 个对象。\n"
        "本脚本不会创建 Null，也不会改变对象层级。\n"
        "已尽量跳过隐藏对象、父级隐藏对象、Object Solo 隐藏对象和隐藏 Layer 对象。"
    )


if __name__ == "__main__":
    main()
