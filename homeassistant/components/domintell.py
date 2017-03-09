"""
Connect to a Domintell gateway via pydomintell API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.domintell/
"""
import logging
import os
import socket
import sys

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.setup import setup_component
from homeassistant.const import (ATTR_BATTERY_LEVEL, CONF_NAME,
                                 CONF_OPTIMISTIC, EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON)
from homeassistant.helpers import discovery
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'
ATTR_DESCRIPTION = 'description'
ATTR_DEVICE = 'device'
CONF_DEVICE = 'device'
CONF_DEBUG = 'debug'
CONF_GATEWAYS = 'gateways'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_TCP_PORT = 'tcp_port'
DEFAULT_VERSION = 1.4
DEFAULT_TCP_PORT = 5003
DOMAIN = 'domintell'
MYSENSORS_GATEWAYS = 'domintell_gateways'

REQUIREMENTS = [
    #'https://github.com/theolind/pymysensors/archive/'
    #'0b705119389be58332f17753c53167f551254b6c.zip#pymysensors==0.8'
    ]


def is_socket_address(value):
    """Validate that value is a valid address."""
    try:
        socket.getaddrinfo(value, None)
        return value
    except OSError:
        raise vol.Invalid('Device is not a valid domain name or ip address')


def has_parent_dir(value):
    """Validate that value is in an existing directory which is writetable."""
    parent = os.path.dirname(os.path.realpath(value))
    is_dir_writable = os.path.isdir(parent) and os.access(parent, os.W_OK)
    if not is_dir_writable:
        raise vol.Invalid(
            '{} directory does not exist or is not writetable'.format(parent))
    return value


def has_all_unique_files(value):
    """Validate that all persistence files are unique and set if any is set."""
    persistence_files = [
        gateway.get(CONF_PERSISTENCE_FILE) for gateway in value]
    if None in persistence_files and any(
            name is not None for name in persistence_files):
        raise vol.Invalid(
            'persistence file name of all devices must be set if any is set')
    if not all(name is None for name in persistence_files):
        schema = vol.Schema(vol.Unique())
        schema(persistence_files)
    return value


def is_persistence_file(value):
    """Validate that persistence file path ends in either .pickle or .json."""
    if value.endswith(('.json', '.pickle')):
        return value
    else:
        raise vol.Invalid(
            '{} does not end in either `.json` or `.pickle`'.format(value))


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_GATEWAYS): vol.All(
            cv.ensure_list, has_all_unique_files,
            [{
                vol.Required(CONF_DEVICE):
                    vol.Any(is_socket_address),
                vol.Optional(CONF_PERSISTENCE_FILE):
                    vol.All(cv.string, is_persistence_file, has_parent_dir),
                vol.Optional(
                    CONF_TCP_PORT,
                    default=DEFAULT_TCP_PORT): cv.port,
            }]
        ),
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
        vol.Optional(CONF_PERSISTENCE, default=True): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the MySensors component."""
    import domintell.domintell as domintell

    persistence = config[DOMAIN].get(CONF_PERSISTENCE)

    def setup_gateway(device, persistence_file, tcp_port):
        """Return gateway after setup of the gateway."""
        socket.getaddrinfo(device, None)
        # valid ip address
        gateway = domintell.Deth01Gateway(
            device, event_callback=None, persistence=persistence,
            persistence_file=persistence_file,
            port=tcp_port)
        gateway.debug = config[DOMAIN].get(CONF_DEBUG)
        gateway = GatewayWrapper(gateway, device)
        # pylint: disable=attribute-defined-outside-init
        gateway.event_callback = gateway.callback_factory()

        def gw_start(event):
            """Callback to trigger start of gateway and any persistence."""
            if persistence:
                for node_id in gateway.sensors:
                    gateway.event_callback('persistence', node_id)
            gateway.start()
            hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                                 lambda event: gateway.stop())

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, gw_start)

        return gateway

    gateways = hass.data.get(MYSENSORS_GATEWAYS)
    if gateways is not None:
        _LOGGER.error(
            '%s already exists in %s, will not setup %s component',
            MYSENSORS_GATEWAYS, hass.data, DOMAIN)
        return False

    # Setup all devices from config
    gateways = []
    conf_gateways = config[DOMAIN][CONF_GATEWAYS]

    for index, gway in enumerate(conf_gateways):
        device = gway[CONF_DEVICE]
        persistence_file = gway.get(
            CONF_PERSISTENCE_FILE,
            hass.config.path('domintell{}.pickle'.format(index + 1)))
        tcp_port = gway.get(CONF_TCP_PORT)
        ready_gateway = setup_gateway(
            device, persistence_file, tcp_port)
        if ready_gateway is not None:
            gateways.append(ready_gateway)

    if not gateways:
        _LOGGER.error(
            'No devices could be setup as gateways, check your configuration')
        return False

    hass.data[MYSENSORS_GATEWAYS] = gateways

    #for component in ['sensor', 'switch', 'light', 'binary_sensor', 'climate',
    #                  'cover']:
    #    discovery.load_platform(hass, component, DOMAIN, {}, config)
    for component in ['switch', 'binary_sensor']:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    #discovery.load_platform(
    #    hass, 'device_tracker', DOMAIN, {}, config)

    #discovery.load_platform(
    #    hass, 'notify', DOMAIN, {CONF_NAME: DOMAIN}, config)

    return True


def pf_callback_factory(map_sv_types, devices, entity_class, add_devices=None):
    """Return a new callback for the platform."""
    def mysensors_callback(gateway, node_id):
        """Callback for domintell platform."""

        new_devices = []
        key = node_id

        #if child.type not in map_sv_types or \
        #   value_type not in map_sv_types[child.type]:
        #    return

        if gateway.sensors[node_id]["type"] != map_sv_types:
            return

        if key in devices:
            if add_devices:
                devices[key].schedule_update_ha_state(True)
            else:
                devices[key].update()
            return
        
        #if isinstance(entity_class, dict):
        #    device_class = entity_class[child.type]
        #else:
        device_class = entity_class
        devices[key] = device_class(
            gateway, node_id, 0, gateway.sensors[node_id]["desc"], 0, 0)
        if add_devices:
            new_devices.append(devices[key])
        else:
            devices[key].update()

        if add_devices and new_devices:
            add_devices(new_devices, True)
    return mysensors_callback


class GatewayWrapper(object):
    """Gateway wrapper class."""

    def __init__(self, gateway, device):
        """Setup class attributes on instantiation.

        Args:
        gateway (mysensors.SerialGateway): Gateway to wrap.
        optimistic (bool): Send values to actuators without feedback state.
        device (str): Path to serial port, ip adress or mqtt.

        Attributes:
        _wrapped_gateway (mysensors.SerialGateway): Wrapped gateway.
        platform_callbacks (list): Callback functions, one per platform.
        optimistic (bool): Send values to actuators without feedback state.
        device (str): Device configured as gateway.
        __initialised (bool): True if GatewayWrapper is initialised.
        """
        self._wrapped_gateway = gateway
        self.platform_callbacks = []
        self.device = device
        self.__initialised = True

    def __getattr__(self, name):
        """See if this object has attribute name."""
        # Do not use hasattr, it goes into infinite recurrsion
        if name in self.__dict__:
            # This object has the attribute.
            return getattr(self, name)
        # The wrapped object has the attribute.
        return getattr(self._wrapped_gateway, name)

    def __setattr__(self, name, value):
        """See if this object has attribute name then set to value."""
        if '_GatewayWrapper__initialised' not in self.__dict__:
            return object.__setattr__(self, name, value)
        elif name in self.__dict__:
            object.__setattr__(self, name, value)
        else:
            object.__setattr__(self._wrapped_gateway, name, value)

    def callback_factory(self):
        """Return a new callback function."""
        def node_update(update_type, node_id):
            """Callback for node updates from the MySensors gateway."""
            _LOGGER.debug('Update %s: node %s', update_type, node_id)
            for callback in self.platform_callbacks:
                callback(self, node_id)

        return node_update


class DomintellDeviceEntity(object):
    """Represent a MySensors entity."""

    def __init__(
            self, gateway, node_id, child_id, name, value_type, child_type):
        """
        Setup class attributes on instantiation.

        Args:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.

        Attributes:
        gateway (GatewayWrapper): Gateway object.
        node_id (str): Id of node.
        child_id (str): Id of child.
        _name (str): Entity name.
        value_type (str): Value type of child. Value is entity state.
        child_type (str): Child type of child.
        battery_level (int): Node battery level.
        _values (dict): Child values. Non state values set as state attributes.
        mysensors (module): Mysensors main component module.
        """
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        self.child_type = child_type
        self._values = {}

    @property
    def should_poll(self):
        """Mysensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        node = self.gateway.sensors[self.node_id]
        #child = node.children[self.child_id]
        attr = {
            #ATTR_BATTERY_LEVEL: node.battery_level,
            #ATTR_CHILD_ID: self.child_id,
            ATTR_DESCRIPTION: node["desc"],
            #ATTR_DEVICE: self.gateway.device,
            #ATTR_NODE_ID: self.node_id,
        }

        #set_req = self.gateway.const.SetReq

        for value_type, value in self._values.items():
            try:
                #attr[set_req(value_type).name] = value
                attr["ID"] = self.node_id
                attr["Value"] = value
            except ValueError:
                _LOGGER.error('Value_type %s is not valid for domintell '
                              'version %s', value_type,
                              self.gateway.protocol_version)
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        value = node["value"]

        #if value_type in (set_req.V_ARMED, set_req.V_LIGHT,
        #                  set_req.V_LOCK_STATUS, set_req.V_TRIPPED):
        #    self._values[value_type] = (
        #        STATE_ON if int(value) == 1 else STATE_OFF)
        #elif value_type == set_req.V_DIMMER:
        #    self._values[value_type] = int(value)
        #else:
        self._values[self.value_type] = value
