import math

MM_PER_INCH = 25.4

def optimise(commands, deviation_threshold):
    return list(optimise_drills(optimise_deviation(commands, deviation_threshold)))

def point_line((ax,ay), (bx,by), (px,py)):
    """ Distance of point (px,py) from line between (ax,ay) and (bx,by) """
    normal = math.hypot(bx-ax,by-ay)
    abs_fact = abs( (px-ax)*(by-ay) - (py-ay)*(bx-ax) )
    return abs_fact / normal

def lookahead(iterable, null_item=None):
    iterator = iter(iterable) # in case a list is passed
    pprev = iterator.next()
    prev = iterator.next()
    for item in iterator:
        yield pprev, prev, item
        pprev = prev
        prev = item
    yield (pprev, prev, null_item)
    yield (prev, null_item, null_item)

def annotate_state(commands):
    """ Walk the list of commands and yield tuples of (pos, units_mm, absolute, command) for each command:
    - pos is the starting position (in current units) for the command
    - units_mm is true if units are mm, false if inches
    - absolute is true if in absolute positioning mode
    - command is the original command
    """
    pos = (0,0)
    absolute = False
    units_mm = True
    for c in commands:
        if c["name"] in ("G90", "G91"):
            absolute =  ( c["name"] == "G90" )
        elif c["name"] == "G20" and units_mm:
            units_mm = False
            pos = (pos[0]/MM_PER_INCH, pos[1]/MM_PER_INCH)
        elif c["name"] == "G21":
            units_mm = True
            pos = (pos[0]*MM_PER_INCH, pos[1]*MM_PER_INCH)
        elif c["name"] in ("G0", "G1"):
                if "X" in c:
                    if absolute:
                        pos = (c["X"], pos[1])
                    else:
                        pos = (pos[0]+c["X"], pos[1])
                if "Y" in c:
                    if absolute:
                        pos = (pos[0], c["Y"])
                    else:
                        pos = (pos[0], pos[1]+c["Y"])
        yield pos,units_mm,absolute,c


def optimise_deviation(commands, thres_mm):
    """
    Go over any sequences of linear movements and combine any that are
    within "threshold" mm deviation from a straight line
    """
    skip_next = False
    thres = thres_mm # keep threshold in current units
    thres_is_mm = True
    for (pos,units_mm,absolute,a),b,c in lookahead(annotate_state(commands)):
        b = b[-1] if b else None
        c = c[-1] if c else None
        if skip_next:
            skip_next = False
            continue
        if thres_is_mm and not units_mm:
            thres = thres / MM_PER_INCH
            thres_is_mm = False
        if units_mm and not thres_is_mm:
            thres = thres * MM_PER_INCH
            thres_is_mm = True
        if a["name"] in ("G0", "G1"):
            try:
                if absolute and b and c and "G1" == a["name"] == b["name"] == c["name"] and a["Z"]==b["Z"]==c["Z"]:
                    dist = point_line((a.get("X", pos[0]), a.get("Y", pos[1])),(c["X"], c["Y"]),(b["X"], b["Y"]))
                    skip_next = dist < thres
                elif (not absolute) and b and "G1" == a["name"] == b["name"] and a["Z"]==b["Z"]:
                    dist = point_line((0,0), (b["X"],b["Y"]), (a["X"],a["Y"]))
                    skip_next = dist < thres
            except KeyError:
                pass
        yield a


def optimise_drills(commands):
    """ Optimise any sequence of absolute positioned drill commands (G81/G82)

    To try and reduce to-ing and fro-ing across workpiece
    """
    drills = []
    drilltype = None
    for pos,units_mm,absolute,c in annotate_state(commands):
        if c["name"] in ("G81","G82") and absolute and "X" in c and "Y" in c:
            drills.append(c)
        else:
            if len(drills):
                for d in order_drills(pos, drills):
                    yield d
                drills = []
            yield c

def order_drills(pos, drills):
    """ Given a list of drill cycles, sort them for minimal distance travelled (greedy, non-optimal) """
    while len(drills):
        # sort by distance from current point
        closest = min(drills, key=lambda a: math.hypot(pos[0]-a["X"],pos[1]-a["Y"]))
        yield closest
        pos = (closest["X"], closest["Y"])
        drills.remove(closest)

