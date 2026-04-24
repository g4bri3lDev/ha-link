# ha-link

A small CLI tool for managing Home Assistant custom integration development against a single HA core clone.

Instead of maintaining one HA core clone per integration, `ha-link` symlinks your selected integrations into the core's `custom_components/` directory so you can switch between them with an interactive picker.

Edits to your integration source are reflected immediately in the running HA instance — no copying needed.

## Requirements

- Python 3.11+
- A local clone of [Home Assistant core](https://github.com/home-assistant/core)

## Install

```bash
pip install ha-link
# or
uv tool install ha-link
```

## First run

Run `ha-link` with no arguments. If no config is found, a short wizard guides you through setting the core path and registering your first integration repo:

```
No HA core path configured yet.
? Path to your HA core repo: ~/Developer/homeassistant/core
Core set to: /home/you/Developer/homeassistant/core

No integrations registered yet.
? Add your first integration repo now? Yes
? Path to the integration repo: ~/Developer/my-integration
? Alias for this integration: my-integration
Registered 'my-integration' (my_integration)
```

## Usage

```bash
ha-link                      # interactive picker → sync symlinks
ha-link list                 # show all registered repos and their link status
ha-link add <path>           # register a new integration repo
ha-link remove <alias>       # unregister a repo (existing symlink not removed)
ha-link set-core <path>      # change the HA core path
```

### Picker

Running `ha-link` with no arguments opens an interactive checkbox. Use arrow keys and space to toggle, enter to confirm. Already-linked integrations are pre-checked.

```
? Select integrations to activate:
 ❯ ◉ my-integration    (my_integration)
   ◯ another-one       (another_integration)
```

### Adding a new integration

Point `ha-link add` at the repo root. It auto-detects the integration domain from `custom_components/<domain>/manifest.json` and prompts for an alias.

```bash
ha-link add ~/Developer/my-new-integration
# ? Alias for this integration: [my-new-integration] my-new-integration
# Registered 'my-new-integration' (my_new_integration)
```

### Unregistered symlinks

If `ha-link list` finds symlinks in `custom_components/` that aren't registered, it marks them with `[?]` and offers to adopt them:

```
  [✓] my-integration       my_integration    ~/Developer/my-integration
  [?] (unregistered)       old_integration   ~/Developer/old-integration
```

## Config

Config lives at `~/.config/ha-link/config.toml`. You can edit it directly.

```toml
[core]
path = "/home/you/Developer/homeassistant/core"

[[repos]]
alias = "my-integration"
path = "/home/you/Developer/my-integration"

[[repos]]
alias = "another-one"
path = "/home/you/Developer/another-integration"
```

Each repo must contain a `custom_components/<domain>/manifest.json`. Symlinks are created at `{core}/config/custom_components/<domain>` if that directory exists (HA's built-in dev config), otherwise at `{core}/custom_components/<domain>`.
