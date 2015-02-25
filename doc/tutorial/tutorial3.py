import os
import sys
from cly import *

def do_quit():
    sys.exit(0)

def do_cat(file):
    print 'moo'
    print open(os.path.expanduser(file)).read()

grammar = XMLGrammar('tutorial3.xml')
interact(grammar, data={
    'do_cat': do_cat,
    'do_quit': do_quit,
    })
