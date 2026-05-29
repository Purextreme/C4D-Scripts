import c4d
from c4d import documents

# =========================
# 参数区
# =========================

SIZE_TOLERANCE = 0.08
# 边界框尺寸允许误差，0.08 = 8%

POLY_TOLERANCE = 0.05
# 面数允许误差，0.05 = 5%

POINT_TOLERANCE = 0.05
# 点数允许误差，0.05 = 5%

MIN_GROUP_COUNT = 2
# 至少多少个相似对象才打组

GROUP_ROOT_NAME = "Auto_Similar_Groups"

ONLY_POLYGON_OBJECTS = True
# True：只处理 Polygon Object
# False：也可以尝试处理其他有点信息的对象，但不推荐


# =========================
# 工具函数
# =========================

def get_all_children(obj):
    """递归获取对象及其子对象"""
    result = []

    def walk(o):
        while o:
            result.append(o)
            if o.GetDown():
                walk(o.GetDown())
            o = o.GetNext()

    walk(obj)
    return result


def collect_scene_objects(doc):
    """收集整个场景对象"""
    first = doc.GetFirstObject()
    if not first:
        return []

    result = []

    def walk(o):
        while o:
            result.append(o)
            if o.GetDown():
                walk(o.GetDown())
            o = o.GetNext()

    walk(first)
    return result


def is_valid_mesh(obj):
    """判断是否是可分析的模型对象"""
    if ONLY_POLYGON_OBJECTS:
        return obj.CheckType(c4d.Opolygon)

    return hasattr(obj, "GetPointCount") and obj.GetPointCount() > 0


def get_world_scale_from_matrix(mg):
    """从全局矩阵中估算对象缩放"""
    sx = mg.v1.GetLength()
    sy = mg.v2.GetLength()
    sz = mg.v3.GetLength()
    return c4d.Vector(sx, sy, sz)


def get_object_signature(obj):
    """
    获取对象特征：
    - 排序后的包围盒尺寸
    - 面数
    - 点数
    """

    if not obj.CheckType(c4d.Opolygon):
        return None

    rad = obj.GetRad() * 2.0
    scale = get_world_scale_from_matrix(obj.GetMg())

    size = c4d.Vector(
        abs(rad.x * scale.x),
        abs(rad.y * scale.y),
        abs(rad.z * scale.z)
    )

    # 排序后比较，降低对象旋转方向带来的影响
    sorted_size = sorted([size.x, size.y, size.z])

    poly_count = obj.GetPolygonCount()
    point_count = obj.GetPointCount()

    if poly_count <= 0 or point_count <= 0:
        return None

    return {
        "size": sorted_size,
        "poly_count": poly_count,
        "point_count": point_count
    }


def relative_close(a, b, tolerance):
    """相对误差比较"""
    if a == 0 and b == 0:
        return True

    base = max(abs(a), abs(b), 0.000001)
    return abs(a - b) / base <= tolerance


def signatures_similar(sig_a, sig_b):
    """判断两个对象特征是否相似"""

    for a, b in zip(sig_a["size"], sig_b["size"]):
        if not relative_close(a, b, SIZE_TOLERANCE):
            return False

    if not relative_close(
        sig_a["poly_count"],
        sig_b["poly_count"],
        POLY_TOLERANCE
    ):
        return False

    if not relative_close(
        sig_a["point_count"],
        sig_b["point_count"],
        POINT_TOLERANCE
    ):
        return False

    return True


def cluster_objects(objects):
    """按相似度进行简单聚类"""
    clusters = []

    for obj in objects:
        sig = get_object_signature(obj)
        if sig is None:
            continue

        placed = False

        for cluster in clusters:
            ref_sig = cluster["signature"]
            if signatures_similar(sig, ref_sig):
                cluster["objects"].append(obj)
                placed = True
                break

        if not placed:
            clusters.append({
                "signature": sig,
                "objects": [obj]
            })

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


# =========================
# 主逻辑
# =========================

def main():
    doc = documents.GetActiveDocument()
    if doc is None:
        return

    selected = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

    if selected:
        candidates = []
        for obj in selected:
            candidates.extend(get_all_children(obj))
    else:
        candidates = collect_scene_objects(doc)

    # 去重
    seen = set()
    unique_candidates = []
    for obj in candidates:
        if obj not in seen:
            seen.add(obj)
            unique_candidates.append(obj)

    mesh_objects = [obj for obj in unique_candidates if is_valid_mesh(obj)]

    if not mesh_objects:
        c4d.gui.MessageDialog("没有找到可处理的 Polygon Object。")
        return

    clusters = cluster_objects(mesh_objects)

    valid_clusters = [
        c for c in clusters
        if len(c["objects"]) >= MIN_GROUP_COUNT
    ]

    if not valid_clusters:
        c4d.gui.MessageDialog("没有找到数量足够的相似对象。可以适当调大 SIZE_TOLERANCE / POLY_TOLERANCE。")
        return

    doc.StartUndo()

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

    doc.EndUndo()
    c4d.EventAdd()

    c4d.gui.MessageDialog(
        f"完成：找到 {len(valid_clusters)} 组相似对象。\n"
        f"已整理到 Null：{GROUP_ROOT_NAME}"
    )


if __name__ == "__main__":
    main()