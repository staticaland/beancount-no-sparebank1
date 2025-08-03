# Examples

This directory contains example scripts demonstrating different ways to use `beancount-no-sparebank1`.

## Files

### `uv_script_example.py`
Demonstrates the **uv script dependencies** approach with `beancount-no-sparebank1`. This shows how the `# /// script` inline dependency declaration works with `uv run` to automatically install and use the package.

**Usage:**
```bash
# Make it executable (optional)
chmod +x examples/uv_script_example.py

# Run with uv - automatically installs dependencies
uv run examples/uv_script_example.py

# Or run directly if executable
./examples/uv_script_example.py
```

### `project_example.py`
Demonstrates the **uv project** approach. This script uses `beancount-no-sparebank1` within a uv project environment.

**Usage:**
```bash
# First, set up a uv project
uv init my-beancount-project
cd my-beancount-project
uv add beancount-no-sparebank1

# Copy the example script to your project
cp ../examples/project_example.py .

# Run with uv
uv run python project_example.py
```

### `local_package_test.py`
Tests the actual `beancount-no-sparebank1` package functionality. This script demonstrates the complete API usage with proper configuration.

**Usage:**
```bash
# Run in an environment where beancount-no-sparebank1 is installed
python examples/local_package_test.py
```

## Notes

- `uv_script_example.py` demonstrates the uv script approach with automatic installation of `beancount-no-sparebank1`
- `project_example.py` and `local_package_test.py` both use the package within an existing environment
- All scripts print information about the configured importers instead of actually running imports
- To use these scripts for real imports, uncomment the `ingest` lines and provide actual CSV/PDF files from SpareBank 1
- Make sure you have the necessary CSV or PDF files in your working directory when running the actual import