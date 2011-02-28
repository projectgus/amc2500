"""
A simple incomplete Python g-code parser module using pyparsing

At this point it is intended to support the subset of g-code dumped by the Inkscape
gcodetools plugin. http://www.cnc-club.ru/forum/viewtopic.php?f=15&t=35&start=0

It doesn't do much by itself, see also amc2500_gcode.py for an implementation to work with the
AMC2500 CNC controller.
"""

from pyparsing import *
import sys

"""
Evaluate a gcode file, including evaluating variable/parameter values to their final values,
and return a list of "command objects" that can then be used for actions.

command_classes is a dict of supported command names mapping to the classes that are instantiated, ie
{ "G00" : CmdG00,  "G01" : CmdG01,   etc. }    

Each class needs to take a constructor of the form (args, comments) where args is a dict of supplied arguments (values evaluated to floats) and comments is a list of comment strings attached to the command (normally only one.)

The function returns a list of these instantiated objects, or throws an error if a parse problem occurs.
"""
def parse(command_classes, filename):    
    ast = script.parseString(open(filename).read()).asList()
    for c in ast:
        print c
    variables = { }    

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
            return command_classes["Comment"](command[1])
        if not isinstance(command[0],str):
            print "Misparsed command %s" % command
        elif command[0] in command_classes: # command
            args = [ a for a in command[1:] if not isinstance(a, list) or a[0] != "Comment" ]
            comments = [a[1] for a in command[1:] if not a in args ]            
            named_args = {}
            for a in args:
                named_args[a[0]] = evaluate_expr(a[1])
            return command_classes[command[0]](named_args, comments)
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
 
