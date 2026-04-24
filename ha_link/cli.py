from pathlib import Path
import typer
import questionary
from ha_link import config as cfg
from ha_link.linker import detect_domain, find_custom_components, linked_domains, sync_symlink

app = typer.Typer(no_args_is_help=False, add_completion=False)


def _require_config() -> cfg.Config:
    c = cfg.load()
    if not c.core_path:
        typer.echo("No HA core path set. Run: ha-link set-core <path>")
        raise typer.Exit(1)
    if not c.repos:
        typer.echo("No repos registered. Run: ha-link add <path>")
        raise typer.Exit(1)
    return c


def _run_picker() -> None:
    c = _require_config()
    core = Path(c.core_path)
    cc = find_custom_components(core)
    currently_linked = linked_domains(cc)

    choices = []
    domain_map: dict[str, tuple[str, str]] = {}  # alias -> (domain, repo_path)

    for repo in c.repos:
        domain = detect_domain(Path(repo.path))
        if domain is None:
            typer.echo(f"Warning: could not detect domain for '{repo.alias}' ({repo.path})")
            continue
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

    if selected is None:  # user hit Ctrl-C
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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _run_picker()


@app.command()
def add(path: str = typer.Argument(..., help="Path to the integration repo")) -> None:
    """Register a new integration repo."""
    repo_path = Path(path).expanduser().resolve()
    if not repo_path.is_dir():
        typer.echo(f"Error: {repo_path} is not a directory.")
        raise typer.Exit(1)

    domain = detect_domain(repo_path)
    if domain is None:
        typer.echo(f"Error: no custom_components/<domain>/manifest.json found in {repo_path}")
        raise typer.Exit(1)

    alias = questionary.text(
        "Alias for this integration:",
        default=domain.replace("_", "-"),
    ).ask()

    if not alias:
        raise typer.Exit(0)

    c = cfg.load()
    if any(r.alias == alias for r in c.repos):
        typer.echo(f"Error: alias '{alias}' already exists.")
        raise typer.Exit(1)

    c.repos.append(cfg.Repo(alias=alias, path=str(repo_path)))
    cfg.save(c)
    typer.echo(f"Registered '{alias}' ({domain})")


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
    core_label = c.core_path or "(not set)"
    typer.echo(f"Core: {core_label}\n")

    if not c.repos:
        typer.echo("No repos registered.")
        return

    core = Path(c.core_path) if c.core_path else None
    cc = find_custom_components(core) if core else None
    currently_linked = linked_domains(cc) if cc else set()

    for repo in c.repos:
        domain = detect_domain(Path(repo.path)) or "?"
        status = "✓" if domain in currently_linked else " "
        typer.echo(f"  [{status}] {repo.alias:<28} {domain:<35} {repo.path}")


@app.command()
def set_core(path: str = typer.Argument(..., help="Path to the HA core repo")) -> None:
    """Set the path to the Home Assistant core repo."""
    core_path = Path(path).expanduser().resolve()
    if not core_path.is_dir():
        typer.echo(f"Error: {core_path} is not a directory.")
        raise typer.Exit(1)
    c = cfg.load()
    c.core_path = str(core_path)
    cfg.save(c)
    typer.echo(f"Core set to: {core_path}")
