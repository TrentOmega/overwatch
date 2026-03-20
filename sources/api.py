def fetch(source_config, since=None):
    """Stub for API-based source adapters. Extend per adapter type."""
    adapter = source_config.get("adapter", "generic")
    raise NotImplementedError(f"API adapter '{adapter}' not yet implemented")
