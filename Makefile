dist:
	@echo Build python distribution
	@echo "(If no 'build' module, install with 'python -m pip install build setuptools_scm')"
	python -m build

publish:
	@echo "Publish to PyPI at https://pypi.python.org/pypi/asttokens/"
	@VER=`python -c 'import setuptools_scm; print(setuptools_scm.get_version())'`; \
	echo "Version in setup.py is $$VER"; \
	echo "Git tag is `git describe --tags`"; \
	echo "Run this manually: twine upload dist/asttokens-$$VER*"

docs:
	@echo Build documentation in docs/_build/html
	source env/bin/activate ; PYTHONPATH=$(abspath .) $(MAKE) -C docs html

clean:
	python setup.py clean
	source env/bin/activate ; PYTHONPATH=$(abspath .) $(MAKE) -C docs clean

.PHONY: dist publish docs clean
