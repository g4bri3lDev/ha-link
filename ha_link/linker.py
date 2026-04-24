from pathlib import Path


def detect_domain(repo_path: Path) -> str | None:
    cc = repo_path / "custom_components"
    if not cc.is_dir():
        return None
    for sub in sorted(cc.iterdir()):
        if sub.is_dir() and (sub / "manifest.json").exists():
            return sub.name
    return None


def find_custom_components(core_path: Path) -> Path:
    # HA's built-in dev config lives at core/config/ when using script/develop
    dev_config_cc = core_path / "config" / "custom_components"
    if dev_config_cc.exists():
        return dev_config_cc
    return core_path / "custom_components"


def find_unmanaged(cc_path: Path, managed_domains: set[str]) -> list[tuple[str, Path]]:
    """Return (domain, repo_root) for symlinks in cc_path not in managed_domains."""
    if not cc_path.is_dir():
        return []
    result = []
    for p in cc_path.iterdir():
        if p.is_symlink() and p.name not in managed_domains:
            # target is repo/custom_components/domain — repo root is two levels up
            repo_root = p.resolve().parent.parent
            result.append((p.name, repo_root))
    return result


def linked_domains(cc_path: Path) -> set[str]:
    if not cc_path.is_dir():
        return set()
    return {p.name for p in cc_path.iterdir() if p.is_symlink()}


def sync_symlink(cc_path: Path, repo_path: Path, domain: str, activate: bool) -> str:
    target = repo_path / "custom_components" / domain
    link = cc_path / domain

    if activate:
        if link.is_symlink():
            if link.resolve() == target.resolve():
                return "unchanged"
            link.unlink()
        elif link.exists():
            return f"error: {link} exists and is not a symlink — skipping"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        return "linked"
    else:
        if link.is_symlink():
            link.unlink()
            return "unlinked"
        return "unchanged"

