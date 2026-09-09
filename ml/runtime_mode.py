"""Shared execution gate. Unknown profiles fail closed; legacy is explicit default."""
import os


def runtime_mode():
    mode = os.getenv('HDT_RUNTIME_MODE', 'disabled')
    return mode if mode in {'historical', 'summary6_replay'} else 'disabled'


def historical_enabled():
    return runtime_mode() == 'historical'
