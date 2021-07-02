#!/usr/bin/env python -u

"""Scan serial ports for GPS devices
    Symlinks to detected devices are created under /dev/serial/gps/
    This script needs root permission to create the symlinks
"""
from __future__ import print_function
import subprocess
import serial
import time
import pynmea2

class GPSEnumerator:

    def detect_gps(self, dev):
        """
        Attempts to detect the GPS device attached to serial port 'dev'
        Returns the new path with encoded name if detected, or None if the
        device was not detected
        """

        try:
            with serial.Serial("/dev/serial/by-id/" + dev, 115200,timeout=0.5) as gps:
                #Flush
                for i in range(4):
                    gps.readline()

                #Check for valid NMEA
                try:
                    pynmea2.parse(gps.readline().decode('ascii', errors='replace'))
                except Exception as exception:
                    print("Invalid NMEA: ", exception)
                    return None

                #GPS ID
                #gps_id = len(subprocess.check_output("ls /dev/serial/gps", shell=True).split("\n")) - 1

                description = "/dev/serial/gps/gps"
        except Exception as exception:
            print("An exception has occurred: ", exception)
            return None

        return description

    def make_symlink(self, origin, target):
        """
        follows target to real device an links origin to it
        origin => target
        Returns True if sucessful
        """
        try:
            # Follow link to actual device
            target_device = subprocess.check_output(' '.join(["readlink", "-f", "/dev/serial/by-id/%s" % origin]), shell=True)
            # Strip newline from output
            target_device = target_device.decode().split('\n')[0]

            # Create another link to it
            subprocess.check_output(' '.join(["mkdir", "-p", "/dev/serial/gps"]), shell=True)
            subprocess.check_output("ln -fs %s %s" % (
                target_device,
                target), shell=True)
            print(origin, " linked to ", target)
            return True
        except subprocess.CalledProcessError as exception:
            print(exception)
            return False


    def erase_old_symlinks(self):
        """
        Erases all symlinks at "/dev/serial/gps/"
        """
        try:
            subprocess.check_output(["rm", "-rf", "/dev/serial/gps"])
        except subprocess.CalledProcessError as exception:
            print(exception)


    def list_serial_devices(self):
        """
        Lists serial devices at "/dev/serial/by-id/"
        """
        # Look for connected serial devices
        try:
            output = subprocess.check_output("ls /dev/serial/by-id", shell=True)
            return output.decode().strip().split("\n")
        except subprocess.CalledProcessError as exception:
            print(exception)
            return []


if __name__ == '__main__':
    enumerator = GPSEnumerator()
    enumerator.erase_old_symlinks()

    # Look at each serial device, probe for GPS
    for dev in enumerator.list_serial_devices():
        print(dev)
        link = enumerator.detect_gps(dev)
        if link:
            print(link)
            enumerator.make_symlink(dev, link)
        else:
            print("Unable to identify device at ", dev)