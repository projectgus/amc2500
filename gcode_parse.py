# -----------------------------------------------------------------------------
# gcode_parser.py
#
# A simple gcode parser - no variables, intended to cover pcb2gcode output only
# -----------------------------------------------------------------------------

# Tokens

import itertools, re

R_TOKEN = r"([A-Z])(-?[0-9]*.?[0-9]+)|(\([^)]*\))|(\n)"
R_TOKEN = re.compile(R_TOKEN, re.MULTILINE)

def parse(content):
    command = { "line" : 1 }
    for tok in R_TOKEN.finditer(content):
        first_group = tok.group(1)
        if first_group is None:
            if tok.group(0) == "\n": # newline
                if command and "name" in command:
                    yield command
                command = { "line" : command["line"]+1 }
            else: # comment
                pass
        elif tok.group(2):
            if first_group in ("G","M"):
                command["name"] = tok.group(0)
            else:
                if not "name" in command:
                    command["name"] =  "G01" # default command
                command[tok.group(1)] = float(tok.group(2))

