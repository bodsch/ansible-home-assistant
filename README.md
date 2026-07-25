# ansible-home-assistant

Ansible role to install, configure and operate [Home Assistant](https://www.home-assistant.io/)
(Core, in a Python virtualenv) on Linux.

> **Status:** Debian is the supported and tested target. Arch Linux support is a
> work in progress.

## How it installs

Home Assistant is installed with `pip` into a dedicated virtualenv
(`/opt/home-assistant` by default) owned by a system user. Home Assistant
**manages the Python dependencies of every enabled integration itself** at
runtime and pins them to exact versions, so the role deliberately does *not*
pre-install integration packages by hand. It only:

1. installs the distribution build toolchain and native libraries (so Home
   Assistant's runtime wheel builds succeed reliably), see `vars/debian.yml`,
2. seeds `wheel` into the virtualenv,
3. installs the `homeassistant` package, and
4. lets Home Assistant install everything else on first start.

## Requirements

- Ansible collection [`bodsch.core`](https://github.com/bodsch/ansible-collection-bodsch-core)
  (see `collections.yml`).
- A Debian-based target.

## Role variables

A selection of the most relevant variables (see `defaults/main.yml` and
`vars/main.yml` for the full set):

| Variable | Default | Description |
| --- | --- | --- |
| `home_assistant_version` | `2026.2.3` | pinned Home Assistant version; leave empty for latest |
| `home_assistant_user.owner` / `.group` | `home-assistant` | system user/group that owns the venv and runs the service |
| `home_assistant_user.home` | `/opt/home-assistant` | virtualenv **and** configuration directory |
| `home_assistant_port` | `8123` | web UI / API port |
| `home_assistant_configuration` | `{}` | merged into `configuration.yaml` |
| `home_assistant_onboarding` | *(disabled)* | headless onboarding, see below |

## Generated configuration

The role renders `configuration.yaml`, `automations.yaml`, `scripts.yaml`,
`scenes.yaml`, `logger.yaml`, `frontend.yaml` and `secrets.yaml` into the
configuration directory and (re)starts the service via a handler on change.

## Automations, scripts and scenes

These are populated from three variables (define them in `group_vars` /
`host_vars` — the role defaults are empty). Each maps onto the exact shape Home
Assistant expects, so the value you write is the value HA reads:

| Variable | Home Assistant file | Type | Merge with defaults |
| --- | --- | --- | --- |
| `home_assistant_automation` | `automations.yaml` | **list** | concatenated (`defaults + yours`) |
| `home_assistant_scripts` | `scripts.yaml` | **mapping** (`script_id: …`) | deep-merged (`combine`) |
| `home_assistant_scenes` | `scenes.yaml` | **list** | concatenated (`defaults + yours`) |

```yaml
# automations.yaml -> a LIST of automations
home_assistant_automation:
  - id: "sunset_lights"                 # stable id -> stays editable in the UI
    alias: "Living room lights at sunset"
    mode: single
    trigger:
      - platform: sun
        event: sunset
        offset: "-00:15:00"
    condition: []
    action:
      - service: light.turn_on
        target:
          entity_id: light.living_room
        data:
          brightness_pct: 60

# scripts.yaml -> a MAPPING of script_id -> definition
home_assistant_scripts:
  arrive_home:
    alias: "Arrive home"
    mode: single
    sequence:
      - service: light.turn_on
        target:
          entity_id: light.hallway
      - service: notify.persistent_notification
        data:
          message: "Welcome home"

# scenes.yaml -> a LIST of scenes
home_assistant_scenes:
  - id: "movie_time"
    name: "Movie time"
    entities:
      light.living_room:
        state: "on"
        brightness: 60
      media_player.tv:
        state: "on"
```

### Source of truth: Ansible vs. the UI

The role owns `automations.yaml` / `scenes.yaml`. Home Assistant's built-in
automation/scene **editor writes to the same files**, so the two will overwrite
each other: Ansible clobbers UI edits on the next run, and the UI clobbers
Ansible's content on save. Pick one source of truth. The clean pattern is to let
Ansible own the managed entries and give the UI its own file:

```yaml
home_assistant_configuration:
  automation: "!include automations.yaml"                # UI editor writes here
  automation manual: "!include_dir_merge_list automations.d/"  # Ansible-managed
```

### Secrets

`home_assistant_secrets` renders `secrets.yaml`. Referencing them with the
`!secret` tag inside an automation does **not** work through templating (the tag
would be emitted as a quoted string and HA would not resolve it). Either put the
real value in directly (vault it with `ansible-vault`), or keep secrets in the
UI. Open an issue if you want first-class `!secret` support.

## HACS (Home Assistant Community Store)

HACS lets you install community integrations, themes and **frontend cards**
(needed for nicer dashboards). Enable it with:

```yaml
home_assistant_hacs:
  enabled: true
  version: latest          # or pin a release tag, e.g. "2.0.5"
```

The role downloads the HACS release archive into `custom_components/hacs`; Home
Assistant installs HACS's Python dependencies on the next restart.

> **One manual step (by design):** HACS activation uses a GitHub device login,
> which cannot be automated headlessly. After the restart, add the HACS
> integration once in the UI (**Settings → Devices & Services → Add integration
> → HACS**) and enter the shown code at <https://github.com/login/device>. HACS
> updates itself from then on.

## Dashboards (YAML mode)

`home_assistant_lovelace` puts Lovelace into **YAML mode** so the role owns the
dashboard. The listed frontend cards are downloaded into `www/community/<name>/`
and registered as resources (served from `/local/community/...`), so the
dashboard renders without installing the cards through the HACS UI first.

```yaml
home_assistant_lovelace:
  enabled: true
  mode: yaml
  resources:
    - name: mushroom
      file: mushroom.js
      url: "https://github.com/piitaya/lovelace-mushroom/releases/latest/download/mushroom.js"
  dashboard:
    title: Home
    views:
      - title: Übersicht
        cards:
          - type: custom:mushroom-light-card
            entity: light.living_room
```

A complete Mushroom overview lives in
[`examples/dashboard-mushroom.yml`](examples/dashboard-mushroom.yml).

Notes:

- In YAML mode the built-in dashboard is no longer editable from the UI — the
  role's `ui-lovelace.yaml` is the source of truth. You can still create
  additional UI-managed dashboards alongside it.
- Cards downloaded by the role live under `/local/community/` and are
  independent of HACS — don't also install the same card via HACS to avoid two
  copies. HACS remains available for everything else.
- After updating a card, browsers may cache the old JS; hard-refresh once.

## Headless onboarding

Normally Home Assistant requires you to click through an onboarding wizard in
the web UI on first start (create the owner, set the location, …). This role can
pre-seed Home Assistant's `.storage` so that step is skipped and the instance
comes up fully configured.

```yaml
home_assistant_onboarding:
  enabled: true
  owner:
    name: "Bodo"
    username: "bodsch"
    password: "{{ vault_ha_admin_password }}"   # use ansible-vault!
    language: "de"
  access_token:
    enabled: true            # create a long-lived API token (see below)
  location:
    name: "Zuhause"
    latitude: 51.96
    longitude: 7.62
    time_zone: "Europe/Berlin"
    unit_system: metric
    currency: "EUR"
    country: "DE"
```

What it does:

- creates the owner user (group `system-admin`, `is_owner: true`) in
  `.storage/auth` and `.storage/auth_provider.homeassistant`. The password is
  hashed exactly the way Home Assistant does it (`base64(bcrypt(password))`),
  using the virtualenv's own `bcrypt`,
- marks all onboarding steps done in `.storage/onboarding`,
- writes the location / units into the `homeassistant:` block of
  `configuration.yaml`,
- optionally creates a long-lived access token for API automation.

### Important behaviour

- **One-time bootstrap.** The seeding only runs when `.storage/auth` does *not*
  already exist. On an instance that has been onboarded before, the step is
  skipped and **no live state is touched** (refresh tokens etc. are preserved).
  To re-seed, stop the service and remove the `.storage` directory.
- **Schema versions are release sensitive.** The storage schema versions are
  configurable under `home_assistant_onboarding.schema` with sensible defaults.
  If a Home Assistant release changes them, verify against an instance you
  onboarded manually (`cat /opt/home-assistant/.storage/onboarding`) and
  override the relevant entry.
- **The `person` store is not seeded** (`person.enabled: false`). Home Assistant
  creates a person for the owner itself, and that store carries schema
  migrations that make hand-seeding fragile. Only enable it together with a
  matching `schema.person.minor_version`.

### Using the access token

With `access_token.enabled: true` a long-lived access token is generated and
stored on the target at `home_assistant_onboarding.access_token.dest`
(`/opt/home-assistant/.ansible_access_token` by default, mode `0600`). A later
play can read it and drive the REST API:

```yaml
- name: read the generated long-lived access token
  ansible.builtin.slurp:
    src: /opt/home-assistant/.ansible_access_token
  register: _ha_token_raw
  no_log: true

- name: call the Home Assistant API
  ansible.builtin.uri:
    url: "http://127.0.0.1:8123/api/"
    headers:
      Authorization: "Bearer {{ _ha_token_raw.content | b64decode | trim }}"
    status_code: 200
  no_log: true
```

A complete, runnable example lives in
[`examples/use-access-token.yml`](examples/use-access-token.yml).

## Example playbook

```yaml
- hosts: home_assistant
  become: true
  roles:
    - role: bodsch.home_assistant
      vars:
        home_assistant_port: 8123
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
