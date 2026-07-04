PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help venv install test integration-test run clean

help:
	@echo "Targets:"
	@echo "  make venv     Create .venv if it does not exist"
	@echo "  make install  Create .venv and install requirements"
	@echo "  make test     Run the unit test suite"
	@echo "  make integration-test  Run the optional live Selenium smoke test"
	@echo "  make run      Run wudd with the venv python"
	@echo "  make clean    Remove generated outputs and downloads"

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

integration-test:
	WUDD_INTEGRATION=1 $(PYTHON) -m unittest tests.test_catalog_integration -v

run:
	./bin/wudd

clean:
	rm -rf downloads outputs
