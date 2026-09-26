import pytest

from envlock.versions import compare_versions, same_minor


@pytest.mark.parametrize("a, b, expected", [
    ("1.0.0", "1.0.1", -1),
    ("1.10.0", "1.9.9", 1),
    ("2.0", "2.0.0", 0),
    ("2.0.0rc1", "2.0.0", -1),
    ("1.2.3-beta.1", "1.2.3", -1),
    ("v18.19.0", "20.11.1", -1),
    ("1:2.0-1", "3.0-1", 1),       # Debian epoch wins
    ("abc", "1.0", None),
])
def test_compare_versions(a, b, expected):
    assert compare_versions(a, b) == expected


def test_same_minor():
    assert same_minor("3.12.1", "3.12.9")
    assert not same_minor("3.11.4", "3.12.0")
    assert not same_minor("x", "3.12.0")
