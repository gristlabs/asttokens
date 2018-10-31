dist:
	@echo Build python distribution
	python setup.py sdist bdist_wheel

publish:
	@echo "Publish to PyPI at https://pypi.python.org/pypi/asttokens/"
	@echo "Version in setup.py is `python setup.py --version`"
	@echo "Git tag is `git describe --tags`"
	@echo "Run this manually: twine upload dist/asttokens-`python setup.py --version`*"

docs:
	@echo Build documentation in docs/_build/html
	source env/bin/activate ; PYTHONPATH=$(abspath .) $(MAKE) -C docs html

clean:
	python setup.py clean
	source env/bin/activate ; PYTHONPATH=$(abspath .) $(MAKE) -C docs clean

.PHONY: dist publish docs clean
