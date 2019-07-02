"""
Support for S0PCM pulse meter.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.s0pcm/
"""
from time import gmtime, time

from serial import Serial
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

__version__ = '1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional('device', default='/dev/ttyACM0'): cv.string,
    vol.Optional('channels', default=[0]):
        vol.All(cv.ensure_list, [0, 1, 2, 3, 4])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the S0PCM platform."""
    s0pcmReader = S0pcmSerialReader(config['device'], 9600)
    # Anyone a suggestion how to do this without reader being added as device?
    add_devices([s0pcmReader])
    # Create and add channel entities
    s0pcmChannels = [S0pcmChannel(channel, s0pcmReader)
                     for channel in config['channels']]
    add_devices(s0pcmChannels)
    # Create and add channel (hourly count) entities
    add_devices([S0pcmChannelHourly(s0pcmChannel)
                 for s0pcmChannel in s0pcmChannels])


class S0pcmSerialReader(Entity):
    """Get data from s0pcm serial device."""

    def __init__(self, device, baudrate):
        """Initialize the data object."""
        self._counts = {key: None for key in range(0, 5)}
        self._serial = Serial(device, baudrate)

    def __del__(self):
        """Close serial connection."""
        self._serial.close()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "S0PCM serial reader"

    @property
    def state(self):
        """Return the state of the sensor."""
        return None

    def GetCount(self, channel):
        """Return the counters per S0PCM channel."""
        return self._counts[channel]

    def update(self):
        """Update and parse buffered serial lines."""
        while (self._serial.inWaiting() > 0):
            data = str(self._serial.readline()).split(':')
            if len(data) == 19:
                self._counts[0] = data[6]
                self._counts[1] = data[9]
                self._counts[2] = data[12]
                self._counts[3] = data[15]
                self._counts[4] = data[18].strip("\\r\\n'")


class S0pcmChannel(Entity):
    """Publish total count of s0pcm pulse meter channel."""

    def __init__(self, channel, s0pcmReader):
        """Initialize the data object."""
        self._channel = channel
        self._s0pcmReader = s0pcmReader
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "S0PCM channel {}".format(self._channel)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update counter value."""
        self._state = self._s0pcmReader.GetCount(self._channel)


class S0pcmChannelHourly(Entity):
    """Publish hourly count increment of s0pcm pulse meter channel."""

    def __init__(self, s0pcmChannel):
        """Initialize the data object."""
        self._s0pcmChannel = s0pcmChannel
        self._last_update = time()
        self._state = None
        self._previousState = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} (hourly)".format(self._s0pcmChannel.name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _getHour(self, timestamp):
        """Return hour (24h) of timestamp."""
        return gmtime(timestamp).tm_hour

    def update(self):
        """Update counter value each hour."""
        if (self._getHour(time()) != self._getHour(self._last_update)):
            if self._s0pcmChannel.state:
                currentState = int(self._s0pcmChannel.state)
                if self._previousState:
                    self._state = currentState - self._previousState
                    self._last_update = time()
                self._previousState = currentState
