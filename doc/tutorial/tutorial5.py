import os
import sys
from cly import *

def do_quit():
    sys.exit(0)

def do_cat(files):
    for file in files:
        print open(os.path.expanduser(file)).read()

grammar = XMLGrammar('tutorial5.xml')
interact(grammar, data={
    'do_cat': do_cat,
    'do_quit': do_quit,
    })
