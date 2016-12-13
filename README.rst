ASTTokens
=========

.. image:: https://img.shields.io/pypi/v/asttokens.svg
    :target: https://pypi.python.org/pypi/asttokens/
.. image:: https://img.shields.io/pypi/pyversions/asttokens.svg
    :target: https://pypi.python.org/pypi/asttokens/
.. image:: https://travis-ci.org/gristlabs/asttokens.svg?branch=master
    :target: https://travis-ci.org/gristlabs/asttokens
.. image:: https://readthedocs.org/projects/asttokens/badge/?version=latest
    :target: http://asttokens.readthedocs.io/en/latest/index.html

.. Start of user-guide

The ``asttokens`` module annotates Python abstract syntax trees (ASTs) with the positions of tokens
and text in the source code that generated them.

It makes it possible for tools that work with logical AST nodes to find the particular text that
resulted in those nodes, for example for automated refactoring or highlighting.

Installation
------------
asttokens is available on PyPI: https://pypi.python.org/pypi/asttokens/::

    pip install asttokens

The code is on GitHub: https://github.com/gristlabs/asttokens.

The API Reference is here: http://asttokens.readthedocs.io/en/latest/api-index.html.

Usage
-----
ASTTokens works with both Python2 and Python3.

ASTTokens can annotate both trees built by `ast <https://docs.python.org/2/library/ast.html>`_,
AND those built by `astroid <https://www.astroid.org/>`_.

Here's an example:

.. code-block:: python

    import asttokens, ast
    source = "Robot('blue').walk(steps=10*n)"
    atok = asttokens.ASTTokens(source, parse=True)

Once the tree has been marked, nodes get ``.first_token``, ``.last_token`` attributes, and
the ``ASTTokens`` object offers helpful methods:

.. code-block:: python

    attr_node = next(n for n in ast.walk(atok.tree) if isinstance(n, ast.Attribute))
    print(atok.get_text(attr_node))
    start, end = attr_node.last_token.startpos, attr_node.last_token.endpos
    print(atok.text[:start] + 'RUN' + atok.text[end:])

Which produces this output:

.. code-block:: text

    Robot('blue').walk
    Robot('blue').RUN(steps=10*n)

The ``ASTTokens`` object also offers methods to walk and search the list of tokens that make up
the code (or a particular AST node), which is more useful and powerful than dealing with the text
directly.


Tests
-----
Tests are in the ``tests/`` subdirectory. To run all tests, run::

    nosetests
