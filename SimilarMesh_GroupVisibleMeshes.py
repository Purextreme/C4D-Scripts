import c4d
from c4d import documents


SIZE_TOLERANCE = 0.08
POLY_TOLERANCE = 0.05
POINT_TOLERANCE = 0.05
MIN_GROUP_COUNT = 2

GROUP_ROOT_NAME = "Auto_Similar_Groups"

ONLY_POLYGON_OBJECTS = True
SKIP_HIDDEN_OBJECTS = True
SKIP_ALREADY_GROUPED = True


def get_all_children(obj):
    result = []

    def walk(current):
        while current:
            result.append(current)
            child = current.GetDown()
            if child:
                walk(child)
            current = current.GetNext()

    walk(obj)
    return result


def collect_scene_objects(doc):
    first = doc.GetFirstObject()
    if not first:
        return []
    return get_all_children(first)


def unique_objects(objects):
    seen = set()
    result = []
    for obj in objects:
        if obj not in seen:
            seen.add(obj)
            result.append(obj)
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


def is_under_existing_auto_group(obj):
    current = obj
    while current:
        name = current.GetName()
        if name == GROUP_ROOT_NAME or name.startswith("Similar_Group_"):
            return True
        current = current.GetUp()
    return False


def should_process_object(obj, doc):
    if SKIP_ALREADY_GROUPED and is_under_existing_auto_group(obj):
        return False
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


def cluster_objects(objects):
    clusters = []
    for obj in objects:
        sig = get_object_signature(obj)
        if sig is None:
            continue

        placed = False
        for cluster in clusters:
            if signatures_similar(sig, cluster["signature"]):
                cluster["objects"].append(obj)
                placed = True
                break

        if not placed:
            clusters.append({"signature": sig, "objects": [obj]})

    return clusters


def make_group_name(index, cluster):
    sig = cluster["signature"]
    size = sig["size"]
    return (
        f"Similar_Group_{index:02d}__"
        f"{len(cluster['objects'])}pcs__"
        f"P{sig['poly_count']}__"
        f"S{size[0]:.1f}_{size[1]:.1f}_{size[2]:.1f}"
    )


def main():
    doc = documents.GetActiveDocument()
    if doc is None:
        return

    selected = doc.GetActiveObjects(0)
    if len(selected) == 1:
        c4d.gui.MessageDialog(
            "当前只选择了 1 个对象。\n"
            "请选择至少 2 个对象进行分组，或改用 SimilarMesh_SelectSimilar.py 选择相似对象。"
        )
        return

    if selected:
        candidates = []
        for obj in selected:
            candidates.extend(get_all_children(obj))
        scope_text = "当前多选对象及其子级"
    else:
        candidates = collect_scene_objects(doc)
        scope_text = "全场景"

    mesh_objects = [
        obj for obj in unique_objects(candidates)
        if should_process_object(obj, doc)
    ]

    if not mesh_objects:
        c4d.gui.MessageDialog(
            "没有找到可处理的 Polygon Object。\n"
            "可能原因：对象被隐藏、父级隐藏、Object Solo 隐藏、在隐藏 Layer 中，或已经位于整理组下。"
        )
        return

    clusters = cluster_objects(mesh_objects)
    valid_clusters = [cluster for cluster in clusters if len(cluster["objects"]) >= MIN_GROUP_COUNT]

    if not valid_clusters:
        c4d.gui.MessageDialog("没有找到数量足够的相似对象。可以适当调大 SIZE_TOLERANCE / POLY_TOLERANCE。")
        return

    if not c4d.gui.QuestionDialog(
        f"将把 {len(valid_clusters)} 组相似对象整理到 {GROUP_ROOT_NAME} 下。\n"
        f"处理范围：{scope_text}。\n"
        "会尽量跳过隐藏对象、Object Solo 隐藏对象和隐藏 Layer 对象。\n\n"
        "是否继续？"
    ):
        return

    doc.StartUndo()
    try:
        root_null = c4d.BaseObject(c4d.Onull)
        root_null.SetName(GROUP_ROOT_NAME)
        doc.InsertObject(root_null)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, root_null)

        group_index = 1
        for cluster in valid_clusters:
            group_null = c4d.BaseObject(c4d.Onull)
            group_null.SetName(make_group_name(group_index, cluster))
            group_null.InsertUnderLast(root_null)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, group_null)

            for obj in cluster["objects"]:
                old_mg = obj.GetMg()
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
                obj.InsertUnderLast(group_null)
                obj.SetMg(old_mg)

            group_index += 1
    finally:
        doc.EndUndo()

    c4d.EventAdd()
    c4d.gui.MessageDialog(
        f"分组完成：找到 {len(valid_clusters)} 组相似对象。\n"
        f"已整理到 Null：{GROUP_ROOT_NAME}\n"
        "已尽量跳过隐藏对象、父级隐藏对象、Object Solo 隐藏对象、隐藏 Layer 对象和已整理对象。"
    )


if __name__ == "__main__":
    main()
