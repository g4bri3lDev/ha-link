from pathlib import Path
import typer
import questionary
from ha_link import config as cfg
from ha_link.linker import (
    detect_domain,
    find_custom_components,
    find_unmanaged,
    linked_domains,
    sync_symlink,
)

app = typer.Typer(no_args_is_help=False, add_completion=False)


def _add_repo(repo_path: Path, c: cfg.Config) -> bool:
    """Shared logic: detect domain, prompt alias, append to config. Returns True if added."""
    if not repo_path.is_dir():
        typer.echo(f"Error: '{repo_path}' is not a directory.")
        return False
    domain = detect_domain(repo_path)
    if domain is None:
        typer.echo(f"Error: no custom_components/<domain>/manifest.json found in {repo_path}")
        return False
    alias = questionary.text(
        "Alias for this integration:",
        default=domain.replace("_", "-"),
    ).ask()
    if not alias:
        return False
    if any(r.alias == alias for r in c.repos):
        typer.echo(f"Error: alias '{alias}' already exists.")
        return False
    c.repos.append(cfg.Repo(alias=alias, path=str(repo_path)))
    cfg.save(c)
    typer.echo(f"Registered '{alias}' ({domain})")
    return True


def _ensure_setup() -> cfg.Config:
    """First-run wizard: guide through setting core path and registering first repo."""
    c = cfg.load()

    if not c.core_path:
        typer.echo("No HA core path configured yet.")
        path_str = questionary.path("Path to your HA core repo:").ask()
        if not path_str:
            raise typer.Exit(0)
        core_path = Path(path_str).expanduser().resolve()
        if not core_path.is_dir():
            typer.echo(f"Error: '{path_str}' is not a directory.")
            raise typer.Exit(1)
        c.core_path = str(core_path)
        cfg.save(c)
        typer.echo(f"Core set to: {core_path}\n")

    if not c.repos:
        typer.echo("No integrations registered yet.")
        if questionary.confirm("Add your first integration repo now?", default=True).ask():
            path_str = questionary.path("Path to the integration repo:").ask()
            if path_str:
                _add_repo(Path(path_str).expanduser().resolve(), c)
                c = cfg.load()

    return c


def _offer_adoption(unmanaged: list[tuple[str, Path]]) -> None:
    if not questionary.confirm(
        f"Register {len(unmanaged)} unregistered integration(s) with ha-link?",
        default=False,
    ).ask():
        return
    for _, repo_root in unmanaged:
        c = cfg.load()
        _add_repo(repo_root, c)


def _run_picker() -> None:
    c = _ensure_setup()
    if not c.repos:
        raise typer.Exit(0)

    core = Path(c.core_path)
    cc = find_custom_components(core)
    currently_linked = linked_domains(cc)
    managed_domains: set[str] = set()

    choices = []
    domain_map: dict[str, tuple[str, str]] = {}

    for repo in c.repos:
        domain = detect_domain(Path(repo.path))
        if domain is None:
            typer.echo(f"Warning: could not detect domain for '{repo.alias}' ({repo.path})")
            continue
        managed_domains.add(domain)
        domain_map[repo.alias] = (domain, repo.path)
        choices.append(
            questionary.Choice(
                title=f"{repo.alias}  ({domain})",
                value=repo.alias,
                checked=domain in currently_linked,
            )
        )

    if not choices:
        typer.echo("No valid integrations found.")
        raise typer.Exit(1)

    selected = questionary.checkbox(
        "Select integrations to activate:",
        choices=choices,
    ).ask()

    if selected is None:
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    selected_set = set(selected)
    any_change = False

    for alias, (domain, repo_path) in domain_map.items():
        result = sync_symlink(cc, Path(repo_path), domain, alias in selected_set)
        if result == "linked":
            typer.echo(f"  + Linked    {domain}")
            any_change = True
        elif result == "unlinked":
            typer.echo(f"  - Unlinked  {domain}")
            any_change = True
        elif result.startswith("error"):
            typer.echo(f"  ! {result}")

    if not any_change:
        typer.echo("  No changes.")

    unmanaged = find_unmanaged(cc, managed_domains)
    if unmanaged:
        names = ", ".join(d for d, _ in unmanaged)
        typer.echo(f"\n  {len(unmanaged)} unregistered symlink(s) left untouched: {names}")
        typer.echo("  Run `ha-link list` to review and register them.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _run_picker()


@app.command()
def add(path: str = typer.Argument(..., help="Path to the integration repo")) -> None:
    """Register a new integration repo."""
    c = cfg.load()
    _add_repo(Path(path).expanduser().resolve(), c)


@app.command()
def remove(alias: str = typer.Argument(..., help="Alias of the repo to unregister")) -> None:
    """Unregister an integration repo (does not remove any existing symlink)."""
    c = cfg.load()
    before = len(c.repos)
    c.repos = [r for r in c.repos if r.alias != alias]
    if len(c.repos) == before:
        typer.echo(f"Error: alias '{alias}' not found.")
        raise typer.Exit(1)
    cfg.save(c)
    typer.echo(f"Removed '{alias}'. Note: any existing symlink was not removed.")


@app.command(name="list")
def list_repos() -> None:
    """Show all registered repos and their current link status."""
    c = cfg.load()
    typer.echo(f"Core: {c.core_path or '(not set)'}")

    core = Path(c.core_path) if c.core_path else None
    cc = find_custom_components(core) if core else None
    typer.echo(f"custom_components: {cc or '(unknown)'}\n")

    managed_domains: set[str] = set()
    currently_linked = linked_domains(cc) if cc else set()

    if not c.repos:
        typer.echo("No integrations registered. Run `ha-link add <path>` to register one.")
    else:
        for repo in c.repos:
            domain = detect_domain(Path(repo.path)) or "?"
            managed_domains.add(domain)
            status = "✓" if domain in currently_linked else " "
            typer.echo(f"  [{status}] {repo.alias:<28} {domain:<35} {repo.path}")

    if cc:
        unmanaged = find_unmanaged(cc, managed_domains)
        for domain, repo_root in unmanaged:
            typer.echo(f"  [?] {'(unregistered)':<28} {domain:<35} {repo_root}")
        if unmanaged:
            typer.echo()
            _offer_adoption(unmanaged)


@app.command()
def set_core(path: str = typer.Argument(..., help="Path to the HA core repo")) -> None:
    """Set the path to the Home Assistant core repo."""
    core_path = Path(path).expanduser().resolve()
    if not core_path.is_dir():
        typer.echo(f"Error: '{path}' is not a directory.")
        raise typer.Exit(1)
    c = cfg.load()
    c.core_path = str(core_path)
    cfg.save(c)
    typer.echo(f"Core set to: {core_path}")
