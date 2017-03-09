"""
Support for Domintell switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.domintell/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import domintell
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.config import load_yaml_config_file
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for switches."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    gateways = hass.data.get(domintell.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    platform_devices = []

    for gateway in gateways:
        map_sv_types = {
        }

        devices = {}
        gateway.platform_callbacks.append(domintell.pf_callback_factory(
            "output", devices, DomintellSwitch, add_devices))
        platform_devices.append(devices)


class DomintellSwitch(domintell.DomintellDeviceEntity, SwitchDevice):
    """Representation of the value of a MySensors Switch child node."""

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return False

    @property
    def is_on(self):
        """Return True if switch is on."""
        if self.value_type in self._values:
            #return self._values[self.value_type] == STATE_ON
            if self._values[self.value_type] == "on":
                return True
            if isinstance(self._values[self.value_type], int) and \
               int(self._values[self.value_type]) > 0:
                return True
            return False
        return False

    def turn_on(self):
        """Turn the switch on."""
        self.gateway.set_value(
            self.node_id, self.child_id, self.value_type, 1)

    def turn_off(self):
        """Turn the switch off."""
        print(self.gateway.set_value(
            self.node_id, self.child_id, self.value_type, 0))
