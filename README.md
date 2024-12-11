# Edilkamin for Home Assistant

![example_integration](doc/edilkamin.png)

This integration provides :

- binary sensor :
  - thank pellet
  - check it's already online 
- sensor :
  - get the temperature
  - get the speed of fan 1
  - get nb alarms and date of it
  - get the actual power 
- switch :
  - turn on/off the stove  
  - turn on/off the airkare function
  - turn on/off the relax function
  - turn on/off the chrono mode
  - turn on/off the schedule
- fan :
  - modify the fan 1 speed  
- climate

_Pay attention_ : If the API changes, I can't guarantee that the integration will continue to work.

## Installation

### Manual Installation
1. Download the latest release.
1. Extract the files and move the `edilakmin` folder into the path to your custom_components. e.g. /config/custom_components.
2. Restart Home Assistant
3. In the home assistant configuration screen click on Integrations.
4. Click on the + icon to add a new integration.
5. Search for `Edilakmin` and select it.
6. Enter the mac address of the stove name and click Submit.

### Installation via Home Assistant Community Store (HACS)
1. Ensure HACS is installed.
1. Add this repo (https://github.com/algra4/ha-edilkamin) has custom repo ([HACS how-to](https://hacs.xyz/docs/faq/custom_repositories))
1. Search for and install the "Edilkamin" integration
2. Restart Home Assistant
3. In the home assistant configuration screen click on Integrations.
4. Click on the + icon to add a new integration.
5. Search for `Edilakmin` and select it.
6. Enter the mac address, username and password.

## Tested device :

- Myrna 
  - motherboard : `1.58.201215a` - `1.0.200824a`
  - wifi_ble_module : `1.0_20` - `1.0.200824a`

## External dependencies

- This project uses the  [edilkamin.py](https://github.com/AndreMiras/edilkamin.py) under MIT licence

## Todo:
- [ ] create test


