"""
Support for Domintell binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.domintell/
"""
import logging

from homeassistant.components import domintell
from homeassistant.components.binary_sensor import (DEVICE_CLASSES,
                                                    BinarySensorDevice)
from homeassistant.const import STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the domintell platform for sensors."""
    # Only act if loaded via domintell by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    gateways = hass.data.get(domintell.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    for gateway in gateways:
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        #pres = gateway.const.Presentation
        #set_req = gateway.const.SetReq
        map_sv_types = {
            #pres.S_DOOR: [set_req.V_TRIPPED],
            #pres.S_MOTION: [set_req.V_TRIPPED],
            #pres.S_SMOKE: [set_req.V_TRIPPED],
        }

        devices = {}
        gateway.platform_callbacks.append(domintell.pf_callback_factory(
            "input", devices, DomintellBinarySensor, add_devices))


class DomintellBinarySensor(
        domintell.DomintellDeviceEntity, BinarySensorDevice):
    """Represent the value of a Domintell Binary Sensor child node."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        #pres = self.gateway.const.Presentation
        #class_map = {
            #pres.S_DOOR: 'opening',
            #pres.S_MOTION: 'motion',
            #pres.S_SMOKE: 'smoke',
        #}
        #if class_map.get(self.child_type) in DEVICE_CLASSES:
        #    return class_map.get(self.child_type)
        return 'light'
