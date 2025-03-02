"""Critical fallback error messages for system-level failures."""

CRITICAL_FALLBACK = {
    'config_load_failed': "CRITICAL: Unable to load configuration: {error}",
    'yaml_not_found': "CRITICAL: Configuration file not found: {path}",
    'invalid_yaml': "CRITICAL: Invalid YAML configuration: {error}",
    'system_error': "CRITICAL: Unrecoverable system error: {error}"
}

def get_fallback_message(key: str, **kwargs) -> str:
    """Get fallback message for critical errors when config is unavailable."""
    template = CRITICAL_FALLBACK.get(key, CRITICAL_FALLBACK['system_error'])
    try:
        return template.format(**kwargs)
    except Exception as e:
        return CRITICAL_FALLBACK['system_error'].format(error=str(e))
