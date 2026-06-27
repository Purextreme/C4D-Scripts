import c4d
import random
import math

# =========================
# User Settings
# =========================

PROCESS_CHILDREN = True          # True: 对选中对象的所有子级 spline 起作用
HIDE_ORIGINAL_SPLINES = True     # True: 隐藏原始 spline

MASTER_CIRCLE_NAME = "PROFILE_Circle_Master"
RESULT_ROOT_NAME = "Generated_Sweep_From_SVG"

CIRCLE_RADIUS_CM = 0.8

# 随机位置，单位 cm
RANDOM_POS_X = 0.0
RANDOM_POS_Y = 0.0
RANDOM_POS_Z = 0.0

# 随机角度，单位 degree
RANDOM_ROT_H = 0.0
RANDOM_ROT_P = 0.0
RANDOM_ROT_B = 0.0

# 材质设置
MATERIAL_PREFIX = "EM_Spline_"
USE_OBJECT_DISPLAY_COLOR_FALLBACK = True
LUMINANCE_BRIGHTNESS = 1.0


# =========================
# Helpers
# =========================

def safe_set(obj, param_id, value):
    """
    某些 C4D 版本里部分材质通道 ID 可能不存在。
    用 safe_set 避免因为某个通道 ID 不兼容导致整段脚本报错。
    """
    try:
        obj[param_id] = value
    except Exception:
        pass


def is_spline(obj):
    if obj is None:
        return False
    return obj.CheckType(c4d.Ospline)


def iter_children(obj):
    child = obj.GetDown()
    while child:
        yield child
        for sub in iter_children(child):
            yield sub
        child = child.GetNext()


def collect_target_splines(selection):
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
        guid = obj.GetGUID()
        if guid not in seen:
            unique.append(obj)
            seen.add(guid)

    return unique


def get_spline_color(obj):
    """
    优先读取 spline 上第一个材质的颜色；
    如果没有材质，则读取对象 Display Color。
    """
    tex_tag = obj.GetTag(c4d.Ttexture)

    if tex_tag:
        mat = tex_tag.GetMaterial()
        if mat:
            try:
                if mat[c4d.MATERIAL_USE_LUMINANCE]:
                    return mat[c4d.MATERIAL_LUMINANCE_COLOR]
            except Exception:
                pass

            try:
                return mat[c4d.MATERIAL_COLOR_COLOR]
            except Exception:
                pass

    if USE_OBJECT_DISPLAY_COLOR_FALLBACK:
        try:
            return obj[c4d.ID_BASEOBJECT_COLOR]
        except Exception:
            pass

    return c4d.Vector(1.0, 1.0, 1.0)


def create_emission_material(doc, name, color):
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(name)

    # 关闭所有常见材质通道，只保留 Luminance
    safe_set(mat, c4d.MATERIAL_USE_COLOR, False)
    safe_set(mat, c4d.MATERIAL_USE_DIFFUSION, False)
    safe_set(mat, c4d.MATERIAL_USE_LUMINANCE, True)
    safe_set(mat, c4d.MATERIAL_USE_TRANSPARENCY, False)
    safe_set(mat, c4d.MATERIAL_USE_REFLECTION, False)
    safe_set(mat, c4d.MATERIAL_USE_ENVIRONMENT, False)
    safe_set(mat, c4d.MATERIAL_USE_FOG, False)
    safe_set(mat, c4d.MATERIAL_USE_BUMP, False)
    safe_set(mat, c4d.MATERIAL_USE_NORMAL, False)
    safe_set(mat, c4d.MATERIAL_USE_ALPHA, False)
    safe_set(mat, c4d.MATERIAL_USE_SPECULAR, False)
    safe_set(mat, c4d.MATERIAL_USE_DISPLACEMENT, False)

    # 发光颜色
    safe_set(mat, c4d.MATERIAL_LUMINANCE_COLOR, color)
    safe_set(mat, c4d.MATERIAL_LUMINANCE_BRIGHTNESS, LUMINANCE_BRIGHTNESS)

    doc.InsertMaterial(mat)
    mat.Update(True, True)

    return mat


def create_new_master_circle():
    """
    每次运行都新建独立的 Master Circle。
    不再搜索旧的 PROFILE_Circle_Master，避免影响之前生成好的 Sweep。
    """
    circle = c4d.BaseObject(c4d.Osplinecircle)
    circle.SetName(MASTER_CIRCLE_NAME)
    circle[c4d.PRIM_CIRCLE_RADIUS] = CIRCLE_RADIUS_CM
    circle.SetRelPos(c4d.Vector(0, 0, 0))
    circle.SetRelRot(c4d.Vector(0, 0, 0))
    return circle


def create_instance_to_circle(master_circle):
    inst = c4d.BaseObject(c4d.Oinstance)
    inst.SetName("Circle_Profile_Instance")
    inst[c4d.INSTANCEOBJECT_LINK] = master_circle
    return inst


def random_vector_cm(rx, ry, rz):
    return c4d.Vector(
        random.uniform(-rx, rx),
        random.uniform(-ry, ry),
        random.uniform(-rz, rz)
    )


def random_rotation_rad(rh, rp, rb):
    return c4d.Vector(
        math.radians(random.uniform(-rh, rh)),
        math.radians(random.uniform(-rp, rp)),
        math.radians(random.uniform(-rb, rb))
    )


def add_material_tag(obj, mat):
    tag = c4d.TextureTag()
    tag.SetMaterial(mat)
    obj.InsertTag(tag)


def hide_object(obj):
    obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
    obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF


# =========================
# Main
# =========================

def main():
    doc = c4d.documents.GetActiveDocument()
    selection = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

    if not selection:
        c4d.gui.MessageDialog("请先选中一个对象，或选中包含 spline 子级的父对象。")
        return

    splines = collect_target_splines(selection)

    if not splines:
        c4d.gui.MessageDialog("没有找到 spline 对象。")
        return

    doc.StartUndo()

    # 创建本次结果根组
    result_root = c4d.BaseObject(c4d.Onull)
    result_root.SetName(RESULT_ROOT_NAME)
    doc.InsertObject(result_root)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, result_root)

    # 每次运行都创建一个新的 Master Circle
    # 并放到 Generated_Sweep_From_SVG 的第一个子级位置
    master_circle = create_new_master_circle()
    master_circle.InsertUnder(result_root)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, master_circle)

    for src in splines:
        color = get_spline_color(src)

        mat_name = MATERIAL_PREFIX + src.GetName()
        mat = create_emission_material(doc, mat_name, color)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)

        sweep = c4d.BaseObject(c4d.Osweep)
        sweep.SetName("Sweep_" + src.GetName())

        profile_inst = create_instance_to_circle(master_circle)

        path = src.GetClone()
        path.SetName("Path_" + src.GetName())

        # 随机 PSR 加在路径 spline 上
        path.SetRelPos(
            path.GetRelPos() +
            random_vector_cm(RANDOM_POS_X, RANDOM_POS_Y, RANDOM_POS_Z)
        )

        path.SetRelRot(
            path.GetRelRot() +
            random_rotation_rad(RANDOM_ROT_H, RANDOM_ROT_P, RANDOM_ROT_B)
        )

        # Sweep 子级顺序：
        # 1. 截面 profile instance
        # 2. 路径 spline
        sweep.InsertUnderLast(result_root)
        profile_inst.InsertUnderLast(sweep)
        path.InsertUnderLast(sweep)

        add_material_tag(sweep, mat)

        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, sweep)

        if HIDE_ORIGINAL_SPLINES:
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, src)
            hide_object(src)

    doc.EndUndo()
    c4d.EventAdd()

    c4d.gui.MessageDialog(
        "完成：已为 {} 条 spline 创建独立 Sweep。\n本次生成了独立的 {}，不会影响之前的对象。".format(
            len(splines),
            MASTER_CIRCLE_NAME
        )
    )


if __name__ == "__main__":
    main()