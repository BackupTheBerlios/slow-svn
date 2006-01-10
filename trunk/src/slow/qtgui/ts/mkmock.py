#!/usr/bin/env python

import re, sys, os, string
from itertools import izip

re_source    = re.compile('.*<source[^>]*>([^<]+)</source[^>]*>', re.I)
re_translate = re.compile('(.*<translation)\s+type="unfinished"[^>]*>\s*(</translation.*)', re.I)

#input, output = os.popen2('chef', 'rw')
def translate(text):
    input.write(source + '\n')
    input.flush()
    return output.readline()[:-1]

TTABLE = string.maketrans(string.ascii_lowercase + string.ascii_uppercase,
                          string.ascii_uppercase + string.ascii_lowercase)

def translate(text):
    return ''.join(c.translate(TTABLE) for c in text)

def translate(text):
    upper = text.upper()
    lower = text.lower()
    return ''.join( char_pair[i&1]
                    for i, char_pair in enumerate(izip(upper, lower)) )

subst = ''
for line in sys.stdin:
    source_match = re_source.match(line)
    translate_match = re_translate.match(line)
    if source_match:
        source = source_match.group(1)
        subst  = translate(source)
        print subst,
        if subst == source:
            subst += ' bork'
        print line,
    elif translate_match:
        print translate_match.expand('\\1>%s\\2' % subst)
    else:
        print line,

#input.close()
