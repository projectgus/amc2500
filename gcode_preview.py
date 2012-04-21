""" Module to preview gcode data onto a wxPython DC

Usage:

* First call initial_context(dc) to get the initial context for the preview.

* Call preview_command(command,context) once for each gcode command.

"""

def initial_context(dc):
    return { "dc" : dc, "x" : 0.0, "y" : 0.0, "z" : 0.0, "relative" : False }

def preview_command(args, context):
    command = args["command"]
    try:
        COMMANDS[command](args, context)
    except KeyError:
        print "WARNING: Command %s not supported for previewing" % command


def cmd_G00_rapid_move(args, context):
    _draw_linear_move(args, context)

def cmd_G01_linear_move(args, context):
    _draw_linear_move(args, context)

def cmd_G04_dwell(args, context):
    pass

def cmd_G20_inches(args, context):
    pass

def cmd_G21_mm(args, context):
    pass

def cmd_G90_absolute(args, context):
    context["relative"] = False

def cmd_G91_relative(args, context):
    context["relative"] = True

def cmd_G94_feedrate_per_minute(args, context):
    pass

def _draw_linear_move(args,context):
    dc = context["dc"]
    _update_position(args, context)
    prev_coords = (context["x"], context["y"])
    for axis in "x", "y", "z": # update context to new position
        try:
            if context["relative"]:
                context[axis] = context[axis] + args[axis]
            else:
                context[axis] = args[axis]
        except KeyError:
            pass
    colour = "GREY" if context["z" < 0 else "BLACK"
    dc.SetBrush(wx.Brush(None, wx.TRANSPARENT))
    dc.SetPen(wx.Pen(colour, 1))
    dc.DrawLine(*prev_coords, context["x"], context["y"])


# make a dict from command name (ie G94) to command function (ie cmd_G94_feedrate_)
COMMANDS = dict([(p[0].split("_")[1], p[1]) for p in __dict__.items if p[0].startswith("cmd_")])

