"""Shared execution gate. Unknown profiles fail closed; legacy is explicit default."""
import os


def runtime_mode():
    return os.getenv('HDT_RUNTIME_MODE', 'historical')


def historical_enabled():
    return runtime_mode() == 'historical'
