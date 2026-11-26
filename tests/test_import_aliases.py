import ast

import pytest

from asttokens import ASTTokens


CASES = [
  'import «a»',
  'import «a as b»',
  'import «a.b.c»',
  'import «a.b as renamed», «c.d», «e as f»',
  'import «same as alias», «same as alias»',
  'from pkg import «name»',
  'from pkg import «first as renamed», «second»',
  'from a import «a as a», «a»',
  'from . import «name as renamed»',
  'from ...pkg import «first», «second as renamed»',
  'from pkg import «*»',
  'from pkg import («first as renamed», # trailing comment\n  «second»,)',
  'from pkg import (\n  «name # between the name and as\n  as renamed»,\n)',
  'import «pkg \\\n  . module as \\\n  renamed»',
  'import «first», \\\n  «second as renamed»',
  'from pkg import \\\n  «first as renamed», «second»',
  'from K import «K as 𝕒», «é»',
  'before = 0; import «a as b», «c.d»; after = 1 # trailing comment',
  'def outer():\n  from pkg import («name as renamed»,\n    «other»,)\n',
]


def source_and_ranges(marked):
  parts = marked.split('«')
  source = parts[0]
  ranges = []
  for part in parts[1:]:
    text, tail = part.split('»')
    start = len(source)
    source += text
    ranges.append((start, len(source)))
    source += tail
  return source, ranges


@pytest.mark.parametrize('marked', CASES)
@pytest.mark.parametrize('provided_tree', [False, True])
def test_import_alias_ranges(marked, provided_tree):
  source, expected = source_and_ranges(marked)
  atok = ASTTokens(source, tree=ast.parse(source)) if provided_tree else ASTTokens(source, parse=True)
  statement = next(n for n in ast.walk(atok.tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
  assert len(statement.names) == len(expected)
  for alias, span in zip(statement.names, expected):
    assert atok.get_text_range(alias, padded=False) == span
    assert atok.get_text(alias, padded=False) == source[slice(*span)]
    tokens = list(atok.get_tokens(alias))
    assert tokens[0].startpos == span[0]
    assert tokens[-1].endpos == span[1]
  assert atok.get_text(statement, padded=False) == ast.get_source_segment(source, statement)
