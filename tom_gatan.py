import DigitalMicrograph as DM
from time import sleep
import socket

class PtychoGatan():
    def __init__(self) -> None:
        pass
    
    def first_scan(self):
        # Need to check if it's in STEM mode and `Scan` is available
        DM.DS_InvokeAcquisitionButtonEx(5, 0)
        DM.DS_FinishAcquisition()

    def detectors_out(self):
        self.cam = DM.GetActiveCamera()
        # TODO: Check Orius and K2 independently
        # self.orius = DM.GetCameraByID(1)
        if self.cam.GetInserted() == True:
            self.cam.SetInserted(False)
            sleep(2)
            if self.cam.GetInserted == True:
                print("Cannot retract the camera.\n")

    def check_screen_status(self):
        status = {0: 'Down', 1: 'FocusScreen', 2: 'Up'}
        self.screen_status = status[DM.Py_Microscope().GetScreenPosition()]

    def screen_up(self):
        self.screen_status = DM.Py_Microscope().GetScreenPosition()
        DM.Py_Microscope().SetScreenPosition(0)
        sleep(2)
        if self.check_screen_status() != 'Up':
            print('Cannot lift the screen. Current status:', self.screen_status)

    def focus_screen_down(self):
        DM.Py_Microscope().SetScreenPosition(1)
        sleep(2)
        if self.check_screen_status() == 'Up':
            print('Cannot drop the screen. Current status:', self.screen_status)
        elif self.check_screen_status() == 'Down':
            print('Focus Screen not activated. Current status:', self.screen_status)

    def screen_down(self):
        DM.Py_Microscope().SetScreenPosition(2)
        sleep(2)
        if self.check_screen_status() != 'Down':
            print('Cannot drop the screen. Current status:', self.screen_status)

    def all_grey():
        return

    def _send():
        return

    def _receive():
        return

def ptycho_prep(gms):
    gms.detectors_out()
    gms.screen_up()
    gms.all_grey()

gatan = PtychoGatan()

# gatan_host = 
# gatan_port = 

tom = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tom.bind((gatan_host, gatan_port))
tom.listen(5)
ongoing = True

while True:
    conn, addr = tom.accept()
    conn.send(str.encode("GATAN,CTL,This is Major Tom to Ground Control.\n"))
    from_client = ""
    while True:
        data = conn.recv(4096)
        if data.decode() == "CTL,GATAN,STOP": break
        if data.decode() == "CTL,GATAN,TERMINATE":
            ongoing = False
            break
        from_client = data[4:].decode()
        print(from_client) 
        eval(from_client) 
        conn.send(str.encode("GATAN,CTL,Evaluated Command: "+ from_client +"\n"))
    conn.close()
    print("Client disconnected")

tom.close()

