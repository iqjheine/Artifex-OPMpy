import numpy as np
import serial as serial
import time as t
from sys import exit
import re
import warnings

OPM500_BYTE_DLY = 0.01 # delay per char sent over serial, 10ms is recommended
OPM500_SND_RCV_DLY = 0.1 # reply delay of OPM500
RCV_RETRY_MAX = 10 # number of retries when reading N lines from the input buffer.  
class OPM500:

    def __init__(self, port):
        """
        
    
        Parameters
        ----------
        port : str
            serial port to connect to OPM500
    
        Returns
        -------
        None.
    
        """
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = 115200
        ser.bytesize = serial.EIGHTBITS #number of bits per bytes
        ser.parity = serial.PARITY_NONE #set parity check: no parity
        ser.stopbits = serial.STOPBITS_ONE #number of stop bits
        ser.timeout = 3           #timeout-block read
        ser.xonxoff = False     #disable software flow control
        ser.rtscts = False     #disable hardware (RTS/CTS) flow control
        ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
        ser.writeTimeout = 3   
        try:    
            ser.open()
        except:
            print("could not open the serial port:"+str(port)+". Please make sure the device is connected and powered on.")
            exit(-1)
        self.ser = ser
        ## Start USB Mode
        ans = self._send("$U")
        if ans[0] !="U OK":
            print("Unexpected return initializing USB, expected 'U OK', got: ", str(ans[0]))
            exit(-1)
        
        self.conv = 1
        self.uncal = True
    def __del__(self):
        self._send("$T")
        self.ser.close()
        
    def __call__(self):
        pass
    
    def _send(self, msg, rcv = True):
        """
        
        simple commands ($U $I) can be sent at once
        e.g. the wavelength calibration can only be successfully retrieved by sending each char separately
        therefore all chars of a command are sent in succession.

        Parameters
        ----------
        msg : str
            message to be sent to OPM500
        rcv : bool
            whether an answer is expected and should be received
        Returns
        -------
        ans : array of strs
            dependent on rcv:
                False: an empty array [""]
                True: each answer line of the OPM500, stripping \n\r
        """    
        
        if type(msg)!=type(str()):
            print("invalid message in send: ", str(msg))
            return
        for i in msg:
            self.ser.write(i.encode("utf-8"))
            t.sleep(OPM500_BYTE_DLY)
        #self.ser.flushOutput()
        if rcv:
            return self._recv(lines = 1)
        return [""]
    def _recv(self, lines=10):
        """
        Parameters
        ----------
        lines : int
            # of lines to receive. 
        Returns
        -------
        ans : array of strs
           
            each answer line of the OPM500, stripping \n\r

        """
        ans = []
        t.sleep(OPM500_SND_RCV_DLY)
        retry = 0
        while len(ans)<lines and retry <= RCV_RETRY_MAX:
            while self.ser.in_waiting and len(ans)<lines:
                #print(msg,"chars in buffer: ", self.ser.in_waiting)
                line = self.ser.readline()[:-1]
                ans.append(line.decode("utf-8"))
                t.sleep(OPM500_BYTE_DLY)
                self.ser.read(1)#strip carriage return
            retry += 1
            t.sleep(OPM500_BYTE_DLY)
        return ans
    def identify(self):
        """
        Print the identification of the OPM500

        Returns
        -------
        ident_raw: list of strings
        contains the id of the Powermeter and relevant sensor data

        """
        ident_raw = self._send("$I")
        for _ in ident_raw:
            print(_)
        return ident_raw
    def wavelengthcal(self, wavelength):
        """
        Returns the PD calibration factor in A/W for a given wavelength 
        and stores them in the OPM500 Object to automatically calibrate power values
    
        Parameters
        ----------
        wavelength : int
        range : [0, 9999]
             Wavelength in [nm]; <=4 decimal integer

        Returns
        -------
        cal : Photodiode calibration in A/W for given wavelength
            DESCRIPTION.

        """
        
        

        data = self._send("L"+'{:0>4}'.format(int(wavelength)))
        
        if data == [] or data == [""] or data == [[]]:
            warnings.warn("no calibration data received")
            return 0
        else:
            try:
                
                cal = re.findall(r"[-+]?(?:\d*\,*\d+)", str(data[0]))
                cal = float(cal[-1].replace(",","."))
            except: 
                warnings.warn("Could not convert: "+str(data)+" to claibration value")
                return 0
            self.uncal=False
            self.conv = cal 
            self.auto_gain = True
            #print()
            #print(cal)
            return cal
    def zero(self, reset = False):
        pass
    def gain(self, gain = 0 ):
        if gain == 0:
            ans = self._send("V?")[0]
            return int(ans[-1])
        ans = self._send("V"+str(int(gain)))
        if ans[0] == "V"+str(int(gain))+" OK":
            return gain
        else: 
            warnings.warn("could not set gain")
    def _autogain(self, power):
        """
        

        Parameters
        ----------
        autogain : bool
            DESCRIPTION.

        Returns
        -------
        None.

        """
        if not self.auto_gain:
            return
        gain = self.gain()
        startgain = gain
        fs = np.array([0,100,10,1,100,10,1])[gain]*122.85/self.conv
        fs /= [0,1e6,1e6,1e6,1e9,1e9,1e9][gain]
        if power / fs >0.9:
            gain -=1
        elif power / fs <0.1:
            gain +=1
        else:
            return gain
        if gain>=1 and gain <=6:
            self.gain(gain)
            return gain
        else: return startgain
    def autogain(self, autogain):
        self.auto_gain = bool(autogain)
    def filterbandwidth(self, bw : int = 0):
        pass
    def power(self, warn_uncal = True):
        """
        warn_uncal : bool
            Whether to warn if the returned power is uncalibrated.

        Returns
        -------
        float : power
            a single power value returned from the OPM500, calibrated to a wavelength, or returned as raw photocurrent
        """
        ans = self._send("$E")
        ans = ans[0].replace(",",".")
        prefix = 1
        if ans[-2:] =="uA":
            prefix = 1e-6
        elif ans[-2:] == "nA":
            prefix = 1e-9
        if self.uncal and warn_uncal:
            warnings.warn("Wavelength is unset, power will be returned as Photocurrent")
        power = float(ans[1:-2])/self.conv*prefix
        self._autogain(power)
        return power
    def power_fast(self, samples = 1000):
        pass
        # self._send("$",rcv=False)
        # self.ser.flushInput()
        # pass
    def dbm(self, power_lin):
        return 10*np.log10(power_lin/(1e-3))

def main():
    opm = OPM500("COM6")
    #opm.identify()
    opm.wavelengthcal("1950")
    opm.gain()
    opm.gain(6)
    opm.autogain(True)
    while 1:
        print(f"{opm.power():.2E}"+"W")


if __name__ == "__main__":
    main()
