# Python module for control of AMC2500 CNC engraver controller. 
# Very rough, made by reverse-engineering controller commands.
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

STEPS_PER_MM=(1/0.006350)
MAX_RPM=5000
MIN_RPM=1000

SHORT_TIMEOUT=0.5

"""
Class to remote control an AMC2500 w/ a Quick Circuit 5000 attached.

Code developed through protocol reverse engineering, so who knows if it will work

Notable properties:

pos - this is where the controller thinks it is, in steps

"""
class AMC2500:

    """
    Construct a new controller on the specified serial port
    
    Set debug and/or trace if you want some info on stdout about 
    what the controller is doing.
    """
    def __init__(self, 
                 port='/dev/ttyUSB0',
                 debug=True,
                 trace=True):
        self.ser = serial.Serial(
            port=port,
            baudrate=9600)
        self.ser.open()
        self.trace=trace
        self.debug=debug
        self.pos = (0,0)  # pos is always stored internally in steps
        self.limits = (0,0) # x and y, each limit state can be 0,-1,1 for Off,-,+
        self.jogging = False
        self.set_units_steps()
        self._debug("Initialising controller on %s..." % port)
        self._write("IM", SHORT_TIMEOUT)
        self._write("EO0", SHORT_TIMEOUT)
        self.set_speed(4000)
    

    def set_units(self, steps_per_unit):
        self._debug("Setting units to %d steps/unit" % steps_per_unit)
        self.steps_per_unit = steps_per_unit

    def set_units_mm(self):
        self.set_units(STEPS_PER_MM)
                
    def set_units_steps(self):
        self.set_units(1)


    def _steps_to_units(self, steps):
        if isinstance(steps, tuple):
            return tuple([ self._steps_to_units(s) for s in list(steps) ])
        return steps / self.steps_per_unit
    def _units_to_steps(self, units):
        if isinstance(units, tuple):
            return tuple([ self._units_to_steps(u) for u in list(units) ])
        return units * self.steps_per_unit

    
    """ Get the current (estimated) absolute position of the head
        in the currently set unit
    """
    def get_pos(self):
        return self._steps_to_units(self.pos)

    """ Set head speed (units/second for the currently set unit)

        Two unknown commands here - VSxxx & ATxx

        VM is definitely head speed, steps/second. Seems to apply whether motor is on
        or off, head up or down. Others maybe acceleration? Apply in some other cases??

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
    def set_speed(self, speed):    
        self.speed = speed
        steps_per_second = int(self._units_to_steps(speed))
        self._write("VS%d" % (steps_per_second / 4)) ## ???                
        self._write("VM%d" % steps_per_second)
        self._write("AT%d" % (20 if steps_per_second > 1000 else 10)) ## ??

    """
    Set the spindle speed in rpm

    This one is internally a bit confusing, the jog dialog gives 1000rpm=0, 5000rpm=99
    but the other UI says up to 24000rpm so maybe you can go above 99
    """
    def set_spindle_speed(self, rpm):
        if rpm > MAX_RPM:
            rpm = MAX_RPM
        if rpm < MIN_RPM:
            rpm = MIN_RPM
        ss = 100.0 * (rpm - MIN_RPM)/(MAX_RPM - MIN_RPM)
        self._write("SS%d" % round(ss))

    """
    Move the spindle head up/down as per the is_down parameter

    Returns tuple of dx,dy coords but they should always be zero??

    How up/down exact positions are determined is not yet known!
    """
    def head_down(self, is_down):
        return self._write_pos("HD" if is_down else "HU", SHORT_TIMEOUT)

    """
    Turn the spindle motor on/off as per the spindle_on paramether
    """
    def spindle(self, spindle_on):
        self._write("MO%d" % ( 1 if spindle_on else 0 ))

    """
    Start jogging the spindle head in either or both x & y directions
    
    x & y can be positive, negative or zero but actual value is ignored.

    You need to follow this command with a stop_jog command
    """
    def jog(self, x, y, jog_speed=1000):
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
        self._write("JAX%s" % jog_dir(x))
      if y != 0:
        self._write("VJ%d" % jog_speed)
        self._write("JAY%s" % jog_dir(y))
     
      self.jogging = True
        
    """
    Stop jogging and update the internal position of the motor

    This should always be the next command called after .jog()

    Returns a tuple of (dx, dy) in units jogged by if no error has occured
    """
    def stop_jog(self):
        if not self.jogging:
            self._error("Not jogging, stop makes no sense")
        self.jogging = False
        self._write_pos("JAX0", SHORT_TIMEOUT)
        self._write_pos("JAY0", SHORT_TIMEOUT)
    
    """
    Move the axis by a certain number of units dx & dy

    If successful, returns the actual number of units moved as a tuple (dx,dy)
    """
    def move_by(self, dx, dy):
        if self.limits[0] != 0 and (dx * self.limits[0] < 0) :
            self.limits = (0, self.limits[1])
        if self.limits[1] != 0 and (dy * self.limits[1] < 0) :
            self.limits = (self.limits[0], 0)
      
        dx_s = self._units_to_steps(dx)
        dy_s = self._units_to_steps(dy)
        if(int(dx_s) == 0 and int(dy_s) == 0):
            return # sending 0,0 breaks the controller

        # todo: calculate an appropriate timeout based on our known stepping rate
        return self._write_pos("DA%d,%d,0\nGO" % (self._units_to_steps(dx), 
                                      self._units_to_steps(dy)), 180)
    
    """
    Move the axis to an absolute position x,y based on currently known position
    """
    def move_to(self, x, y):
        (x_s, y_s) = self._units_to_steps(x), self._units_to_steps(y)        
        (dx_s, dy_s) = (x_s-self.pos[0], y_s-self.pos[1])
        return self.move_by(self._steps_to_units(dx_s), self._steps_to_units(dy_s))

    """
    Find the zero position (X- & Y-) and zero the known coordinates on that point
    """
    def zero(self):
        return self.find_corner(-1, -1, True)

    """
    Find a corner based on limits (+1 or -1 for lx & ly) and optionally
    zero the current position on it

    Works by stepping quickly to the limit, backing off slowly, then moving in slowly to the limit again
    """
    def find_corner(self, lx, ly, zero_there=False):
        self.head_down(False)
        self.spindle(False)
        old_speed=self.speed
        fast=self._steps_to_units(8000)
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
        self.set_speed(old_speed)
        if zero_there:
            self.zero_here()

    """
    Zero the head on the current coordinates without moving it
    """
    def zero_here(self):
        self._debug("Zeroing here (was %d,%d steps)" % self.pos)
        self.pos = (0,0)

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
        if response_timeout_s is not None:
            ser = self.ser
            t = ser.timeout
            ser.timeout = response_timeout_s
            rsp = []
            while 1:
                ln = ser.readline()
                rsp.append(ln)
                if self.trace:
                    print "%s R %s" % (ts(), ln)                
                if not ln.startswith("OK"):
                    time.sleep(CMD_SLEEP)
                if ser.inWaiting() > 0:
                        continue
                break
                    
            ser.timeout = t
            return rsp

    
        

    """ Write something which will moves the head and result in an OKdx,dy,dz
    message or possibly a limit switch message.

    Return the dx,dy moved as a tuple (in units)
    """
    def _write_pos(self, cmd, response_timeout_s):
        rsp = self._write(cmd, response_timeout_s)
        dpos = (0,0)
        for l in rsp:            
            vals = re.search(_RE_OK, l)
            if vals is None:
                vals = re.search(_RE_LIMIT, l)                
            if vals is not None:
                vals = vals.groupdict()
                dpos = (int(vals["x"]), int(vals["y"]))
                self._debug("Moved by %d,%d steps" % dpos)
                self.pos = (self.pos[0]+dpos[0], self.pos[1]+dpos[1])
                if "axis" in vals: 
                    ld = 1 if vals["dir"] == "+" else -1
                    if vals["axis"] == "X":
                        self.limits = (ld, self.limits[1])
                    elif vals["axis"] == "Y":
                        self.limits = (self.limits[0], ld)                    
                    self._debug("At limits (%d,%d)" % self.limits)
        return (self._steps_to_units(dpos[0]), self._steps_to_units(dpos[1]))

_RE_AXES=r"(?P<x>[-\d]+),(?P<y>[-\d]+),(?P<z>[-\d]+)"
_RE_OK = r"OK" + _RE_AXES
_RE_LIMIT = r"LI(?P<axis>.)(?P<dir>.)," + _RE_AXES

def ts():
    return datetime.datetime.now().isoformat()

