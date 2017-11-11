"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import io
from os import path
from setuptools import setup

here = path.dirname(__file__)

# Get the long description from the README file
with io.open(path.join(here, 'README.rst'), encoding='utf-8') as f:
  long_description = f.read()

setup(
  name='asttokens',
  version='1.1.7',
  description='Annotate AST trees with source code positions',
  long_description=long_description,
  url='https://github.com/gristlabs/asttokens',

  # Author details
  author='Dmitry Sagalovskiy, Grist Labs',
  author_email='dmitry@getgrist.com',

  # Choose your license
  license='Apache 2.0',

  # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
  classifiers=[
    # How mature is this project? Common values are
    #   3 - Alpha
    #   4 - Beta
    #   5 - Production/Stable
    'Development Status :: 4 - Beta',

    # Indicate who your project is intended for
    'Intended Audience :: Developers',

    'Topic :: Software Development :: Libraries :: Python Modules ',
    'Topic :: Software Development :: Code Generators',
    'Topic :: Software Development :: Compilers',
    'Topic :: Software Development :: Interpreters',
    'Topic :: Software Development :: Pre-processors',

    'Environment :: Console',
    'Operating System :: OS Independent',

    # Specify the Python versions you support here. In particular, ensure
    # that you indicate whether you support Python 2, Python 3 or both.
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: Implementation :: CPython',
  ],

  # What does your project relate to?
  keywords='code ast parse tokenize refactor',

  # You can just specify the packages manually here if your project is
  # simple. Or you can use find_packages().
  packages=['asttokens'],

  # List run-time dependencies here.  These will be installed by pip when
  # your project is installed. For an analysis of "install_requires" vs pip's
  # requirements files see:
  # https://packaging.python.org/en/latest/requirements.html
  install_requires=['six'],

  # List additional groups of dependencies here (e.g. development
  # dependencies). You can install these using the following syntax,
  # for example:
  # $ pip install -e .[dev,test]
  extras_require={
    'test': ['astroid', 'nose', 'coverage'],
  },
  test_suite="nose.collector",
)
