import pytest

import cfg

def test_single_file():
    graph = cfg.ControlFlowGraph()
    graph.construct_from_file("tests/projects/single_file/main.py", False)

    assert graph.function_exists("foo")
    assert graph.function_exists("bar")
    assert not graph.function_exists("does_not_exist")
