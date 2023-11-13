# WARNING
# This Makefile is only intended to provide aliases for developers.
# Its "build" and "install" commands have nothing to do with the usual "make build install"

.PHONY: install qa style typing tests clean build install-doc serve-doc

install:
	pip install -e .[dev]

qa: style typing tests

style:
	flake8 clyo tests

typing:
	mypy clyo tests

tests:
	py.test --cov=clyo --cov-report=term-missing --cov-report=xml:cov.xml tests

tests-x:
	py.test --cov=clyo --cov-report=term-missing --cov-report=xml:cov.xml -x tests

clean:
	rm -Rf build dist clyo.egg-info .pytest_cache

build:
	python setup.py sdist bdist_wheel

install-doc:
	pip install -e .[doc]

serve-doc:
	ENABLE_PROD=False mkdocs serve
