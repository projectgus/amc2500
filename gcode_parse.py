# -----------------------------------------------------------------------------
# gcode_parser.py
#
# A simple gcode parser - no variables, intended to cover pcb2gcode output only
# -----------------------------------------------------------------------------

# Tokens

import itertools, re

import ply.lex as lex

class ParserException(Exception):
    pass

tokens = (
   'COMMAND',
   'SPINDLE_COMMAND',
   'PARAM',
   'COMMENT',
   'newline',
)

def t_COMMAND(t):
    r'[GMT][0-9]+'
    while len(t.value) > 2 and t.value[1] == '0': # strip M06 to M6, and such
        t.value = t.value[0] + t.value[2:]
    return t

def t_SPINDLE_COMMAND(t):
    r'S[0-9]+'
    t.value = int(t.value[1:])
    return t

def t_PARAM(t):
    r'[XYZFPR]-?([0-9]+\.)?[0-9]+'
    t.value = (t.value[0],
               float(t.value[1:]))
    return t

def t_COMMENT(t):
    r'\(([^)]*)\)'
    t.value = t.value[1:-1]
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

t_ignore  = ' \t'

def t_error(t):
    raise ParserException("Illegal character '%s' at line %d" % (t.value[0],
                                                 t.lexer.lineno))

lexer = lex.lex()

# the sticky commands are the ones where the same command may be repeated on a new line without repeating the command tag
STICKY_COMMANDS = [ "G1", "G81" ]


class ParserCtx:
    def __init__(self):
        self.command = None
        self.sticky_command = None
        self.has_args = False

def parse_command(ctx, tok):
    ctx.command = { 'name' : tok.value,
                'line' : tok.lineno,
                }
    ctx.has_args = True
    if tok.value in STICKY_COMMANDS:
        ctx.sticky_command = ctx.command

def parse_spindle_command(ctx, tok):
    ctx.command = { 'name' : 'S',
                    'line' : tok.lineno,
                    'S' : tok.value,
                    }
    ctx.has_args = True

def parse_param(ctx, tok):
    if ctx.command is None:
        raise ParserException("Got parameter without a defined command on line %d" % tok.lineno)
    ctx.command[tok.value[0]] = tok.value[1]
    ctx.command['line'] = tok.lineno
    ctx.has_args = True

def parse_newline(ctx, tok):
    old_command = ctx.command
    has_args = ctx.has_args

    try:
        ctx.command = ctx.sticky_command.copy()
    except AttributeError:
        ctx.command = None
    ctx.has_args = False

    if old_command is not None and has_args:
        return old_command

def parse_comment(ctx,tok):
    name = "message" if tok.value.startswith("MSG") else "comment"
    return { "name" : name, "value" : tok.value.strip(), "line" : tok.lineno }

PARSER_FUNCTIONS = {
    "COMMAND" : parse_command,
    "SPINDLE_COMMAND" : parse_spindle_command,
    "PARAM" : parse_param,
    "newline" : parse_newline,
    "COMMENT" : parse_comment,
    }


def parse(content):
    lexer.input(content)

    ctx = ParserCtx()
    while True:
        tok = lexer.token()
        if tok is None:
            return
        try:
            result = PARSER_FUNCTIONS[tok.type](ctx, tok)
            if result is not None:
                yield result
        except KeyError:
            raise ParserException("Unexpected token in stream: %s" % tok)
