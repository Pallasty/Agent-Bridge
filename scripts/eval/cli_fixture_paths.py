"""Platform path mapping for isolated CLI fixtures; never touches host state."""
from pathlib import Path
import sys


def database_path(root: Path, platform: str | None = None) -> Path:
    """Mirror ab_store::default_db_path with HOME/XDG rooted in the fixture.

    Resolve the fixture root so macOS /var aliases do not enter SQLite's
    NOFOLLOW boundary. Do not create links or change production path policy.
    """
    root = root.resolve(strict=True)
    platform = sys.platform if platform is None else platform
    if platform == 'darwin':
        return root / 'home/Library/Application Support/agent-bridge/state.db'
    if platform.startswith('linux'):
        return root / 'data/agent-bridge/state.db'
    raise ValueError(f'unsupported CLI fixture platform: {platform}')
