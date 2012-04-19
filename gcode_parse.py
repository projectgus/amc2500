# -----------------------------------------------------------------------------
# gcode_parser.py
#
# A simple gcode parser - no variables, intended to cover pcb2gcode output only
# -----------------------------------------------------------------------------

# Tokens

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
    r'[XYZPF]'
    t.lexer.argument = t.value
    return t

def t_COMMAND(t):
    r'[GMS]'
    t.lexer.command = t.value
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

# Parsing rules

precedence = (
    ('left', 'NUMBER'),
    ('left','ARGUMENT'),
    ('left','COMMAND'),
)

# dictionary of names
names = { }

def p_statements_statement_noterm(t):
    'statements : statement statements'
    t[0] = [ t[1] ] + t[2]

def p_statements_statement_term(t):
    'statements : statement'
    t[0] = [ t[1] ]

def p_statement_command_args(t):
    'statement : COMMAND NUMBER arguments'
    t[0] = (t.lexer.command, t[2], t[3])

def p_statement_command_noargs(t):
    'statement : COMMAND NUMBER'
    t[0] = (t.lexer.command, t[2])

def p_arguments_argument_cont(t):
    'arguments : ARGUMENT NUMBER arguments'
    t[0] = [ (t[1], t[2]) ] + t[3]

def p_argumentlines_argument_term(t):
    'arguments : ARGUMENT NUMBER'
    t[0] = [ (t[1], t[2]) ]

def p_error(p):
    print "Syntax error in input! %s" % p


import ply.yacc as yacc
parser = yacc.yacc()
