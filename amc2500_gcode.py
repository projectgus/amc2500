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
import gcode

# dimension in mm, total area the head can cover (limit to limit)
# and the area inside that which corresponds to the bed

# (placeholder values atm)
TOTAL_HEIGHT=350
TOTAL_WIDTH=300

BED_HEIGHT=300
BED_WIDTH=290
BED_X = 5
BED_Y = 10

# how much larger should the preview be than real life (ie pixel:mm)?
PREVIEW_SCALE=2
def scale(d):
    if isinstance(d, tuple):
        return tuple(scale(list(d)))
    if isinstance(d, list):
        return [ x*PREVIEW_SCALE for x in list(d) ]
    else:
        return float(d)*PREVIEW_SCALE


def process(filename):    
    command_classes = {
        "Comment" : Comment,
        "G00" : CmdG00,
        "G01" : CmdG01,
        "G02" : CmdG02,
        "G03" : CmdG03,
        "G21" : CmdG21,
        "M2"  : CmdM2,
        "M3"  : CmdM3,
        "M5"  : CmdM5 }
    print "Parsing %s" % filename
    commands = gcode.parse(command_classes, filename)
    print "Extracted %d commands" % len(commands)
    frame = PreviewFrame(commands)


def line_pen(state):
    color = { (False, True) :  "GREY",
              (False, False) : "GREY",
              (True, False) :  "DARKRED", # head down spindle off should not happen
              (True, True) :  "BLACK",
              }[(state.head_down, state.spindle_on)]
    width = 2 if state.head_down else 1
    return wx.Pen(color, width)
                      

# Command classes, this is where the magic happens #                

class Comment:
    def __init__(self, comment):
        self.comment = comment
    def __repr__(self):
        return "Comment %s" % self.comment

    def render_preview(self, state, dc):
        print self
        return state

class CmdCommon:
    def __init__(self, args, comments):
        self.args = args
        self.comments = comments

    # update some common preview state
    def render_preview(self, state, dc):
        print self
        if "Z" in self.args:
            state.head_down = self.args["Z"] <= 0
        dc.SetPen(line_pen(state))
        return state

    def render_preview_line(self, state, dc): # G00 & G01 have the same line in preview
        state = CmdCommon.render_preview(self, state,dc)
        if not ("X" in self.args or "Y" in self.args): # just a Z movement, common code does that
            return state
        x = self.args.get("X", state.x)
        y = self.args.get("Y", state.y)
        lines = [ scale([state.x, state.y, x, y]) ]
        print "Line %s" % lines
        dc.DrawLineList(lines)
        state.x = x
        state.y = y
        return state
        
    def render_preview_arc(self, state, dc, cw):
        state = CmdCommon.render_preview(self,state,dc)
        # cheat for now and draw a three-part line !
        x = self.args.get("X", state.x)
        y = self.args.get("Y", state.y)
        i = self.args.get("I", 0)+state.x
        j = self.args.get("J", 0)+state.y
        dc.DrawLine(scale(state.x), scale(state.y), scale(x), scale(y))
        # if not cw:
        #     dc.DrawArc(x, y, state.x, state.y, i, j)
        # else:
        #     dc.DrawArc(state.x, state.y, x, y, i, j)
        state.x = x
        state.y = y
        return state




""" G00 - high speed move (slew)
"""
class CmdG00(CmdCommon):
    def __init__(self, args, comments):
        CmdCommon.__init__(self, args, comments)

    def __repr__(self):
        return "G00 %s %s" % (self.args, self.comments)

    def render_preview(self, state, dc):
        return CmdCommon.render_preview_line(self, state,dc)

""" G01 - linear move (machine)
"""
class CmdG01(CmdCommon):
    def __init__(self, args, comments):
                CmdCommon.__init__(self, args, comments)
    def __repr__(self):
        return "G01 %s %s" % (self.args, self.comments)

    def render_preview(self, state, dc):
        return CmdCommon.render_preview_line(self, state,dc)
        
        
""" G02 - CW 2D circular move (using IJ params, K params make no sense here)
"""
class CmdG02(CmdCommon):
    def __init__(self, args, comments):
                CmdCommon.__init__(self, args, comments)
    def __repr__(self):
        return "G02 %s %s" % (self.args, self.comments)

    def render_preview(self, state, dc):
        return CmdCommon.render_preview_arc(self, state, dc, True)


""" G03 - CCW 2D circular move (using IJ params, K params make no sense here)
"""
class CmdG03(CmdCommon):
    def __init__(self, args, comments):        
                CmdCommon.__init__(self, args, comments)
    def __repr__(self):
        return "G03 %s %s" % (self.args, self.comments)

    def render_preview(self, state, dc):
        return CmdCommon.render_preview_arc(self,state,dc, False)

""" G21 - set mm mode. this is all we support atm anyhow ;)
"""
class CmdG21(CmdCommon):
    def __init__(self, args, comments):        
                CmdCommon.__init__(self, args, comments)
    def __repr__(self):
        return "G21 %s %s" % (self.args, self.comments)

    def render_preview(self, state, dc):
        return CmdCommon.render_preview(self,state,dc)

""" M2 - end of program 
"""
class CmdM2:
    def __init__(self, args, comments):        
        pass
        
    def __repr__(self):
        return "M2"

    def render_preview(self, state, dc):
        return state


""" M3 - spindle on
"""
class CmdM3:
    def __init__(self, args, comments):        
        pass        
    def __repr__(self):
        return "M3"

    def render_preview(self, state, dc):
        state.spindle_on = True
        return state

""" M5 - spindle off
"""
class CmdM5:
    def __init__(self, args, comments):
        pass    
    def __repr__(self):
        return "M5"

    def render_preview(self, state, dc):
        state.spindle_on = False
        return state
 

class PreviewFrame(wx.Frame):
        def __init__(self, commands):
            wx.Frame.__init__( self,
                               None, -1, "Plot Preview",
                               size=(scale(TOTAL_WIDTH),
                                     scale(TOTAL_HEIGHT)+100),
                               style=wx.DEFAULT_FRAME_STYLE )
            self.commands = commands
            sizer = wx.BoxSizer( wx.VERTICAL )
            self.canvas = wx.Panel(self, size=scale((TOTAL_WIDTH,TOTAL_HEIGHT)))
            sizer.Add( self.canvas )
            self.canvas.Bind(wx.EVT_PAINT, self.on_paint)
            self.SetSizer(sizer)
            self.SetAutoLayout(1)
            self.Show(1)
                       
        def on_paint(self, event):
            dc = wx.PaintDC(event.GetEventObject())
            self.clear(dc)
            class State:
                pass
            state = State()
            state.x = 0
            state.y = 0
            state.head_down = False
            state.spindle_on = False
            for cmd in self.commands:
                state = cmd.render_preview(state, dc)
            
        def clear(self, dc):
            dc.Clear()
            dc.SetPen(wx.Pen("DARKGREY", 4))
            dc.DrawRectangle(scale(BED_X), scale(BED_Y), 
                              scale(BED_WIDTH), scale(BED_HEIGHT))
            
            
        
        



def main():
    app = wx.PySimpleApp()
    process(sys.argv[1])
    app.MainLoop()
    app.Destroy()

if __name__ == "__main__":
    main()
