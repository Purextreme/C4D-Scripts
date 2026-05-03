import c4d
from c4d import gui
# Welcome to the world of Python


# Script state in the menu or the command palette
# Return True or c4d.CMD_ENABLED to enable, False or 0 to disable
# Alternatively return c4d.CMD_ENABLED|c4d.CMD_VALUE to enable and check/mark
#def state():
#    return True

# Main function
baseDraw = doc.GetActiveBaseDraw()
if baseDraw is None:
   raise RuntimeError()

display = baseDraw.GetParameter(c4d.BASEDRAW_DATA_SDISPLAYACTIVE, c4d.DESCFLAGS_GET_0)

if display == c4d.BASEDRAW_SDISPLAY_GOURAUD:
    print("Gouraud Shading")
    c4d.CallCommand(17105) # Gouraud Shading (Lines)
if display == c4d.BASEDRAW_SDISPLAY_GOURAUD_WIRE:
    print("Gouraud Shading line")
    c4d.CallCommand(12091) # Gouraud Shading
if display == c4d.BASEDRAW_SDISPLAY_QUICK:
    print("Quick Shading")
    c4d.CallCommand(17107) # Quick Shading (Lines)
if display == c4d.BASEDRAW_SDISPLAY_QUICK_WIRE:
    print("# Quick Shading (Lines)")
    c4d.CallCommand(12092) # Quick Shading