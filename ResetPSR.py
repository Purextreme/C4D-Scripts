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
obj.SetRelPos(c4d.Vector(0,0,0))  #设置绝对位置
obj.SetAbsScale(c4d.Vector(1,1,1))
obj.SetAbsRot(c4d.Vector(0,0,0))
c4d.EventAdd() #发送全局事件消息
#最后一句似乎是必要的，更多的语法参考 https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d/C4DAtom/GeListNode/BaseList2D/BaseObject/index.html#BaseObject.SetAbsPos