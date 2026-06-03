from pathlib import Path


PART2_ROOT = Path(__file__).resolve().parents[2]
SKILL_SOURCES = ["/skills"]
MEMORY_SOURCES = ["/memories/AGENTS.md"]


def build_filesystem_backend():
    from deepagents.backends import FilesystemBackend

    return FilesystemBackend(root_dir=PART2_ROOT, virtual_mode=True)
