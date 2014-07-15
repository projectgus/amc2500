This is a rough attempt at working with the AMC2500 stepper controller via a serial port, 
from Python code.

amc2500 is a simple Python module for sending commands to the controller
gcode is a parser for a simple subset of gcode (aiming for the commands used by Inkscape gcodetools)
jogger is a hacky WX widgets interface to get the contoller moving about

It's all implemented via sniffing the serial protocol, unsupported, and may never work properly (looks like we may be removing the
AMC2500 from our PCB Engraver and driving it directly from EMC via parallel port.)

# NOTICE

This project is no longer maintained as I moved away from the city
(Canberra) where I had access to the QuickCircuit (it belongs to [Make Hack Void hackerspace](http://makehackvoid.com/)).
[@devdsp](http://github.com/devdsp), who also did some of the original hacking,
may still be interested in it.

[Make Hack Void has a wiki page about the QuickCircuit](https://wiki.makehackvoid.com/howto:pcb_engraver), also.

The code in the master branch here includes a Python file,
`engrave_gcode.py`, which is an interactive console program that has
been successfully used to make some simple circuit boards from the
output of the [pcb2gcode](http://sourceforge.net/projects/pcb2gcode/)
script. Pics:

![Engraved PCB heated bed](http://i.imgur.com/1gHlHYom.jpg)

![Engraving a shield](http://projectgus.com/wp-content/uploads/2012/09/flatdrier-9219.jpg)

`engrave_gcode.py` is not a polished end user experience, and probably
only usable if you read the Python code first to get a rough idea what
it's about to do.

The is a second branch, "old_ui", that contains a GUI that never quite
worked beyond simple manual movements.

**I don't really recommend anyone uses any of this**. If you don't
have access to the "QuickCircuit" software, then reverse engineering
the controller box to drive the stepper motors directly will let you
use something like [LinuxCNC](http://linuxcnc.org/) or
[GRBL](http://bengler.no/grbl) and then you can borrow on all of the
accumulated community knowledge and existing documentation for these
processes, instead of talking to a relatively rare custom
controller. The wiki page linked above has a link to some plug-in
interposer boards to drive the steppers on the controller (designed by
Alastair D'Silva), although I don't think these were ever tested.

That all said, if you are interested in taking over this project (or
you have questions I might be able to answer), please let me know.
