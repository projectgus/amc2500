#!/usr/bin/env python
import argparse, sys, termios, tty, curses, re, time, itertools
import gcode_parse

from amc2500 import AMC2500, SimController

parser = argparse.ArgumentParser(description='Engrave some gcode file(s) from the pcb2gcode package.')
parser.add_argument('--sim', action='store_true',
                    help="Testing option: simulation run only (no real engraver involved.)")
parser.add_argument('--no-spindle', action='store_true',
                    help='Testing option: keep the spindle motor off during the engraving pass.')
parser.add_argument('--head-up', action='store_true',
                    help='Testing option: keep the spindle head up during the engraving pass.')
parser.add_argument('-', '--no-jog', action='store_true',
                    help='Skip the "jog to find origin" step (use if the spindle head is already over the starting point.')
parser.add_argument('-s', '--serial-port', default='/dev/ttyUSB0',
                    help="Specify the serial port that the engraver is connected to.")
parser.add_argument('-v', '--verbose', action='store_true',
                    help="Verbose mode (print every command the engraver executes to stderr.")
parser.add_argument('files', nargs='+', help="One or more gcode files, which will be sent to the engraver in the order given. Insert the phrase TC by itself between any two files where you want a toolchange run.")


def header(path):
    return [  ]



def footer(path):
    return [  ]

def main():
    args = parser.parse_args()

    print "Loading gcode..."
    commands = [ ]
    toolchange = False
    for path in args.files:
        if path == "TC":
            toolchange = True
        else:
            with open(path) as f:
                try:
                    commands.append({"name" : "message", "value" : "Starting gcode file %s" % path })
                    if toolchange:
                        commands += [ { "name" : "message", "value" : "Tool change requested on command line..." },
                                      { "name" : "M6" }
                                      ]
                        toolchange = False
                    commands += list(gcode_parse.parse(f.read()))
                    commands.append({"name" : "message", "value" : "End of gcode file %s" % path })
                except gcode_parse.ParserException, err:
                    print "Failed to parse %s: %s" % (path, err)
                    sys.exit(1)

    print "Connecting to AMC controller..."
    controller = SimController() if args.sim else AMC2500(port=args.serial_port)
    controller.trace = args.verbose
    controller.debug = args.verbose

    if not args.no_jog:
        jog_controller(controller)
    print "Ready to start. Controller should be above origin of design."
    print "This is %s." % ("a simulated run only" if args.sim else
                           "just a dry run (head up, no spindle.)" if (args.head_up and args.no_spindle) else
                           "a run with the engraving head up" if args.head_up else
                           "a run with the spindle off (CHECK NO TOOL IS INSTALLED)" if args.no_spindle else
                           "NOT A DRY RUN SO BE SURE")
    print "Press Ctrl-C at any time to stop engraving."
    go = ""
    while go != "GO":
        go = raw_input("Type GO and press enter to start the engraving pass... ")
    engrave(controller, commands, args)


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
        print "D/U to move head Down/Up to check position."
        print "S to toggle spindle power."
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
            elif c == "s":
                controller.set_spindle(not controller.spindle)
            elif c in ( "q", "o" ):
                do_quit = (c == "q")
                break
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    if do_quit:
        sys.exit(1)


def engrave(controller, commands, args):
    controller.zero_here()
    controller.set_units_mm()
    current = 0
    args.absolute = False

    def linear_move(c):
        """G00, G01"""
        if "F" in c:
            controller.set_speed(float(c["F"])/60) # mm/min to mm/sec
        if "Z" in c:
            controller.set_head_down(c["Z"] < 0 and not args.head_up)
        try:
            if args.absolute:
                controller.move_to(c["X"], c["Y"])
            else:
                controller.move_by(c["X"], c["Y"])
        except KeyError:
            pass

    def set_spindle_speed(c):
        """Sxxxxxxx"""
        rpm = c["S"]
        # 0-99 is the range for the controller's spindle arg,
        # 24k is our max speed I think
        controller.set_spindle_speed(rpm * 100 / 24000)

    def finish_program(c):
        """M2"""
        print "Program End!"
        controller.set_head_down(False)
        controller.set_spindle(False)
        controller.set_max_speed()
        controller.move_to(0,0)

    def tool_change(c):
        """M6"""
        controller.set_head_down(False)
        controller.set_spindle(False)
        old_units = controller.steps_per_unit
        old_speed = controller.cur_speed
        controller.set_units_mm()
        controller.set_max_speed()
        old_pos = controller.get_pos()
        while controller.move_by(-200,0) == (-200,0):
            pass # drive the controller to the toolchange position, 200mm at a time
        while controller.move_by(0,-200) == (0,-200):
            pass
        go = ""
        while go != "GO":
            go = raw_input("Type 'GO' and press enter to resume engraving once you've finished the toolchange")
        controller.move_to(*old_pos)
        controller.set_units(old_units)
        controller.set_speed(old_speed)

    def drill_cycle(c):
        """G81/G82"""
        controller.set_head_down(False)
        controller.set_spindle(False)

        # preliminary move
        old_speed = controller.cur_speed
        controller.set_max_speed() # may be too fast, check for skipped steps
        if args.absolute:
            controller.move_to(c["X"],c["Y"])
        else:
            controller.move_by(c["X"],c["Y"])
        controller.set_speed(old_speed)

        # drillify!
        controller.set_spindle(not args.no_spindle)
        controller.set_head_down(not args.head_up)
        time.sleep(c.get("P",3)) # should maybe use R & Z here to calculate a dwell period for G81... ???

        # done
        controller.set_head_down(False)
        controller.set_spindle(False)

    def ignore(c):
        pass

    def message(c):
        print c["value"]

    def set_absolute(to):
        args.absolute = to

    ACTIONS = {
        "G0" : linear_move,
        "G1" : linear_move,
        "G4" : lambda c: time.sleep(c.get("P",0)),
        "G20" : lambda c: controller.set_units_inches(),
        "G21" : lambda c: controller.set_units_mm(),
        "G64" : ignore, # max deviation, ignore for now
        "G81" : drill_cycle,
        "G82" : drill_cycle,
        "G90" : lambda c: set_absolute(True),
        "G91" : lambda c: set_absolute(False),
        "G94" : ignore, # units per minute feed rate (default)
        "M2"  : finish_program,
        "M3" : lambda c: controller.set_spindle(not args.no_spindle),
        "M5" : lambda c: controller.set_spindle(False),
        "M6" : tool_change,
        "M9" : ignore, # coolant off
        "S" : set_spindle_speed,
        "comment" : ignore,
        "message" : message
        }

    for c in commands:
        if args.verbose:
            sys.stderr.write("%s\n" % c)
        try:
            ACTIONS[c["name"]](c)
        except KeyError:
            print "Ignoring unexpected command %s (line %d)" % (c["name"], c["line"])
        current += 1
        print "Command %d/%d" % (current, len(commands))

if __name__ == "__main__":
    main()
