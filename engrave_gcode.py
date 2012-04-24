#!/usr/bin/env python
import getopt, sys, termios, tty, curses, re, time
import gcode_parse, gcode_normalise

from amc2500 import AMC2500, SimController

def usage():
    print "engrave_gcode [--no-spindle] [--head-up] [--no-jog|n] [--verbose|v] [--sim|s] gcode.ngc"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "sdnv", ["sim", "head-up", "no-spindle", "no-jog", "verbose"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    no_spindle = False
    head_up = False
    verbose = False
    jog_first = True
    simulate = False
    try:
        path = args[0]
    except:
        print "No gcode file specified"
        usage()
        sys.exit(2)
    for o, a in opts:
        verbose = verbose or o in ("--verbose", "v")
        head_up = head_up or (o == "head-up")
        no_spindle = no_spindle or (o == "no-spindle")
        jog_first = jog_first and not o in ("--no-jog", "n")
        simulate = simulate or o in ("-s", "--sim")

    print "Loading gcode file..."
    with open(path) as f:
        commands = list(gcode_parse.parse(f.read()))

    print "Normalising gcode content..."
    dimensions = gcode_normalise.normalise(commands)
    print "Done. Engraved dimensions will be %.1f x %.1fmm" % dimensions

    print "Connecting to AMC controller..."
    controller = SimController() if simulate else AMC2500()
    controller.trace = verbose
    controller.debug = verbose

    if jog_first:
        jog_controller(controller)
    print "Ready to start. Controller should be above bottom-left corner of design."
    print "This is %s." % ("a simulated run only" if simulate else
                           "just a dry run (head up, no spindle.)" if (head_up and no_spindle) else
                           "a run with the engraving head up" if head_up else
                           "a run with the spindle off (CHECK NO TOOL IS INSTALLED)" if no_spindle else
                           "NOT A DRY RUN SO BE SURE")
    print "Press Ctrl-C at any time to stop engraving."
    go = ""
    while go != "GO":
        go = raw_input("Type GO and press enter to start the engraving pass... ")
    engrave(controller, commands, head_up, no_spindle, verbose)


def jog_controller(controller):
    do_quit = False
    old_settings = termios.tcgetattr(sys.stdin)
    controller.set_units_steps()
    try:
        tty.setcbreak(sys.stdin.fileno())
        print "Jog the head around to find origin (bottom-left corner) for engraving."
        print
        print "HJKL to jog head around."
        print "0-9 to set jog speed."
        print "D/U to move head Down/Up to check position"
        print "O when found origin, Q to abort and quit."
        print

        speed = pow(2,5)
        saved_speed = None
        while True:
            c = sys.stdin.read(1).lower()
            if c == 'j':
                controller.move_by(0,speed)
            elif c == 'k':
                controller.move_by(0, -speed)
            elif c == 'h':
                controller.move_by(-speed,0)
            elif c == 'l':
                controller.move_by(speed,0)
            elif re.match("[0-9]", c):
                speed = pow(2,ord(c) - ord("0"))
            elif c == "d":
                saved_speed = speed
                speed = 0
                controller.set_head_down(True)
            elif c == "u" and saved_speed is not None:
                controller.set_head_down(False)
                speed = saved_speed
                saved_speed = None
            elif c in ( "q", "o" ):
                do_quit = (c == "q")
                break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    if do_quit:
        sys.exit(1)


def engrave(controller, commands, head_up, no_spindle, verbose):
    controller.zero_here()
    controller.set_units_mm()
    current = 0
    for c in commands:
        if verbose:
            print c
        name = c["name"]
        if name in ("G00", "G01"): # linear move
            if "F" in c:
                controller.set_speed(float(c["F"])/60) # mm/min to mm/sec
            controller.set_head_down(c["Z"] < 0 and not head_up)
            controller.move_to(c["X"], c["Y"])
        elif name in ( "M3", "M5" ): # spindle on/off
            controller.set_spindle(c == "M3" and not no_spindle)
        elif name == "G04":
            time.sleep(c.get("P", 0))
        elif name.startswith("S"): # spindle speed... weird command format!
            rpm = int(S[1:])
            controller.set_spindle_speed(rpm * 100 / 24000) # 0-99 is the range for this arg, 24k is our max speed I think
        elif name in ( "G20", "G90" ): # abs coords or mm, expected and ignorable
            pass
        elif name == "G64": # max deviation, ignoring for now...
            pass
        elif name in ("G94", "M9" ): # various commands we can ignore...
            pass
        elif name == "M2" : # program end
            print "Program End!"
            controller.set_head_down(False)
            controller.set_spindle_on(False)
            controller.move_to(0,0)
        else:
            print "Ignoring unexpected command %s (line %d)" % (c["name"], c["line"])
        current += 1
        message = "Command %d/%d" % (current, len(commands))
        print message + "\b"*len(message+1) # will overwrite on next print statement

if __name__ == "__main__":
    main()
