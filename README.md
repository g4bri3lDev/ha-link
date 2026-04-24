# ha-link

A small CLI tool for managing Home Assistant custom integration development against a single HA core clone.

Instead of maintaining one HA core clone per integration, `ha-link` symlinks your selected integrations into the core's `custom_components/` directory so you can switch between them with an interactive picker.

## How it works

`ha-link` maintains a list of registered integration repos and a path to your HA core clone. When you run it, you get a checkbox picker to select which integrations should be active. It then creates or removes symlinks in `{core}/config/custom_components/` accordingly.

Edits to your integration source are reflected immediately in the running HA instance — no copying needed.

## Install

```bash
cd ~/Developer/ha-link
uv tool install -e .
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
 ❯ ◉ dynamic-image  (dynamic_image)
   ◯ mvg  (munich_public_transport)
   ◯ open-epaper-link  (open_epaper_link)
   ◯ opendisplay-ha  (opendisplay)
```

### Adding a new integration

Point `ha-link add` at the repo root. It auto-detects the integration domain from `custom_components/<domain>/manifest.json` and prompts for an alias.

```bash
ha-link add ~/Developer/my-new-integration
# Alias for this integration: [my-integration] my-integration
# Registered 'my-integration' (my_integration)
```

## Config

Config lives at `~/.config/ha-link/config.toml`. You can edit it directly.

```toml
[core]
path = "/Users/you/Developer/homeassistant/core"

[[repos]]
alias = "my-integration"
path = "/Users/you/Developer/my-integration"
```

The tool expects each repo to contain a `custom_components/<domain>/` folder with a `manifest.json`. Symlinks are created at `{core}/config/custom_components/<domain>` (HA's built-in dev config directory).
