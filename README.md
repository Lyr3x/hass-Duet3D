# Duet3D integration for Home Assistant

Code Based on the OctoPrint integration from Hass: [octoprint integration github](https://github.com/home-assistant/home-assistant/tree/dev/homeassistant/components/octoprint)

This is a work in progress, the code is working but there is still lots to do

## Installation

### From HACS

1. Install HACS if you haven't already (see [installation guide](https://hacs.netlify.com/docs/installation/manual)).
2. Add custom repository `https://github.com/garethbradley/hass-Duet3D` as "Integration" in the settings tab of HACS.
3. Find and install "Duet3D" integration in HACS's "Integrations" tab.
4. Restart your Home Assistant.

### Manual

1. Download and unzip the [repo archive](https://github.com/garethbradley/hass-Duet3D/archive/master.zip). (You could also click "Download ZIP" after pressing the green button in the repo, alternatively, you could clone the repo from SSH add-on).
2. Copy contents of the archive/repo into your `/config` directory.
3. Restart your Home Assistant.

### Config
The following configuration is taken from the excellent article: [Getting started with Duet Wifi, RepRapFirmware, and Home Assistant](https://begala.io/home-assistant/duet-wifi-feat-home-assistant/).

Add the following config to the `/config/configuration.yaml` file:

```yaml
# Duet Integration
duet3d:
  host: !secret duet3d-host
  name: !secret duet3d-name
  number_of_tools: 1
  bed: true
  sensors:
    monitored_conditions:
      - 'Current State'
      - 'Temperatures'
      - 'Job Percentage'
      - 'Time Elapsed'
      - 'Time Remaining'
```
