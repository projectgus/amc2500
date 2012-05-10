"""
Take a list of gcode commands and normalise them:

* Convert all relative movements & coordinates to absolute ones

* Convert all units to mm

* Calculate the actual engraved area, then translate all commands
  so the bottom-left engraved point is at the origin.

* Convert all feed rates to mm/minute

Returns a tuple of (width, height)
"""

INF=float("inf")

MM_PER_INCH = 25.4

def normalise(commands):
    min_x = min_y = INF
    max_x = max_y = -INF
    x = y = z = 0
    inches = False
    feed_inches = False
    rate = None
    for command in commands:
        name = command["name"]
        if name in ( "G20", "G21" ):
            inches = (name == "G20")
            command["name"] = "G21" # all in mm
        elif name in ( "G90", "G91" ):
            relative = (name == "G91")
            command["name"] = "G90" # all absolute
        elif name in ( "G00", "G01" ):
            scalar = MM_PER_INCH if inches else 1
            ox,oy = x,y
            if relative:
                x += command.get("X", 0.0) * scalar
                y += command.get("Y", 0.0) * scalar
                z += command.get("Z", 0.0) * scalar
            else:
                x = command.get("X", x/scalar) * scalar
                y = command.get("Y", y/scalar) * scalar
                z = command.get("Z", z/scalar) * scalar
            if "F" in command:
                rate = command["F"] * scalar
            if rate:
                command["F"] = rate
            command["X"] = x
            command["Y"] = y
            command["Z"] = z
            if z < 0: # toolpiece down
                min_x = min(x, min_x)
                min_y = min(y, min_y)
                max_x = max(x, max_x)
                max_y = max(y, max_y)
    # do the actual normalisation pass
    for command in commands:
        if command["name"] in [ "G00", "G01" ]:
            command["X"] = command["X"] - min_x
            command["Y"] = command["Y"] - min_y
            # clamp values between min & max ranges, this should only apply for "toolpiece up" movements
            # (keep them from zipping anywhere silly)
            command["X"] = min(max(command["X"], 0), max_x-min_x)
            command["Y"] = min(max(command["Y"], 0), max_y-min_y)
    return (max_x-min_x, max_y-min_y)
