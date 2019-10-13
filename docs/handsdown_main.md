# Handsdown: Main

- [Handsdown: Main](#handsdown-main)
  - [get_logger](#get_logger)
  - [main](#main)

> Auto-generated documentation for [handsdown.main](..//home/vlad/work/vemel/handsdown/handsdown/main.py) module.

Main CLI entrypoint for `handsdown`

#### Attributes

- `EXCLUDE_EXPRS` - Path glob expressions to always exclude.
  By default: `build/*`, `tests/*`, `test/*` are excluded.
- `SOURCES_GLOB_EXPR` - Glob expr to lokkup python source files: `**/*.py`

## get_logger

[🔍 find in source code](../handsdown/main.py#L22)

```python
def get_logger(level: int) -> logging.Logger
```

Get stdout stream logger.

#### Arguments

- `level` - Desired logging level.

#### Returns

A `logging.Logger` instance.

## main

[🔍 find in source code](../handsdown/main.py#L46)

```python
def main() -> None
```

Main entrypoint for CLI.