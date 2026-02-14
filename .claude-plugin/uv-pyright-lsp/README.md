# uv-pyright-lsp

Pyright Language Server Protocol (LSP) integration for Claude Code, launched via `uv run` for project-specific Python type checking.

## Features

- **Project-isolated Pyright**: Uses the project's own Python environment and dependencies via `uv`
- **Seamless Integration**: Provides type checking, code completion, go-to-definition, and more
- **No Global Installation**: Works with Pyright installed in the project's virtual environment

## Supported Extensions

- `.py` - Python source files
- `.pyi` - Python type stub files

## How It Works

This plugin launches Pyright LSP server using `uv run pyright-langserver --stdio`, which:

1. Runs `pyright-langserver` from the project's virtual environment
2. Communicates with Claude Code via standard input/output (stdio)
3. Provides language features like type checking, autocomplete, and navigation

## Installation

The plugin should already be enabled in this project. To verify:

```bash
# Check if plugin is loaded
claude plugin list
```

## Requirements

This plugin requires:

1. **uv** - The Python package installer (https://github.com/astral-sh/uv)
2. **Pyright** - Must be installed in the project via uv

To install Pyright in the current project:

```bash
uv add pyright
# or
uv pip install pyright
```

## Usage

Once enabled, Claude Code automatically uses this plugin for `.py` and `.pyi` files:

- **Type Checking**: Automatic type errors detection as you type
- **Code Completion**: Intelligent autocomplete based on type information
- **Go to Definition**: Navigate to function/class definitions
- **Find References**: Find all usages of a symbol
- **Refactoring**: Safe code refactoring with type checking

## Configuration

Pyright configuration is loaded from standard locations:

- `pyrightconfig.json` in project root
- `[tool.pyright]` section in `pyproject.toml`

Example `pyrightconfig.json`:

```json
{
  "include": ["src"],
  "exclude": ["**/node_modules",
    "**/__pycache__",
    "src/zzz_od/geometry"
  ],
  "ignore": [],
  "defineConstant": {
    "DEBUG": true
  },
  "stubPath": "src/typings",
  "typeCheckingMode": "standard"
}
```

## Troubleshooting

### Pyright not found

If you see errors about `pyright-langserver` not being found:

```bash
# Install pyright in the project
uv pip install pyright

# Verify installation
uv run pyright --version
```

### Type checking not working

1. Check that `pyrightconfig.json` exists and is valid
2. Verify the Python environment is correctly configured
3. Check Claude Code's LSP output for errors

### uv command not found

Install uv following official documentation: https://github.com/astral-sh/uv#installation

## Comparison with pyright-lsp

This plugin differs from the official `pyright-lsp` plugin:

| Feature | pyright-lsp | uv-pyright-lsp |
|---------|-------------|-----------------|
| Pyright installation | Global (npm/pip/pipx) | Project-local (uv) |
| Command | `pyright-langserver` | `uv run pyright-langserver` |
| Isolation | Uses global Pyright | Uses project's virtual environment |
| Best for | General Python development | Project-specific environments |

## More Information

- [Pyright Documentation](https://github.com/microsoft/pyright)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Claude Code LSP Integration](https://docs.anthropic.com/claude-code/lsp)
