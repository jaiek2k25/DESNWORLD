"""Allow `python -m desnworld` as an alias for `python -m desnworld.cli`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
