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
    frame = GCodeFrame(commands)

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


class GCodeFrame(wx.Frame):
        def __init__(self, commands):
            wx.Frame.__init__( self,
                               None, -1, "GCode Plot",
                               size=(500,500) )
            panel = wx.Panel(self, -1)
            self.commands = commands
            self.cur_index = None
 
            self.Connect(-1, -1, EVT_ENGRAVING_DONE_ID, self.on_engraving_done)
            self.Connect(-1, -1, EVT_ENGRAVING_CMD_END_ID, self.on_engrave_cmd_end)
            self.Connect(-1, -1, EVT_ENGRAVING_CMD_START_ID, self.on_engrave_cmd_start)

            controls = self.get_control_buttons(panel)
            modes = self.get_mode_settings(panel)

            self.disable_when_engraving = [ controls, modes ]

            self.preview = PreviewPanel(panel, lambda:(self.commands, self.cur_index))            

            # layout
            grid = wx.GridBagSizer(vgap=5,hgap=5 )
            
            grid.AddMany([
                    (self.preview,           (0,0), (50,1), wx.EXPAND),

                    (controls,              (0,1), (2,1), wx.EXPAND),
                    (modes,                 (2,1), (2,2), wx.EXPAND),
                    ])
            grid.AddGrowableRow(2)
            grid.AddGrowableCol(0)
            panel.SetSizerAndFit(grid, wx.EXPAND)
            self.Show()


        def get_control_buttons(self, panel):
            self.btn_engrave = wx.Button(panel, label="Engrave")
            self.Bind(wx.EVT_BUTTON,self.on_engrave,self.btn_engrave)
            self.btn_engrave.SetDefault()
            self.engraving = False

            self.btn_stop = wx.Button(panel, label="Stop")
            self.Bind(wx.EVT_BUTTON,self.on_stop, self.btn_stop)
            self.btn_stop.Enabled = False

            # layout            
            box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Controls"), wx.HORIZONTAL)
            box.Add(self.btn_engrave)
            box.Add(self.btn_stop)
            return box

        def get_mode_settings(self, panel):
            self.chk_simulation = wx.CheckBox(panel, label="Simulation Mode")
            self.chk_simulation.Value = True

            self.chk_headup = wx.CheckBox(panel, label="Keep Head Up")
            self.chk_spindleoff = wx.CheckBox(panel, label="Keep Spindle Off")

            # layout
            box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Modes"), wx.VERTICAL)
            box.Add(self.chk_simulation)
            box.Add(self.chk_headup)
            box.Add(self.chk_spindleoff)
            return box
                                 
        def on_engrave(self, event):
            if self.engraving:
                return # already running
                        
            try:
                if self.chk_simulation.Value:
                    self.controller = SimController()
                else:
                    self.controller = AMC2500()     
                self.preview.update_drawing()
                self.cur_renderer = DCRenderer(down_colour="GREEN", up_colour="LIGHTGREEN")
                self.done_renderer = DCRenderer(down_colour="BLACK")                      
                self.engraving = True
                self.btn_engrave.Enabled = False
                self.btn_stop.Enabled = True
                self.worker = WorkerThread(self, AMCRenderer(self.controller, 
                                                             keep_spindle_off=self.chk_spindleoff.Value, 
                                                             keep_head_up=self.chk_headup.Value))
            except AMCError as e:
                self.show_dialog("Failed to start engraving: %s" % str(e))
                self.controller.zero()

        def on_engrave_cmd_start(self, event):
            """cmd start just draws green to canvas temporarily, 
            will be replaced by black on cmd end or resize"""
            self.cur_index = event.index
            command = self.commands[event.index]
            dc = self.preview.get_instant_dc()
            self.cur_renderer.render(command, dc, "GREEN")

        def on_engrave_cmd_end(self, event):
            """cmd end draws in black, draws to both backing buffer and current canvas"""
            self.cur_index = event.index+1
            command = self.commands[event.index]
            dc = self.preview.get_buffered_dc()
            self.done_renderer.render(command, dc) # immediate to screen


        def on_engraving_done(self, event):
            if event.error is not None:
                self.show_dialog(event.error)
            self.engraving = False
            self.btn_engrave.Enabled = True
            self.btn_stop.Enabled = False
            self.cur_index = None

                                         
        def on_stop(self, index):
            if not self.engraving:
                return
            self.engraving = False
            self.worker.abort()            
            self.controller.set_head_down(False)
            self.controller.set_spindle(False)
            self.show_dialog("Engraving stopped early due to stop button.")
            
        def show_dialog(self, msg):
                dlg = wx.MessageDialog( 
                    self, 
                    str(msg),
                    "AMC2500", 
                    wx.OK
                    )                    
                dlg.ShowModal()
                dlg.Destroy()


class PreviewPanel(wx.Panel):
    """ Panel for previewing a set of gcode commands to a window 
    
    Provides buffered & unbuffered clientdcs for doing temporary & permanent
    rendering to the panel.
    """
    def __init__(self, parent, command_cb):
        """
        command_cb = a callback which returns a tuple (commands, index) for the current list of commands
        and the current index (if engraving is in progress)
        """
        wx.Panel.__init__(self,parent)
        self.Bind(wx.EVT_PAINT, self._on_paint)            
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._last_size = None
        self._command_cb = command_cb
        self._on_size(None) # initial redraw
        
    def update_drawing(self):
        """Call this method to redraw the entire gcode layout from scratch

        This is an expensive method, only call it if something has really changed."""
        dc = wx.GCDC(wx.BufferedDC(wx.ClientDC(self), self._buffer))
        self._do_drawing(dc)
            
        
    def get_instant_dc(self):
        """Call this method to get a non-buffered DC which will be erased when the panel
        next redraws properly"""
        dc = wx.GCDC(wx.ClientDC(self))
        self._scale_dc(dc)
        return dc
        
    def get_buffered_dc(self):
        """Call this method to get a buffered DC to make changes via the back-buffer"""
        dc = wx.GCDC(wx.BufferedDC(wx.ClientDC(self), self._buffer))
        self._scale_dc(dc)
        return dc

    # internal methods follow

    def _scale_dc(self, dc):
        sx = float(self.Size.width) / TOTAL_WIDTH
        sy = float(self.Size.height) / TOTAL_HEIGHT
        scale = min(sx, sy)
        dc.SetUserScale(scale, scale)
        
    def _do_drawing(self, dc):
        dc.BeginDrawing()
        dc.SetBackground( wx.Brush("White") )
        dc.Clear()
        self._scale_dc(dc)
        dc.SetPen(wx.Pen("DARKGREY", 4))
        dc.DrawRectangle(BED_X, BED_Y, BED_WIDTH, BED_HEIGHT)
        preview_renderer = DCRenderer(up_colour="LIGHTGREY", down_colour="BLACK")            
        render_index = 0
        (commands, index) = self._command_cb() # callback gets all current commands, index point
        for cmd in commands:
            if index is None or render_index > index:
                preview_renderer.down_colour = "DARKGREY" # past "drawn" section, onto preview section
            preview_renderer.render(cmd, dc, None)
            render_index += 1
        dc.EndDrawing()
                
    def _on_paint(self, event):
        """ Paint event doesn't do anything except to blit in the pre-existing buffer"""
        dc = wx.GCDC(wx.BufferedPaintDC(self, self._buffer))

    def _on_size(self, event):
        size = self.GetClientSizeTuple()
        if size == self._last_size:
            return # No change in size, no need to redraw
        self._last_size = size
        width,height = size
        print "making bitmap %s,%s" % (width,height)
        self._buffer = wx.EmptyBitmap(width, height)
        self.update_drawing()
        
        

def main():
    app = wx.PySimpleApp()
    process(sys.argv[1])
    app.MainLoop()
    app.Destroy()

if __name__ == "__main__":
    main()
