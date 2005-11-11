#!/bin/sh
PYTHONPATH="src:$PYTHONPATH" python src/slow/qtgui/gui.py $@
