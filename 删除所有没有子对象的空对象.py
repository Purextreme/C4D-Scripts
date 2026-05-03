import c4d
from c4d import gui
# Welcome to the world of Python


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

# Main function
def main():
    gui.MessageDialog('Hello World!')

# Execute main()
def removeempty(obj):
    if not obj:
        return
    removeempty(obj.GetDown())
    removeempty(obj.GetNext())
    if not obj.GetDown():
        if obj.GetType()== c4d.Onull:
            if not obj.GetFirstTag():
                obj.Remove()
def main():
    obj = doc.GetFirstObject()
    removeempty(obj)
    c4d.EventAdd()
if __name__=='__main__':
    main()