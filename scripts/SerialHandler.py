from serial import Serial
import json

class SerialHandler:
    def __init__(self, port, baud) :
        self.ser = Serial(port=port, baudrate=baud)

    def read(self):
        while 1:
            if(self.ser.readable()):
                payload = self.ser.readline()
                data_json = json.loads(payload)

                return data_json
        
    def write(self, payload):
        if(self.ser.writable()):
            return self.ser.write(payload)
        else:
            return False
