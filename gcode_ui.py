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
from threading import Thread

# dimension in mm, total area the head can cover (limit to limit)
# and the area inside that which corresponds to the bed

# (reasonably accurate values atm)
TOTAL_HEIGHT=390
TOTAL_WIDTH=431

BED_HEIGHT=322
BED_WIDTH=271
BED_X = 35
BED_Y = 55



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
        dc.SetPen(wx.Pen(self.get_colour(override_colour), 1 if self.head else 0.2))
        if cmd.to_x == cmd.fr_x and cmd.to_y == cmd.fr_y:
            return # just a Z movement
        lines = [ [cmd.fr_x, cmd.fr_y, cmd.to_x, cmd.to_y] ]
        dc.DrawLineList(lines)
        
    @when(M3)
    def render(self, cmd, dc, override_colour=None):
        self.spindle = True
    @when(M5)
    def render(self, cmd, dc, override_colour=None):
        self.spindle = False


EVT_ENGRAVING_DONE_ID = wx.NewId()
EVT_ENGRAVING_CMD_START_ID = wx.NewId()
EVT_ENGRAVING_CMD_END_ID = wx.NewId()

class EngravingDoneEvent(wx.PyEvent):
     """Event to signify that engraving is done"""
     def __init__(self, error=None):
         wx.PyEvent.__init__(self)
         self.SetEventType(EVT_ENGRAVING_DONE_ID)
         self.error=error

class EngravingCmdStart(wx.PyEvent):
     """Event to signify that engraving is starting a command"""
     def __init__(self, index):
         wx.PyEvent.__init__(self)
         self.SetEventType(EVT_ENGRAVING_CMD_START_ID)
         self.index=index

class EngravingCmdEnd(wx.PyEvent):
     """Event to signify that engraving has just finished a command"""
     def __init__(self, index):
         wx.PyEvent.__init__(self)
         self.SetEventType(EVT_ENGRAVING_CMD_END_ID)
         self.index=index
 
class WorkerThread(Thread):
    """Worker Thread for running the engraver."""
    def __init__(self, window, renderer):
        Thread.__init__(self)
        self._window=window
        self._renderer=renderer
        self._aborting=False
        self.start()
        
    def run(self):
        controller=self._window.controller
        commands=self._window.commands
        try:             
            controller.zero()
            controller.set_units_mm()
            controller.set_spindle_speed(5000)
            
            for i in range(0, len(commands)):
                if self._aborting:
                    wx.PostEvent(self._window, EngravingDoneEvent(None))
                    return
                
                wx.PostEvent(self._window, EngravingCmdStart(i))
                self._renderer.render(commands[i])
                wx.PostEvent(self._window, EngravingCmdEnd(i))
            wx.PostEvent(self._window, EngravingDoneEvent(None))
        except Exception as e:
            wx.PostEvent(self._window, EngravingDoneEvent(e))
            controller.zero()
 
    def abort(self):
        self._aborting = True


class PreviewFrame(wx.Frame):
        def __init__(self, commands):
            wx.Frame.__init__( self,
                               None, -1, "Plot Preview",
                               size=(500,500) )
            panel = wx.Panel(self, -1)
            self.commands = commands
            self.cur_index = None
            self.preview_renderer = None
            self.canvas = wx.Panel(panel, -1)
            self.canvas.Bind(wx.EVT_PAINT, self.on_paint)            
            self.canvas.Bind(wx.EVT_SIZE, self.on_size)
            self.on_size(None)

            self.btn_engrave = wx.Button(panel, label="Engrave")
            self.Bind(wx.EVT_BUTTON,self.on_engrave,self.btn_engrave)
            self.btn_engrave.SetDefault()
            self.engraving = False

            self.btn_stop = wx.Button(panel, label="Stop")
            self.Bind(wx.EVT_BUTTON,self.on_stop, self.btn_stop)
            self.btn_stop.Enabled = False

            self.chk_simulation = wx.CheckBox(panel, label="Simulation Mode")
            self.chk_simulation.Value = True
            
            self.Connect(-1, -1, EVT_ENGRAVING_DONE_ID, self.on_engraving_done)
            self.Connect(-1, -1, EVT_ENGRAVING_CMD_END_ID, self.on_engrave_cmd_end)
            self.Connect(-1, -1, EVT_ENGRAVING_CMD_START_ID, self.on_engrave_cmd_start)

            # layout
            grid = wx.GridBagSizer(vgap=5 )
            
            grid.AddMany([
                    (self.btn_engrave,      (0,0), (1,1)),
                    (self.btn_stop,         (0,1), (1,1)),

                    (self.chk_simulation,   (1,0), (1,1)),                   

                    (self.canvas,                    (2,0), (1,2), wx.EXPAND),
                    ])
            grid.AddGrowableRow(2)
            grid.AddGrowableCol(0)
            panel.SetSizerAndFit(grid, wx.EXPAND)
            self.Show()
                       
        def on_paint(self, event):
            dc = wx.GCDC(wx.BufferedPaintDC(self.canvas, self._buffer))

        def update_drawing(self):
            dc = wx.GCDC(wx.BufferedDC(wx.ClientDC(self.canvas), self._buffer))
            self.do_drawing(dc)
            
        def scale_dc(self, dc):
            sx = float(self.canvas.Size.width) / TOTAL_WIDTH
            sy = float(self.canvas.Size.height) / TOTAL_HEIGHT
            scale = min(sx, sy)
            dc.SetUserScale(scale, scale)

        def do_drawing(self, dc):
            dc.BeginDrawing()
            dc.SetBackground( wx.Brush("White") )
            dc.Clear()
            self.scale_dc(dc)
            dc.SetPen(wx.Pen("DARKGREY", 4))
            dc.DrawRectangle(BED_X, BED_Y, BED_WIDTH, BED_HEIGHT)
            if self.preview_renderer is None:
                self.preview_renderer = DCRenderer(up_colour="LIGHTGREY", down_colour="BLACK")            
            self.preview_renderer.down_colour = "BLACK"
            index = 0
            for cmd in self.commands:
                if self.cur_index is None or index > self.cur_index:
                    self.preview_renderer.down_colour = "DARKGREY" # onto preview section
                self.preview_renderer.render(cmd, dc, None)
                index += 1
            dc.EndDrawing()

        def on_size(self, event):
            width,height = self.canvas.GetClientSizeTuple()
            print "making bitmap %s,%s" % (width,height)
            self._buffer = wx.EmptyBitmap(width, height)
            self.update_drawing()

                                 
        def on_engrave(self, event):
            if self.engraving:
                return # already running
                        
            try:
                if self.chk_simulation.Value:
                    self.controller = SimController()
                else:
                    self.controller = AMC2500()     
                self.preview_renderer = None
                self.update_drawing()
                self.done_renderer = DCRenderer(down_colour="BLACK")                      
                self.engraving = True
                self.btn_engrave.Enabled = False
                self.btn_stop.Enabled = True
                self.worker = WorkerThread(self, AMCRenderer(self.controller))
            except AMCError as e:
                self.show_error("Failed to start engraving: %s" % str(e))
                self.controller.zero()

        def on_engrave_cmd_start(self, event):
            """cmd start just draws green to canvas, will be replaced by black on cmd end or resize"""
            self.cur_index = event.index
            command = self.commands[event.index]
            dc = wx.GCDC(wx.ClientDC(self.canvas))
            self.scale_dc(dc)
            self.preview_renderer.render(command, dc, "GREEN")

        def on_engrave_cmd_end(self, event):
            """cmd end draws in black, draws to both backing buffer and current canvas"""
            self.cur_index = event.index+1
            command = self.commands[event.index]
            dc = wx.GCDC(wx.BufferedDC(wx.ClientDC(self.canvas), self._buffer))
            self.scale_dc(dc)
            self.done_renderer.render(command, dc) # immediate to screen


        def on_engraving_done(self, event):
            if event.error is not None:
                self.show_error(event.error)
            self.engraving = False
            self.btn_engrave.Enabled = True
            self.btn_stop.Enabled = False
            self.cur_index = None

                                         
        def on_stop(self, index):
            if not self.engraving:
                return
            self.engraving = False


        def show_error(self, msg):
                dlg = wx.MessageDialog( 
                    self, 
                    str(msg),
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
