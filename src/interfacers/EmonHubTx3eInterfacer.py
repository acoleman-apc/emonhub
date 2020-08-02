import re
import time
import Cargo
from . import EmonHubSerialInterfacer as ehi

"""class EmonHubTx3eInterfacer

EmonHub Serial Interfacer key:value pair format
e.g: ct1:0,ct2:0,ct3:0,ct4:0,vrms:524,pulse:0
for csv format use the EmonHubSerialInterfacer

"""


class EmonHubTx3eInterfacer(ehi.EmonHubSerialInterfacer):

    def __init__(self, name, com_port='', com_baud=9600):
        """Initialize interfacer

        com_port (string): path to COM port e.g /dev/ttyUSB0
        com_baud (numeric): typically 115200 now for emontx etc

        """

        # Initialization
        super().__init__(name, com_port, com_baud)

        self._settings.update({
            'nodename': ""
        })

        # Initialize RX buffer
        self._rx_buf = ''
        
        self._init_complete = False

    def send_cal(self,cmd):
      self._ser.write((cmd+"\n").encode());
      time.sleep(0.1)
      reply = self._ser.readline().decode().rstrip()
      if reply=="Cal: "+cmd:
          self._log.debug("Calibration command sent successfully: "+cmd)
      else:
          self._log.error("Calibration command error cmd:"+cmd+", reply:"+reply)
          
    def online_configuration(self):
        self._log.debug("")
        self._log.debug("Online Calibration")
        # voltage calibration
        if "vcal" in self._settings:
            self.send_cal("k0 %.2f 0.00" % self._settings["vcal"]) 
        # current calibration
        for key in self._settings:
            if key.find("ical")==0: 
                ch = int(key.split("ical")[1])
                # If an array of amplitude and phase calibration send both, otherwise set phase cal to 0
                if isinstance(self._settings[key],list):
                    self.send_cal("k%d %.2f %.2f" % (ch,self._settings[key][0],self._settings[key][1]))
                else:
                    self.send_cal("k%d %.2f 0.00" % (ch,self._settings[key]))
        self._log.debug("")

    def read(self):
        """Read data from serial port and process if complete line received.

        Read data format is key:value pairs e.g:
        ct1:0,ct2:0,ct3:0,ct4:0,vrms:524,pulse:0

        """

        if not self._ser:
            return False

        # Read serial RX
        self._rx_buf = self._rx_buf + self._ser.readline().decode()

        # If line incomplete, exit
        if '\n' not in self._rx_buf:
            return

        # Remove CR,LF
        f = self._rx_buf[:-2].strip()
        
        if f=="Settings:" or f=="Calibration:":
            self._rx_buf = ''
            return False

        # Create a Payload object
        c = Cargo.new_cargo(rawdata=f)

        # Reset buffer
        self._rx_buf = ''

        # Parse the ESP format string
        values = []
        names = []

        for item in f.split(','):
            parts = item.split(':')
            if len(parts) == 2:
                # check for alphanumeric input name
                if re.match(r'^[\w-]+$', parts[0]):
                    # check for numeric value
                    value = 0
                    try:
                        value = float(parts[1])
                    except Exception:
                        self._log.debug("input value is not numeric: " + parts[1])

                    names.append(parts[0])
                    values.append(value)
                    
                    # Send online configuration at the right point
                    if self._init_complete==False:
                        self._init_complete = True
                        self.online_configuration()
                        
                else:
                    self._log.debug("invalid input name: " + parts[0])

        if self._settings["nodename"] != "":
            c.nodename = self._settings["nodename"]
            c.nodeid = self._settings["nodename"]
        else:
            c.nodeid = int(self._settings['nodeoffset'])

        c.realdata = values
        c.names = names

        if len(values) == 0:
            return False

        return c

    def set(self, **kwargs):
        
        for key, setting in self._settings.items():
            if key in kwargs:
                # replace default
                self._settings[key] = kwargs[key]

        if "vcal" in kwargs:
            self._settings["vcal"] = float(kwargs["vcal"])
        
        # up to 20 ical channels    
        for ch in range(1,20):
            key = "ical"+str(ch)
            if key in kwargs:
                if isinstance(kwargs[key],list):
                    if len(kwargs[key])==2:
                        self._settings[key] = [float(kwargs[key][0]),float(kwargs[key][1])]
                else:
                    self._settings[key] = float(kwargs[key])
