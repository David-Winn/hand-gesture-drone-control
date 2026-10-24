"""Test ESP-Drone UDP connection with cflib."""
import logging
import time

logging.basicConfig(level=logging.DEBUG)

import cflib.crtp
from cflib.crazyflie import Crazyflie

print("Initializing drivers...")
cflib.crtp.init_drivers()

print("Creating Crazyflie instance...")
cf = Crazyflie()

def on_connected(uri):
    print(f"CONNECTED to {uri}")

def on_disconnected(uri):
    print(f"DISCONNECTED from {uri}")

def on_failed(uri, msg):
    print(f"CONNECTION FAILED to {uri}: {msg}")

cf.connected.add_callback(on_connected)
cf.disconnected.add_callback(on_disconnected)
cf.connection_failed.add_callback(on_failed)

print("Opening link to udp://192.168.43.42:2390...")
cf.open_link('udp://192.168.43.42:2390')

print("Waiting 5 seconds...")
time.sleep(5)

print(f"is_connected: {cf.is_connected()}")
cf.close_link()
print("Done")
