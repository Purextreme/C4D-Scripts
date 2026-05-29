import c4d
import os

def get_top_level_objects(doc):
    objs = []
    obj = doc.GetFirstObject()
    while obj:
        objs.append(obj)
        obj = obj.GetNext()
    return objs

def main():
    doc = c4d.documents.GetActiveDocument()

    folder = c4d.storage.LoadDialog(
        title="选择包含 SVG 的文件夹",
        flags=c4d.FILESELECT_DIRECTORY
    )

    if not folder:
        return

    svg_files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".svg")
    ])

    if not svg_files:
        c4d.gui.MessageDialog("该文件夹里没有 SVG 文件。")
        return

    doc.StartUndo()

    group = c4d.BaseObject(c4d.Onull)
    group.SetName("Imported_SVG_Assets")
    doc.InsertObject(group)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, group)

    imported_count = 0

    for svg_path in svg_files:
        before = set(get_top_level_objects(doc))

        ok = c4d.documents.MergeDocument(
            doc,
            svg_path,
            c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS
        )

        if not ok:
            print("导入失败:", svg_path)
            continue

        after = get_top_level_objects(doc)
        new_objs = [obj for obj in after if obj not in before and obj != group]

        file_base = os.path.splitext(os.path.basename(svg_path))[0]

        # 如果一个 SVG 导入出多个对象，则包一层 Null
        if len(new_objs) > 1:
            asset_null = c4d.BaseObject(c4d.Onull)
            asset_null.SetName(file_base)
            asset_null.InsertUnderLast(group)
            doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, asset_null)

            for obj in new_objs:
                mg = obj.GetMg()
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
                obj.Remove()
                obj.InsertUnderLast(asset_null)
                obj.SetMg(mg)

        elif len(new_objs) == 1:
            obj = new_objs[0]
            mg = obj.GetMg()
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            obj.SetName(file_base)
            obj.Remove()
            obj.InsertUnderLast(group)
            obj.SetMg(mg)

        imported_count += 1
        print("已导入:", svg_path)

    doc.EndUndo()
    c4d.EventAdd()

    c4d.gui.MessageDialog(f"完成：导入 {imported_count} 个 SVG。")

if __name__ == "__main__":
    main()