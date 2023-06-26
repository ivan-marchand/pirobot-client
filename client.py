import json
import socket
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

from gamepad import GamePad


class Client(object):

    def __init__(self, app):
        self.app = app
        self.socket = None
        self.motor_slow_mode = False
        self.host_ip = None
        self.config_path = "config"
        self.actions = {}
        self.controller_mapping = {}
        self.axis_mapping = {}
        self.absolute_axis_positions = {}
        self.axis_positions = {}
        if not os.path.isdir(self.config_path):
            self.config_path = "/etc/piremote/config"

        self.load_config()

    def load_config(self):
        with open(os.path.join(self.config_path, "actions.json")) as action_file:
            self.actions = json.load(action_file)

        with open(os.path.join(self.config_path, "controller.json")) as controller_file:
            self.controller_mapping = json.load(controller_file)
            if "gamepad" in self.controller_mapping:
                for device_name, gamepad_config in self.controller_mapping.get("gamepad").items():
                    gamepad_absolute_mapping = gamepad_config.get("absolute_axis", {})
                    gamepad_config["axis_mapping"] = {}
                    for code, config in gamepad_absolute_mapping.items():
                        action, axis = config["action"], config["axis"]
                        if action not in gamepad_config["axis_mapping"]:
                            gamepad_config["axis_mapping"][action] = {}
                        gamepad_config["axis_mapping"][action][axis] = config
                        gamepad_config["axis_mapping"][action][axis]["code"] = code

    def run_action(self, action_id):
        if action_id == "app_close":
            self.app.close()
        elif action_id == "select_host":
            self.app.open_select_host_window()
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

    def connect(self, host_ip):
        try:
            if self.socket is not None:
                self.socket.close()
            self.socket = socket.socket(socket.AF_INET)
            self.socket.settimeout(1)
            self.socket.connect((host_ip, 8000))
            self.host_ip = host_ip
        except:
            print(f"Unable to connect to {host_ip}")
            raise

    def get_gamepad_config(self):
        if GamePad.gamepad is not None and GamePad.gamepad.device is not None:
            return self.controller_mapping.get("gamepad", {}).get(GamePad.gamepad.device.name.strip(), {})
        else:
            print("Not gamepad connect")
            return {}

    def gamepad_absolute_axis_callback(self, axis, position):
        self.absolute_axis_positions[axis] = position
        gamepad_absolute_mapping = self.get_gamepad_config().get("absolute_axis", {})
        if axis in gamepad_absolute_mapping:
            action = gamepad_absolute_mapping[axis]["action"]
            axis_mapping = self.get_gamepad_config().get("axis_mapping", {})
            if action in axis_mapping:
                x_pos = self.get_normalized_position(action, "x")
                y_pos = self.get_normalized_position(action, "y")
                self.axis_positions[action] = {"x": x_pos, "y": y_pos}
                self.run_axis_action(action)

    def get_normalized_position(self, action, axis):
        axis_mapping = self.get_gamepad_config().get("axis_mapping")
        if axis not in axis_mapping[action]:
            return 0
        code = axis_mapping[action][axis]["code"]
        positions = {str(code): value for code, value in self.absolute_axis_positions.items()}
        if code not in positions:
            return 0
        absolute_position = positions[code]["value"]
        max_pos = axis_mapping[action][axis].get("max", positions[code]["max"])
        min_pos = axis_mapping[action][axis].get("min", positions[code]["min"])
        value_normalized = float(absolute_position - min_pos) / float(max_pos - min_pos)
        value_normalized = int(-100 + (value_normalized * 200))
        value_normalized = min(100, value_normalized)
        value_normalized = max(-100, value_normalized)
        return value_normalized

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
                                                                          duration=10,
                                                                          distance=None,
                                                                          rotation=None,
                                                                          auto_stop=False,
                                                                          )))

    def run_axis_action(self, action):
            x_pos = self.axis_positions.get(action, {}).get("x", 0)
            y_pos = self.axis_positions.get(action, {}).get("y", 0)
            if action == "motor":
                self.move_motor(x_pos, y_pos)
            elif action == "camera":
                self.move_camera(x_pos, y_pos)

    def gamepad_key_callback(self, key, down):
        key_str, code = key
        if not isinstance(key_str, list):
            key_str = [key_str]
        key_str.append(str(code))
        gamepad_key_mapping = self.get_gamepad_config().get("key", {})
        found = False
        for k in key_str:
            if k in gamepad_key_mapping:
                found = True
                key_config = gamepad_key_mapping[k]
                if "action" in key_config:
                    action = key_config["action"]
                    if "axis" in key_config:
                        axis = key_config["axis"]
                        if action not in self.axis_positions:
                            self.axis_positions[action] = {"x": 0, "y": 0}
                        self.axis_positions[action][axis] = key_config["down"] if down else key_config["up"]
                        self.run_axis_action(action)
                    elif down:
                        self.run_action(action)
                break

        if not found:
            print(f"Key not mapped {key}")

    def send_message(self, message):
        try:
            self.socket.sendall(json.dumps(message).encode() + b"\n")
        except:
            # In case of failure try to reconnect
            if self.host_ip is not None:
                print("Unable to send message, reconnect")
                self.connect(self.host_ip)
                self.socket.sendall(json.dumps(message).encode() + b"\n")

    def button_callback(self, action_id):
        self.run_action(action_id)

    def key_press_callback(self, e):
        keyboard_mapping = self.controller_mapping.get("keyboard")
        key_str = QKeySequence(e.key()).toString().upper()
        if e.key() == Qt.Key_Shift:
            key_str = "SHIFT"
        elif e.key() == Qt.Key_Alt:
            key_str = "ALT"
        elif e.key() == Qt.Key_Control:
            key_str = "CONTROL"
        if key_str in keyboard_mapping:
            self.run_action(keyboard_mapping[key_str]["action"])
        else:
            print(f"Key not found {key_str}")