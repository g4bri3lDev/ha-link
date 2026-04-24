from dataclasses import dataclass, field
from pathlib import Path
import tomllib
import tomli_w

CONFIG_PATH = Path.home() / ".config" / "ha-link" / "config.toml"


@dataclass
class Repo:
    alias: str
    path: str


@dataclass
class Config:
    core_path: str = ""
    repos: list[Repo] = field(default_factory=list)


def load() -> Config:
    if not CONFIG_PATH.exists():
        return Config()
    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)
    core_path = data.get("core", {}).get("path", "")
    repos = [Repo(alias=r["alias"], path=r["path"]) for r in data.get("repos", [])]
    return Config(core_path=core_path, repos=repos)


def save(config: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if config.core_path:
        data["core"] = {"path": config.core_path}
    if config.repos:
        data["repos"] = [{"alias": r.alias, "path": r.path} for r in config.repos]
    with CONFIG_PATH.open("wb") as f:
        tomli_w.dump(data, f)
