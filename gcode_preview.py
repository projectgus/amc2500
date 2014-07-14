""" Module to preview gcode data onto a wxPython DC

Usage:

* first call gcode_normalise.normalise() to normalise the gcode

* First call initial_context() to get the initial context for the preview.

* Call preview_command(command,context) once for each gcode command.

"""
import wx

MM_PER_INCH = 25.4

def initial_context(dc):
    return { "dc" : dc, "X" : 0.0, "Y" : 0.0, "Z" : 0.0, "relative" : False, "inches" : False }

def preview_command(args, context):
    command = args["name"]
    try:
        command = COMMANDS[command]
    except KeyError:
        print "WARNING: Command %s not supported for previewing" % command
        return
    command(args, context)

def cmd_G00_rapid_move(args, context):
    _draw_linear_move(args, context)

def cmd_G01_linear_move(args, context):
    _draw_linear_move(args, context)

def cmd_G04_dwell(args, context):
    pass

def cmd_G20_inches(args, context):
    context["inches"] = True

def cmd_G21_mm(args, context):
    context["inches"] = True

def cmd_G90_absolute(args, context):
    context["relative"] = False

def cmd_G91_relative(args, context):
    context["relative"] = True

def cmd_G94_feedrate_per_minute(args, context):
    pass

def _draw_linear_move(args,context):
    print args
    prev_coords = (context["X"], context["Y"])
    for axis in "X", "Y", "Z": # update context to new position
        try:
            if context["inches"]:
                args[axis] = args[axis] * MM_PER_INCH
            if context["relative"]:
                context[axis] = context[axis] + args[axis]
            else:
                context[axis] = args[axis]
        except KeyError:
            continue
    colour = "GREY" if context["Z"] > 0 else "BLACK"
    dc = context["dc"]
    dc.SetBrush(wx.Brush(None, wx.TRANSPARENT))
    dc.SetPen(wx.Pen(colour, 1))
    print "(%.2f, %.2f -> %.2f,%.2f)" % (prev_coords[0],prev_coords[1], context["X"],context["Y"])
    dc.DrawLine(prev_coords[0], prev_coords[1], context["X"], context["Y"])


# make a dict from command name (ie G94) to command function (ie cmd_G94_feedrate_)
COMMANDS = dict([(p[0].split("_")[1], p[1]) for p in globals().items() if p[0].startswith("cmd_")])

print COMMANDS
