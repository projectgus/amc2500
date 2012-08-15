#!/usr/bin/env python
import argparse, sys, termios, tty, curses, re, time, itertools, select
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
        print "Jog the controller to set up the initial pass. When done, tool should be over the origin point."
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


def _grabkey():
    """ Grab a key from stdin once one is available, but also clear any pending keyboard
    buffer to defeat keyboard repeat rate backing them up

    In the case many characters are waiting in the stdin keyboard buffer, the last pressed
    key is returned
    """
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    try:
        # call to select indicates if there is anything ready in stdin
        #
        # first call has timeout == None so blocks until something is ready,
        # subsequent calls have timeout == 0 so only poll for more characters buffered
        timeout = None
        while len(select.select([sys.stdin], [], [], timeout)[0]) > 0:
            result = sys.stdin.read(1)
            timeout = 0
        return result
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def jog_controller(controller):
    print "HJKL (capitals) to start continuous jog in a direction, any key to stop jogging."
    print "hjkl (no capitals) to nudge the head around in a direction."
    print "0-9 to set the number of steps to nudge by (0 for 1 step, 1 for 2 steps, 9 for 512 steps.)"
    print "D/U to move head Down/Up to check position or cut depth."
    print "S to toggle spindle power."
    print "QWERTY to set spindle speed 10% / 20% / 40% / 60% / 80% / 100%"
    print "I to perform an isolation width test (two horizontal 1mm lines at & above the current point.)"
    print "Type ! when you're done"
    print

    speed = pow(2,5)
    saved_speed = None
    jogging = False
    controller.set_head_down(False)
    controller.set_spindle_on(False)
    controller.save_state()
    controller.set_units_steps()
    try:
        while True:
            rc = _grabkey()
            c = rc.lower()
            if c == 'j':
                if rc == 'j':
                    controller.move_by(0,speed)
                else:
                    controller.jog(0,1)
                    jogging = True
            elif c == 'k':
                if rc == 'k':
                    controller.move_by(0, -speed)
                else:
                    controller.jog(0,-1)
                    jogging = True
            elif c == 'h':
                if rc == 'h':
                    controller.move_by(-speed,0)
                else:
                    controller.jog(-1,0)
                    jogging = True
            elif c == 'l':
                if rc == 'l':
                    controller.move_by(speed,0)
                else:
                    controller.jog(1,0)
                    jogging = True
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
                controller.set_spindle_on(not controller.get_spindle_on())
            elif c in [ 'q','w','e','r','t','y' ]:
                speed = { 'q':10, 'w':20, 'e':40, 'r':60, 't':80, 'y':99 }[c]
                controller.set_spindle_speed(speed)
            elif c == "i":
                width = raw_input("Enter the isolation width to test in mm (engraver will make two parallel 15mm lines this far apart.)\n> ")
                try:
                    width = float(width)
                    if width <= 0 or width > 10:
                        raise ValueError()
                    controller.save_state()
                    try:
                        controller.set_units_mm()
                        controller.set_speed(4) # 4mm/sec for test pass
                        controller.set_spindle_on(True)
                        controller.set_head_down(True)
                        controller.move_by(15, 0)
                        controller.set_head_down(False)
                        controller.move_by(0,width)
                        controller.set_head_down(True)
                        controller.move_by(-15, 0)
                        controller.set_head_down(False)
                        controller.set_spindle_on(False)
                        controller.move_by(0,-width)
                    finally:
                        controller.restore_state()
                    print "Finished the isolation width test"
                except ValueError:
                    print "Invalid isolation width, going back to jogging..."
            elif c == "!":
                return
            if jogging:
                _grabkey()
                controller.stop_jog()
                jogging = False
    except KeyboardInterrupt:
        controller.set_head_down(False)
        controller.set_spindle_on(False)
        sys.exit(1)
    finally:
        controller.restore_state()

def engrave(controller, commands, args):
    controller.zero_here()
    controller.set_units_mm()
    current = 0
    args.absolute = False

    def linear_move(c):
        """G00, G01"""
        is_fast = c["name"] == "G0"
        if "F" in c:
            controller.set_speed(float(c["F"])/60) # mm/min to mm/sec
        if "Z" in c:
            controller.set_head_down(c["Z"] < 0 and not args.head_up)
        if is_fast:
            controller.save_state()
            controller.set_max_speed()
        try:
            if args.absolute:
                controller.move_to(c["X"], c["Y"])
            else:
                controller.move_by(c["X"], c["Y"])
        except KeyError:
            pass
        if is_fast:
            controller.restore_state()

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
        controller.set_spindle_on(False)
        controller.set_max_speed()
        controller.move_to(0,0)

    def tool_change(c):
        """M6"""
        # move to the toolchange position
        controller.set_head_down(False)
        controller.set_spindle_on(False)
        controller.save_state()
        controller.set_units_mm()
        controller.set_max_speed()
        while controller.move_by(-200,0) == (-200,0):
            pass # drive the controller to the toolchange position, 200mm at a time
        while controller.move_by(0,-200) == (0,-200):
            pass

        print "Perform the tool change, jog the head around if necessary to make depth test cut(s)"
        print "When you're done the controller will automatically return to the correct position"
        jog_controller(controller)

        # go back to where we were
        controller.restore_state(True)

    def drill_cycle(c):
        """G81/G82"""
        controller.set_head_down(False)

        # preliminary move
        controller.save_state()
        controller.set_max_speed() # may be too fast, check for skipped steps
        if args.absolute:
            controller.move_to(c["X"],c["Y"])
        else:
            controller.move_by(c["X"],c["Y"])
        controller.restore_state()

        # drillify!
        controller.set_head_down(not args.head_up)
        time.sleep(c.get("P",1.2)) # should maybe use R & Z here to calculate a dwell period for G81... ???

        # done
        controller.set_head_down(False)

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
        "M3" : lambda c: controller.set_spindle_on(not args.no_spindle),
        "M5" : lambda c: controller.set_spindle_on(False),
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

    controller.find_corner(-1,-1)

if __name__ == "__main__":
    main()
