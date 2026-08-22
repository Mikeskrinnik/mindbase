import pytest
from mindbase_shared.models import FragmentCreate, ContextQuery


def test_fragment_create_minimal():
    f = FragmentCreate(content="Hello world")
    assert f.source == "cli"
    assert f.content == "Hello world"


def test_context_query_defaults():
    q = ContextQuery(query="test")
    assert q.limit == 10
    assert q.min_importance == 0.0
