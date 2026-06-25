import c4d

# ============================================================
# 逐帧关键帧动画平滑工具
# ============================================================
#
# 功能说明：
# 本脚本用于复制当前选中的对象，并在复制体上对其关键帧动画进行平滑过滤。
# 原始对象不会被修改，平滑后的对象会自动命名为 “原对象名_SMOOTH”。
#
# 主要用途：
# 适合处理逐帧烘焙动画、相机反求动画、跟踪数据、动作捕捉数据等
# “每一帧都有关键帧”的动画曲线。
#
# 例如：
# - Syntheyes / PFTrack / Blender / DA3 等工具反求得到的相机动画
# - C4D 中 Bake Objects 之后产生的逐帧 PSR 动画
# - 导入 FBX / Alembic 后带有轻微抖动的逐帧 Transform 动画
#
# 平滑逻辑：
# 脚本会对 Position / Rotation / Scale 的 F-Curve 数值进行移动平均过滤，
# 从而削弱相邻帧之间的高频抖动，同时尽量保留整体运动趋势。
#
# 使用建议：
# - 默认参数适合轻度防抖；
# - 如果仍然抖动，可以适当增加 SMOOTH_RADIUS 或 SMOOTH_ITERATIONS；
# - 参数过大可能导致相机漂移、运动滞后或匹配不准；
# - 对反求相机使用时，建议先复制测试，并与原始相机对比画面匹配度。
#
# 注意：
# 本脚本不是重新解算相机，也不是物理稳定器；
# 它只是对已有关键帧曲线做数值平滑过滤。
#
# ============================================================

# =========================
# 参数区
# =========================

# 平滑半径：
# 1 = 当前帧参考前后各 1 个 key，比较安全
# 2 = 前后各 2 个 key，更平滑但更容易漂
SMOOTH_RADIUS = 1

# 平滑迭代次数：
# 1 = 轻微平滑
# 2 = 推荐
# 3+ = 更强，但可能改变相机运动
SMOOTH_ITERATIONS = 2

# 是否保留首尾关键帧不变
PRESERVE_END_KEYS = True

# 是否只处理 PSR 动画
# True：只平滑 Position / Rotation / Scale，推荐用于相机
# False：会平滑所有动画轨道，包括焦距、参数等，不推荐默认使用
ONLY_TRANSFORM_TRACKS = True


# =========================
# 工具函数
# =========================

TRANSFORM_IDS = {
    c4d.ID_BASEOBJECT_REL_POSITION,
    c4d.ID_BASEOBJECT_REL_ROTATION,
    c4d.ID_BASEOBJECT_REL_SCALE,
}


def is_transform_track(track):
    """
    判断当前 CTrack 是否属于对象的 Position / Rotation / Scale。
    """
    try:
        desc_id = track.GetDescriptionID()
        if desc_id is None or len(desc_id) == 0:
            return False

        main_id = desc_id[0].id
        return main_id in TRANSFORM_IDS

    except Exception:
        return False


def smooth_values(values, radius=1, preserve_ends=True):
    """
    对一组 key value 做加权移动平均。
    radius=1 时，相当于：
    新值 = 前一个 * 0.25 + 当前 * 0.5 + 后一个 * 0.25
    """
    count = len(values)

    if count <= 2:
        return values[:]

    result = values[:]

    start = 1 if preserve_ends else 0
    end = count - 1 if preserve_ends else count

    for i in range(start, end):
        weighted_sum = 0.0
        weight_total = 0.0

        for offset in range(-radius, radius + 1):
            j = i + offset

            if j < 0 or j >= count:
                continue

            # 中间权重大，两侧权重小
            weight = radius + 1 - abs(offset)

            weighted_sum += values[j] * weight
            weight_total += weight

        if weight_total > 0:
            result[i] = weighted_sum / weight_total

    return result


def smooth_curve(curve):
    """
    平滑单条 F-Curve。
    """
    if curve is None:
        return 0

    key_count = curve.GetKeyCount()

    if key_count <= 2:
        return 0

    keys = [curve.GetKey(i) for i in range(key_count)]
    values = [key.GetValue() for key in keys]

    for _ in range(SMOOTH_ITERATIONS):
        values = smooth_values(
            values,
            radius=SMOOTH_RADIUS,
            preserve_ends=PRESERVE_END_KEYS
        )

    for i, key in enumerate(keys):
        key.SetValue(curve, values[i])

        # 尽量改成 spline 插值，让曲线更连续
        try:
            key.SetInterpolation(curve, c4d.CINTERPOLATION_SPLINE)
        except Exception:
            pass

    return key_count


def smooth_tracks_on_object(obj):
    """
    平滑对象上的动画轨道。
    """
    if obj is None:
        return 0

    total_keys = 0

    tracks = obj.GetCTracks()

    for track in tracks:
        if ONLY_TRANSFORM_TRACKS and not is_transform_track(track):
            continue

        curve = track.GetCurve()
        total_keys += smooth_curve(curve)

    return total_keys


def smooth_hierarchy(obj):
    """
    递归处理对象及其子级。
    """
    total = 0

    current = obj
    while current:
        total += smooth_tracks_on_object(current)

        child = current.GetDown()
        if child:
            total += smooth_hierarchy(child)

        current = current.GetNext()

    return total


def duplicate_and_smooth(op, doc):
    """
    复制对象，然后在复制体上做平滑。
    """
    clone = op.GetClone(c4d.COPYFLAGS_0)

    if clone is None:
        return None, 0

    clone.SetName(op.GetName() + "_SMOOTH")

    parent = op.GetUp()
    pred = op

    doc.InsertObject(clone, parent, pred)

    key_count = smooth_hierarchy(clone)

    return clone, key_count


# =========================
# 主函数
# =========================

def main():
    doc = c4d.documents.GetActiveDocument()
    selected = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)

    if not selected:
        c4d.gui.MessageDialog("请先选中需要复制并平滑关键帧的对象。")
        return

    doc.StartUndo()

    new_objects = []
    total_keys = 0

    for op in selected:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)

        clone, key_count = duplicate_and_smooth(op, doc)

        if clone:
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, clone)
            new_objects.append(clone)
            total_keys += key_count

    # 选中新生成的对象
    for op in selected:
        op.DelBit(c4d.BIT_ACTIVE)

    for clone in new_objects:
        clone.SetBit(c4d.BIT_ACTIVE)

    doc.EndUndo()
    c4d.EventAdd()

    c4d.gui.MessageDialog(
        "完成。\n\n"
        "已复制对象数量：{}\n"
        "已处理关键帧数量：{}\n\n"
        "原始对象未被修改。".format(len(new_objects), total_keys)
    )


if __name__ == "__main__":
    main()