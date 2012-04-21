# -----------------------------------------------------------------------------
# gcode_parser.py
#
# A simple gcode parser - no variables, intended to cover pcb2gcode output only
# -----------------------------------------------------------------------------

# Tokens

import itertools

command = {
    'G00' : 'RAPID_MOVE',
    'G01' : 'LINEAR_MOVE',
#    'G02' : 'CLOCKWISE_MOVE',
#    'G03' : 'COUNTER_CLOCKWISE_MOVE',
    'G04' : 'DWELL',

    'G20' : 'INCHES',
    'G21' : 'MM',

    'G90' : 'ABSOLUTE',
    'G91' : 'RELATIVE',
    'G94' : 'FEEDRATE_PER_MINUTE',
}

tokens = [
    'ARGUMENT',
    'NUMBER',
    'COMMAND',
    ]

def t_ARGUMENT(t):
    r'([XYZPF])(-?[0-9]*\.?[0-9]+)'
    t.value = (t.lexer.lexmatch.group(2), float(t.lexer.lexmatch.group(3)))
    return t

def t_COMMAND(t):
    r'[GMS][0-9]+'
    return t

def t_COMMENT(t):
    r'\(([^)]+)\)'
    pass

def t_NUMBER(t):
    r'-?[0-9]*\.?[0-9]+'
    t.value = float(t.value) if "." in t.value else int(t.value)
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")
    return None

def t_whitespace(t):
    r'[ \t]'
    pass

def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

# Build the lexer
import ply.lex as lex
lexer = lex.lex()

def parse(content):
    lexer.input(content)
    command = None
    for tok in lexer:
        if tok.type == "COMMAND":
            if command:
                yield command
            command = { "name" : tok.value, "line" : tok.lexer.lineno }
        elif tok.type == "ARGUMENT":
            tag,value = tok.value
            if tag in command:
                yield command
                command = { "name" : command["name"], "line" : tok.lexer.lineno }
            else:
                command[tag] = value

content = open("front.ngc").read()

x = list(parse(content))
print len(x)
#for c in parse(content):
#    print c


