# pyconnect ista for Home Assistant

Home Assistant custom integration for istaConnect, powered by the `pyconnect-ista` Python package.

## Installation

Copy the `custom_components/pyconnect_ista` folder into your Home Assistant `custom_components` directory:

```text
config/
  custom_components/
    pyconnect_ista/
```

Restart Home Assistant, then add the integration from:

```text
Settings -> Devices & services -> Add integration -> ista Connect
```

For HACS, add this repository as a custom repository of type `Integration`.

## Configuration

The integration uses Home Assistant config flow. Enter your istaConnect email and password.

## Entities

The integration creates sensors for latest and historical summaries of:

- heat
- hot water
- cold water

## Debug logging

```yaml
logger:
  logs:
    custom_components.pyconnect_ista: debug
    pyconnect_ista: debug
```
