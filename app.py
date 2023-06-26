import traceback

from PyQt5 import QtGui
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, QMainWindow, QLineEdit, QCompleter, QStatusBar
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread

import cv2
import numpy as np
import socket
import struct
import time
import threading

from gamepad import GamePad
from client import Client


class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    FPS_UPDATE_INTERVAL = 1

    def __init__(self, host_ip):
        super().__init__()
        self.host_ip = host_ip
        self.running = False
        self.frame_counter = 0
        self.last_frame_ts = None
        self.fps = 0

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            try:
                # create socket
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                port = 8001
                client_socket.connect((self.host_ip, port))  # a tuple
                data = b""
                payload_size = struct.calcsize("Q")
                self.last_frame_ts = time.time()
                while self.running:
                    while len(data) < payload_size:
                        packet = client_socket.recv(4 * 1024)  # 4K
                        if not packet: break
                        data += packet
                    packed_msg_size = data[:payload_size]
                    data = data[payload_size:]
                    msg_size = struct.unpack("Q", packed_msg_size)[0]

                    while len(data) < msg_size:
                        data += client_socket.recv(4 * 1024)
                    # New frame received, indicate we're ready for the next one
                    client_socket.send(b"RDY\n")
                    frame_data = data[:msg_size]
                    data = data[msg_size:]
                    frame = np.frombuffer(frame_data, dtype="byte")
                    frame = cv2.imdecode(frame, cv2.IMREAD_UNCHANGED)
                    # Update fps
                    self.frame_counter += 1
                    now = time.time()
                    if now > self.last_frame_ts + VideoThread.FPS_UPDATE_INTERVAL:
                        self.fps = round(self.frame_counter / (now - self.last_frame_ts))
                        self.last_frame_ts = now
                        self.frame_counter = 0

                    self.change_pixmap_signal.emit(frame)
            except KeyboardInterrupt:
                self.stop()
            except ConnectionRefusedError:
                traceback.print_exc()
                print("Unable to connect to video server")
                time.sleep(1)
                continue
            except:
                traceback.print_exc()
                continue
            finally:
                client_socket.close()


class Button(QPushButton):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resize(100, 100)
        self.setFlat(True)
        self.setStyleSheet("color: rgb(0, 255, 0); border :2px solid; border-color: rgb(0, 255, 0);")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFont(QFont('Times', 20))
        #self.clicked.connect(lambda: client.button_callback(id))


class ImageLabel(QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #button = Button("...")

        # setting geometry of button
        #button.resize(200, 200)

        #vlayout = QVBoxLayout(self)
        #vlayout.setAlignment(Qt.AlignRight | Qt.AlignTop)
        #vlayout.addWidget(Button("..."))
        #vlayout.addWidget(Button("Hello"))

    def mousePressEvent(self, event):
        print("clicked", event)
        cursor = QtGui.QCursor()
        print(event.pos())


class ConnectToHostPopup(QDialog):
    def __init__(self, callback, message=None):
        super().__init__()
        self.setWindowTitle("Select Host")
        self.setGeometry(50, 50, 500, 110)
        self.callback = callback
        self.host = "localhost"

        vbox = QVBoxLayout()
        if message is not None:
            label = QLabel(message)
            label.setStyleSheet("color: red;")
            vbox.addWidget(label)

        host_selector = QLineEdit()
        host_selector.setCompleter(QCompleter(['localhost', 'picaterpillar.local', 'raspberrypi.local']))
        host_selector.textChanged.connect(self.host_selected)
        vbox.addWidget(host_selector)

        hbox = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        hbox.addWidget(cancel_button)
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.setFocus()
        ok_button.clicked.connect(self.connect_to_host)
        hbox.addWidget(ok_button)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

    def connect_to_host(self):
        self.callback(self.host)
        self.close()

    def host_selected(self, value):
        self.host = value


class App(QMainWindow):
    def __init__(self, hostname, full_screen=False):
        super().__init__()

        self.setWindowTitle("PiRobot Remote Control")
        self.resize(800, 600)
        if full_screen:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.showFullScreen()

        # create the label that holds the image
        self.image_label = ImageLabel(self)
        self.setCentralWidget(self.image_label)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Connecting...")
        self.setStatusBar(self.status_bar)

        # Connect to Host
        self.client = Client(self)
        self.video_thread = None
        self.gamepad_thread = None
        if hostname is None:
            self.open_select_host_window()
        else:
            self.connect_to_host(hostname)

    def connect_to_host(self, hostname):
        try:
            host_ip = socket.gethostbyname(hostname)
            self.client = Client(self)
            self.client.connect(host_ip)
            # create the video capture thread
            if self.video_thread is not None:
                self.video_thread.stop()
            self.video_thread = VideoThread(host_ip)
            # connect its signal to the update_image slot
            self.video_thread.change_pixmap_signal.connect(self.update_image)
            # start the thread
            self.video_thread.start()
            # GamePad
            if self.gamepad_thread is not None:
                self.stop_gamepad()
            self.start_gamepad()
            self.status_bar.showMessage("Connected!")
        except:
            traceback.print_exc()
            self.open_select_host_window(f"Unable to connect to {hostname}")

    def open_select_host_window(self, message=None):
        self.p = ConnectToHostPopup(callback=self.connect_to_host, message=message)
        self.p.show()

    def start_gamepad(self):
        callback = {
            "absolute_axis": self.client.gamepad_absolute_axis_callback,
            "key": self.client.gamepad_key_callback
        }
        self.gamepad_thread = threading.Thread(target=GamePad.start_loop, kwargs=dict(callback=callback), daemon=True)
        self.gamepad_thread.start()

    def stop_gamepad(self):
        if self.gamepad_thread is not None:
            GamePad.stop_loop()
            self.gamepad_thread = None

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.image_label.setPixmap(qt_img)
        self.status_bar.showMessage(f"Connected! FPS: {self.video_thread.fps}")

    def convert_cv_qt(self, cv_img):
        """Convert from an opencv image to QPixmap"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        rgb_image = cv2.resize(rgb_image, (self.image_label.size().width(), self.image_label.size().height()))
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(w, h, Qt.KeepAspectRatio)
        return QPixmap.fromImage(p)

    def keyPressEvent(self, e):
        self.client.key_press_callback(e)
