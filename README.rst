ASTTokens
=========

.. image:: https://img.shields.io/pypi/v/asttokens.svg
    :target: https://pypi.org/project/asttokens/
.. image:: https://img.shields.io/pypi/pyversions/asttokens.svg
    :target: https://pypi.org/project/asttokens/
.. image:: https://travis-ci.org/gristlabs/asttokens.svg?branch=master
    :target: https://travis-ci.org/gristlabs/asttokens

.. Start of user-guide

The ``asttokens`` module annotates Python abstract syntax trees (ASTs) with the positions of tokens
and text in the source code that generated them.

It makes it possible for tools that work with logical AST nodes to find the particular text that
resulted in those nodes, for example for automated refactoring or highlighting.

Installation
------------
asttokens is available on PyPI: https://pypi.python.org/pypi/asttokens/::

    pip install asttokens

The code is available on GitHub: https://github.com/gristlabs/asttokens.

Usage
-----
``asttokens`` work with both Python2 and Python3. Here's an example:

.. code-block:: python

    import asttokens, ast
    source = "Robot('blue').walk(steps=10*n)"
    atok = asttokens.ASTTokens(source)
    tree = ast.parse(source)
    atok.mark_tokens(tree)

Once the tree has been marked, nodes get ``.first_token``, ``.last_token`` attributes, and
the ``ASTTokens`` object offers helpful methods:

.. code-block:: python

    attr_node = next(n for n in ast.walk(tree) if isinstance(n, ast.Attribute), None)
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
