"""
A simple incomplete Python g-code parser module

Originally implemented using pyparsing, this was clean but v. slow so now implemented
less cleanly using regexes, string munging and python eval (ewww, I know!)

At this point it is intended to support the subset of g-code dumped by the Inkscape
gcodetools plugin. http://www.cnc-club.ru/forum/viewtopic.php?f=15&t=35&start=0

It doesn't do much by itself, see gcode_ui.py for a gcode GUI to work with the
AMC2500 CNC controller.
"""

import sys, math, re

# Command classes for the gcode object model

class BaseCommand(object):
    def __init__(self, last_args, args, comments):
        self.comment = " ".join(comments) if isinstance(comments, list) else comments

    def get_distance(self):
        """Returns the number of units spanned/travelled by this command"""
        return 0
    

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

    def get_distance(self):
        return math.hypot(self.fr_x-self.to_x, self.fr_y-self.to_y)

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
    Evaluate a gcode file, including evaluating variable/parameter
    values to their final values, and return a list of "command
    objects" that can then be used for actions..

    Parsing & intrepeting technique is a bit rough. First regexes pull
    out the major form of each line, then an evaluate pass checks all the
    values and does variable assignment, etc.  Expressions are evaluated
    by converting them to Python (variables names like #11 are converted
    to Python-safe names like V11) and then using eval().

    This hacky pile of techniques will not scale to much more
    complexity, so if more complexity is needed we should find a
    parser framework like pyparsing but with better performance.
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

    token_cmds = [ ]

    lineno=0
    for line in open(filename):
        lineno += 1        
        line = line.strip()
        if len(line) == 0 or line == "%":
            continue
        match = scan_line(line)
        if len(match) == 0:
            raise Exception("Unable to scan line #%d '%s'" % (lineno, line))

        def parse_expr(tag,simple,compl):
            if len(simple) > 0 and len(compl) > 0:
                raise Exception("Line #%d: Mis-parse of command arguments: %s %s %s" 
                                % (lineno, tag, simple, compl))
            if len(compl) == 0:
                return { "tag" : tag, "value" : float(simple) }            
            return { "tag" : tag, "expr" : compl.strip("[]").replace("#", "V") }

        if "args" in match:
            match["args"] = [ parse_expr(tag, simple, compl) for tag,simple,compl in match["args"] ]
        token_cmds.append(match)
    print len(token_cmds)

    variables = { '__builtins__': None }    

    # trace whatever last evaluated value for these arguments was
    cur_args = { "X" : 0.0, "Y" : 0.0, "Z" : 0.0, "F" : 0.0 }

    def evaluate_command(command): 
        comment = command.get("comment", "")
        if "assign" in command: # assingment
            variable = command["assign"].replace("#", "V")
            variables[variable] = eval( command["expr"].strip("[]"), variables, {} )
            return None
        elif command.get("command", None) in command_classes: # known command
            args = command["args"]
            named_args = {}
            for a in args:
                if "value" in a:
                    named_args[a["tag"]] = a["value"] # simple
                else:
                    named_args[a["tag"]] = eval( a["expr"], variables, {} )
            result = command_classes[command["command"]](cur_args, named_args, comment)
            cur_args.update(named_args)
            return result
        elif len(comment) > 0:
            return Comment(cur_args, {}, comment)
        else:
            raise Exception("Unrecognised command %s" % command)

    evl = [ evaluate_command(command) for command in token_cmds ]
    evl = [ c for c in evl if c is not None ]
    return evl


# top-level command elements

def get_cmd_arg_expr(with_tag):
    arg_tag = r"([A-Z])"
    number_arg = r"(-?\d+(?:\.\d+))"
    expr_arg = r"(\[[^\]]+\])" # args can either be simple numbers (parse by regex) or expressions (parse by pyparsing)
    return r"(?:%s(?:%s|%s))" % (arg_tag if with_tag else "", number_arg, expr_arg)    

def get_cmd_assign_expr():
    return r"(#\d+)\s*=\s*" + get_cmd_arg_expr(False)

RE_ASSIGN =  re.compile(get_cmd_assign_expr())     # ie #33 = 4 * 5 + #1
RE_CMDTAG = re.compile("^([GM]\d+)")               # ie M03 or G22
RE_CMD_ARG = re.compile(get_cmd_arg_expr(True))    # ie X3.0 or Z[#11+3]
RE_COMMENT_EOL = re.compile("(?:\(([^\)]*)\))$")   # ie (Some comment at the end of a line)

# scan a line into a dict indicating a match for one of the above common line forms
def scan_line(line):
    res = {}
    cmd = re.match(RE_CMDTAG, line)
    if cmd is not None:        # if it looks like a command, pull all the individual arguments
        args = re.findall(RE_CMD_ARG, line)
        res = { "command" : cmd.group(1), "args" : args }
    else:
        asn = re.match(RE_ASSIGN, line)
        if asn is not None:
            res = { "assign" : asn.group(1), "expr" : asn.group(2) }

    com = re.match(RE_COMMENT_EOL, line)
    if com is not None:
        res["comment"] = com.group(1)
    return res
