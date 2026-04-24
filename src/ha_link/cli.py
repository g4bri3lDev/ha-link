from pathlib import Path
import typer
import questionary
from rich.console import Console
from rich.table import Table
from rich import box
from ha_link import config as cfg
from ha_link.linker import (
    detect_domain,
    find_custom_components,
    find_unmanaged,
    linked_domains,
    sync_symlink,
)

app = typer.Typer(no_args_is_help=False, add_completion=False)
console = Console()


def _shrink(path: Path | str) -> str:
    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def _err(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")


def _add_repo(repo_path: Path, c: cfg.Config) -> bool:
    if not repo_path.is_dir():
        _err(f"'{repo_path}' is not a directory.")
        return False
    domain = detect_domain(repo_path)
    if domain is None:
        _err(f"no custom_components/<domain>/manifest.json found in {_shrink(repo_path)}")
        return False
    alias = questionary.text(
        "Alias for this integration:",
        default=domain.replace("_", "-"),
    ).ask()
    if not alias:
        return False
    if any(r.alias == alias for r in c.repos):
        _err(f"alias '{alias}' already exists.")
        return False
    c.repos.append(cfg.Repo(alias=alias, path=str(repo_path)))
    cfg.save(c)
    console.print(f"[green]✓[/green] Registered [bold]{alias}[/bold] ({domain})")
    return True


def _ensure_setup() -> cfg.Config:
    c = cfg.load()

    if not c.core_path:
        console.print("[dim]No HA core path configured yet.[/dim]")
        path_str = questionary.path("Path to your HA core repo:").ask()
        if not path_str:
            raise typer.Exit(0)
        core_path = Path(path_str).expanduser().resolve()
        if not core_path.is_dir():
            _err(f"'{path_str}' is not a directory.")
            raise typer.Exit(1)
        c.core_path = str(core_path)
        cfg.save(c)
        console.print(f"[green]✓[/green] Core set to: {_shrink(core_path)}\n")

    if not c.repos:
        console.print("[dim]No integrations registered yet.[/dim]")
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
            console.print(f"[yellow]Warning:[/yellow] could not detect domain for '{repo.alias}' ({_shrink(repo.path)})")
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
        _err("No valid integrations found.")
        raise typer.Exit(1)

    selected = questionary.checkbox("Select integrations to activate:", choices=choices).ask()

    if selected is None:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)

    selected_set = set(selected)
    any_change = False

    for alias, (domain, repo_path) in domain_map.items():
        result = sync_symlink(cc, Path(repo_path), domain, alias in selected_set)
        if result == "linked":
            console.print(f"  [green]+[/green] Linked   {domain}")
            any_change = True
        elif result == "unlinked":
            console.print(f"  [red]-[/red] Unlinked {domain}")
            any_change = True
        elif result.startswith("error"):
            console.print(f"  [bold red]![/bold red] {result}")

    if not any_change:
        console.print("[dim]  No changes.[/dim]")

    unmanaged = find_unmanaged(cc, managed_domains)
    if unmanaged:
        names = ", ".join(d for d, _ in unmanaged)
        console.print(f"\n[yellow]  {len(unmanaged)} unregistered symlink(s) left untouched:[/yellow] {names}")
        console.print("[dim]  Run `ha-link list` to review and register them.[/dim]")


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
        _err(f"alias '{alias}' not found.")
        raise typer.Exit(1)
    cfg.save(c)
    console.print(f"Removed [bold]{alias}[/bold]. [dim]Note: any existing symlink was not removed.[/dim]")


@app.command(name="list")
def list_repos() -> None:
    """Show all registered repos and their current link status."""
    c = cfg.load()
    core = Path(c.core_path) if c.core_path else None
    cc = find_custom_components(core) if core else None

    console.print(f"[bold]Core:[/bold]              {_shrink(c.core_path) if c.core_path else '[dim](not set)[/dim]'}")
    console.print(f"[bold]custom_components:[/bold] {_shrink(cc) if cc else '[dim](unknown)[/dim]'}")

    managed_domains: set[str] = set()
    currently_linked = linked_domains(cc) if cc else set()

    if not c.repos:
        console.print("\nNo integrations registered. Run [bold]ha-link add [i]<path>[/i][/bold] to register one.")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold", pad_edge=False)
    table.add_column("", width=1, no_wrap=True)
    table.add_column("Alias", min_width=20)
    table.add_column("Domain", min_width=24)
    table.add_column("Path", style="dim")

    for repo in c.repos:
        domain = detect_domain(Path(repo.path)) or "?"
        managed_domains.add(domain)
        if domain in currently_linked:
            table.add_row("[green]✓[/green]", f"[bold]{repo.alias}[/bold]", domain, _shrink(repo.path))
        else:
            table.add_row(" ", repo.alias, domain, _shrink(repo.path))

    if cc:
        unmanaged = find_unmanaged(cc, managed_domains)
        for domain, repo_root in unmanaged:
            table.add_row("[yellow]?[/yellow]", "[dim](unregistered)[/dim]", domain, _shrink(repo_root))

    console.print(table)

    if cc:
        unmanaged = find_unmanaged(cc, managed_domains)
        if unmanaged:
            _offer_adoption(unmanaged)


@app.command()
def set_core(path: str = typer.Argument(..., help="Path to the HA core repo")) -> None:
    """Set the path to the Home Assistant core repo."""
    core_path = Path(path).expanduser().resolve()
    if not core_path.is_dir():
        _err(f"'{path}' is not a directory.")
        raise typer.Exit(1)
    c = cfg.load()
    c.core_path = str(core_path)
    cfg.save(c)
    console.print(f"[green]✓[/green] Core set to: {_shrink(core_path)}")
