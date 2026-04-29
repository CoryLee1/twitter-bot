import os


def clean_env_value(value: str) -> str:
    return value.strip().strip('"').strip("'").strip("‘").strip("’")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return clean_env_value(value)


def env_list(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name)
    if not raw_value:
        return default

    values = [clean_env_value(item) for item in raw_value.split(",")]
    values = [item for item in values if item]
    return values or default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return clean_env_value(value).lower() in {"1", "true", "yes", "y", "on"}
