import c4d
import math
import time
from collections import defaultdict

# ============================================================
# C4D Visibility Scanner - Debug Test Version
# C4D 2024.5.1 compatible
# ============================================================


# ============================================================
# CONFIG
# ============================================================

ONLY_SELECTED_ROOTS = False

CAMERA_COUNT = 100

# 测试阶段只渲染前 5 个相机
# 测通后改成 None，跑完整 100 个相机
MAX_RENDER_CAMERAS = 100

CAMERA_GROUP_NAME = "VIS_SCAN_TEMP_CAMERAS"
CAMERA_NAME_PREFIX = "VIS_SCAN_TEMP_CAM_"

TEMP_MATERIAL_PREFIX = "VIS_SCAN_ID_MAT_"
TEMP_TEXTURE_TAG_PREFIX = "VIS_SCAN_ID_TAG_"

RENDER_WIDTH = 512
RENDER_HEIGHT = 512
FRAME_MARGIN = 1.10
CAMERA_DISTANCE_MULTIPLIER = 5.0

# 如果像素统计仍慢，可以改成 2
PIXEL_STEP = 1

# 颜色容差。配合 lookup table 使用。
COLOR_TOLERANCE = 3

BACKGROUND_RGB = (0, 0, 0)

BORDERLINE_CAMERA_THRESHOLD = 2
BORDERLINE_PIXEL_THRESHOLD = 50

LAYER_VISIBLE = "VIS_VISIBLE_KEEP"
LAYER_BORDERLINE = "VIS_BORDERLINE_REVIEW"
LAYER_NEVER_SEEN = "VIS_NEVER_SEEN_CANDIDATE"

SHOW_REPORT_DIALOG = True
PRINT_FULL_REPORT_TO_CONSOLE = True

CLEANUP_TEMP_CAMERAS = True
CLEANUP_TEMP_MATERIALS = True
CLEANUP_TEMP_TEXTURE_TAGS = True

DEBUG_PRINT_TEXTURE_TAG_ORDER = False


# ============================================================
# Status bar compatibility
# ============================================================

def status_set_text(text):
    try:
        if hasattr(c4d, "gui") and hasattr(c4d.gui, "StatusSetText"):
            c4d.gui.StatusSetText(text)
            return
    except Exception:
        pass

    try:
        if hasattr(c4d, "StatusSetText"):
            c4d.StatusSetText(text)
            return
    except Exception:
        pass


def status_set_bar(value):
    try:
        if hasattr(c4d, "gui") and hasattr(c4d.gui, "StatusSetBar"):
            c4d.gui.StatusSetBar(value)
            return
    except Exception:
        pass

    try:
        if hasattr(c4d, "StatusSetBar"):
            c4d.StatusSetBar(value)
            return
    except Exception:
        pass


def status_clear():
    try:
        if hasattr(c4d, "gui") and hasattr(c4d.gui, "StatusClear"):
            c4d.gui.StatusClear()
            return
    except Exception:
        pass

    try:
        if hasattr(c4d, "StatusClear"):
            c4d.StatusClear()
            return
    except Exception:
        pass


# ============================================================
# Primitive whitelist
# ============================================================

PRIMITIVE_TYPE_NAMES = [
    "Ocube",
    "Osphere",
    "Ocylinder",
    "Oplane",
    "Ocone",
    "Otorus",
    "Odisc",
    "Opyramid",
    "Oplatonic",
    "Ofigure",
    "Otube",
    "Ocapsule",
    "Orelief",
    "Olandscape",
]

PRIMITIVE_TYPES = set()

for type_name in PRIMITIVE_TYPE_NAMES:
    type_id = getattr(c4d, type_name, None)
    if type_id is not None:
        PRIMITIVE_TYPES.add(type_id)


# ============================================================
# Common object utils
# ============================================================

def iter_objects(op):
    while op:
        yield op

        child = op.GetDown()
        if child:
            for sub in iter_objects(child):
                yield sub

        op = op.GetNext()


def is_target_object(op):
    if op is None:
        return False

    if op.CheckType(c4d.Opolygon):
        return True

    if op.GetType() in PRIMITIVE_TYPES:
        return True

    return False


def get_roots(doc):
    if ONLY_SELECTED_ROOTS:
        return doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)

    first = doc.GetFirstObject()
    return [first] if first else []


def collect_target_objects(doc):
    roots = get_roots(doc)
    result = []

    for root in roots:
        if root is None:
            continue

        for op in iter_objects(root):
            if is_target_object(op):
                result.append(op)

    return result


def find_top_level_object_by_name(doc, name):
    op = doc.GetFirstObject()

    while op:
        if op.GetName() == name:
            return op
        op = op.GetNext()

    return None


# ============================================================
# BBox / points
# ============================================================

def get_object_world_bbox_points(op):
    mg = op.GetMg()
    mp = op.GetMp()
    rad = op.GetRad()

    local_points = [
        c4d.Vector(mp.x - rad.x, mp.y - rad.y, mp.z - rad.z),
        c4d.Vector(mp.x + rad.x, mp.y - rad.y, mp.z - rad.z),
        c4d.Vector(mp.x - rad.x, mp.y + rad.y, mp.z - rad.z),
        c4d.Vector(mp.x + rad.x, mp.y + rad.y, mp.z - rad.z),
        c4d.Vector(mp.x - rad.x, mp.y - rad.y, mp.z + rad.z),
        c4d.Vector(mp.x + rad.x, mp.y - rad.y, mp.z + rad.z),
        c4d.Vector(mp.x - rad.x, mp.y + rad.y, mp.z + rad.z),
        c4d.Vector(mp.x + rad.x, mp.y + rad.y, mp.z + rad.z),
    ]

    return [mg * p for p in local_points]


def collect_world_bbox_points(objects):
    points = []

    for op in objects:
        points.extend(get_object_world_bbox_points(op))

    return points


def compute_bbox_from_points(points):
    if not points:
        return None, None, None, 0.0

    bbox_min = c4d.Vector(points[0])
    bbox_max = c4d.Vector(points[0])

    for p in points:
        bbox_min.x = min(bbox_min.x, p.x)
        bbox_min.y = min(bbox_min.y, p.y)
        bbox_min.z = min(bbox_min.z, p.z)

        bbox_max.x = max(bbox_max.x, p.x)
        bbox_max.y = max(bbox_max.y, p.y)
        bbox_max.z = max(bbox_max.z, p.z)

    center = (bbox_min + bbox_max) * 0.5
    radius = (bbox_max - center).GetLength()

    return bbox_min, bbox_max, center, radius


# ============================================================
# ID color generation
# ============================================================

def generate_id_colors(count):
    if count <= 0:
        return []

    level_count = int(math.ceil(count ** (1.0 / 3.0)))
    level_count = max(2, level_count)

    low = 32
    high = 224

    values = [
        int(round(low + (high - low) * i / float(level_count - 1)))
        for i in range(level_count)
    ]

    colors = []

    for r in values:
        for g in values:
            for b in values:
                if (r, g, b) == BACKGROUND_RGB:
                    continue
                colors.append((r, g, b))

    # 打散排序，避免相邻对象颜色过近
    colors.sort(key=lambda c: ((c[0] * 3 + c[1] * 5 + c[2] * 7) % 251, c[0], c[1], c[2]))

    return colors[:count]


def rgb8_to_vector(rgb):
    return c4d.Vector(
        rgb[0] / 255.0,
        rgb[1] / 255.0,
        rgb[2] / 255.0
    )


# ============================================================
# Temporary materials / tags
# ============================================================

def create_id_material(doc, rgb, index):
    color = rgb8_to_vector(rgb)

    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(f"{TEMP_MATERIAL_PREFIX}{index:04d}_{rgb[0]}_{rgb[1]}_{rgb[2]}")

    mat[c4d.MATERIAL_USE_COLOR] = False
    mat[c4d.MATERIAL_USE_DIFFUSION] = False
    mat[c4d.MATERIAL_USE_LUMINANCE] = False
    mat[c4d.MATERIAL_USE_TRANSPARENCY] = False
    mat[c4d.MATERIAL_USE_REFLECTION] = False
    mat[c4d.MATERIAL_USE_ENVIRONMENT] = False
    mat[c4d.MATERIAL_USE_FOG] = False
    mat[c4d.MATERIAL_USE_BUMP] = False
    mat[c4d.MATERIAL_USE_NORMAL] = False
    mat[c4d.MATERIAL_USE_ALPHA] = False
    mat[c4d.MATERIAL_USE_DISPLACEMENT] = False

    mat[c4d.MATERIAL_USE_LUMINANCE] = True
    mat[c4d.MATERIAL_LUMINANCE_COLOR] = color
    mat[c4d.MATERIAL_COLOR_COLOR] = color

    doc.InsertMaterial(mat)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)
    mat.Message(c4d.MSG_UPDATE)

    return mat


def assign_temp_id_material(op, mat, index):
    """
    临时 ID 材质 Tag 插到对象 Tag 列表最后，
    避免被原本材质 Tag 覆盖。
    """
    tag = c4d.TextureTag()
    tag.SetName(f"{TEMP_TEXTURE_TAG_PREFIX}{index:04d}")
    tag[c4d.TEXTURETAG_MATERIAL] = mat

    last_tag = op.GetFirstTag()

    if last_tag is None:
        op.InsertTag(tag)
    else:
        while last_tag.GetNext():
            last_tag = last_tag.GetNext()

        tag.InsertAfter(last_tag)

    return tag


def debug_print_texture_tag_order(op):
    names = []
    tag = op.GetFirstTag()

    while tag:
        if tag.CheckType(c4d.Ttexture):
            mat = tag[c4d.TEXTURETAG_MATERIAL]
            mat_name = mat.GetName() if mat else "None"
            names.append(f"{tag.GetName()} -> {mat_name}")

        tag = tag.GetNext()

    print(op.GetName(), "Texture Tags:", names)


def cleanup_temp_texture_tags(doc):
    removed = 0
    root = doc.GetFirstObject()

    while root:
        for op in iter_objects(root):
            tag = op.GetFirstTag()
            while tag:
                next_tag = tag.GetNext()

                if tag.CheckType(c4d.Ttexture) and tag.GetName().startswith(TEMP_TEXTURE_TAG_PREFIX):
                    try:
                        doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, tag)
                    except Exception:
                        pass
                    tag.Remove()
                    removed += 1

                tag = next_tag

        root = root.GetNext()

    return removed


def cleanup_temp_materials(doc):
    removed = 0
    mat = doc.GetFirstMaterial()

    while mat:
        next_mat = mat.GetNext()

        if mat.GetName().startswith(TEMP_MATERIAL_PREFIX):
            doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, mat)
            mat.Remove()
            removed += 1

        mat = next_mat

    return removed


def cleanup_old_temp_cameras(doc):
    group = find_top_level_object_by_name(doc, CAMERA_GROUP_NAME)
    if group is None:
        return 0

    doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, group)
    group.Remove()
    return 1


def setup_temp_id_materials(doc, objects):
    colors = generate_id_colors(len(objects))

    object_to_color = {}
    color_to_object = {}
    temp_materials = []

    for index, op in enumerate(objects):
        rgb = colors[index]
        mat = create_id_material(doc, rgb, index + 1)
        tag = assign_temp_id_material(op, mat, index + 1)

        try:
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
        except Exception:
            pass

        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)

        object_to_color[op] = rgb
        color_to_object[rgb] = op
        temp_materials.append(mat)

        if DEBUG_PRINT_TEXTURE_TAG_ORDER:
            debug_print_texture_tag_order(op)

    return object_to_color, color_to_object, temp_materials


# ============================================================
# Camera generation
# ============================================================

def fibonacci_sphere_points(count):
    points = []

    if count <= 1:
        return [c4d.Vector(0, 1, 0)]

    golden_angle = math.pi * (3.0 - math.sqrt(5.0))

    for i in range(count):
        y = 1.0 - (i / float(count - 1)) * 2.0
        r = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden_angle * i

        x = math.cos(theta) * r
        z = math.sin(theta) * r

        points.append(c4d.Vector(x, y, z))

    return points


def look_at(obj, target):
    pos = obj.GetAbsPos()
    direction = target - pos

    if direction.GetLength() <= 0.000001:
        return

    hpb = c4d.utils.VectorToHPB(direction)
    obj.SetAbsRot(hpb)


def sync_camera_film_aspect(cam, width, height):
    film_aspect = float(width) / float(height)

    cam_film_aspect_id = getattr(c4d, "CAMERAOBJECT_FILMASPECT", None)
    if cam_film_aspect_id is not None:
        try:
            cam[cam_film_aspect_id] = film_aspect
        except Exception:
            pass

    cam.Message(c4d.MSG_UPDATE)


def compute_camera_local_bounds(cam, world_points):
    inv_mg = ~cam.GetMg()
    local_points = [inv_mg * p for p in world_points]

    min_x = min(p.x for p in local_points)
    max_x = max(p.x for p in local_points)
    min_y = min(p.y for p in local_points)
    max_y = max(p.y for p in local_points)

    width = max_x - min_x
    height = max_y - min_y

    return width, height, min_x, max_x, min_y, max_y


def compute_parallel_zoom(projected_width, projected_height, render_w, render_h, margin):
    needed_width = max(projected_width * margin, 0.000001)
    needed_height = max(projected_height * margin, 0.000001)

    zoom_x = float(render_w) / needed_width
    zoom_y = float(render_h) / needed_height
    zoom = min(zoom_x, zoom_y)

    return zoom


def setup_parallel_camera_auto_fit(cam, world_points, render_w, render_h, margin):
    cam.SetProjection(c4d.Pparallel)
    sync_camera_film_aspect(cam, render_w, render_h)

    cam.SetZoom(1.0)
    cam.Message(c4d.MSG_UPDATE)

    projected_width, projected_height, min_x, max_x, min_y, max_y = compute_camera_local_bounds(cam, world_points)

    offset_x = (min_x + max_x) * 0.5
    offset_y = (min_y + max_y) * 0.5

    mg = cam.GetMg()
    new_pos = cam.GetAbsPos() + mg.v1 * offset_x + mg.v2 * offset_y
    cam.SetAbsPos(new_pos)
    cam.Message(c4d.MSG_UPDATE)

    projected_width, projected_height, min_x, max_x, min_y, max_y = compute_camera_local_bounds(cam, world_points)

    zoom = compute_parallel_zoom(
        projected_width,
        projected_height,
        render_w,
        render_h,
        margin
    )

    cam.SetZoom(zoom)
    cam.Message(c4d.MSG_UPDATE)

    return zoom


def create_camera_group(doc):
    group = c4d.BaseObject(c4d.Onull)
    group.SetName(CAMERA_GROUP_NAME)
    doc.InsertObject(group)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, group)
    return group


def create_scan_cameras(doc, center, radius, world_points):
    cleanup_old_temp_cameras(doc)

    group = create_camera_group(doc)
    directions = fibonacci_sphere_points(CAMERA_COUNT)

    camera_distance = max(radius * CAMERA_DISTANCE_MULTIPLIER, 1000.0)

    cameras = []
    zoom_values = []

    for i, direction in enumerate(directions):
        cam = c4d.BaseObject(c4d.Ocamera)
        cam.SetName(f"{CAMERA_NAME_PREFIX}{i + 1:03d}")

        cam_pos = center + direction * camera_distance
        cam.SetAbsPos(cam_pos)
        look_at(cam, center)

        cam.InsertUnder(group)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, cam)

        zoom = setup_parallel_camera_auto_fit(
            cam,
            world_points,
            RENDER_WIDTH,
            RENDER_HEIGHT,
            FRAME_MARGIN
        )

        cameras.append(cam)
        zoom_values.append(zoom)

    return group, cameras, zoom_values


# ============================================================
# Render settings
# ============================================================

def set_standard_renderer(rd):
    try:
        rd[c4d.RDATA_RENDERENGINE] = c4d.RDATA_RENDERENGINE_STANDARD
        print("[OK] Renderer set to Standard")
        return True
    except Exception as e:
        print("[WARN] Failed to set Standard Renderer:", e)
        return False


def set_anti_aliasing_none(rd):
    aa_id = getattr(c4d, "RDATA_ANTIALIASING", None)

    if aa_id is None:
        print("[WARN] RDATA_ANTIALIASING not found")
        return False

    candidate_names = [
        "ANTIALIASING_NONE",
        "RDATA_ANTIALIASING_NONE",
    ]

    for name in candidate_names:
        value = getattr(c4d, name, None)
        if value is None:
            continue

        try:
            rd[aa_id] = value
            print("[OK] Anti-Aliasing set to None")
            return True
        except Exception:
            pass

    try:
        rd[aa_id] = 0
        print("[OK] Anti-Aliasing set to 0 fallback")
        return True
    except Exception as e:
        print("[WARN] Failed to set AA None:", e)
        return False


def disable_output_related_render_settings(rd):
    """
    避免工程原本的 Save / Multi-Pass / Dithering 等设置影响 ID 渲染。
    """
    candidates = [
        ("RDATA_SAVEIMAGE", False, "Save Image"),
        ("RDATA_MULTIPASS_ENABLE", False, "Multi-Pass"),
        ("RDATA_ALPHACHANNEL", False, "Alpha Channel"),
        ("RDATA_8BIT_DITHERING", False, "8 Bit Dithering"),
    ]

    for attr_name, value, label in candidates:
        attr_id = getattr(c4d, attr_name, None)
        if attr_id is None:
            print("[INFO] Render setting not found:", attr_name)
            continue

        try:
            rd[attr_id] = value
            print("[OK]", label, "disabled")
        except Exception as e:
            print("[WARN] Failed to set", label, ":", e)


def set_render_resolution_and_aspect(doc, width, height):
    rd = doc.GetActiveRenderData()

    if rd is None:
        return None

    doc.AddUndo(c4d.UNDOTYPE_CHANGE, rd)

    set_standard_renderer(rd)

    rd[c4d.RDATA_XRES] = width
    rd[c4d.RDATA_YRES] = height

    pixel_aspect_id = getattr(c4d, "RDATA_PIXELASPECT", None)
    if pixel_aspect_id is not None:
        rd[pixel_aspect_id] = 1.0

    film_aspect_id = getattr(c4d, "RDATA_FILMASPECT", None)
    if film_aspect_id is not None:
        rd[film_aspect_id] = float(width) / float(height)

    set_anti_aliasing_none(rd)
    disable_output_related_render_settings(rd)

    rd.Message(c4d.MSG_UPDATE)
    c4d.EventAdd()

    return rd


def set_render_camera(doc, rd, cam):
    rdata_camera_id = getattr(c4d, "RDATA_CAMERA", None)

    if rdata_camera_id is not None:
        try:
            rd[rdata_camera_id] = cam
        except Exception:
            pass

    bd = doc.GetActiveBaseDraw()
    if bd is not None:
        try:
            bd.SetSceneCamera(cam)
        except Exception:
            pass

    rd.Message(c4d.MSG_UPDATE)
    c4d.EventAdd()


# ============================================================
# In-memory rendering
# ============================================================

def init_bitmap(width, height):
    bmp = c4d.bitmaps.BaseBitmap()
    result = bmp.Init(width, height, 24)

    if result != c4d.IMAGERESULT_OK:
        return None

    return bmp


def get_render_bc(rd):
    """
    在 C4D 2024.5.1 中，RenderDocument 使用 rd.GetData() 仍然可正常工作。
    GetData() 会触发 deprecation warning，但不会影响当前功能。
    这里通过 warnings.filterwarnings 隐藏该提示。
    """
    return rd.GetData()

def render_camera_to_bitmap(doc, rd, cam, width, height):
    set_render_camera(doc, rd, cam)

    bmp = init_bitmap(width, height)
    if bmp is None:
        return None, False

    render_bc = get_render_bc(rd)
    flags = c4d.RENDERFLAGS_EXTERNAL

    result = c4d.documents.RenderDocument(
        doc,
        render_bc,
        bmp,
        flags
    )

    if result != c4d.RENDERRESULT_OK:
        return bmp, False

    return bmp, True


# ============================================================
# Bitmap color statistics - optimized with lookup table
# ============================================================

def build_color_lookup(known_colors, tolerance):
    """
    为每个 ID 色生成容差范围内的 RGB 查找表。
    例如 tolerance=3，则每个颜色生成 7*7*7 = 343 个邻近颜色。
    统计像素时可以 O(1) 查表，而不是每个像素遍历所有 known colors。
    """
    lookup = {}
    collision_count = 0

    for color in known_colors:
        r0, g0, b0 = color

        for dr in range(-tolerance, tolerance + 1):
            r = r0 + dr
            if r < 0 or r > 255:
                continue

            for dg in range(-tolerance, tolerance + 1):
                g = g0 + dg
                if g < 0 or g > 255:
                    continue

                for db in range(-tolerance, tolerance + 1):
                    b = b0 + db
                    if b < 0 or b > 255:
                        continue

                    rgb = (r, g, b)

                    if rgb not in lookup:
                        lookup[rgb] = color
                    else:
                        if lookup[rgb] != color:
                            collision_count += 1

    print("Color lookup size:", len(lookup))
    print("Color lookup collisions:", collision_count)

    return lookup


def get_pixel_rgb(bmp, x, y):
    rgb = bmp.GetPixel(x, y)

    try:
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:
        return None


def count_bitmap_colors(bmp, color_lookup):
    width, height = bmp.GetSize()

    color_counts = defaultdict(int)
    unknown_non_bg_count = 0

    for y in range(0, height, PIXEL_STEP):
        for x in range(0, width, PIXEL_STEP):
            rgb = get_pixel_rgb(bmp, x, y)
            if rgb is None:
                continue

            if rgb == BACKGROUND_RGB:
                continue

            mapped_color = color_lookup.get(rgb)

            if mapped_color is not None:
                color_counts[mapped_color] += 1
            else:
                unknown_non_bg_count += 1

    return color_counts, unknown_non_bg_count


def run_visibility_render_scan(doc, rd, cameras, color_to_object):
    known_colors = list(color_to_object.keys())

    color_lookup = build_color_lookup(known_colors, COLOR_TOLERANCE)

    total_color_pixel_counts = defaultdict(int)
    camera_seen_counts = defaultdict(int)
    total_unknown_non_bg = 0
    render_success = 0
    render_failed = 0

    cameras_to_render = cameras
    if MAX_RENDER_CAMERAS is not None:
        cameras_to_render = cameras[:MAX_RENDER_CAMERAS]

    print("Render camera limit:", len(cameras_to_render), "/", len(cameras))

    total_render_time = 0.0
    total_count_time = 0.0

    for index, cam in enumerate(cameras_to_render):
        status_set_text(f"Visibility Scan Rendering {index + 1}/{len(cameras_to_render)}")
        status_set_bar(int((index + 1) * 100 / len(cameras_to_render)))

        print("Rendering camera:", index + 1, "/", len(cameras_to_render), cam.GetName())

        t0 = time.time()
        bmp, ok = render_camera_to_bitmap(doc, rd, cam, RENDER_WIDTH, RENDER_HEIGHT)
        t1 = time.time()

        render_time = t1 - t0
        total_render_time += render_time

        if not ok or bmp is None:
            render_failed += 1
            print("  Render failed. Render time:", round(render_time, 3), "s")
            continue

        render_success += 1

        color_counts, unknown_non_bg = count_bitmap_colors(bmp, color_lookup)
        t2 = time.time()

        count_time = t2 - t1
        total_count_time += count_time

        total_unknown_non_bg += unknown_non_bg

        for color_rgb, count in color_counts.items():
            if count <= 0:
                continue

            total_color_pixel_counts[color_rgb] += count
            camera_seen_counts[color_rgb] += 1

        print(
            "  Time:",
            "render =", round(render_time, 3), "s,",
            "count =", round(count_time, 3), "s,",
            "visible colors =", len(color_counts),
            "unknown =", unknown_non_bg
        )

    status_clear()

    print("Total render time:", round(total_render_time, 3), "s")
    print("Total count time:", round(total_count_time, 3), "s")

    return {
        "total_color_pixel_counts": total_color_pixel_counts,
        "camera_seen_counts": camera_seen_counts,
        "total_unknown_non_bg": total_unknown_non_bg,
        "render_success": render_success,
        "render_failed": render_failed,
        "total_render_time": total_render_time,
        "total_count_time": total_count_time,
        "rendered_camera_count": len(cameras_to_render),
    }


# ============================================================
# Layer assignment
# ============================================================

def get_or_create_layer(doc, name, color=None):
    root = doc.GetLayerObjectRoot()
    if root is None:
        print("Layer root not found.")
        return None

    layer = root.GetDown()

    while layer:
        if layer.GetName() == name:
            return layer
        layer = layer.GetNext()

    try:
        layer = c4d.documents.LayerObject()
    except Exception as e:
        print("Failed to create LayerObject:", e)
        return None

    layer.SetName(name)

    if color is not None:
        try:
            data = layer.GetLayerData(doc)
            data["color"] = color
            layer.SetLayerData(doc, data)
        except Exception:
            pass

    layer.InsertUnder(root)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, layer)

    return layer


def assign_object_to_layer(doc, op, layer):
    if op is None or layer is None:
        return False

    layer_link_id = getattr(c4d, "ID_LAYER_LINK", None)
    if layer_link_id is None:
        print("ID_LAYER_LINK not found.")
        return False

    try:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
        op[layer_link_id] = layer
        return True
    except Exception as e:
        print("Failed to assign layer:", op.GetName(), e)
        return False


def classify_objects(objects, object_to_color, stats):
    total_color_pixel_counts = stats["total_color_pixel_counts"]
    camera_seen_counts = stats["camera_seen_counts"]

    visible = []
    borderline = []
    never_seen = []

    object_stats = {}

    for op in objects:
        color_rgb = object_to_color.get(op)

        if color_rgb is None:
            never_seen.append(op)
            object_stats[op] = {
                "color": None,
                "cameras_seen": 0,
                "pixel_count": 0,
                "category": "NO_COLOR"
            }
            continue

        pixel_count = int(total_color_pixel_counts.get(color_rgb, 0))
        cameras_seen = int(camera_seen_counts.get(color_rgb, 0))

        if cameras_seen == 0 or pixel_count == 0:
            category = "NEVER_SEEN"
            never_seen.append(op)
        elif cameras_seen <= BORDERLINE_CAMERA_THRESHOLD or pixel_count <= BORDERLINE_PIXEL_THRESHOLD:
            category = "BORDERLINE"
            borderline.append(op)
        else:
            category = "VISIBLE"
            visible.append(op)

        object_stats[op] = {
            "color": color_rgb,
            "cameras_seen": cameras_seen,
            "pixel_count": pixel_count,
            "category": category
        }

    return visible, borderline, never_seen, object_stats


def assign_layers(doc, visible, borderline, never_seen):
    layer_visible = get_or_create_layer(doc, LAYER_VISIBLE, c4d.Vector(0.25, 0.75, 0.25))
    layer_borderline = get_or_create_layer(doc, LAYER_BORDERLINE, c4d.Vector(1.0, 0.7, 0.1))
    layer_never = get_or_create_layer(doc, LAYER_NEVER_SEEN, c4d.Vector(1.0, 0.2, 0.2))

    visible_count = 0
    borderline_count = 0
    never_count = 0

    for op in visible:
        if assign_object_to_layer(doc, op, layer_visible):
            visible_count += 1

    for op in borderline:
        if assign_object_to_layer(doc, op, layer_borderline):
            borderline_count += 1

    for op in never_seen:
        if assign_object_to_layer(doc, op, layer_never):
            never_count += 1

    return visible_count, borderline_count, never_count


# ============================================================
# Report
# ============================================================

def build_report(objects, visible, borderline, never_seen, object_stats, stats, cleanup_report):
    lines = []

    lines.append("Visibility Scan Finished")
    lines.append("=" * 52)
    lines.append("")
    lines.append(f"Target objects: {len(objects)}")
    lines.append(f"Camera count created: {CAMERA_COUNT}")
    lines.append(f"Camera count rendered: {stats.get('rendered_camera_count')}")
    lines.append(f"Render size: {RENDER_WIDTH} x {RENDER_HEIGHT}")
    lines.append(f"Pixel step: {PIXEL_STEP}")
    lines.append(f"Color tolerance: {COLOR_TOLERANCE}")
    lines.append("")
    lines.append(f"Rendered cameras success: {stats['render_success']}")
    lines.append(f"Rendered cameras failed: {stats['render_failed']}")
    lines.append(f"Unknown non-bg pixels: {stats['total_unknown_non_bg']}")
    lines.append("")
    lines.append(f"Total render time: {round(stats.get('total_render_time', 0.0), 3)} s")
    lines.append(f"Total count time: {round(stats.get('total_count_time', 0.0), 3)} s")
    lines.append("")
    lines.append(f"Visible objects: {len(visible)}")
    lines.append(f"Borderline objects: {len(borderline)}")
    lines.append(f"Never seen candidates: {len(never_seen)}")
    lines.append("")
    lines.append("Cleanup:")
    for item in cleanup_report:
        lines.append("  " + item)

    lines.append("")
    lines.append("Never Seen Candidates:")
    if never_seen:
        for op in never_seen:
            st = object_stats.get(op, {})
            lines.append(
                f"  [NOT SEEN] {op.GetName()} | "
                f"CamerasSeen={st.get('cameras_seen')} | "
                f"Pixels={st.get('pixel_count')}"
            )
    else:
        lines.append("  None")

    lines.append("")
    lines.append("Borderline Review:")
    if borderline:
        for op in borderline:
            st = object_stats.get(op, {})
            lines.append(
                f"  [BORDERLINE] {op.GetName()} | "
                f"CamerasSeen={st.get('cameras_seen')} | "
                f"Pixels={st.get('pixel_count')}"
            )
    else:
        lines.append("  None")

    return "\n".join(lines)


def show_report_dialog(report_text):
    max_chars = 1800

    if len(report_text) > max_chars:
        dialog_text = report_text[:max_chars]
        dialog_text += "\n\n... Report truncated in dialog. Full report is printed in Console."
    else:
        dialog_text = report_text

    c4d.gui.MessageDialog(dialog_text)


# ============================================================
# Main
# ============================================================

def main():
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return

    c4d.StopAllThreads()
    doc.StartUndo()

    cleanup_report = []

    try:
        print("")
        print("=" * 60)
        print("Visibility Scan Tool Started")
        print("=" * 60)

        old_cam_groups = cleanup_old_temp_cameras(doc)
        old_tags = cleanup_temp_texture_tags(doc)
        old_mats = cleanup_temp_materials(doc)

        if old_cam_groups:
            cleanup_report.append(f"Old temp camera groups removed before scan: {old_cam_groups}")
        if old_tags:
            cleanup_report.append(f"Old temp texture tags removed before scan: {old_tags}")
        if old_mats:
            cleanup_report.append(f"Old temp materials removed before scan: {old_mats}")

        objects = collect_target_objects(doc)

        if not objects:
            c4d.gui.MessageDialog("No target objects found.\nOnly Polygon Objects and C4D basic Primitives are supported.")
            return

        world_points = collect_world_bbox_points(objects)
        bbox_min, bbox_max, center, radius = compute_bbox_from_points(world_points)

        if center is None:
            c4d.gui.MessageDialog("Failed to compute scene bounding box.")
            return

        print("Target objects:", len(objects))
        print("Scene center:", center)
        print("Scene radius:", radius)

        object_to_color, color_to_object, temp_materials = setup_temp_id_materials(doc, objects)
        print("Temporary ID materials created:", len(temp_materials))

        rd = set_render_resolution_and_aspect(doc, RENDER_WIDTH, RENDER_HEIGHT)
        if rd is None:
            c4d.gui.MessageDialog("No active RenderData found.")
            return

        cam_group, cameras, zoom_values = create_scan_cameras(doc, center, radius, world_points)
        print("Temporary cameras created:", len(cameras))

        if zoom_values:
            print("Zoom min:", min(zoom_values))
            print("Zoom max:", max(zoom_values))
            print("Zoom avg:", sum(zoom_values) / len(zoom_values))

        stats = run_visibility_render_scan(doc, rd, cameras, color_to_object)

        visible, borderline, never_seen, object_stats = classify_objects(
            objects,
            object_to_color,
            stats
        )

        assigned_visible, assigned_borderline, assigned_never = assign_layers(
            doc,
            visible,
            borderline,
            never_seen
        )

        print("Layer assigned visible:", assigned_visible)
        print("Layer assigned borderline:", assigned_borderline)
        print("Layer assigned never seen:", assigned_never)

        if CLEANUP_TEMP_TEXTURE_TAGS:
            removed_tags = cleanup_temp_texture_tags(doc)
            cleanup_report.append(f"Temp texture tags removed after scan: {removed_tags}")

        if CLEANUP_TEMP_MATERIALS:
            removed_mats = cleanup_temp_materials(doc)
            cleanup_report.append(f"Temp materials removed after scan: {removed_mats}")

        if CLEANUP_TEMP_CAMERAS:
            removed_cam_groups = cleanup_old_temp_cameras(doc)
            cleanup_report.append(f"Temp camera groups removed after scan: {removed_cam_groups}")

        report_text = build_report(
            objects,
            visible,
            borderline,
            never_seen,
            object_stats,
            stats,
            cleanup_report
        )

        if PRINT_FULL_REPORT_TO_CONSOLE:
            print("")
            print(report_text)
            print("")

        if SHOW_REPORT_DIALOG:
            show_report_dialog(report_text)

        print("=" * 60)
        print("Visibility Scan Tool Finished")
        print("=" * 60)

    except Exception as e:
        c4d.gui.MessageDialog("Visibility Scan failed:\n" + str(e))
        print("[ERROR] Visibility Scan failed:", e)
        raise

    finally:
        status_clear()
        doc.EndUndo()
        c4d.EventAdd()


if __name__ == "__main__":
    main()