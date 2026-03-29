import os
import yaml


def load_config(config_path):
    """Load pipeline configuration from a YAML file."""
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    return cfg


def resolve_path(base_dir, relative_path):
    """Join base_dir and relative_path, returning an absolute path."""
    return os.path.abspath(os.path.join(base_dir, relative_path))
