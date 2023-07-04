import json
import os
import socket
import threading

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence


class Client(object):

    def __init__(self, app):
        self.app = app
        self.socket = None
        self.motor_slow_mode = False
        self.host_ip = None
        self.port = None
        self.config_path = "config"
        self.actions = {}
        self.controller_mapping = {}
        self.axis_mapping = {}
        self.axis_positions = {}
        if not os.path.isdir(self.config_path):
            self.config_path = "/etc/piremote/config"
        self.consumers = {}

        self.load_config()

    def is_connected(self):
        return self.socket is not None

    def load_config(self):
        with open(os.path.join(self.config_path, "actions.json")) as action_file:
            self.actions = json.load(action_file)

        with open(os.path.join(self.config_path, "controller.json")) as controller_file:
            self.controller_mapping = json.load(controller_file)
            if "gamepad" in self.controller_mapping:
                for device_name, gamepad_config in self.controller_mapping.get("gamepad").items():
                    gamepad_absolute_mapping = gamepad_config.get("absolute_axis", {})
                    gamepad_config["axis_mapping"] = {}
                    for axis, config in gamepad_absolute_mapping.items():
                        action, action_axis = config["action"], config["axis"]
                        if action not in gamepad_config["axis_mapping"]:
                            gamepad_config["axis_mapping"][action] = {}
                        gamepad_config["axis_mapping"][action][action_axis] = config
                        gamepad_config["axis_mapping"][action][action_axis]["axis"] = axis

    def run_action(self, action_id):
        if action_id == "app_close":
            self.app.close()
        elif action_id == "say_message":
            self.app.open_play_message_window(destination="audio")
        elif action_id == "display_message":
            self.app.open_play_message_window(destination="lcd")
        elif action_id == "motor_slow_mode":
            self.motor_slow_mode = not self.motor_slow_mode
        elif action_id in self.actions:
            commands = self.actions[action_id]
            for command in commands:
                if "type" in command:
                    self.send_message(command)
        else:
            print(f"Action not found {action_id}")

    def __del__(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def connect(self, host_ip, port):
        try:
            if self.socket is not None:
                self.socket.close()
                self.socket = None
            self.socket = socket.socket(socket.AF_INET)
            self.socket.settimeout(1)
            self.socket.connect((host_ip, port))
            self.host_ip = host_ip
            self.port = port
            threading.Thread(target=self.run_forever, daemon=True).start()
        except:
            self.socket = None
            print(f"Unable to connect to {host_ip}")
            raise

    def register_consumer(self, message_type, consumer):
        if message_type not in self.consumers:
            self.consumers[message_type] = []
        self.consumers[message_type].append(consumer)

    def run_forever(self):
        buffer = ""
        while self.socket is not None:
            try:
                self.socket.setblocking(False)
                packet = self.socket.recv(4 * 1024)  # 4K
                if not packet:
                    continue
                buffer += packet.decode()
                pos = buffer.find("\n")
                if pos > 0:
                    message = buffer[:pos]
                    buffer = buffer[pos + 1:]
                    message = json.loads(message)
                    for consumer in self.consumers.get(message["type"], []):
                        consumer(message)
            except:
                continue

    def get_gamepad_config(self, joystick):
        guid = joystick.get_guid()
        gamepad_mapping = self.controller_mapping.get("gamepad", {})
        if guid in gamepad_mapping:
            return gamepad_mapping[guid]
        else:
            return gamepad_mapping["default"]

    def gamepad_absolute_axis_callback(self, joystick, axis):
        gamepad_config = self.get_gamepad_config(joystick)
        gamepad_absolute_mapping = gamepad_config.get("absolute_axis", {})
        axis_str = str(axis)
        if axis_str in gamepad_absolute_mapping:
            action = gamepad_absolute_mapping[axis_str]["action"]
            axis_mapping = gamepad_config.get("axis_mapping", {})
            if action in axis_mapping:
                x_pos = joystick.get_axis(int(axis_mapping[action]["x"]["axis"])) if "x" in axis_mapping[action] else 0.0
                y_pos = joystick.get_axis(int(axis_mapping[action]["y"]["axis"])) if "y" in axis_mapping[action] else 0.0
                self.run_axis_action(action, x_pos, y_pos)

    def gamepad_hat_callback(self, joystick, hat, x_pos, y_pos):
        gamepad_config = self.get_gamepad_config(joystick)
        hat_mapping = gamepad_config.get("hat", {})
        hat_str = str(hat)
        if hat_str in hat_mapping:
            action = hat_mapping[hat_str]["action"]
            self.run_axis_action(action, x_pos, -y_pos)

    def move_camera(self, x_pos, y_pos):
        if abs(y_pos) < 2:
            self.send_message(dict(type="camera", action="center_position"))
        else:
            position = int(min(max(100 - (100 + y_pos) / 2, 0), 100))
            self.send_message(dict(type="camera", action="set_position", args=dict(position=position)))

    def move_motor(self, x_pos, y_pos):
        if abs(x_pos) == 0 and abs(y_pos) == 0:
            self.send_message(dict(type="motor", action="stop"))
        else:

            right_speed = min(max(-y_pos - x_pos, -100), 100)
            left_speed = min(max(-y_pos + x_pos, -100), 100)

            if self.motor_slow_mode:
                right_speed = int(0.3 * right_speed)
                left_speed = int(0.3 * left_speed)

            if left_speed < 0:
                left_orientation = 'B'
            else:
                left_orientation = 'F'

            if right_speed < 0:
                right_orientation = 'B'
            else:
                right_orientation = 'F'

            self.send_message(dict(type="motor", action="move", args=dict(left_orientation=left_orientation,
                                                                          left_speed=abs(left_speed),
                                                                          right_orientation=right_orientation,
                                                                          right_speed=abs(right_speed),
                                                                          duration=30,
                                                                          distance=None,
                                                                          rotation=None,
                                                                          auto_stop=False,
                                                                          )))

    def run_axis_action(self, action, x_pos, y_pos):
        x_pos_percent = int(x_pos * 100)
        y_pos_percent = int(y_pos * 100)
        if action == "motor":
            self.move_motor(x_pos_percent, y_pos_percent)
        elif action == "camera":
            self.move_camera(x_pos_percent, y_pos_percent)

    def gamepad_button_callback(self, joystick, button, down):
        gamepad_button_mapping = self.get_gamepad_config(joystick).get("button", {})
        button_str = str(button)  # Convert to string, as config is in json
        if button_str in gamepad_button_mapping:
            button_config = gamepad_button_mapping[button_str]
            if "action" in button_config:
                action = button_config["action"]
                if "axis" in button_config:
                    axis = button_config["axis"]
                    if action not in self.axis_positions:
                        self.axis_positions[action] = {"x": 0.0, "y": 0.0}
                    self.axis_positions[action][axis] = float(button_config["down"]) if down else float(button_config["up"])
                    self.run_axis_action(action, self.axis_positions[action]["x"], self.axis_positions[action]["y"])
                elif down:
                    self.run_action(action)
        else:
            print(f"Button not mapped {button}")

    def send_message(self, message):
        try:
            self.socket.sendall(json.dumps(message).encode() + b"\n")
        except:
            # In case of failure try to reconnect
            if self.host_ip is not None:
                print("Unable to send message, reconnect")
                self.connect(self.host_ip, self.port)
                self.socket.sendall(json.dumps(message).encode() + b"\n")

    def play_message(self, message, destination="lcd"):
        socket_message = {
            "type": "message",
            "action": "play",
            "args": {"message": message, "destination": destination}
        }
        self.send_message(socket_message)

    def key_press_callback(self, e, down):
        keyboard_mapping = self.controller_mapping.get("keyboard")
        key_str = QKeySequence(e.key()).toString().upper()
        if e.key() == Qt.Key_Shift:
            key_str = "SHIFT"
        elif e.key() == Qt.Key_Alt:
            key_str = "ALT"
        elif e.key() == Qt.Key_Control:
            key_str = "CONTROL"
        if key_str in keyboard_mapping:
            key_config = keyboard_mapping[key_str]
            if "action" in key_config:
                action = key_config["action"]
                if "axis" in key_config:
                    axis = key_config["axis"]
                    if action not in self.axis_positions:
                        self.axis_positions[action] = {"x": 0, "y": 0}
                    self.axis_positions[action][axis] = key_config["down"] if down else key_config["up"]
                    self.run_axis_action(action, self.axis_positions[action]["x"], self.axis_positions[action]["y"])
                elif down:
                    self.run_action(action)
        else:
            print(f"Key not found {key_str}")