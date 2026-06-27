import c4d

# ============================================================
# Sketch Spline Display Color Builder
# ------------------------------------------------------------
# 功能：
# 1. 对选中的 spline 或其子级 spline 生效
# 2. 读取 spline 的 Display Color
# 3. 为每条 spline 创建同色 Sketch Material
# 4. 给 spline 创建 Sketch Style Tag
# 5. 将 Sketch Style Tag > Lines > Default Visible 指向对应材质
# 6. 可选：额外添加普通 Texture Tag，方便在对象管理器里看到材质标签
# 7. 尝试自动添加 Render Settings > Sketch and Toon，并勾选 Splines
# ============================================================

# =========================
# User Settings
# =========================

PROCESS_CHILDREN = True

MATERIAL_PREFIX = "SK_DisplayColor_"

# True：把对象显示颜色模式设为 Always，方便确认 Display Color 被使用
FORCE_OBJECT_COLOR_MODE = True

# True：删除对象上旧的 Sketch Style Tag，避免重复叠加
DELETE_OLD_SKETCH_STYLE_TAGS = False

# True：删除对象上旧的 Texture Tag，避免重复挂一堆材质标签
DELETE_OLD_TEXTURE_TAGS = False

# True：额外给对象挂一个普通 Texture Tag。
# 注意：Sketch 真正生效靠 Sketch Style Tag 的 Default Visible。
# 这个 Texture Tag 主要是为了在对象管理器里更直观看到材质球标签。
ADD_TEXTURE_TAG_FOR_VISIBILITY = True

# True：Default Hidden 也使用同一个 Sketch Material
ASSIGN_HIDDEN_MAT_TOO = True

# True：只打开 Splines 线条类型，关闭 Outline / Edges 等其它类型
DISABLE_OTHER_LINE_TYPES = True

# True：尝试自动配置 Render Settings 里的 Sketch and Toon
CONFIGURE_RENDER_SETTINGS = True

# True：运行脚本时弹窗输入线条厚度。
# False：直接使用下面的 LINE_THICKNESS。
ASK_THICKNESS_ON_RUN = True

# Sketch 线条粗细。单位通常是像素相关的 Sketch Thickness 参数。
# 不同 C4D 版本参数 ID 可能不同，所以脚本会通过名称尽量设置。
LINE_THICKNESS = 3.0

# Sketch 线条透明度
LINE_OPACITY = 1.0


# =========================
# Helpers
# =========================

def safe_set(node, param_id, value):
    try:
        node[param_id] = value
        return True
    except Exception:
        return False


def is_spline(obj):
    return obj is not None and obj.CheckType(c4d.Ospline)


def iter_children(obj):
    child = obj.GetDown()
    while child:
        yield child
        for sub in iter_children(child):
            yield sub
        child = child.GetNext()


def collect_splines(selection):
    result = []

    for obj in selection:
        if is_spline(obj):
            result.append(obj)

        if PROCESS_CHILDREN:
            for child in iter_children(obj):
                if is_spline(child):
                    result.append(child)

    unique = []
    seen = set()

    for obj in result:
        try:
            guid = obj.GetGUID()
        except Exception:
            guid = id(obj)

        if guid not in seen:
            unique.append(obj)
            seen.add(guid)

    return unique


def get_display_color(obj):
    try:
        return obj[c4d.ID_BASEOBJECT_COLOR]
    except Exception:
        return c4d.Vector(1.0, 1.0, 1.0)


def force_display_color_mode(obj):
    if not FORCE_OBJECT_COLOR_MODE:
        return

    try:
        obj[c4d.ID_BASEOBJECT_USECOLOR] = c4d.ID_BASEOBJECT_USECOLOR_ALWAYS
    except Exception:
        pass


def set_desc_params_by_name(node, value, include_keywords, exclude_keywords=None):
    """
    通过 Description 名称容错设置参数。
    Sketch Material 在不同 C4D 版本里参数 ID 可能不完全一致，
    所以这里用名字匹配作为补充。
    """
    exclude_keywords = exclude_keywords or []
    changed = 0

    try:
        desc = node.GetDescription(c4d.DESCFLAGS_DESC_NONE)
    except Exception:
        return 0

    if not desc:
        return 0

    for bc, param_id, group_id in desc:
        try:
            name = str(bc[c4d.DESC_NAME]).lower()
        except Exception:
            continue

        if not any(k.lower() in name for k in include_keywords):
            continue

        if any(k.lower() in name for k in exclude_keywords):
            continue

        try:
            node[param_id] = value
            changed += 1
        except Exception:
            pass

    return changed


def configure_sketch_material_basic(mat, color, thickness):
    """
    尽量把 Sketch Material 设置成：
    - 指定颜色
    - 固定线宽
    - 不透明
    """

    # 颜色：通过名称匹配尽量设置所有 color/colour 参数
    set_desc_params_by_name(mat, color, ["color", "colour"])

    # 线宽：通过名称匹配 thickness / width / size
    set_desc_params_by_name(
        mat,
        float(thickness),
        ["thickness", "width", "size"],
        ["variation", "random", "map"]
    )

    # 透明度 / opacity
    set_desc_params_by_name(
        mat,
        float(LINE_OPACITY),
        ["opacity"],
        ["variation", "random", "map"]
    )

    mat.Update(True, True)


def create_sketch_material(doc, name, color, thickness):
    if not hasattr(c4d, "Msketch"):
        raise RuntimeError("当前 C4D Python 环境没有 c4d.Msketch，无法创建 Sketch Material。")

    mat = c4d.BaseMaterial(c4d.Msketch)
    mat.SetName(name)

    configure_sketch_material_basic(mat, color, thickness)

    doc.InsertMaterial(mat)
    mat.Update(True, True)

    return mat


def remove_tags_by_type(doc, obj, tag_type):
    tag = obj.GetFirstTag()
    while tag:
        nxt = tag.GetNext()
        try:
            if tag.CheckType(tag_type):
                doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, tag)
                tag.Remove()
        except Exception:
            pass
        tag = nxt


def find_first_tag_by_type(obj, tag_type):
    tag = obj.GetFirstTag()
    while tag:
        try:
            if tag.CheckType(tag_type):
                return tag
        except Exception:
            pass
        tag = tag.GetNext()
    return None


def add_texture_tag(doc, obj, mat):
    """
    额外添加普通 Texture Tag。
    这个不是 Sketch 渲染的核心，但方便你在对象管理器里看到材质标签。
    """
    if DELETE_OLD_TEXTURE_TAGS:
        remove_tags_by_type(doc, obj, c4d.Ttexture)

    tag = c4d.TextureTag()
    tag.SetMaterial(mat)
    obj.InsertTag(tag)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
    return tag


def set_only_spline_lines(node):
    """
    node 可以是 Sketch Style Tag 或 Sketch VideoPost。
    设置 Lines 类型：只启用 Splines。
    """
    if DISABLE_OTHER_LINE_TYPES:
        maybe_line_type_ids = [
            "OUTLINEMAT_LINE_OUTLINE",
            "OUTLINEMAT_LINE_FOLD",
            "OUTLINEMAT_LINE_OVERLAPS",
            "OUTLINEMAT_LINE_CREASE",
            "OUTLINEMAT_LINE_ANGLE",
            "OUTLINEMAT_LINE_BORDER",
            "OUTLINEMAT_LINE_MATERIAL",
            "OUTLINEMAT_LINE_EDGES",
            "OUTLINEMAT_LINE_INTERSECTION",
            "OUTLINEMAT_LINE_TRI",
            "OUTLINEMAT_LINE_MOTION",
            "OUTLINEMAT_LINE_CONTOUR",
            "OUTLINEMAT_LINE_ISOPARMS",
            "OUTLINEMAT_LINE_PARTICLES",
        ]

        for name in maybe_line_type_ids:
            if hasattr(c4d, name):
                safe_set(node, getattr(c4d, name), False)

    if hasattr(c4d, "OUTLINEMAT_LINE_SPLINES"):
        safe_set(node, c4d.OUTLINEMAT_LINE_SPLINES, True)


def create_or_update_sketch_style_tag(doc, obj, sketch_mat):
    if not hasattr(c4d, "Tsketchstyle"):
        raise RuntimeError("当前 C4D Python 环境没有 c4d.Tsketchstyle，无法创建 Sketch Style Tag。")

    if DELETE_OLD_SKETCH_STYLE_TAGS:
        remove_tags_by_type(doc, obj, c4d.Tsketchstyle)

    tag = find_first_tag_by_type(obj, c4d.Tsketchstyle)

    if tag is None:
        tag = c4d.BaseTag(c4d.Tsketchstyle)
        obj.InsertTag(tag)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
    else:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)

    # 启用 Sketch Style Tag
    if hasattr(c4d, "TOONRESTRICT_ENABLE"):
        safe_set(tag, c4d.TOONRESTRICT_ENABLE, True)

    # Mix 设置成 Use / Set，尽量让本 tag 的设置直接生效
    if hasattr(c4d, "TOONRESTRICT_MIX") and hasattr(c4d, "TOONRESTRICT_MIX_SET"):
        safe_set(tag, c4d.TOONRESTRICT_MIX, c4d.TOONRESTRICT_MIX_SET)

    # Lines 类型：只启用 Splines
    set_only_spline_lines(tag)

    # Combine = All
    if hasattr(c4d, "OUTLINEMAT_LINE_COMBINEMODE") and hasattr(c4d, "OUTLINEMAT_LINE_COMBINEMODE_ALL"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_COMBINEMODE, c4d.OUTLINEMAT_LINE_COMBINEMODE_ALL)

    # Hidden Cull = Self
    if hasattr(c4d, "OUTLINEMAT_LINE_OUTLINE_SHOW_OBJS") and hasattr(c4d, "OUTLINEMAT_LINE_OUTLINE_SHOW_OBJS_OBJECT"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_OUTLINE_SHOW_OBJS, c4d.OUTLINEMAT_LINE_OUTLINE_SHOW_OBJS_OBJECT)

    if hasattr(c4d, "OUTLINEMAT_LINE_OUTLINE_SHOW_SELFOFF"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_OUTLINE_SHOW_SELFOFF, True)

    # 关键：Default Visible 指向本条 spline 的 Sketch Material
    if hasattr(c4d, "OUTLINEMAT_LINE_DEFAULT_MAT_V"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_DEFAULT_MAT_V, sketch_mat)

    if ASSIGN_HIDDEN_MAT_TOO and hasattr(c4d, "OUTLINEMAT_LINE_DEFAULT_MAT_H"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_DEFAULT_MAT_H, sketch_mat)

    # Line Materials = Defaults
    if hasattr(c4d, "OUTLINEMAT_LINE_INDIVIDUALMATS") and hasattr(c4d, "OUTLINEMAT_LINE_INDIVIDUALMATS_DEFAULTS"):
        safe_set(tag, c4d.OUTLINEMAT_LINE_INDIVIDUALMATS, c4d.OUTLINEMAT_LINE_INDIVIDUALMATS_DEFAULTS)

    return tag


def ensure_sketch_and_toon_vp(doc):
    if not hasattr(c4d, "VPsketch"):
        return None

    rd = doc.GetActiveRenderData()
    vp = rd.GetFirstVideoPost()

    while vp:
        try:
            if vp.CheckType(c4d.VPsketch):
                return vp
        except Exception:
            pass
        vp = vp.GetNext()

    try:
        sketch_vp = c4d.documents.BaseVideoPost(c4d.VPsketch)
    except Exception:
        return None

    if sketch_vp is not None:
        rd.InsertVideoPost(sketch_vp)

    return sketch_vp


def configure_render_settings_sketch(vp):
    if vp is None:
        return False

    set_only_spline_lines(vp)
    return True


def ask_user_thickness(default_value):
    """
    运行时弹出输入框，让用户决定本次 Sketch Material 的线条厚度。
    取消或输入非法内容时，返回 None，主程序会中止。
    """
    if not ASK_THICKNESS_ON_RUN:
        return float(default_value)

    text = c4d.gui.InputDialog(
        "请输入 Sketch 线条厚度，例如 2、3、5：",
        str(default_value)
    )

    if text is None:
        return None

    try:
        value = float(text)
    except Exception:
        c4d.gui.MessageDialog("厚度必须是数字，例如 2、3、5。")
        return None

    if value <= 0:
        c4d.gui.MessageDialog("厚度必须大于 0。")
        return None

    return value


# =========================
# Main
# =========================

def main():
    doc = c4d.documents.GetActiveDocument()
    selection = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

    if not selection:
        c4d.gui.MessageDialog("请先选中 spline，或选中包含 spline 子级的父对象。")
        return

    splines = collect_splines(selection)

    if not splines:
        c4d.gui.MessageDialog("没有找到 spline 对象。")
        return

    thickness = ask_user_thickness(LINE_THICKNESS)
    if thickness is None:
        return

    doc.StartUndo()

    # 尝试配置 Render Settings > Sketch and Toon
    sketch_vp = None
    if CONFIGURE_RENDER_SETTINGS:
        sketch_vp = ensure_sketch_and_toon_vp(doc)
        if sketch_vp is not None:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, sketch_vp)
            configure_render_settings_sketch(sketch_vp)

    count = 0

    for sp in splines:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, sp)

        force_display_color_mode(sp)
        color = get_display_color(sp)

        mat = create_sketch_material(doc, MATERIAL_PREFIX + sp.GetName(), color, thickness)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)

        create_or_update_sketch_style_tag(doc, sp, mat)

        if ADD_TEXTURE_TAG_FOR_VISIBILITY:
            add_texture_tag(doc, sp, mat)

        count += 1

    doc.EndUndo()
    c4d.EventAdd()

    c4d.gui.MessageDialog(
        "完成：已为 {} 条 spline 创建 Sketch Style Tag。\n"
        "本次 Sketch 线条厚度：{}。\n"
        "每条 spline 的 Default Visible 已绑定对应 Display Color 的 Sketch Material。\n"
        "同时已按设置额外添加普通 Texture Tag，方便在对象管理器中查看材质。\n\n"
        "如果渲染仍不显示，请确认：\n"
        "1. 使用 Standard / Physical 渲染器测试；\n"
        "2. Render Settings > Sketch and Toon > Lines > Splines 已勾选；\n"
        "3. 对象上的 Sketch Style Tag > Lines > Default Visible 有材质。".format(count, thickness)
    )


if __name__ == "__main__":
    main()
