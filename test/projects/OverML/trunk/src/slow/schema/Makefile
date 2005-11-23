TRANG=trang
RNGVAL=rng-val

RNC_COMMON_IMPORTS=namespaces common mathml
RNC_OVERML_IMPORTS=nala himdel slosl edsl

NO_INPUT=datatypes.rnc

############

COMMON_IMPORTS=$(addsuffix .rnc,$(RNC_COMMON_IMPORTS))
OVERML_IMPORTS=$(addsuffix .rnc,$(RNC_OVERML_IMPORTS))

RNC=$(filter-out $(NO_INPUT), $(filter-out $(COMMON_IMPORTS),$(filter-out %.m.rnc,$(wildcard *.rnc))))
RNG=$(addsuffix .rng,$(basename $(RNC)))
RNG_MODULES=$(addsuffix .m.rng,$(filter-out overml,$(basename $(RNC))))
RNC_MODULES=$(addsuffix .m.rnc,$(filter-out overml,$(basename $(RNC))))
TESTS=$(wildcard $(addsuffix .xml,$(basename $(RNC))))

.INTERMEDIATE: %.m.rnc

.PHONY: all test clean

all: rng

rng: $(RNG)
modules: $(RNG_MODULES)


test: $(addsuffix .rng,$(basename $(TESTS)))
	@for test in $(TESTS); do \
		echo "Validating $$test ..."; \
		$(RNGVAL) "$${test%xml}rng" "$$test"; \
	done

clean:
	rm -f $(RNG) $(RNG_MODULES) $(RNC_MODULES) *~

overml.rng: overml.m.rnc $(OVERML_IMPORTS)
	@echo "Building overml.rng ..."
	@cat $^ | $(TRANG) -I rnc -O rng /dev/fd/0 "$@"

%.m.rnc: %.rnc $(COMMON_IMPORTS)
	@echo "Merging components of $< ..."
	@(for file in $(filter-out $<,$^); do \
		fgrep -vq "$$file" "$<" && sed -e '/start/ s/^start /_$${file%.*}_start /g' "$$file" ; \
		echo ; \
	  done ; \
	  grep -q '^start *=' $< || sed -ne '/=/ s/^\([a-z_]\+\) *=.*/start = \1/p ; T next ; q ; :next d' "$<" ; \
	  cat "$<" ; \
	 ) > $@

%.rng: %.m.rnc
	@echo "Running $(TRANG) to build $@ from $< ..."
	@$(TRANG) -I rnc -O rng $< "$@"

%.m.rng: %.m.rnc
	@echo "Running $(TRANG) to build $@ from $< ..."
	@$(TRANG) -I rnc -O rng $< /dev/fd/1 \
	 | sed -e ':x s/\n *// ; s/<start.*<\/start>// ; N ; bx' > "$@"

%.xsd: %.rnc
	$(TRANG) $< $@

%.dtd: %.rnc
	$(TRANG) $< $@
