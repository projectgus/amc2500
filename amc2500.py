# Python module for control of AMC2500 CNC engraver controller. 
# Very rough, made by reverse-engineering controller commands.
#
# NB: X & Y axes are swapped between the controller hardware and this
# module.  This is because we find the AMC2500 lays out more
# comfortably with the origin at the bottom-left, and the bed in
# 'portrait' orientation.
#
#
#  Copyright (C) 2011 Angus Gratton

#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import datetime, re, time
import serial
import math
import copy
import collections

STEPS_PER_INCH=4000 # steps are 4 thou
STEPS_PER_MM=STEPS_PER_INCH/25.4

MOVEABLE_WIDTH = (431 * STEPS_PER_MM)
MOVEABLE_HEIGHT= (390 * STEPS_PER_MM)

SHORT_TIMEOUT=0.5

# Function to calculate the "central angle" property of an
# arc, which is passed to the controller.
#
# i,j is the centre of the circle - O
# arc starts from the current position of the toolhead - A
# x,y is the arc end position - B
#
# Returned value is the central angle angle AOB of this arc,
# scaled via a mystery integer constant
#
# Note that because x,y axes are swapped between software and 
# hardware, calculations also swap these axes.
def central_angle_steps( i, j, x, y, cw ):
    if not cw:
        theta1 = math.atan2(   - i,   - j)
        theta2 = math.atan2( x - i, y - j)
    else:
        theta1 = math.atan2(     i,     j)
        theta2 = math.atan2(-x + i,-y + j)
    
    central_angle = theta1-theta2

    if central_angle > 0 if cw else central_angle < 0:
      central_angle = -central_angle
    
    return central_angle * 32770


class AMCError(EnvironmentError):
    """ Exception for anything that goes wrong from the controller"""
    def __init__(self, error):
        EnvironmentError.__init__(self, (-1, error))

class AMC2500:
    """
    Class to remote control an AMC2500 w/ a Quick Circuit 5000 attached.

    Code developed through protocol reverse engineering, so who knows if it will work

    """
    def __init__(self,
                 port='/dev/ttyUSB0',
                 debug=True,
                 trace=True):

        """
        Construct a new controller on the specified serial port

        Set debug and/or trace if you want some info on stdout about
        what the controller is doing.
        """
        self.ser = self._get_serial(port)
        self.ser.open()
        self.trace=trace
        self.debug=debug
        self.limits = (0,0)
        self.jogging = False

        # set up initial state as an anonymous object, so we can save/restore it later on
        state = type("AMC2500_InternalState", (), {})()
        state.cur_step_speed = 1
        state.steps_per_unit = 1
        state.head_down = False
        state.spindle_on = False
        state.spindle_speed = -1
        state.pos = (0,0) # pos always stored in steps

        self._states = [ state ]

        self.set_units_steps()
        self._debug("Initialising controller on %s..." % port)
        self._write("IM", SHORT_TIMEOUT) # puts head up, spindle off
        self._write("EO0", SHORT_TIMEOUT)
        self.set_speed(1000, True)

    @property
    def state(self):
        return self._states[-1]

    def save_state(self):
        """
        Save the current internal state & position on the controller
        so we can restore to it later.

        Saved states can be stacked and then restored later."""
        self._states.append(copy.copy(self.state))

    def restore_state(self, move_back=False):
        """
        Restore the last saved state of the controller.
        Optionally move the controller back to its old position
        (won't work if the controller has been zeroed since saving it.)
        """
        restore = self._states[-2]
        self.set_units_steps()
        if move_back:
            self.set_head_down(False)
            self.set_spindle_on(False)
            self.set_max_speed()
            self.move_to(*restore.pos)
        else: # not moving back, so just accept where we are
            restore.pos = self.state.pos
        self.set_speed(restore.cur_step_speed)
        self.set_spindle_speed(restore.spindle_speed)
        if restore.spindle_on and not self.get_spindle_on():
            self.set_head_down(False)
        self.set_spindle_on(restore.spindle_on)
        self.set_head_down(restore.head_down)
        self.set_units(restore.steps_per_unit)
        self._states.pop()

    def _get_serial(self, port):
        return serial.Serial(port=port, baudrate=9600)

    def set_units(self, steps_per_unit):
        self._debug("Setting units to %d steps/unit" % steps_per_unit)
        self.state.steps_per_unit = float(steps_per_unit)

    def set_units_mm(self):
        return self.set_units(STEPS_PER_MM)

    def set_units_inches(self):
        return self.set_units(STEPS_PER_INCH)

    def set_units_steps(self):
        return self.set_units(1)


    def _steps_to_units(self, steps):
        if isinstance(steps, tuple):
            return tuple([ self._steps_to_units(s) for s in list(steps) ])
        return float(steps) / self.state.steps_per_unit
    def _units_to_steps(self, units):
        if isinstance(units, tuple):
            return tuple([ self._units_to_steps(u) for u in list(units) ])
        return int(float(units) * self.state.steps_per_unit)

    def get_pos(self):
        """ Get the current (estimated) absolute position of the head
        in the currently set unit
        """
        return self._steps_to_units(self.state.pos)

    def get_speed(self):
        self._steps_to_units(self.state.cur_step_speed)

    def set_max_speed(self):
        """ You can run as high as 4000steps/second but you miss steps """
        self.set_speed(self._steps_to_units(1500))

    def set_speed(self, speed, force_redundant_set=False):
        """ Set head speed (units/second for the currently set unit)

        Returns the old speed

        VM is the linear speed, when making linear moves, steps/second (linear distance)
        VS is the arc speed, when making arc moves (steps/second around the circumference)
        AT is acceleration/deceleration length, range seems to be:
        -20 (full slow acceleration) to
        1 (no acceleration) to
        20 (full acceleration)

        (No idea what that's about) Some observed values:

        When moving quick
        VS1000
        VM4000
        AT21

        When moving slow (ie probing near a limit switch)
        VS399
        VM400
        AT20

        When testing "depth of cut"
        VM6
        AT-7
        """
        if speed == 0:
            raise AMCError("Cannot set speed to 0 units/second")
        steps_per_second = max(self._units_to_steps(speed), 1)
        if self.state.cur_step_speed == steps_per_second and not force_redundant_set:
            return
        self.state.cur_step_speed = steps_per_second
        self._write("VS%d" % steps_per_second) ## ???
        self._write("VM%d" % steps_per_second)
        self._write("AT%d" % (20 if steps_per_second > 1000 else -10)) ## guesses at useful values
        self.set_spindle_speed(self.state.spindle_speed) # setting speed seems to reset this back to full speed

    def set_spindle_speed(self, ss):
        """
        Set the spindle speed

        There are two spindles that are designed for this machine.
        We have the slow spindle which runs from 1k to 5k. The fast spindle
        is speced to 25k. Valid range is 0 to 99 and any passed value
        will be clamped by this method.

        """
        changing_speed = (ss != self.state.spindle_speed) and self.state.spindle_on
        self.state.spindle_speed = ss
        ss = min(99, max(ss, 0))
        self._write_pos("SS%d" % round(ss),10)
        if changing_speed:
            time.sleep(0.3) # spindle takes time to spin up/down

    def set_head_down(self, is_down):
        """
        Move the spindle head up/down as per the is_down parameter
        
        Returns tuple of dx,dy coords but they should always be zero??
        
        How up/down exact positions are determined is not yet known!
        """
        if is_down == self.state.head_down:
            return
        res = self._write_pos("HD" if is_down else "HU", SHORT_TIMEOUT)
        self.state.head_down = is_down
        time.sleep(0.3) # head movements not instant
        return res

    def get_spindle_on(self):
        return self.state.spindle_on

    def set_spindle_on(self, spindle_on):
        """
        Turn the spindle motor on/off as per the spindle_on paramether
        """        
        if spindle_on == self.state.spindle_on:
            return
        self.state.spindle_on = spindle_on
        self._write("MO%d" % ( 1 if spindle_on else 0 ))
        self.set_spindle_speed(self.state.spindle_speed) # setting on seems to reset this back to full speed
        time.sleep(0.3) # spindle takes time to spin up/down

    def jog(self, x, y, jog_speed=1000):
        """
        Start jogging the spindle head in either or both x & y directions
        
        x & y can be positive, negative or zero but actual value is ignored.
        
        You need to follow this command with a stop_jog command
        """
        if( x != 0 and y != 0 ):
            self._error("You can't jog two axes at once")

        def jog_dir(a):
            return "0" if a == 0 else "+" if a > 0 else "-"
            
        if self.limits[0] != 0 and (x * self.limits[0] < 0) :
            self.limits = (0, self.limits[1])
        if self.limits[1] != 0 and (y * self.limits[1] < 0) :
            self.limits = (self.limits[0], 0)

        if x != 0:
            self._write("VJ%d" % jog_speed)
            self._write("JAY%s" % jog_dir(x)) # swapped hw axes
        if y != 0:
            self._write("VJ%d" % jog_speed)
            self._write("JAX%s" % jog_dir(y)) # swapped hw axes
     
        self.jogging = True
        
    def stop_jog(self):
        """
        Stop jogging and update the internal position of the motor
        
        This should always be the next command called after .jog()
        
        Returns a tuple of (dx, dy) in units jogged by if no error has occured
        """
        if not self.jogging:
            self._error("Not jogging, stop makes no sense")
        self.jogging = False
        self._write_pos("JAX0", SHORT_TIMEOUT)
        self._write_pos("JAY0", SHORT_TIMEOUT)
    
    def move_by(self, dx, dy):
        """
        Move the axis by a certain number of units dx & dy

        If successful, returns the actual number of units moved as a tuple (dx,dy)
        """
        dx_s = self._units_to_steps(dx)
        dy_s = self._units_to_steps(dy)

        return self._move_by_steps(dx_s, dy_s)

    def _move_by_steps(self, dx_s, dy_s):
        if dx_s == 0 and dy_s == 0:
            return # sending 0,0 breaks the controller

        if self.limits[0] != 0 and (dx_s * self.limits[0] < 0) :
            self.limits = (0, self.limits[1])
        if self.limits[1] != 0 and (dy_s * self.limits[1] < 0) :
            self.limits = (self.limits[0], 0)

        # todo: calculate an appropriate timeout based on our known stepping rate
        return self._write_pos("DA%d,%d,0\nGO" % (dy_s, dx_s), 180)


    def arc_by(self, dx, dy, i, j, cw):
        """
        Move by (dx,dy) units arcing around the circle centered at (i,j), Clockwise if CW else Counter Clockwise

        If successful, returns the actual number of units moved as a tuple (dx,dy)
        """
        dx_s = self._units_to_steps(dx)
        dy_s = self._units_to_steps(dy)

        i_s = self._units_to_steps(i)
        j_s = self._units_to_steps(j)

        if dx_s == 0 and dy_s == 0:
            return # sending 0,0 breaks the controller

        if i_s == 0 and j_s == 0:
            return # sending 0,0 is likely to break the controller

        if i_s == dx_s and j_s == dy_s:
            return # sending (i,j) == (dx,dy) is likely to break the controller

       	arc_s = central_angle_steps(i_s, j_s, dx_s, dy_s, cw)

        return self._write_pos("CR%d,%d,0,%d,%d,0,%d\nGO" % (j_s, i_s, 
            dy_s, dx_s, arc_s),180)

    def move_to(self, x, y):
        """
        Move the axis to an absolute position x,y based on currently known position
        """
        print "Moving to %.1f,%.1f" % (x,y)
        (x_s, y_s) = self._units_to_steps(x), self._units_to_steps(y)
        (dx_s, dy_s) = (x_s-self.state.pos[0], y_s-self.state.pos[1])
        print "Steps, moving %d,%d->%d,%d delta %d,%d" % (self.state.pos[0],self.state.pos[1],x_s,y_s,dx_s,dy_s)
        return self._move_by_steps(dx_s,dy_s)

    def arc_to(self, x, y, i, j, cw):
        """
        Move the axis to an absolute position x,y based on currently known position
        """
        (x_s, y_s) = self._units_to_steps(x), self._units_to_steps(y)        
        (dx_s, dy_s) = (x_s-self.state.pos[0], y_s-self.state.pos[1])
        (i_s, j_s) = self._units_to_steps(i), self._units_to_steps(j)        
        (di_s, dj_s) = (i_s-self.state.pos[0], j_s-self.state.pos[1])
        return self.arc_by(self._steps_to_units(dx_s), self._steps_to_units(dy_s),
                                self._steps_to_units(di_s), self._steps_to_units(dj_s),cw)


    def zero(self):
        """
        Find the zero position (X- & Y-) and zero the known coordinates on that point
        """
        return self.find_corner(-1, -1, True)

    def find_corner(self, lx, ly, zero_there=False):
        """
        Find a corner based on limits (+1 or -1 for lx & ly) and optionally
        zero the current position on it
        
        Works by stepping quickly to the limit, backing off slowly, then moving in slowly 
        to the limit again
        """

        self.set_head_down(False)
        self.set_spindle_on(False)
        self.save_state()
        fast=self._steps_to_units(2000)
        slow=self._steps_to_units(250)
        big=self._steps_to_units(80000)
        small=self._steps_to_units(1000)
        self.set_speed(fast)
        while self.limits[0] != lx:
            self.move_by(big if lx > 0 else -1*big,0)
        self.move_by(-1*small/2 if lx > 0 else small/2,0)
        self.set_speed(slow)
        self.move_by(small if lx > 0 else -1*small,0)
        if self.limits[0] != lx:
            self._error("Failed to find X limit %d, got limit value %d" % (lx, self.limits[0]))

        self.set_speed(fast)
        while self.limits[1] != ly:
            self.move_by(0, big if ly>0 else -1*big)
        self.move_by(0, -1*small/2 if ly>0 else small/2)
        self.set_speed(slow)
        self.move_by(0,small if ly > 0 else -1*small)
        if self.limits[1] != ly:
            self._error("Failed to find Y limit %d, got limit value %d" % (ly, self.limits[1]))
        self.restore_state()
        if zero_there:
            self.zero_here()

    def zero_here(self):
        """Zero the head on the current coordinates without moving it"""
        self._debug("Zeroing here (was %d,%d steps)" % self.state.pos)
        self.state.pos = (0,0)

    def reinitialise(self):
        self._debug("Reinitialising...")
        self._write("IM", SHORT_TIMEOUT) # puts head up, spindle off
        self._write("EO0", SHORT_TIMEOUT)
        self.set_speed(self.get_speed(), True)

    def _error(self, msg):
        print "%s E %s" % (ts(), msg)
    
    def _debug(self, msg):
        if self.debug:
            print "%s D %s" % (ts(), msg)
    
    def _write(self, cmd, response_timeout_s=None):
        CMD_SLEEP=0.01
        while self.ser.inWaiting() > 0:
            dumped = self.ser.read(self.ser.inWaiting())
            print "WARNING dumping unexpected %d chars '%s'" % (len(dumped),dumped)
        self.ser.write("%s\n" % cmd)
        if self.trace:
            print "%s W %s" % (ts(), cmd)
        if response_timeout_s is None:
            time.sleep(CMD_SLEEP)
        else:
            ser = self.ser
            t = ser.timeout
            ser.timeout = response_timeout_s
            rsp = []
            while 1:
                ln = ser.readline()
                rsp.append(ln)
                if self.trace:
                    print "%s R %s" % (ts(), ln)                
                if ln.startswith("ER"):
                    self._debug("Error State")
                    self.reinitialise()
                    raise AMCError("Controller Error: %s (command was %s)" % (ln[1:], cmd))
                if not (ln.startswith("OK") or ln.startswith("ES")):
                    time.sleep(CMD_SLEEP)
                if ser.inWaiting() > 0:
                        continue
                break
                    
            ser.timeout = t
            return rsp

    def _write_pos(self, cmd, response_timeout_s):
        """ Write something which will moves the head and result in an OKdx,dy,dz
        message or possibly a limit switch message.
        
        Return the dx,dy moved as a tuple (in units)
        """
        rsp = self._write(cmd, response_timeout_s)
        dpos = (0,0)
        for l in rsp:       
            at_limits = False
            #todo: parse this stuff properly
            vals = re.search(_RE_ES, l)
            emergency_stop = vals is not None            
            if vals is None:
                vals = re.search(_RE_LIMIT, l)                
                at_limits = vals is not None
            if vals is None:
                vals = re.search(_RE_OK, l)
            if vals is not None:
                vals = vals.groupdict()
                dpos = (int(vals["y"]), int(vals["x"])) # axes swapped fr h/w
                self._debug("Moved by %d,%d steps" % dpos)
                self.state.pos = (self.state.pos[0]+dpos[0], self.state.pos[1]+dpos[1])
                if emergency_stop:
                    self._debug("Emergency Stop")
                    self.reinitialise()
                    raise AMCError("Emergency Stop button was pushed")                     
                if at_limits:
                    ld = 1 if vals["dir"] == "+" else -1
                    if vals["axis"] == "Y": # axes swapped from h/w, so X
                        self.limits = (ld, self.limits[1])
                    elif vals["axis"] == "X": # Y
                        self.limits = (self.limits[0], ld)                    
                    self._debug("At limits (%d,%d)" % self.limits)
        return (self._steps_to_units(dpos[0]), self._steps_to_units(dpos[1]))


class SimController(AMC2500):
    """
    A simulated AMC2500 controller for testing.

    Simulated at the serial port level, with a test stub serial port
    """
    def __init__(self,
                 port='/dev/ttyUSB0',
                 debug=True,
                 trace=True):
        AMC2500.__init__(self, port, debug, trace)

    def _get_serial(self, port):
        return FakeSerial()

class FakeSerial:
    """ A fake AMC2500 serial port, like serial() but fakes its responses """
    def __init__(self, *args):
        self.x = 0
        self.y = 0 # track our own position
        self.timeout = None
        self.buffer = [] # what we have waiting to read back to the caller

    def open(self):
        pass

    def write(self, data):
        for line in data.split("\n"):
            move = re.search(_RE_DA, line)

            # We treat arcs as moves too
            if move is None:
              move = re.search(_RE_CR, line)

            print line
            if move is not None:
                move = move.groupdict()
                dx = int(move["x"])
                dy = int(move["y"])

                def get_limit(delta, pos, maxx):
                    pos += delta
                    limit = 0
                    if pos > maxx:
                        limit = 1
                        delta = delta - (pos - maxx)
                        pos = maxx
                    if pos < 0:
                        limit = -1
                        delta = delta + pos
                        pos = 0                
                    return (delta, pos, limit)

                (dx, self.x, limit_x) = get_limit(dx, self.x, MOVEABLE_WIDTH)
                (dy, self.y, limit_y) = get_limit(dy, self.y, MOVEABLE_HEIGHT)
                if limit_x != 0:
                    self.buffer.insert(0, "LIX%s,%d,%d,0" % ("+" if limit_x > 0 else "-", dx, dy))
                if limit_y != 0:
                    self.buffer.insert(0, "LIY%s,%d,%d,0" % ("+" if limit_y > 0 else "-", dx, dy))
                if limit_x == 0 and limit_y == 0:
                    self.buffer.insert(0, "OK%d,%d,0" % (dx, dy))
            elif line == "IM": # init command
                self.buffer.insert(0, "ES0,0,0") # emergency stop
                self.buffer.insert(1, "")
            elif re.search(r"^SS[0-9]+", line): # spindle speed
                self.buffer.insert(0, "OK")
            elif re.search(r"^EO.$", line): # echo on/off
                self.buffer.insert(0, "echo off")                
            elif re.search(r"^H.$", line): # head up/down
                self.buffer.insert(0, "OK0,0,0")
            elif line in [ "VS0", "VM0", "AT0" ]:
                raise AMCError("Cannot set a zero speed (bad command %s)" % line)
            elif line == "DA0,0,0":
                raise AMCError("Cannot set DA0,0,0 non-movement (breaks controller)")
                
            # TODO: recognise jog commands, other commands w/ responses 

        return len(data)

    def readline(self):
        if len(self.buffer) > 0:
            time.sleep(0.01)
            return self.buffer.pop(0)
        else:
            raise serial.SerialException("Called readline on an empty buffer!")

    def read(self, size):
        buf = "\n".join(self.buffer)
        self.buffer = buf[size:].split("\n")
        print "Returning %s remainder is %s" % (buf[:size], self.buffer)
        return buf[:size]

    def inWaiting(self):
        return len("\n".join(self.buffer))


_RE_AXES=r"(?P<x>[-\d]+),(?P<y>[-\d]+),(?P<z>[-\d]+)"
_RE_CIRC=r"(?P<i>[-\d]+),(?P<j>[-\d]+),(?P<k>[-\d]+)"
_RE_OK = r"OK" + _RE_AXES
_RE_ES = r"ES" + _RE_AXES
_RE_DA = r"^DA" + _RE_AXES + "$"
_RE_CR = r"^CR" + _RE_CIRC + "," + _RE_AXES +",[-\d]+$"
_RE_LIMIT = r"LI(?P<axis>.)(?P<dir>.)," + _RE_AXES

def ts():
    return datetime.datetime.now().isoformat()

