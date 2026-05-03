import c4d
from c4d import Vector

# ============================================================
# MoI / STEP BBox Metadata Transfer for Cinema 4D 2024
# v0.2
#
# 用途：
# STEP_REF 作为参考模型，提供对象名 / 材质 / Layer / 层级
# MOI_MESH 作为高质量 mesh，接收 STEP_REF 的 metadata
#
# 推荐场景结构：
#
# STEP_REF
#   shell01
#   button01
#
# MOI_MESH
#   obj1
#   obj2
#
# 运行后：
#
# MOI_REBUILT
#   ...
# ============================================================


# =========================
# 用户配置区
# =========================

STEP_ROOT_NAME = "STEP_REF"       # STEP 导入模型的总 Null 名称
MOI_ROOT_NAME = "MOI_MESH"        # MoI 导入模型的总 Null 名称
RESULT_ROOT_NAME = "MOI_REBUILT"  # 重建后的 MoI 结果总 Null 名称

MOI_NAME_PREFIX = "obj"           # 只处理 obj1 / obj2 / obj3 这种 MoI 对象

CENTER_TOLERANCE = 0.05           # bbox 中心点误差容忍，参考 bbox 对角线的 5%
SIZE_TOLERANCE = 0.05             # bbox 尺寸误差容忍，5%

LOW_CONFIDENCE_SCORE = 0.03       # 超过该分数则标记 CHECK_

COPY_TEXTURE_TAGS = True          # 复制材质 tag
COPY_LAYER = True                 # 复制 C4D Layer
DELETE_MOI_TEXTURE_TAGS = True    # 删除 MoI 原始材质 tag
REBUILD_HIERARCHY = True          # 根据 STEP 层级重建 MoI 层级

CREATE_LEAF_NULL = False          # 是否为每个匹配对象也创建一个同名 Null
ADD_PARENT_NAME_TO_RENAME = True  # 重命名时加入 STEP 父级名
SHOW_START_NOTICE = True          # 运行前显示说明窗口

DRY_RUN = False                   # True = 只打印匹配结果，不实际修改


# =========================
# 提示窗口
# =========================

def show_start_notice():
    msg = (
        "MoI / STEP BBox Metadata Transfer\n\n"
        "运行前请确认场景中有两个总组：\n\n"
        "1. STEP_REF\n"
        "   - STEP 导入的参考模型\n"
        "   - 用于提供对象名、材质、Layer、层级\n\n"
        "2. MOI_MESH\n"
        "   - MoI / FBX 导入的高质量模型\n"
        "   - 子对象通常命名为 obj1 / obj2 / obj3 ...\n\n"
        "脚本会根据 bbox 匹配：\n"
        "obj* → STEP 对象\n\n"
        "然后复制名称、材质、Layer，并重建层级。\n\n"
        "当前设置：\n"
        f"STEP_ROOT_NAME = {STEP_ROOT_NAME}\n"
        f"MOI_ROOT_NAME = {MOI_ROOT_NAME}\n"
        f"RESULT_ROOT_NAME = {RESULT_ROOT_NAME}\n"
        f"DRY_RUN = {DRY_RUN}\n\n"
        "是否继续？"
    )

    return c4d.gui.QuestionDialog(msg)


# =========================
# 基础工具函数
# =========================

def get_descendants(root):
    """获取 root 下所有子对象，不包含 root 自身。"""
    result = []

    def walk(obj):
        child = obj.GetDown()
        while child:
            result.append(child)
            walk(child)
            child = child.GetNext()

    walk(root)
    return result


def is_geometry_object(obj):
    """判断是否是可用于 bbox 的几何对象。"""
    return isinstance(obj, c4d.PointObject) and obj.GetPointCount() > 0


def get_world_bbox(obj):
    """
    获取对象的世界空间 bbox。
    返回: (min_v, max_v, center, size, diag)
    """
    if not is_geometry_object(obj):
        return None

    mg = obj.GetMg()
    points = obj.GetAllPoints()

    if not points:
        return None

    world_points = [mg * p for p in points]

    min_x = min(p.x for p in world_points)
    min_y = min(p.y for p in world_points)
    min_z = min(p.z for p in world_points)

    max_x = max(p.x for p in world_points)
    max_y = max(p.y for p in world_points)
    max_z = max(p.z for p in world_points)

    min_v = Vector(min_x, min_y, min_z)
    max_v = Vector(max_x, max_y, max_z)
    center = (min_v + max_v) * 0.5
    size = max_v - min_v
    diag = size.GetLength()

    return min_v, max_v, center, size, diag


def safe_ratio(a, b):
    """计算相对误差。"""
    if abs(b) < 0.000001:
        return abs(a)
    return abs(a - b) / abs(b)


def bbox_match_score(moi_bbox, ref_bbox):
    """
    bbox 匹配评分。
    分数越低越接近。
    """
    _, _, moi_center, moi_size, _ = moi_bbox
    _, _, ref_center, ref_size, ref_diag = ref_bbox

    ref_diag_safe = max(ref_diag, 0.000001)

    center_error = (moi_center - ref_center).GetLength() / ref_diag_safe

    size_error_x = safe_ratio(moi_size.x, ref_size.x)
    size_error_y = safe_ratio(moi_size.y, ref_size.y)
    size_error_z = safe_ratio(moi_size.z, ref_size.z)

    size_error = max(size_error_x, size_error_y, size_error_z)

    score = center_error + size_error

    return score, center_error, size_error


def remove_texture_tags(obj):
    """删除对象上的材质 tag。"""
    tags = list(obj.GetTags())

    for tag in tags:
        if tag.CheckType(c4d.Ttexture):
            tag.Remove()


def copy_texture_tags(src, dst):
    """复制材质 tag。"""
    for tag in src.GetTags():
        if tag.CheckType(c4d.Ttexture):
            new_tag = tag.GetClone()
            dst.InsertTag(new_tag)


def copy_layer(src, dst, doc):
    """复制 C4D Layer。"""
    try:
        layer = src.GetLayerObject(doc)
        if layer:
            dst.SetLayerObject(layer)
    except Exception:
        pass


def get_parent_path(obj, root):
    """
    获取 obj 相对 root 的父级路径。
    不包含 root，不包含 obj 自身。
    """
    path = []
    parent = obj.GetUp()

    while parent and parent != root:
        path.append(parent.GetName())
        parent = parent.GetUp()

    path.reverse()
    return path


def get_parent_name(obj, root):
    """
    获取 obj 相对 root 的直接父级名。
    用于重命名。
    """
    parent = obj.GetUp()

    if parent and parent != root:
        return parent.GetName()

    return "ROOT"


def sanitize_name(name):
    """
    简单清理对象名，避免过长空格。
    C4D 对名字限制不严，这里不做强制替换。
    """
    if not name:
        return "Unnamed"

    return str(name).strip()


def get_or_create_null(parent, name, doc, cache):
    """
    在 parent 下获取或创建同名 Null。
    cache 用于避免重复创建。
    """
    name = sanitize_name(name)
    key = (id(parent), name)

    if key in cache:
        return cache[key]

    child = parent.GetDown()
    while child:
        if child.GetName() == name and child.CheckType(c4d.Onull):
            cache[key] = child
            return child
        child = child.GetNext()

    null = c4d.BaseObject(c4d.Onull)
    null.SetName(name)

    if not DRY_RUN:
        null.InsertUnderLast(parent)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, null)

    cache[key] = null
    return null


def build_new_name(moi_obj, ref_obj, step_root, is_low_confidence):
    """
    构建新的 MoI 对象名。
    默认格式：
    obj1_PARENT_REFNAME
    低可信则：
    CHECK_obj1_PARENT_REFNAME
    """
    old_name = sanitize_name(moi_obj.GetName())
    ref_name = sanitize_name(ref_obj.GetName())
    parent_name = sanitize_name(get_parent_name(ref_obj, step_root))

    if ADD_PARENT_NAME_TO_RENAME and parent_name != "ROOT":
        new_name = f"{old_name}_{parent_name}_{ref_name}"
    else:
        new_name = f"{old_name}_{ref_name}"

    if is_low_confidence:
        new_name = "CHECK_" + new_name

    return new_name


def find_best_match(moi_obj, ref_candidates, used_refs):
    """
    为一个 MoI 对象寻找最匹配的 STEP 对象。
    一对一匹配：已使用过的 STEP 对象不会再次匹配。
    """
    moi_bbox = get_world_bbox(moi_obj)

    if not moi_bbox:
        return None

    best = None

    for ref_obj, ref_bbox in ref_candidates:
        if ref_obj in used_refs:
            continue

        score, center_error, size_error = bbox_match_score(moi_bbox, ref_bbox)

        if center_error <= CENTER_TOLERANCE and size_error <= SIZE_TOLERANCE:
            if best is None or score < best["score"]:
                best = {
                    "ref": ref_obj,
                    "score": score,
                    "center_error": center_error,
                    "size_error": size_error,
                }

    return best


def print_object_path(obj, root):
    """打印对象相对 root 的路径，便于排查。"""
    names = []
    current = obj

    while current and current != root:
        names.append(current.GetName())
        current = current.GetUp()

    names.reverse()
    return "/".join(names)


# =========================
# 主逻辑
# =========================

def main():
    doc = c4d.documents.GetActiveDocument()

    if SHOW_START_NOTICE:
        if not show_start_notice():
            return

    step_root = doc.SearchObject(STEP_ROOT_NAME)
    moi_root = doc.SearchObject(MOI_ROOT_NAME)

    if not step_root or not moi_root:
        c4d.gui.MessageDialog(
            "找不到 STEP_REF 或 MOI_MESH。\n\n"
            "请确认场景中有两个总组：\n\n"
            f"{STEP_ROOT_NAME}\n"
            f"{MOI_ROOT_NAME}"
        )
        return

    step_objects = get_descendants(step_root)
    moi_objects = get_descendants(moi_root)

    ref_candidates = []
    for obj in step_objects:
        bbox = get_world_bbox(obj)
        if bbox:
            ref_candidates.append((obj, bbox))

    moi_candidates = []
    for obj in moi_objects:
        if obj.GetName().lower().startswith(MOI_NAME_PREFIX.lower()):
            if get_world_bbox(obj):
                moi_candidates.append(obj)

    if not ref_candidates:
        c4d.gui.MessageDialog("STEP_REF 下没有找到可匹配的几何对象。")
        return

    if not moi_candidates:
        c4d.gui.MessageDialog("MOI_MESH 下没有找到 obj* 几何对象。")
        return

    print("=" * 72)
    print("MoI / STEP BBox Metadata Transfer v0.2")
    print(f"STEP root:       {STEP_ROOT_NAME}")
    print(f"MoI root:        {MOI_ROOT_NAME}")
    print(f"Result root:     {RESULT_ROOT_NAME}")
    print(f"STEP candidates: {len(ref_candidates)}")
    print(f"MoI candidates:  {len(moi_candidates)}")
    print(f"Center tol:      {CENTER_TOLERANCE}")
    print(f"Size tol:        {SIZE_TOLERANCE}")
    print(f"Low confidence:  {LOW_CONFIDENCE_SCORE}")
    print(f"DRY_RUN:         {DRY_RUN}")
    print("=" * 72)

    doc.StartUndo()

    result_root = None
    null_cache = {}

    if REBUILD_HIERARCHY:
        result_root = doc.SearchObject(RESULT_ROOT_NAME)

        if not result_root:
            result_root = c4d.BaseObject(c4d.Onull)
            result_root.SetName(RESULT_ROOT_NAME)

            if not DRY_RUN:
                doc.InsertObject(result_root)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, result_root)

    used_refs = set()
    matched_count = 0
    low_confidence_count = 0
    unmatched = []

    for moi_obj in moi_candidates:
        best = find_best_match(moi_obj, ref_candidates, used_refs)

        if not best:
            unmatched.append(moi_obj)
            print(f"[UNMATCHED] {print_object_path(moi_obj, moi_root)}")
            continue

        ref_obj = best["ref"]
        used_refs.add(ref_obj)
        matched_count += 1

        is_low_confidence = best["score"] >= LOW_CONFIDENCE_SCORE

        if is_low_confidence:
            low_confidence_count += 1
            status = "CHECK"
        else:
            status = "MATCH"

        old_name = moi_obj.GetName()
        ref_name = ref_obj.GetName()
        new_name = build_new_name(moi_obj, ref_obj, step_root, is_low_confidence)

        print(
            f"[{status}] "
            f"{print_object_path(moi_obj, moi_root)}  -->  "
            f"{print_object_path(ref_obj, step_root)} | "
            f"new='{new_name}' | "
            f"score={best['score']:.4f}, "
            f"center={best['center_error']:.4f}, "
            f"size={best['size_error']:.4f}"
        )

        if DRY_RUN:
            continue

        doc.AddUndo(c4d.UNDOTYPE_CHANGE, moi_obj)

        if DELETE_MOI_TEXTURE_TAGS:
            remove_texture_tags(moi_obj)

        moi_obj.SetName(new_name)

        if COPY_TEXTURE_TAGS:
            copy_texture_tags(ref_obj, moi_obj)

        if COPY_LAYER:
            copy_layer(ref_obj, moi_obj, doc)

        if REBUILD_HIERARCHY and result_root:
            parent_path = get_parent_path(ref_obj, step_root)
            target_parent = result_root

            for name in parent_path:
                target_parent = get_or_create_null(target_parent, name, doc, null_cache)

            if CREATE_LEAF_NULL:
                target_parent = get_or_create_null(target_parent, ref_name, doc, null_cache)

            doc.AddUndo(c4d.UNDOTYPE_CHANGE, moi_obj)
            moi_obj.InsertUnderLast(target_parent)

    if unmatched and REBUILD_HIERARCHY and result_root and not DRY_RUN:
        unmatched_null = get_or_create_null(result_root, "_UNMATCHED_MOI", doc, null_cache)

        for obj in unmatched:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.InsertUnderLast(unmatched_null)

    doc.EndUndo()
    c4d.EventAdd()

    print("=" * 72)
    print(f"Matched:        {matched_count}")
    print(f"Low confidence: {low_confidence_count}")
    print(f"Unmatched:      {len(unmatched)}")
    print("=" * 72)

    c4d.gui.MessageDialog(
        f"处理完成。\n\n"
        f"匹配成功：{matched_count}\n"
        f"低可信匹配：{low_confidence_count}\n"
        f"未匹配：{len(unmatched)}\n\n"
        "低可信对象会带 CHECK_ 前缀。\n"
        "详细结果请看 Console。"
    )


if __name__ == "__main__":
    main()