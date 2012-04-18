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

arguments = [ 'X','Y','Z', 'P' ]

tokens = [
    # Other tokens
    'COMMENT',
    'ARGUMENT',
    'COMMAND',
    ] + list(command.values()) + arguments

def t_COMMAND(t):
    r'[GM][0-9]+'
    t.type = command.get(t.value,'COMMAND')
    return t

def t_COMMENT(t):
    r'\(([^\)])\)'
    pass

def t_ARGUMENT(t):
    r'[%s]-?[0-9\.]+' % ''.join(arguments)
    t.type = t.value[0]
    t.value = float(t.value[1:])
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")

def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

# Build the lexer
import ply.lex as lex
lex.lex()

# Parsing rules

#precedence = (
#    ('left','PLUS','MINUS'),
#    ('left','TIMES','DIVIDE'),
#    ('right','UMINUS'),
#    )

# dictionary of names
names = { }

def p_statement_command(t):
    'statement : COMMAND arguments'
    names[t[1]] = t[3]

def p_argument_arguments(t):
    'arguments : 

def p_statement_expr(t):
    'statement : expression'
    print(t[1])


import ply.yacc as yacc
yacc.yacc()
