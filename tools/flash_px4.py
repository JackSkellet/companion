#!/usr/bin/python -u

import os
from urllib2 import urlopen
import time
import sys
import signal
home = os.environ['HOME']
from optparse import OptionParser

def timeout(signum, frame):
    print 'Timed out waiting for firmware on stdin!'
    exit(1)

parser = OptionParser()
parser.add_option("--url",dest="url",help="Firmware download URL (optional)")
parser.add_option("--stdin",action="store_true",dest="fromStdin",default=False,help="Expect input from stdin")
parser.add_option("--file", dest="file", default=None, help="Load from file")
parser.add_option("--latest",action="store_true",dest="latest",default=False,help="Upload latest development firmware")
(options,args) = parser.parse_args()

if options.fromStdin:
                # Get firmware from stdin if possible
                print "Trying to read file from stdin..."

                signal.signal(signal.SIGALRM, timeout)
                signal.alarm(5)
                fileIn = sys.stdin.read()
                signal.alarm(0)

                if fileIn:
                                file = open("/tmp/ardusub.apj","w")
                                file.write(fileIn)
                                file.close()
                                print "Got firmware file from stdin!"
                else:
                                error("Read error on stdin!")
elif options.file is not None:
                try:
                    print("Attempting upload from file %s") % options.file
                    open(options.file)
                except Exception as e:
                    print("Error opening file %s: %s") % (options.file, e)
                    exit(1)
else:
                # Download most recent firmware
                if options.url:
                                firmwareURL = options.url
                                print "Downloading ArduSub firmware from %s" % firmwareURL
                elif options.latest:
                                firmwareURL = "https://firmware.ardupilot.org/Sub/latest/Pixhawk1/ardusub.apj"
                                print "Downloading latest ArduSub firmware from %s" % firmwareURL
                else:
                                firmwareURL = "https://firmware.ardupilot.org/Sub/stable/Pixhawk1/ardusub.apj"
                                print "Downloading stable ArduSub firmware from %s" % firmwareURL

                try:
                                firmwarefile = urlopen(firmwareURL)
                                with open("/tmp/ardusub.apj", "wb") as local_file:
                                    local_file.write(firmwarefile.read())

                                local_file.close()

                except Exception as e:
                                print(e)
                                print "Error downloading firmware! Do you have an internet connection? Try 'ping ardusub.com'"
                                exit(1)


# Stop screen session with mavproxy
print "Stopping mavproxy"
os.system("screen -X -S mavproxy quit")

# Flash Pixhawk
print "Flashing Pixhawk..."
if options.file is not None:
    if(os.system("python -u " + home + "/companion/tools/uploader.py "
    "'%s'" % options.file) != 0):
                print "Error flashing pixhawk!"
                exit(1)
else:
    if(os.system("python -u "+home+"/companion/tools/uploader.py "
    "/tmp/ardusub.apj") != 0):
                print "Error flashing pixhawk! Do you have most recent version of companion? Try 'git pull' or scp."
                exit(1)


# Wait a few seconds
print "Waiting to restart mavproxy..."
time.sleep(10)

# Start screen session with mavproxy
print "Restarting mavproxy"
os.system("screen -dm -S mavproxy "+home+"/companion/scripts/start_mavproxy_telem_splitter.sh")

print "Complete!"
