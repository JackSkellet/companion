#!/usr/bin/env python3
"""
Driver for the Cerulean DVL-75
"""

from dvl import DvlDriver
import json

thread = None

class API:

    dvl = None

    def __init__(self, dvl: DvlDriver):
        self.dvl = dvl


if __name__ == '__main__':
    dvl = DvlDriver()
    dvl.start()