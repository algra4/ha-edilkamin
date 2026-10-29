# Edilkamin for Home Assistant

[![Tests](https://github.com/algra4/ha-edilkamin/actions/workflows/tests.yml/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/tests.yml)
[![Dependabot Updates](https://github.com/algra4/ha-edilkamin/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/dependabot/dependabot-updates)
[![CodeQL](https://github.com/algra4/ha-edilkamin/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/algra4/ha-edilkamin/actions/workflows/github-code-scanning/codeql)



- [Edilkamin for Home Assistant](#edilkamin-for-home-assistant)
  - [Available sensors](#available-sensors)
    - [Binary sensors](#binary-sensors)
    - [Climate](#climate)
    - [Fan](#fan)
    - [Sensors](#sensors)
    - [Switches](#switches)
  - [Installation](#installation)
    - [Installation via HACS (recommended)](#installation-via-hacs-recommended)
  - [Automations](#automations)
    - [Send notification when the tank is empty](#send-notification-when-the-tank-is-empty)
  - [Send notification whe the tank has been refill](#send-notification-whe-the-tank-has-been-refill)
  - [Tested device](#tested-device)
  - [External dependencies](#external-dependencies)
  - [Thanks](#thanks)
  - [Development notes](#development-notes)



![example_integration](doc/edilkamin.png)


> [!WARNING]  
> If the API changes, I can't guarantee that the integration will continue to work.

## Available sensors

### Binary sensors

| Name    | Description |
| -------- | ------- |
| `Check configuration`  | Check if the pellet stove is available via api   |
| `Tank`  | Give the information if the pellet stove must be refill or not   |

### Climate

The climate entity is able to:
- select the target temperature
- switch the mode
  - off
  - heat
- select the preset
  - auto
  - manual p1
  - manual p2
  - manual p3
  - manual p4
  - manual p5
- control the main fan

### Fan
The Integration creates the number of fans depending on the pellet stove

| Name    | Description |
| -------- | ------- |
| `Fan ${index}`  |  Manage the fan   |

### Sensors

| Name    | Description | Unit
| -------- | ------- | ------- |
| `Temperature`  |  The actual temperature   | celsius |
| `Buffer temperature` | Buffer tank water temperature, when reported by the stove | celsius |
| `Boiler temperature` | Boiler water temperature, when reported by the stove | celsius |
| `Fan ${index}`  |  The fan speed  | int |
| `Nb alarms`  |  The number of alarms | int |
| `Actual power`  |  The pover of the pellet stove | int |
| `Operational phase`  |  The phase of the pellet stove | Off, Ignition, On, Shutdown, Cooling, Alarm, Final cleaning, Unknown |
| `Autonomy`  |  Time remaining before the pellet stove turns off if no pellets are added | minute |
| `Power ons`  |  Number of times the pellet stove has been turn on | int |
| `P1 working hours` ... `P5 working hours` | Lifetime working time at each power level | h |
| `Total working hours` | Sum of all five lifetime working-time counters | h |

Working hours come from `nvm.total_counters.p1_working_time` through
`p5_working_time`, without conversion. The hour unit was checked against the
physical remote control of a Pellkamin 10 evo plus; other models have not been
independently verified. These duration sensors use `total_increasing` because
they accumulate operating time; Home Assistant treats a decrease as a new meter
cycle. Missing or invalid counters make the affected sensor unavailable, never
zero. The total requires all five counters, including explicitly reported zeros.
The total covers P1-P5 working time, not necessarily every operating phase.
Resettable `nvm.service_counters` are deliberately not used or exposed: they must
not be mixed with lifetime hours, and their reset semantics need separate validation.

### Switches

| Name    | Description |
| -------- | ------- |
| `Airekare`  |  Switch the airekare mode   |
| `Chrono mode` | Switch the chrono mode     |
| `Relax mode`    | Switch the relax mode    |
| `Stand by mode`    | Switch the stand by mode. <br> When the Stand-by function is active, in the automatic and crono modes, the product switches off once the temperature set-point is reached and turns on again when the room temperature drops below the chosen value    |


## Installation

Click on this button:

[![Open your Home Assistant instance and open the repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg?style=flat-square)](https://my.home-assistant.io/redirect/hacs_repository/?owner=algra4&repository=ha-edilkamin&category=integration)


### Installation via HACS (recommended)
1. Ensure HACS is installed.
1. Add this repo (https://github.com/algra4/ha-edilkamin) has custom repo ([HACS how-to](https://hacs.xyz/docs/faq/custom_repositories))
1. Search for and install the "Edilkamin" integration
2. Restart Home Assistant
3. In the home assistant configuration screen click on Integrations.
4. Click on the + icon to add a new integration.
5. Search for `Edilakmin` and select it.
6. Enter the mac address and your edilkamin username and password.

<details>
  <summary>Manual Installation</summary>
  
  1. Download the latest release.
  2. Extract the files and move the `edilakmin` folder into the path to your custom_components. e.g. /config/custom_components.
  3. Restart Home Assistant
  4. In the home assistant configuration screen click on Integrations.
  5. Click on the + icon to add a new integration.
  6. Search for `Edilakmin` and select it.
  7. Enter the mac address of the pellet stove name and click Submit.
</details>


## Optional estimated pellet consumption

Disabled by default. In **Settings → Devices & services → Edilkamin → Configure**,
check **Enable pellet estimate** and enter your own per-power P1–P5 rates in
**kg/h**. Every rate is optional: leave blank for **unknown**. Zero, negative,
non-numeric and non-finite values are rejected. There are **no default rates**
and no universally applicable calibration. Saving options reloads this entry.

When enabled, the existing stove device gains:

- **Estimated pellet consumption**: a numeric cumulative kg sensor,
  `weight` / `total_increasing`, initially **0 kg**, not lifetime hours × rates.
- **Pellet estimate incomplete**: a diagnostic problem binary sensor, with a
  `reasons` attribute. It turns on if a positive increment uses an unknown rate
  (`pN_uncalibrated`), a counter decreases (`pN_counter_reset`), a calibration
  boundary skips a gap (`calibration_gap`), or arithmetic overflows.
  An unknown rate with **zero increment is fine**, including P4 and P5.

Weigh pellets and record hours between repeatable full-hopper refills to derive
your own rates. Mixed-power runs and whole-hour rounding make calibration
uncertain. This is **an estimate, not a fuel meter**.

### Accounting boundaries and limitations

- Reads `nvm.total_counters.p1_working_time` … `p5_working_time` from the
  **existing device coordinator**, never from entity IDs, the current power
  setting, service counters, or elapsed wall time. No additional API polling
  or device commands are added. No Energy dashboard, kWh, or cost entities.
- Each power starts at its **first valid reading after enabling**, which is a
  baseline only. Subsequent positive integer hour increments add
  `delta_hours × active_kg_per_hour`. Whole-hour counters give stepped readings;
  no sub-hour interpolation or startup/shutdown fuel is estimated. Unit
  verification is specific to the Pellkamin 10 evo plus, not all stove models.
- Previous valid counters, numeric kg, settings and diagnostic reasons are saved
  together in HA `.storage/edilkamin_pellet_<config_entry_id>`. Devices use
  separate coordinators and stores. Every changed transaction is awaited and
  read back from disk before being published; writes and option changes are
  serialized. Cancelled refreshes drain their shielded disk transaction before
  releasing the lock. Unloading closes the old estimator so a late refresh cannot
  overwrite the replacement instance. Back up HA storage along with config.
- Restarts, reloads and ordinary API/HA downtime with **unchanged enabled
  settings** retain baselines and count recovered increments exactly once.
  Store errors fail the coordinator update rather than publish unsaved totals;
  a subsequent successful update can retry. Corrupt or unreadable estimate
  storage is preserved and isolated: the stove integration continues without
  the estimate. Restore a backup and reload the entry to resume it; disabling
  the estimate remains possible without overwriting the damaged file. Abrupt
  OS/storage failure can still require restoring a backup; this is not a
  filesystem durability guarantee.
- Missing/malformed counters are **not zero**. Each power retains its previous
  valid baseline, so recovery can catch up with the same rate. The kg entity is
  unavailable while any counter is invalid or the coordinator update fails;
  the stored subtotal remains intact. A power missing at initial enable starts
  only at its first valid reading, not at guessed historical hours. Diagnostic
  `off` means no **detected** omitted increment, not verified complete telemetry.
- A counter decrease adds **no consumption for that power**, preserves the kg
  accumulated so far and establishes the decreased value as the next baseline.
  Later positive increments count normally. The reset leaves a sticky problem
  because usage across the reset cannot be reconstructed. A reset-and-rebound
  hidden entirely between readings cannot be detected from cumulative hours.
- **Calibration changes deliberately rebaseline, rather than settle via an
  extra API call.** Existing kg is never repriced. All five baselines are
  dropped and each power's first subsequent valid reading becomes its new
  baseline. Thus usage since the last processed sample through that reading
  is deliberately **unestimated** (possibly a long gap while offline).
  `calibration_gap` stays on, even if there was in fact no usage. The Options
  Flow persists this boundary before committing options, including when the
  entry is unloaded; setup also reconciles persisted settings after a restart.
- **Disabling** preserves kg and sticky reasons but drops baselines and removes
  the new runtime entities. Re-enabling starts new baselines and never catches
  up the disabled interval. Existing entity-registry entries may remain as
  unavailable while disabled. Fractional hours straddling a boundary cannot be
  separated by whole-hour counters: the next increment may include that
  rounding fraction. Turning estimation off does not turn the stove off.
- **Sticky means sticky:** adding a missing rate, resetting a stove counter,
  restarting HA, or disabling/re-enabling does **not** clear diagnostic history.
  There is intentionally no "clear problem" button pretending lost fuel was
  recovered. To deliberately start a **new zero-based history**, stop HA, back
  up and remove only this entry's `.storage/edilkamin_pellet_<config_entry_id>`,
  then restart. This clears kg **and** reasons and starts fresh baselines; do
  not do it just to hide an incomplete old total. The cumulative sensor's HA
  statistics may retain the prior meter cycle; do not equate those statistics
  with the newly reset native total. Never delete all of `.storage`.

## Automations

### Send notification when the tank is empty

```yaml
alias: Tank empty
triggers:
  - type: problem
    device_id: f892184070f74cfbf812bb4000cd1c58 # id of the Edilkamindevice
    entity_id: be3da6cdd182ec44f8ac6ba68e28997e # id of the binary_sensor tank 
    domain: binary_sensor
    trigger: device
actions:
  - action: notify.notify
    metadata: {}
    data:
      message: The pellet tank is almost empty, so it's time to feed it.
      title: 🔥 Pellet stove 🔥
mode: single

```

## Send notification whe the tank has been refill

```yaml
alias: Tank full
triggers:
  - type: no_problem
    device_id: f892184070f74cfbf812bb4000cd1c58 # id of the Edilkamindevice
    entity_id: be3da6cdd182ec44f8ac6ba68e28997e # id of the binary_sensor tank 
    domain: binary_sensor
    trigger: device
actions:
  - action: notify.notify
    metadata: {}
    data:
      message: The pellet tank has been filled
      title: 🔥 Pellet stove 🔥
mode: single
```

## Tested device

- Myrna 
  - motherboard : `1.58.201215a` - `1.0.200824a`
  - wifi_ble_module : `1.0_20` - `1.0.200824a`
 
- Blade H
  - platine firmware : `4.1.240802a`
  - core control pan : `4.1.241010a`

## External dependencies

- This project uses the  [edilkamin.py](https://github.com/AndreMiras/edilkamin.py) under MIT licence thanks to @AndreMiras

## Thanks
- thanks to [@nghaye](https://github.com/nghaye/ha-edilkamin) for some inspiration to improve integration

## Development notes

- Home Assistant installs this integration's runtime dependencies from `custom_components/edilkamin/manifest.json` when the integration is loaded.
- For local development and CI, dependencies are managed with `pyproject.toml` and `uv`.
  - Install dev dependencies: `uv sync`
  - Run tests: `uv run pytest -v`
- Linting/formatting uses Ruff (replacing flake8 and isort). Basic commands:
  - Lint: `uv run ruff check .`
  - Format (optional): `uv run ruff format .`


