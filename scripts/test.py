# library python
from SerialHandler import SerialHandler
import threading
import time
from datetime import datetime
import json

PORT = "COM6"
BAUDRATE = 115200

serial_handler = SerialHandler(PORT, BAUDRATE)
status = "preheat"
filetime = datetime.now().isoweekday()
filename = "output.txt"
is_run = True

def baca_serial():
    global is_run
    while(is_run):
        global status
    
        c = input()
    
        if(c == "p"):
            status= "preheat"
        elif(c == "c"):
            status= "charge"
        elif(c == "1"):
            status= "first crack"
        elif(c == "2"):
            status= "second crack"
        elif(c == "l"):
            status= "light"
        elif(c == "m"):
            status= "medium"
        elif(c == "d"):
            status= "dark"
        elif(c == "q"):
            status= "finish"

        o = "#" + status + ";"
        serial_handler.write(o.encode())

def baca_sensor():
    global is_run
    while(is_run):
        try:
            t = datetime.now()
            data = serial_handler.read()
            data["time"] = str(t)
            data["status"] = str(status)

            print(data)

            out = json.dumps(data)
            
            print(filename)
            break

            f = open(filename, "+a")
            f.write(out + '\n')
            f.close()

        except Exception as e:
            print(e)
            
if __name__ == "__main__":
    thread_serial_listen = threading.Thread(target=baca_sensor)
    thread_serial_listen.start()

    serial_handler.ser.flush()

    baca_serial()
    
        
