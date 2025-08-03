# Examples

This directory contains example scripts demonstrating different ways to use `beancount-no-sparebank1`.

## Files

### `uv_script_example.py`
Demonstrates the **uv script dependencies** approach. This script includes inline dependency declarations and can be run directly with `uv run`.

**Usage:**
```bash
# Make it executable (optional)
chmod +x examples/uv_script_example.py

# Run with uv
uv run examples/uv_script_example.py

# Or run directly if executable
./examples/uv_script_example.py
```

### `project_example.py`
Demonstrates the **uv project** approach. This script doesn't include inline dependencies and should be used within a uv project.

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

## Notes

- Both examples use the same importer configuration
- The scripts print information about the configured importers instead of actually running the import
- To use these scripts for real imports, uncomment the `ingest` lines and provide actual CSV/PDF files from SpareBank 1
- Make sure you have the necessary CSV or PDF files in your working directory when running the actual import