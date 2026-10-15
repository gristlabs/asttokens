"""Exercise the optional-dependency boundary in a fresh interpreter."""
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def test_without_astroid(tmp_path):
  import coverage
  from .context import asttokens

  parent_astroid = sys.modules.get('astroid')

  # Keep astroid and asttokens already imported by other tests untouched.
  # Explicit coverage collection works with both old and new pytest-cov,
  # including when this test runs in an xdist worker.
  cov = coverage.Coverage.current()
  data_file = str(tmp_path / '.coverage')
  command = [sys.executable, str(Path(__file__).resolve())]
  if cov is not None:
    command += [data_file, str(int(cov.get_option('run:branch')))]
  env = {key: value for key, value in os.environ.items()
         if not key.startswith('COV_CORE_') and key != 'COVERAGE_PROCESS_START'}
  result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
  assert result.returncode == 0, result.stdout + result.stderr
  assert sys.modules['asttokens'] is asttokens
  assert sys.modules.get('astroid') is parent_astroid
  if cov is not None:
    data = coverage.CoverageData(basename=data_file)
    data.read()
    assert data.measured_files(), 'No coverage collected from the child interpreter'
    cov.get_data().update(data)


def check_without_astroid():
  # A fresh process is essential: clearing sys.modules in the pytest process
  # would invalidate the astroid classes held by the rest of the test suite.
  assert not any(name == 'astroid' or name.startswith('astroid.') for name in sys.modules)
  assert 'asttokens' not in sys.modules
  sys.modules['astroid'] = None
  assert importlib.util.find_spec('astroid') is None
  try:
    __import__('astroid')
  except ModuleNotFoundError:
    pass
  else:
    raise AssertionError('astroid must not be importable')

  root = Path(__file__).resolve().parents[1]
  sys.path.insert(0, str(root))
  import asttokens
  from asttokens import ASTText, ASTTokens, astroid_compat, supports_tokenless

  assert Path(asttokens.__file__).resolve() == root / 'asttokens' / '__init__.py'
  assert astroid_compat.NodeNG is None
  assert astroid_compat.BaseContainer is None
  assert astroid_compat.astroid_node_classes is None

  source = (
    "values = [1, 'two', ...]\n"
    "pair = (3, 4)\n"
    "mapping = {'key': 5}\n"
    "def example(arg, default=6, *args, flag=7, **kwargs):\n"
    "    return call(arg, key=default)\n"
  )
  for cls in (ASTTokens, ASTText):
    text = cls(source, tree=ast.parse(source))
    values, pair, mapping, func = text.tree.body
    call = func.body[0].value
    cases = [
      (values.value, "[1, 'two', ...]"),
      (values.value.elts[0], '1'),
      (values.value.elts[1], "'two'"),
      (values.value.elts[2], '...'),
      (pair.value, '(3, 4)'),
      (mapping.value, "{'key': 5}"),
      (call, 'call(arg, key=default)'),
      (call.keywords[0], 'key=default'),
      (func.args.args[0], 'arg'),
    ]
    for node, expected in cases:
      # arg also occurs in the call; the function parameter is its first occurrence.
      start = source.index(expected)
      assert text.get_text_range(node) == (start, start + len(expected)), expected
      assert text.get_text(node) == expected

    if isinstance(text, ASTText):
      # On supported interpreters these nodes need no tokens. Python 3.8
      # keywords/args and all PyPy nodes may already have needed fallback.
      if all(supports_tokenless(node) for node, _ in cases):
        assert text._asttokens is None
      assert not supports_tokenless(func.args)

    expected = 'arg, default=6, *args, flag=7, **kwargs'
    start = source.index(expected)
    assert text.get_text_range(func.args) == (start, start + len(expected))
    assert text.get_text(func.args) == expected
    if isinstance(text, ASTText):
      assert text._asttokens is not None
      assert text.asttokens.get_text(call.keywords[0]) == 'key=default'


if __name__ == '__main__':
  if len(sys.argv) > 1:
    import coverage

    child_cov = coverage.Coverage(
      data_file=sys.argv[1], config_file=False, branch=sys.argv[2] == '1',
      source=[str(Path(__file__).resolve().parents[1] / 'asttokens')],
      context='without-astroid',
    )
    child_cov.start()
    try:
      check_without_astroid()
    finally:
      child_cov.stop()
      child_cov.save()
  else:
    check_without_astroid()
