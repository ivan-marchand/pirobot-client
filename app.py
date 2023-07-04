import traceback

from PyQt5 import QtGui
from PyQt5.QtWidgets import QAction, QHBoxLayout, QLabel, QMenu, QPushButton, QDialog, QMainWindow, QLineEdit, QStatusBar, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QThread

import cv2
import numpy as np
import socket
import struct
import time

from gamepad import GamePad
from client import Client
from input_config_manager import InputConfigManagerPopup
from robot_config_manager import RobotConfigManagerPopup


class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)
    FPS_UPDATE_INTERVAL = 1

    def __init__(self, host_ip, port):
        super().__init__()
        self.host_ip = host_ip
        self.running = False
        self.frame_counter = 0
        self.last_frame_ts = None
        self.fps = 0
        self.port = port

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            try:
                # create socket
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((self.host_ip, self.port))  # a tuple
                data = b""
                payload_size = struct.calcsize("Q")
                self.last_frame_ts = time.time()
                while self.running:
                    while len(data) < payload_size:
                        packet = client_socket.recv(4 * 1024)  # 4K
                        if not packet:
                            break
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


class ImageLabel(QLabel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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


class PlayMessagePopup(QDialog):
    def __init__(self, callback, destination):
        super().__init__()
        self.setWindowTitle(f"Play a message on {destination}")
        self.setGeometry(50, 50, 500, 110)
        self.callback = callback
        self.message = ""
        self.destination = destination

        vbox = QVBoxLayout()

        host_selector = QLineEdit()
        host_selector.textChanged.connect(self.message_udpated)
        vbox.addWidget(host_selector)

        hbox = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        hbox.addWidget(cancel_button)
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.setFocus()
        ok_button.clicked.connect(self.play_message)
        hbox.addWidget(ok_button)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

    def play_message(self):
        self.callback(self.message, self.destination)
        self.close()

    def message_udpated(self, value):
        self.message = value


class App(QMainWindow):
    def __init__(self, hostname, server_port, video_server_port, full_screen):
        super().__init__()

        # Update window title
        self.setWindowTitle("PiRobot Remote Control")

        self.robot_name = "PiRobot"
        self.robot_config = {}
        self.resize(800, 600)
        self.create_menu_bar()
        if full_screen:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.showFullScreen()
        self.popups = {}

        # create the label that holds the image
        self.image_label = ImageLabel(self)
        self.setCentralWidget(self.image_label)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Connect to Host
        self.client = Client(self)
        self.hostname = hostname
        self.server_port = server_port
        self.video_server_port = video_server_port
        self.video_thread = None
        self.gamepad_thread = None
        if self.hostname is None:
            self.open_select_host_window()
        else:
            self.connect_to_host(self.hostname)
        self.update_status_bar()

    def closeEvent(self,event):
        for popup in self.popups.values():
            if popup.isVisible():
                popup.close()

    def update_status_bar(self):
        # Update status bar
        if not self.client.is_connected():
            status_message = "Connecting..."
        else:
            status_message = f"Connected to {self.hostname} | {self.robot_name}"
            if self.video_thread is not None:
                status_message += f" | FPS: {self.video_thread.fps}"

        self.status_bar.showMessage(status_message)

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        # Creating Settings menu
        setting_menu = QMenu("Settings", self)

        # Select host action
        select_host_action = QAction(self)
        select_host_action.setText("Select Host")
        select_host_action.triggered.connect(lambda checked: self.open_select_host_window())
        setting_menu.addAction(select_host_action)

        # Robot config
        robot_config_action = QAction(self)
        robot_config_action.setText("Robot Configuration")
        robot_config_action.triggered.connect(self.open_robot_config_manager)
        setting_menu.addAction(robot_config_action)

        # Robot config
        input_config_action = QAction(self)
        input_config_action.setText("Input Device Configuration")
        input_config_action.triggered.connect(self.open_input_config_manager)
        setting_menu.addAction(input_config_action)

        menu_bar.addMenu(setting_menu)

    def connect_to_host(self, hostname):
        try:
            self.hostname = hostname
            host_ip = socket.gethostbyname(self.hostname)
            self.client = Client(self)
            self.client.register_consumer("status", self.robot_init_callback)
            self.client.connect(host_ip, self.server_port)
            # create the video capture thread
            if self.video_thread is not None:
                self.video_thread.stop()
            self.video_thread = VideoThread(host_ip, self.video_server_port)
            # connect its signal to the update_image slot
            self.video_thread.change_pixmap_signal.connect(self.update_image)
            # Start the video thread
            self.video_thread.start()
            # GamePad
            self.start_gamepad()
            # Status bar
            self.update_status_bar()
        except:
            traceback.print_exc()
            self.open_select_host_window(f"Unable to connect to {self.hostname}")

    def start_gamepad(self):
        callback = {
            "axis_motion": self.client.gamepad_absolute_axis_callback,
            "button": self.client.gamepad_button_callback,
            "hat_motion": self.client.gamepad_hat_callback,
        }
        GamePad.start_gamepad(callback=callback)

    def robot_init_callback(self, message):
        self.robot_name = message["robot_name"]
        self.robot_config = message["config"]
        self.update_status_bar()

    def open_select_host_window(self, message=None):
        if "select_host" not in self.popups or not self.popups["select_host"].isVisible():
            self.popups["select_host"] = ConnectToHostPopup(callback=self.connect_to_host, message=message)
            self.popups["select_host"].show()

    def open_play_message_window(self, destination):
        if "play_message" not in self.popups or not self.popups["play_message"].isVisible():
            self.popups["play_message"] = PlayMessagePopup(callback=self.client.play_message, destination=destination)
            self.popups["play_message"].show()

    def open_robot_config_manager(self):
        if "robot_config_manager" not in self.popups or not self.popups["robot_config_manager"].isVisible():
            self.popups["robot_config_manager"] = RobotConfigManagerPopup(client=self.client)
            self.popups["robot_config_manager"].show()

    def open_input_config_manager(self):
        if "input_config_manager" not in self.popups or not self.popups["input_config_manager"].isVisible():
            self.popups["input_config_manager"] = InputConfigManagerPopup(
                robot_config=self.robot_config, close_callback=self.start_gamepad
            )
            self.popups["input_config_manager"].show()

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        """Updates the image_label with a new opencv image"""
        qt_img = self.convert_cv_qt(cv_img)
        self.image_label.setPixmap(qt_img)
        self.update_status_bar()

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
        if not e.isAutoRepeat():
            self.client.key_press_callback(e, True)

    def keyReleaseEvent(self, e):
        if not e.isAutoRepeat():
            self.client.key_press_callback(e, False)
