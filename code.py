# Programmer: Chris Heise (crheise@icloud.com)
# Program: IoT Plant Monitor 2.0
# Purpose: Monitor soil moisture, sunlight, and temperature
#          of an indoor plant and post to AdafruitIO
# File: code.py

# Conversion formula for lux to ft candles from
# URL: https://www.jwspeaker.com/blog/education-center/five-lighting-terms-you-should-know/#:~:text=A%20single%20foot%2Dcandle%20is,foot%2Dcandle%20%3D%2010.764%20lux.

# Code for connecting to WiFi/AdafruitIO from
# URL: https://docs.circuitpython.org/projects/adafruitio/en/latest/examples.html
# Author: Tony DiCola for Adafruit Industries
# Date Accessed: 24 May 2023
# File Copyright: 2019 Adafruit Industries for Adafruit Industries
# License Identifier: MIT

# Code for displaying to FeatherWing from
# URL: https://learn.adafruit.com/monochrome-oled-breakouts/circuitpython-usage
# Author: ladyada for Adafruit Industries
# Date Accessed: 24 May 2023
# File Copyright: 2019 Adafruit Industries for Adafruit Industries
# License Identifier: MIT

# CHANGELOG:
# - removed DemoFeed and added three custom feeds (temp, moist, sun)
# - when connection to AIO, removed subscribe to DemoFeed
# - added helper function to convert temperature from C to F
# - added configuration of soil sensor and light sensor
# - changed while True loop to take measurements and publish to AIO
# - changed the loop delay from using time.monotonic to time.sleep
# - adjusted code to use a Feather M4 Express with WiFi FeatherWing & ...
# - changed the words the display shows

import time
import board
import busio
import neopixel
import displayio
import terminalio
import adafruit_tsl2591
import adafruit_displayio_ssd1306
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_esp32spi.adafruit_esp32spi_socket as socket

from adafruit_io.adafruit_io import IO_MQTT
from analogio import AnalogIn
from digitalio import DigitalInOut
from adafruit_display_text import label
from adafruit_seesaw.seesaw import Seesaw
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager


### Setup Sensors ###
# Setup soil/temp sensor
i2c = board.I2C()  # uses board.SCL and board.SDA
soil_sensor = Seesaw(i2c, addr=0x36)

# Setup light sensor
light_sensor = adafruit_tsl2591.TSL2591(i2c)

# Helper function to convert celsius to fahrenheit
def cel_to_fahr(celsius):
    return celsius * 1.80 + 32


# Helper method to convert lux to foot-candle
def lux_to_footcandle(lux):
    return lux / 10.764


### Setup Display ###
displayio.release_displays()
oled_reset = board.D9
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C, reset=oled_reset)

WIDTH = 128
HEIGHT = 32
BORDER = 5

display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=WIDTH, height=HEIGHT)

# Make the display context
startup_splash = displayio.Group()
display.show(startup_splash)

color_bitmap = displayio.Bitmap(WIDTH, HEIGHT, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0xFFFFFF  # White

bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
startup_splash.append(bg_sprite)

# Draw a smaller inner rectangle
inner_bitmap = displayio.Bitmap(WIDTH - BORDER * 2, HEIGHT - BORDER * 2, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0x000000  # Black
inner_sprite = displayio.TileGrid(
    inner_bitmap, pixel_shader=inner_palette, x=BORDER, y=BORDER
)
startup_splash.append(inner_sprite)

# Draw a label
text = "Plant Watch 2.0"
text_area = label.Label(
    terminalio.FONT, text=text, color=0xFFFFFF, x=20, y=HEIGHT // 2 - 1
)
startup_splash.append(text_area)


### Setup WiFi and Connect to AdafruitIO ###
# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# For an externally connected ESP32:
esp32_cs = DigitalInOut(board.D13)
esp32_ready = DigitalInOut(board.D11)
esp32_reset = DigitalInOut(board.D12)

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)


# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    print("Connected to Adafruit IO!")


def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))


# pylint: disable=unused-argument
def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print("Disconnected from Adafruit IO!")


# pylint: disable=unused-argument
def message(client, feed_id, payload):
    # Message function will be called when a subscribed feed has a new value.
    print("Feed {0} received new value: {1}".format(feed_id, payload))


# Connect to WiFi
print("Connecting to WiFi...")
wifi.connect()
print("Connected!")

# Initialize MQTT interface with the esp interface
MQTT.set_socket(socket, esp)

# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    port=1883,
    username=secrets["aio_username"],
    password=secrets["aio_key"],
)

# Initialize an Adafruit IO MQTT Client
io = IO_MQTT(mqtt_client)

# Connect the callback methods defined above to Adafruit IO
io.on_connect = connected
io.on_disconnect = disconnected
io.on_subscribe = subscribe
io.on_unsubscribe = unsubscribe
io.on_message = message

# Connect to Adafruit IO
print("Connecting to Adafruit IO...")
io.connect()

measurements = ['Sunlight', 'Moisture', 'Temperature']
measurement_units = {'sunlight': 'Ft-Candles', 'moisture': 'Humidity', 'temperature': 'ºF'}
plant_measurements = {'sunlight': 0.0, 'moisture': 0.0, 'temperature': 0.0}

last_updated = time.monotonic() - 60

while True:
    # Take and send measurements once per minute
    if time.monotonic() - last_updated >= 60:
        # Take measurements
        print("\nTaking measurements...")
        plant_measurements['sunlight'] = lux_to_footcandle(light_sensor.lux)
        plant_measurements['moisture'] = soil_sensor.moisture_read()/20     # Returns a reading between 200 (very dry) and 2000 (very wet), sodivide by 20 to get it between 10 and 100
        plant_measurements['temperature'] = cel_to_fahr(soil_sensor.get_temp())

        # Print measurements (for testing)
        #for i in range(3):
        #    print(f"{measurements[i]}: {plant_measurements[measurements[i].lower()]:.2f} {measurement_units[measurements[i].lower()]} ")

        # Send measurements to AdafruitIO
        try:
            print("\nSending data...")
            io.publish("sun", plant_measurements['sunlight'])
            io.publish("spruce.moisture", (plant_measurements['moisture']))
            io.publish("spruce.temperature", plant_measurements['temperature'])
            print("Measurement data sent!")

        except OSError as e:
            print(f"Failed to get/post data, retrying...\n {e}")
            wifi.reset()
            continue

        last_updated = time.monotonic()
