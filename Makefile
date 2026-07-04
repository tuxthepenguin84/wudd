PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
WUDD ?= ./bin/wudd
BROWSER ?= chrome
WORKERS ?= 4
RUN_FLAGS ?=
INTEGRATION_BROWSER ?= chrome

.PHONY: help venv install test integration-test run run-download run-latest run-latest-download run-live run-live-download run-clean run-clean-download run-firefox run-firefox-download clean

define run_wudd
	$(WUDD) --browser $(BROWSER) --workers $(WORKERS) $(RUN_FLAGS) $(1)
endef

help:
	@echo "Targets:"
	@echo "  make venv                  Create .venv if it does not exist"
	@echo "  make install               Create .venv and install requirements"
	@echo "  make test                  Run the unit test suite"
	@echo "  make integration-test      Run the optional live Selenium smoke test"
	@echo "  make run                   Run the default catalog sweep"
	@echo "  make run-download          Run the default sweep and download payloads"
	@echo "  make run-latest            Run only the latest patch Tuesday results"
	@echo "  make run-latest-download   Latest patch Tuesday results plus downloads"
	@echo "  make run-live              Run live lookups without snapshot cache"
	@echo "  make run-live-download     Live lookups without snapshot cache plus downloads"
	@echo "  make run-clean             Clean outputs first, then run the default sweep"
	@echo "  make run-clean-download    Clean outputs first, then run and download"
	@echo "  make run-firefox           Run the default sweep with Firefox"
	@echo "  make run-firefox-download  Firefox plus downloads"
	@echo "  make clean                 Remove generated outputs and downloads"
	@echo "  Variables: BROWSER=$(BROWSER), WORKERS=$(WORKERS), RUN_FLAGS=\"$(RUN_FLAGS)\""

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

integration-test:
	WUDD_INTEGRATION=1 WUDD_INTEGRATION_BROWSER=$(INTEGRATION_BROWSER) $(PYTHON) -m unittest tests.test_catalog_integration -v

run:
	$(call run_wudd,)

run-download: RUN_FLAGS += --download
run-download:
	$(call run_wudd,)

run-latest: RUN_FLAGS += --latest
run-latest:
	$(call run_wudd,)

run-latest-download: RUN_FLAGS += --latest --download
run-latest-download:
	$(call run_wudd,)

run-live: RUN_FLAGS += --no-snapshot-cache
run-live:
	$(call run_wudd,)

run-live-download: RUN_FLAGS += --no-snapshot-cache --download
run-live-download:
	$(call run_wudd,)

run-clean: RUN_FLAGS += --clean
run-clean:
	$(call run_wudd,)

run-clean-download: RUN_FLAGS += --clean --download
run-clean-download:
	$(call run_wudd,)

run-firefox: BROWSER = firefox
run-firefox:
	$(call run_wudd,)

run-firefox-download: BROWSER = firefox
run-firefox-download: RUN_FLAGS += --download
run-firefox-download:
	$(call run_wudd,)

clean:
	rm -rf downloads outputs
