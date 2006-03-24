PROJECT_FILE=gui.pro
TS_PROJECT_FILE=ts/ts.pro

INTERFACE_FILE=gui_interface.py
GUI_FILES=$(wildcard *.ui)
H_FILES=$(wildcard $(suffix .h,$(GUI_FILES)))
GEN_FILES=$(addsuffix .py,$(addprefix gen,$(basename $(GUI_FILES))))

.PHONY: all trans

all: $(GEN_FILES) $(INTERFACE_FILE) trans

$(INTERFACE_FILE): $(GUI_FILES) $(H_FILES) Makefile
	for file in $(GUI_FILES); do \
		pyuic -p4 -subimpl OverlayDesigner_`basename $$file .ui` $$file ; \
	done | (echo -ne '# -*- coding: utf-8 -*-\n\nfrom qt import *' ; \
	sed -e '/^[ ]*#/d ; /^from \+qt /d ; s/^from \+\([^ ]\)/from gen\1/' \
	) > $@

trans: $(TS_PROJECT_FILE)
	pylupdate $(TS_PROJECT_FILE)
	python ts/mkmock.py < ts/gui_mock.ts > ts/gui_mock.ts.NEW && mv ts/gui_mock.ts.NEW ts/gui_mock.ts

gen%.py: %.ui %.ui.h Makefile
	pyuic -p4 -o $@ -x $<

gen%.py: %.ui Makefile
	pyuic -p4 -o $@ -x $<

clean:
	rm -f $(GEN_FILES) $(INTERFACE_FILE)
