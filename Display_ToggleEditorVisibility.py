import c4d
from c4d import gui
# Welcome to the world of Python


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

# Main function

obj = doc.GetActiveObject() #获取激活的对象
dis =  obj.GetEditorMode() #获取对象显示的状态 2是default,1是off

if dis == 2:
    obj.SetEditorMode(1) #注意缩进
if dis == 1:
    obj.SetEditorMode(2)

c4d.EventAdd() #发送全局事件消息
