# pylibheif

Python bindings for [libheif](https://github.com/strukturag/libheif) using `pybind11` and `scikit-build-core`.

## Overview

`pylibheif` provides high-performance Python bindings for the `libheif` library, enabling reading and writing of HEIF (HEVC), AVIF (AV1), and JPEG2000 images. It leverages `pybind11` for efficient C++/Python interoperability and uses `numpy` for zero-copy data access via the Python Buffer Protocol.

## Key Technologies

- **Python**: 3.11+
- **C++**: C++17
- **Bindings**: `pybind11`
- **Build System**: `scikit-build-core`, `CMake`, `Ninja`
- **Dependencies**: `numpy`, `libheif` (bundled), `kvazaar` (bundled), `dav1d` (bundled)
- **Testing**: `pytest`, `pytest-benchmark`

## Project Structure

- `pylibheif/`: Python package directory.
  - `__init__.py`: Package initialization and async wrappers (`AsyncHeifContext`, `AsyncHeifImageHandle`, `AsyncHeifEncoder`).
  - `_pylibheif`: (Build artifact) The compiled C++ extension module.
- `src/`: C++ implementation of the Python extension (`_pylibheif`).
  - `main.cpp`: Module definition and `pybind11` exports.
  - `context.cpp/hpp`: Wrapper for `heif_context`.
  - `image.cpp/hpp`: Wrapper for `heif_image` and `heif_image_handle`.
  - `encoder.cpp/hpp`: Wrapper for `heif_encoder`.
- `tests/`: Python test suite and benchmarks.
  - `test_pylibheif.py`: Functional tests for synchronous API.
  - `test_async.py`: Tests for asynchronous API.
  - `test_benchmark.py`: Performance benchmarks.
- `third_party/`: Bundled submodules for `libheif`, `kvazaar`, and `dav1d`.
- `pyproject.toml`: Project metadata, dependencies, and `scikit-build-core` configuration.
- `CMakeLists.txt`: Build configuration for the C++ extension and internal libraries.

## Common Commands

### Environment Setup
```bash
# Clone with submodules
git clone --recursive https://github.com/twn39/pylibheif.git
cd pylibheif

# Create virtual environment and install in editable mode
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_pylibheif.py
```

### Performance Benchmarks
```bash
# Run benchmarks
uv run pytest tests/test_benchmark.py --benchmark-only

# Run with comparison to other libraries (if installed)
uv run python tests/compare_encoders.py
```

### Code Quality
```bash
# The project includes configuration for clang-tidy and clang-format
# Run clang-format (requires clang-format installed)
find src -name "*.cpp" -o -name "*.hpp" | xargs clang-format -i
```

## Development Workflow

1.  **C++ Changes**: Modify files in `src/`. Re-run `uv pip install -e .` to rebuild the extension. `scikit-build-core` handles incremental builds efficiently.
2.  **Python Changes**: Modify tests or utility scripts. Changes take effect immediately due to the editable install.
3.  **Dependency Management**: Managed via `uv` and `pyproject.toml`.
4.  **Submodules**: Ensure submodules are initialized (`git submodule update --init --recursive`) as `CMakeLists.txt` depends on them.
