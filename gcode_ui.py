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

# (reasonably accurate values atm)
TOTAL_HEIGHT=390
TOTAL_WIDTH=431

BED_HEIGHT=322
BED_WIDTH=271
BED_X = 35
BED_Y = 55


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
    
       up_colour - colour to use when moving not engraving
       down_colour - colour to use when engraving
       error_colour - colour to use when head down but spindle off
    """

    def __init__(self, up_colour="GREY", down_colour="BLACK", error_colour="DARKRED"):
        self.up_colour = up_colour
        self.down_colour = down_colour
        self.error_colour = error_colour
        self.spindle = False
        self.head = False

    def get_colour(self, override_colour=None):
        if override_colour is not None:
            return override_colour        
        elif self.spindle and self.head:
            return self.down_colour
        elif self.head:
            return self.error_colour
        else:
            return self.up_colour

    @when(BaseCommand, allow_cascaded_calls=True)
    def render(self, cmd, dc, override_colour=None):
        pass

    @when(LinearCommand, allow_cascaded_calls=True)
    def render(self, cmd, dc, override_colour=None):
        self.head = cmd.to_z <= 0
        dc.SetPen(wx.Pen(self.get_colour(override_colour), PREVIEW_SCALE))
        if cmd.to_x == cmd.fr_x and cmd.to_y == cmd.fr_y:
            return # just a Z movement
        lines = [ scale([cmd.fr_x, cmd.fr_y, cmd.to_x, cmd.to_y]) ]
        dc.DrawLineList(lines)
        
    @when(M3)
    def render(self, cmd, dc, override_colour=None):
        self.spindle = True
    @when(M5)
    def render(self, cmd, dc, override_colour=None):
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
            self.do_repaint = True

            self.btn_engrave = wx.Button(self, label="Engrave")
            self.Bind(wx.EVT_BUTTON,self.on_engrave,self.btn_engrave)
            self.btn_engrave.SetDefault()
            self.engraving = False

            self.btn_stop = wx.Button(self, label="Stop")
            self.Bind(wx.EVT_BUTTON,self.on_stop, self.btn_stop)
            self.btn_stop.Enabled = False

            self.chk_simulation = wx.CheckBox(self, label="Simulation Mode")
            self.chk_simulation.Value = True

            # layout
            sizer = wx.BoxSizer( wx.VERTICAL )
            btn_sizer = wx.BoxSizer( wx.HORIZONTAL )
            chk_sizer = wx.BoxSizer( wx.HORIZONTAL )

            btn_sizer.Add(self.btn_engrave)
            btn_sizer.Add(self.btn_stop)

            chk_sizer.Add(self.chk_simulation)
            sizer.Add(btn_sizer)
            sizer.Add(chk_sizer)
            sizer.Add( self.canvas )
            self.SetSizer(sizer)
            self.SetAutoLayout(1)
            self.Show(1)
                       
        def on_paint(self, event):
            if not self.do_repaint:
                return
            self.do_repaint = False
            dc = wx.PaintDC(event.GetEventObject())
            self.preview_renderer = DCRenderer(up_colour="LIGHTGREY", down_colour="DARKGREY")            
            self.clear(dc)
            for cmd in self.commands:
                self.preview_renderer.render(cmd, dc, None)

            
        def clear(self, dc):
            dc.Clear()
            dc.SetPen(wx.Pen("DARKGREY", 4))
            dc.DrawRectangle(scale(BED_X), scale(BED_Y), 
                              scale(BED_WIDTH), scale(BED_HEIGHT))

        def on_engrave(self, event):
            if self.engraving:
                return # already running
                        
            try:
                if self.chk_simulation.Value:
                    self.controller = SimController()
                else:
                    self.controller = AMC2500()                           
                self.controller.zero()
                self.controller.set_units_mm()
                self.controller.set_spindle_speed(5000)
            
                self.done_renderer = DCRenderer(down_colour="BLACK")
                self.engrave_renderer = AMCRenderer(self.controller)
                wx.CallAfter(self.pre_engrave, 0) # need to pump the wx event loop as we engrave
                self.do_repaint = True
                self.canvas.Refresh()
                self.engraving = True
                self.btn_engrave.Enabled = False
                self.btn_stop.Enabled = True
            except AMCError as e:
                self.show_error("Failed to start engraving: %s" % str(e))
                self.controller.zero()

        def pre_engrave(self, index):
            """ pre_engrave runs as a wx event to paint the current drawing section """
            if index < len(self.commands) and self.engraving:
                command = self.commands[index]
                dc = wx.ClientDC(self.canvas)
                self.preview_renderer.render(command, dc, "GREEN")
                self.canvas.Update()
                wx.CallLater(1, self.do_engrave, index)
            else:
                self.controller.zero()
                self.engraving = False
                self.btn_engrave.Enabled = True
                self.btn_stop.Enabled = False

        def do_engrave(self, index):
            """ do_engrave is the step that actuall runs the engraver (blocks the wx event queue) """
            try:
                command = self.commands[index]
                dc = wx.ClientDC(self.canvas)
                self.engrave_renderer.render(command)
                self.done_renderer.render(command, dc)
                self.canvas.Update()
                wx.CallLater(1,self.pre_engrave, index+1)
            except AMCError as e:
                self.show_error("Error while engraving: %s" % str(e))
                self.engraving = False
                self.do_repaint = True
                wx.CallAfter(self.pre_engrave, index+1)
                


        def on_stop(self, index):
            if not self.engraving:
                return
            self.engraving = False


        def show_error(self, msg):
                dlg = wx.MessageDialog( 
                    self, 
                    msg,
                    "AMC2500", 
                    wx.OK
                    )                    
                dlg.ShowModal()
                dlg.Destroy()


def main():
    app = wx.PySimpleApp()
    process(sys.argv[1])
    app.MainLoop()
    app.Destroy()

if __name__ == "__main__":
    main()
