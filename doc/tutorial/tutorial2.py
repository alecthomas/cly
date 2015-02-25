import sys
from cly import *

def do_quit():
    sys.exit(0)

grammar = XMLGrammar('tutorial2.xml')
interact(grammar, data={'do_quit': do_quit})
