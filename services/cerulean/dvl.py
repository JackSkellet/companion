"""
Code for integration of Cerulean DVL-75 with Companion and ArduSub
"""
import threading
import time
from mavlink2resthelper import Mavlink2RestHelper
from companionhelper import request
import json
import socket
from select import select
import math
import os
import serial
import pynmea2

DVL_DOWN = 1
DVL_FORWARD = 2


class DvlDriver(threading.Thread):
    """
    Responsible for the DVL interactions themselves.
    This handles fetching the DVL data and forwarding it to Ardusub
    """

    status = "Starting"
    version = ""
    mav = Mavlink2RestHelper()
    current_orientation = DVL_DOWN
    enabled = True
    rangefinder = False
    timeout = 3  # tcp timeout in seconds
    origin = [0, 0]
    settings_path = os.path.join(os.path.expanduser("~"), ".config", "cerulean", "dvl-75.json")

    def __init__(self, orientation=DVL_DOWN):
        threading.Thread.__init__(self)
        self.current_orientation = orientation

    def wait_for_vehicle(self):
        """
        Waits for a valid heartbeat to Mavlink2Rest
        """
        self.status = "Waiting for vehicle..."
        while not self.mav.get("/HEARTBEAT"):
            time.sleep(1)
        self.status = "Waiting for arming..."

        while not self.vehicle_armed():
            time.sleep(1)

    def vehicle_armed(self):
        base_mode = json.loads(self.mav.get("/HEARTBEAT"))['base_mode']['bits']

        if base_mode == 81:
            return False
        elif base_mode == 89:
            return False
        else:
            return True

    def set_gps_origin(self, lat, lon):
        """
        Sets the EKF origin to lat, lon
        """
        self.mav.set_gps_origin(lat, lon)
        self.origin = [lat, lon]
        # self.save_settings()

    def setup_mavlink(self):
        """
        Sets up mavlink streamrates so we have the needed messages at the
        appropriate rates
        """
        self.status = "Setting up MAVLink streams..."
        self.mav.ensure_message_frequency('ATTITUDE', 30, 5)

    def setup_params(self):
        """
        Sets up the required params for DVL integration
        """
        self.mav.set_param("AHRS_EKF_TYPE", "MAV_PARAM_TYPE_UINT8", 3)
        # TODO: Check if really required. It doesn't look like the ekf2 stops at all
        self.mav.set_param("EK2_ENABLE", "MAV_PARAM_TYPE_UINT8", 0)

        self.mav.set_param("EK3_ENABLE", "MAV_PARAM_TYPE_UINT8", 1)
        self.mav.set_param("VISO__TYPE", "MAV_PARAM_TYPE_UINT8", 1)
        self.mav.set_param("EK3_GPS_TYPE", "MAV_PARAM_TYPE_UINT8", 3)

    def setup_serial(self, timeout=300):
        """
        Sets up the serial port to talk to the DVL
        """
        while timeout > 0:
            try:
                self.serial = serial.Serial('/dev/serial/gps/gps', 115200, timeout=1)
                self.serial.flush()
                return True
            except Exception as error:
                print(error)
                time.sleep(0.1)
            timeout -= 1
        self.status = "Setup serial timeout"
        return False

    def setup_socket(self, timeout=300):
        """
        Sets up the socket to talk to the DVL
        """
        while timeout > 0:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.socket.setblocking(False)
                self.socket.bind(('0.0.0.0', 27000))
                return True
            except socket.error:
                time.sleep(0.1)
            except Exception as error:
                print(error)
                time.sleep(0.1)
            timeout -= 1
        self.status = "Setup connection timeout"
        return False

    def is_nmea(self, packet):
        try:
            if pynmea2.parse(packet):
                return True
            else:
                return False
        except Exception as error:
            pass

    def is_gps_passthrough(self, packet):
        try:
            if (packet[0:5] == 'GPS:$'):
                return True
            else:
                return False
        except Exception as error:
            pass

    def run(self):
        """
        Runs the main routing
        """
        self.wait_for_vehicle()
        self.setup_mavlink()
        self.setup_params()
        self.mode = None
        if self.setup_serial(timeout=3):
            self.mode = "Serial"
        elif self.setup_socket(timeout=3):
            self.mode = "Socket"
        time.sleep(1)
        # self.set_gps_origin(*self.origin)
        self.status = "Running"
        self.last_recv_time = time.time()

        buf = ""
        connected = True
        while True:
            if not self.enabled:
                time.sleep(1)
                buf = ""  # Reset buf when disabled
                continue
            if not self.vehicle_armed():
                time.sleep(1)
                continue
            data = None
            recv = None
            if self.mode == "Serial":
                try:
                    if self.serial:
                        try:
                            recv = self.serial.readline()
                            connected = True
                            if recv:
                                self.last_recv_time = time.time()
                        except socket.error as e:
                            print("Disconnected")
                            connected = False
                        except Exception as e:
                            print("Error receiveing:", e)
                            pass
                except Exception as e:
                    print("Serial Port Error:", error)
                    pass
            elif self.mode == "Socket":
                try:
                    recv = self.socket.recv(4096)
                    connected = True
                    if recv:
                        self.last_recv_time = time.time()
                except socket.error as e:
                    time.sleep(0.01)
                except Exception as e:
                    time.sleep(0.01)
                    print("Error receiveing:", e)
                    continue

            # print(recv.decode())

            self.status = "Running"
            if recv is None:
                time.sleep(0.01)
                continue
            try:

                if self.is_nmea(recv.decode()):
                    data = pynmea2.parse(recv.decode())
                    print(repr(data))
                    dx, dy, dz = data.pdx, data.pdy, data.pdz
                    dt = data.dtu
                    c = data.c

                    # feeding back the angles seem to aggravate the gyro drift issue
                    # angles = self.update_attitude()
                    angles = [0, 0, 0]

                    if self.current_orientation == DVL_DOWN and c >= 70:
                        self.mav.send_vision([dx, dy, dz],
                                             angles,
                                             dt=dt,
                                             confidence=c)

                    elif self.current_orientation == DVL_FORWARD:
                        self.mav.send_vision([dz, dy, -dx],
                                             angles,
                                             dt=dt,
                                             confidence=c)


                elif (self.is_gps_passthrough(recv.decode())):
                    data = pynmea2.parse(recv.decode()[4:])
                    try:
                        if data.latitude and data.longitude:

                            if data.gps_qual > 0 and float(data.horizontal_dil) < 1.8 and float(data.num_sats) > 5:
                                print("HDOP: ", str(float(data.horizontal_dil)))
                                print("Fix: ", str(data.gps_qual))
                                print(repr(data))
                                ms = time.time()
                                self.mav.set_gps_origin(lat=data.latitude, lon=data.longitude)
                    except Exception as error:
                        continue

                else:
                    print("Unsupported Message")

            except Exception as error:
                print("Error fetching data for DVL:", error)
                continue

            time.sleep(0.003)