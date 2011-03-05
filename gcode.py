"""
A simple incomplete Python g-code parser module using pyparsing

At this point it is intended to support the subset of g-code dumped by the Inkscape
gcodetools plugin. http://www.cnc-club.ru/forum/viewtopic.php?f=15&t=35&start=0

It doesn't do much by itself, see also amc2500_gcode.py for an implementation to work with the
AMC2500 CNC controller.
"""

from pyparsing import *
import sys


# Command classes for the gcode object model

class BaseCommand(object):
    def __init__(self, last_args, args, comments):
        self.comment = " ".join(comments) if isinstance(comments, list) else comments
    

class Comment(BaseCommand):
    def __init__(self, last_args, args, comments):
        BaseCommand.__init__(self, last_args, args,comments)
    def __repr__(self):
        return "Comment %s" % self.comment

class LinearCommand(BaseCommand):
    def __init__(self, last_args, args, comments):
        BaseCommand.__init__(self, last_args, args, comments)
        self.fr_x = last_args["X"]
        self.fr_y = last_args["Y"]
        self.fr_z = last_args["Z"]
        self.to_x = args.get("X", self.fr_x)
        self.to_y = args.get("Y", self.fr_y)
        self.to_z = args.get("Z", self.fr_z)
        self.f    = args.get("F", last_args["F"])
    def __repr__(self):
        return "%s (%s,%s,%s) -> (%s,%s,%s) F=%s (%s)"  % ( self.__class__.__name__, 
                                                            self.fr_x, self.fr_y, self.fr_z,    
                                                            self.to_x, self.to_y, self.to_z,
                                                            self.f, self.comment )

class G00(LinearCommand):
    """ G00 - high speed move (slew) """
    def __init__(self, last_args, args, comments):
        LinearCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return LinearCommand.__repr__(self)


class G01(LinearCommand):
    """ G01 - linear move (machine)"""
    def __init__(self, last_args, args, comments):
        LinearCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return LinearCommand.__repr__(self)
        
class G02(LinearCommand):
    """ G02 - CW 2D circular move (using IJ params)
    Currently implemented as a linear move!
    """
    def __init__(self, last_args, args, comments):
        LinearCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return LinearCommand.__repr__(self)

class G03(LinearCommand):
    """ G03 - CCW 2D circular move (using IJ params)
    Currently implemented as a linear move!
    """
    def __init__(self, last_args, args, comments):
        LinearCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return LinearCommand.__repr__(self)

class G21(BaseCommand):
    """ G21 - set mm mode. this is all we support atm anyhow ;) """
    def __init__(self, last_args, args, comments):        
        BaseCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return "G21"

class M2(BaseCommand):
    """ M2 - end of program """
    def __init__(self, last_args, args, comments):        
        BaseCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return "M2"

class M3(BaseCommand):
    """ M3 - spindle on"""
    def __init__(self, last_args, args, comments):        
        BaseCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return "M3"

class M5(BaseCommand):
    """ M5 - spindle off"""
    def __init__(self, last_args, args, comments):        
        BaseCommand.__init__(self, last_args, args, comments)
    def __repr__(self):
        return "M5"


def parse(filename):    
    """
    Evaluate a gcode file, including evaluating variable/parameter values to their final values,
    and return a list of "command objects" that can then be used for actions..
    """
    command_classes = {
                "Comment" : Comment,
                "G00" : G00,
                "G01" : G01,
                "G02" : G02,
                "G03" : G03,
                "G21" : G21,
                "M2"  : M2,
                "M3"  : M3,
                "M5"  : M5 }
    ast = script.parseString(open(filename).read()).asList()
    variables = { }    

    # trace whatever last evaluated value for these arguments was
    cur_args = { "X" : 0.0, "Y" : 0.0, "Z" : 0.0, "F" : 0.0 }

    def evaluate_expr(expr):
        if isinstance(expr, list) and len(expr) == 3 and expr[0] in opn: # expression
            res = opn[expr[0]](evaluate_expr(expr[1]), evaluate_expr(expr[2]))
            return res
        elif isinstance(expr, list) and len(expr) == 1:
            return evaluate_expr(expr[0])
        elif isinstance(expr,str) and expr in variables:
            return variables[expr]
        else:
            return expr    

    def evaluate_command(command): 
        if command[0] == "Comment":
            return command_classes["Comment"](cur_args, {}, command[1])
        if not isinstance(command[0],str):
            print "Misparsed command %s" % command
        elif command[0] in command_classes: # command
            args = [ a for a in command[1:] if not isinstance(a, list) or a[0] != "Comment" ]
            comments = [a[1] for a in command[1:] if not a in args ]            
            named_args = {}
            for a in args:
                named_args[a[0]] = evaluate_expr(a[1])
            result = command_classes[command[0]](cur_args, named_args, comments)
            cur_args.update(named_args)
            return result
        
        elif command[0].startswith("#"): # assignment
            variables[command[0]] = evaluate_expr(command[1])
        else:
            print "Unrecognised command %s" % command

    evl = [ evaluate_command(command) for command in ast if len(command) > 0 ]
    evl = [ c for c in evl if c is not None ]
    return evl

# grammar

def make_infix( toks ):
    if isinstance(toks, ParseResults) and len(toks) == 3 and toks[1] in opn:
        return [ toks[1], make_infix(toks[0]), make_infix(toks[2]) ]
    return toks

# define grammar
# basic tokens

point = Literal('.')
plusorminus = Literal('+') | Literal('-')
number = Word(nums) 
integer = Combine( Optional(plusorminus) + number )
float_number = Combine( integer +
                       Optional( point + Optional(number) )  ).setParseAction(lambda t:float(t[0]))
variable_ref = Combine( Literal("#") + integer )

# commands
expr = Forward()
command_arg = Group(Word("XYZIJKF", max=1) + expr)

comment = Literal("(").suppress() + Regex(r"[^\)]+").setParseAction(lambda t:t.insert(0,"Comment")) + Literal(")").suppress()
m_command = Combine(Literal("M") + integer) + Optional(Group(comment))
g_command = Combine(Literal("G") + integer) + ZeroOrMore(command_arg) + Optional(Group(comment))
assignment = variable_ref + Literal("=").suppress() + expr + Optional(Group(comment))                                                                      

command = (m_command | g_command | assignment) #.setParseAction(lambda t:t.insert(0,"Command"))
command_line = Group( command | comment )

ignore = ( Literal("%") )
line = LineStart() + ZeroOrMore(command_line|ignore.suppress()) + LineEnd()
script = OneOrMore(line) + StringEnd()


# arithmetic expressions
plus  = Literal( "+" )
minus = Literal( "-" )
mult  = Literal( "*" )
div   = Literal( "/" )
addop  = plus | minus
multop = mult | div
lbrk = Literal("[").suppress()
rbrk = Literal("]").suppress()
        
atom = ( float_number | integer | variable_ref ) | ( lbrk + expr + rbrk )
term = Group( atom + ZeroOrMore( ( multop + atom ) ) ).setParseAction(make_infix)
expr << ( term + ZeroOrMore( ( addop + term ) ) ).setParseAction( make_infix )

# map operator symbols to corresponding arithmetic operations
opn = { "+" : ( lambda a,b: a + b ),
        "-" : ( lambda a,b: a - b ),
        "*" : ( lambda a,b: a * b ),
        "/" : ( lambda a,b: a / b ) 
        }
 
