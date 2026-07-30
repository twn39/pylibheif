import pathlib
import pylibheif


def test_py_typed_file_exists():
    """Verify that py.typed marker file exists in pylibheif package."""
    pkg_dir = pathlib.Path(pylibheif.__file__).parent
    py_typed_path = pkg_dir / "py.typed"
    assert py_typed_path.exists(), "py.typed file missing from pylibheif package"


def test_all_symbols_exported():
    """Verify that all names in __all__ are accessible on pylibheif."""
    for symbol in pylibheif.__all__:
        assert hasattr(pylibheif, symbol), (
            f"Symbol {symbol} listed in __all__ but missing"
        )
