#!/usr/bin/env python
"""
A standalone gcode parser to preview and then engrave a subset of gcode onto an
AMC2500 CNC controller w/ a QuickCircuit 5000 engraver.

At this point it is intended to support the subset of g-code dumped by the Inkscape
gcodetools plugin. http://www.cnc-club.ru/forum/viewtopic.php?f=15&t=35&start=0

Guidelines for gcode files:
* Units in mm
* Set offset/scale appropriately for the table
* Z axis >0 is "head up", Z axis 0 or below is "head down"
"""

import sys, wx
from amc2500 import *
from gcode import *
from visitor import is_visitor, when

# dimension in mm, total area the head can cover (limit to limit)
# and the area inside that which corresponds to the bed

# (placeholder values atm)
TOTAL_HEIGHT=300
TOTAL_WIDTH=300

BED_HEIGHT=290
BED_WIDTH=200
BED_X = 90
BED_Y = 5


# how much larger should the preview be than real life (ie pixel:mm)?
PREVIEW_SCALE=1.6
def scale(d):
    if isinstance(d, tuple):
        return tuple(scale(list(d)))
    if isinstance(d, list):
        return [ x*PREVIEW_SCALE for x in list(d) ]
    else:
        return float(d)*PREVIEW_SCALE


def process(filename):    
    print "Parsing %s" % filename
    commands = parse(filename)
    print "Extracted %d commands" % len(commands)
    frame = PreviewFrame(commands)

@is_visitor
class DCRenderer:
    """Renderer to take gcode commands and preview them onto a wxPython DC
    
       up_color - color to use when moving not engraving
       down_color - color to use when engraving
       error_color - color to use when head down but spindle off
    """

    def __init__(self, up_color="GREY", down_color="BLACK", error_color="DARKRED"):
        self.up_color = up_color
        self.down_color = down_color
        self.error_color = error_color
        self.spindle = False
        self.head = False

    def get_color(self, override_color=None):
        if override_color is not None:
            return override_color        
        elif self.spindle and self.head:
            return self.down_color
        elif self.head:
            return self.error_color
        else:
            return self.up_color

    @when(BaseCommand, allow_cascaded_calls=True)
    def render(self, cmd, dc, override_color=None):
        print cmd.comment

    @when(LinearCommand, allow_cascaded_calls=True)
    def render(self, cmd, dc, override_color=None):
        self.head = cmd.to_z <= 0
        dc.SetPen(wx.Pen(self.get_color(override_color), PREVIEW_SCALE))
        if cmd.to_x == cmd.fr_x and cmd.to_y == cmd.fr_y:
            return # just a Z movement
        lines = [ scale([cmd.fr_x, cmd.fr_y, cmd.to_x, cmd.to_y]) ]
        print "Line %s" % lines
        dc.DrawLineList(lines)
        
    @when(M3)
    def render(self, cmd, dc, override_color=None):
        self.spindle = True
    @when(M5)
    def render(self, cmd, dc, override_color=None):
        self.spindle = False


class PreviewFrame(wx.Frame):
        def __init__(self, commands):
            wx.Frame.__init__( self,
                               None, -1, "Plot Preview",
                               size=(scale(TOTAL_WIDTH),
                                     scale(TOTAL_HEIGHT)+40),
                               style=wx.DEFAULT_FRAME_STYLE )
            self.commands = commands
            self.canvas = wx.Panel(self, size=scale((TOTAL_WIDTH,TOTAL_HEIGHT)))
            self.canvas.Bind(wx.EVT_PAINT, self.on_paint)

            self.btn_print = wx.Button(self, label="Print")
            self.Bind(wx.EVT_BUTTON,self.on_print,self.btn_print)

            self.chk_simulation = wx.CheckBox(self, label="Simulation Mode")
            self.chk_simulation.Value = True

            # layout
            sizer = wx.BoxSizer( wx.VERTICAL )
            sizer.Add(self.btn_print)
            sizer.Add(self.chk_simulation) # TODO: non-lame layout
            sizer.Add( self.canvas )
            self.SetSizer(sizer)
            self.SetAutoLayout(1)
            self.Show(1)
                       
        def on_paint(self, event):
            dc = wx.PaintDC(event.GetEventObject())
            renderer = DCRenderer()            
            self.clear(dc)
            for cmd in self.commands:
                renderer.render(cmd, dc, None)

            
        def clear(self, dc):
            dc.Clear()
            dc.SetPen(wx.Pen("DARKGREY", 4))
            dc.DrawRectangle(scale(BED_X), scale(BED_Y), 
                              scale(BED_WIDTH), scale(BED_HEIGHT))

        def on_print(self, event):
            try:
                if self.chk_simulation.Value:
                    controller = SimController()
                else:
                    controller = AMC2500()                           
                controller.zero()
                controller.set_units_mm()
                controller.set_spindle_speed(5000)
            
                renderer = AMCRenderer(controller)
                for comm in self.commands:
                    renderer.render(comm)

            except AMCError as e:
                dlg = wx.MessageDialog( 
                    self, 
                    str(e), 
                    "AMC2500", 
                    wx.OK
                    )                    
                dlg.ShowModal() # Show it
                dlg.Destroy() # finally destroy it when finished.
                controller.zero()


def main():
    app = wx.PySimpleApp()
    process(sys.argv[1])
    app.MainLoop()
    app.Destroy()

if __name__ == "__main__":
    main()
