# Duet3D integration for Home Assistant

This is a work in progress. Entities are created properly and values can be read from the `rr_model` (standalone) or `/machine/status` (SBC) endpoint of your Duet board. The integration is meant to use with RRF 3.4.5 and onwards.
Ensure to select the correct mode (Standalone vs SBC)

## Installation

### From HACS

1. Install HACS if you haven't already (see [installation guide](https://hacs.xyz/docs/configuration/basic)).
2. Add custom repository `https://github.com/lyr3x/hass-Duet3D` as "Integration" in the settings tab of HACS.
3. Find and install "Duet3D" integration in HACS's "Integrations" tab.
4. Restart your Home Assistant.

### Manual

1. Download and unzip the [repo archive](https://github.com/lyr3x/hass-Duet3D/archive/master.zip). (You could also click "Download ZIP" after pressing the green button in the repo, alternatively, you could clone the repo from SSH add-on).
2. Copy contents of the archive/repo into your `/config` directory.
3. Restart your Home Assistant.

### Config
Add the Duet3D Printer integration via the UI. 
1. Parameters => Integrations
2. Add integration
3. Search Duet
4. Configure in UI the app
    a. Name => Name you want to give to your printer
    b. Host => Printer ip adress
    c. Port => Printer port => Usually 80
    d. Password => password, or empty if you don't have one , or if you are using SBC
    e. Update frequency
    f. Number of tools => Number of tools your printer has
    g. Hoted => check if your printer has one
    h. LEDd's installed => check if your printer has LED
    i. Use standalone => check if your board is directly connected to your network. Uncheck if you are in SBC (duet board conencted to a rpi for example) see : [User manuel Duet](https://docs.duet3d.com/en/User_manual/Overview/Getting_started_Duet_3_MB6HC#:~:text=Standalone%20mode%20vs%20SBC%20mode%20The%20Duet%203,%28Duet%20Web%20Control%29%20etc%20work%20in%20both%20modes)



Add the following to your Lovelace dashboard. Remember to update the entity names with those of your own printer (defined by the value of `duet3d-name`)
```yaml
- card:
    cards:
      - type: glance
        entities:
          - entity: sensor.<name>_current_toolbed_temp
            name: Bed
          - entity: sensor.<name>_current_tool1_temp
            name: Tool
          - entity: sensor.<name>_current_state
            name: Status
    type: horizontal-stack
  conditions:
    - entity: switch.<name>
      state: 'on'
  type: conditional
```

There is also the possibility to send GCodes directly with a Home Assistant service:
```yaml
service: duet3d.hevors_send_gcode
data:
  gcode: G28
```
Currently is not working to log the responsen from an e.g `M122`


# Credits
Code initially based on the OctoPrint integration: [octoprint integration github](https://github.com/home-assistant/home-assistant/tree/dev/homeassistant/components/octoprint)