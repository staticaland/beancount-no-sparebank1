# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install git which is needed for the beangulp dependency
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install the project into `/app`
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Make the example scripts executable
RUN chmod +x /app/examples/uv_script_example.py

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Make the virtual environment's Python packages available to uv run
ENV PYTHONPATH="/app/.venv/lib/python3.12/site-packages:$PYTHONPATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Test that the package works by running the help command
CMD ["python", "-c", "import beancount_no_sparebank1.deposit; help(beancount_no_sparebank1.deposit.DepositAccountImporter)"]