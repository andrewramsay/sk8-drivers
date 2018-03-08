pysk8: Python driver for SK8 BLE sensor packs
#############################################

Overview
========
pysk8 is a Python package that provides a basic interface for interacting with 
SK8 Bluetooth Low Energy sensor packs produced by SAMH Engineering. 

Currently the package requires the use of a specific BLE USB dongle, namely the `Silicon Labs BLED112 <https://www.silabs.com/products/wireless/bluetooth/bluetooth-low-energy-modules/bled112-bluetooth-smart-dongle>`_. The reason for this is that most development is currently being done on Windows 10, and the native Bluetooth Low Energy APIs (plural) on that platform have been and probably still are unreliable, arbitrarily limited, badly documented, and difficult to work with. As a final touch, forced OS updates have been known to break previously working functionality. 

In contrast, the BLED112 has an independent onboard BLE stack with a straightforward, documented and stable serial-over-USB interface, and works well with the SK8. 

As the dongle presents itself to the OS as a simple serial device, the package should work equally well under OSX and Linux as well as any modern version of Windows, but those platforms have been rarely tested to date.
