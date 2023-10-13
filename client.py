import aiohttp
import asyncio
import json
import queue
import traceback

from input_config_manager import InputConfigManager


class Client(object):
    message_queue = queue.Queue()

    def __init__(self, app, robot_config):
        self.app = app
        self.motor_slow_mode = False
        self.lock_camera = False
        self.host = None
        self.ws = None
        self.input_config_manager = InputConfigManager(robot_config=robot_config)
        self.axis_positions = {}
        self.consumers = {}

    def is_connected(self):
        return self.ws is not None

    def run_action(self, action_id):
        if action_id == "app_close":
            self.app.close()
        elif action_id == "say_message":
            self.app.open_play_message_window(destination="audio")
        elif action_id == "display_message":
            self.app.open_play_message_window(destination="lcd")
        elif action_id == "motor_slow_mode":
            self.motor_slow_mode = not self.motor_slow_mode
        elif action_id == "lock_camera":
            self.lock_camera = not self.lock_camera
            if not self.lock_camera:
                # Reset camera position
                self.move_camera(0, 0)
        else:
            for command in self.input_config_manager.get_commands_for_action(action_id):
                if "type" in command:
                    self.send_message(command)

    def start_video(self, source):
        message = {
            "type": "camera",
            "action": "start_video",
            "args": {
                "source": source
            }
        }
        self.send_message(message)

    def stop_video(self):
        message = {
            "type": "camera",
            "action": "stop_video",
        }
        self.send_message(message)

    def capture_picture(self, source, picture_format):
        message = {
            "type": "camera",
            "action": "capture_picture",
            "args": {
                "source": source,
                "format": picture_format,
            }
        }
        self.send_message(message)

    def __del__(self):
        if self.ws is not None:
            self.ws.close()
            self.ws = None

    async def connect(self, host):
        self.host = host
        while True:
            try:
                url = f"http://{host}/ws/robot"
                session = aiohttp.ClientSession()
                async with session.ws_connect(url) as ws:
                    print(f"Connected to {url}")
                    self.ws = ws
                    async for msg in ws:
                        message = json.loads(msg.data)
                        for consumer in self.consumers.get(message["topic"], []):
                            consumer(message["message"])
            except:
                traceback.print_exc()
            print(f"Unable to connect to {url}, reconnecting")
            await asyncio.sleep(1)

    def register_consumer(self, message_topic, consumer):
        if message_topic not in self.consumers:
            self.consumers[message_topic] = []
        self.consumers[message_topic].append(consumer)

    def gamepad_absolute_axis_callback(self, joystick, axis):
        group = self.input_config_manager.get_group_for_axis(joystick, axis)
        if group is not None:
            axis_position = self.input_config_manager.get_axis_position_for_group(joystick, group)
            self.run_axis_action(group, axis_position.get("x", 0.0), axis_position.get("y", 0.0))

    def gamepad_hat_callback(self, joystick, hat, x_pos, y_pos):
        group = self.input_config_manager.get_group_for_hat(joystick, hat)
        if group is not None:
            self.run_axis_action(group, x_pos, -y_pos)

    def move_camera(self, x_pos, y_pos):
        if not self.lock_camera:
            if abs(y_pos) < 2:
                self.send_message(dict(type="camera", action="center_position"))
            else:
                position = int(min(max(100 - (100 + y_pos) / 2, 0), 100))
                self.send_message(dict(type="camera", action="set_position", args=dict(position=position)))

    def drive_robot(self, x_pos, y_pos):
        if abs(x_pos) < 0.01 and abs(y_pos) < 0.01:
            self.send_message(dict(type="drive", action="stop"))
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

            self.send_message(dict(type="drive", action="move", args=dict(left_orientation=left_orientation,
                                                                          left_speed=abs(left_speed),
                                                                          right_orientation=right_orientation,
                                                                          right_speed=abs(right_speed),
                                                                          duration=30,
                                                                          distance=None,
                                                                          rotation=None,
                                                                          auto_stop=False,
                                                                          )))

    def run_axis_action(self, group, x_pos, y_pos):
        x_pos_percent = int(x_pos * 100)
        y_pos_percent = int(y_pos * 100)
        if group == "drive":
            self.drive_robot(x_pos_percent, y_pos_percent)
        elif group == "camera":
            self.move_camera(x_pos_percent, y_pos_percent)

    def gamepad_button_callback(self, joystick, button, down):
        action = self.input_config_manager.get_action_for_gamepad_button(joystick, button)
        if action is not None:
            action_config = self.input_config_manager.get_action_config(action)
            if "axis_group" in action_config and "group" in action_config and "axis_name" in action_config:
                group = action_config["group"]
                axis_name = action_config["axis_name"]
                if group not in self.axis_positions:
                    self.axis_positions[group] = {"x": 0.0, "y": 0.0}
                if down:
                    value = action_config.get("down_value", 1.0)
                else:
                    value = action_config.get("up_value", 0.0)
                self.axis_positions[group][axis_name] = value
                self.run_axis_action(group, self.axis_positions[group]["x"], self.axis_positions[group]["y"])
            elif down:
                self.run_action(action)

    def send_message(self, message):
        asyncio.run(self._send_message(message))

    async def _send_message(self, message):
        try:
            await self.ws.send_json(dict(topic="robot", message=message))
        except:
            print("Unable to send message")

    def play_message(self, message, destination="lcd"):
        socket_message = {
            "type": "talk",
            "action": "play",
            "args": {"message": message, "destination": destination}
        }
        self.send_message(socket_message)

    def key_press_callback(self, e, down):
        action = self.input_config_manager.get_axis_group_for_keyboard_key(e.key())
        if action is not None:
            action_config = self.input_config_manager.get_action_config(action)
            if action_config is not None and "axis_group" in action_config and "group" in action_config and "axis_name" in action_config:
                group = action_config["group"]
                axis_name = action_config["axis_name"]
                if group not in self.axis_positions:
                    self.axis_positions[group] = {"x": 0.0, "y": 0.0}
                if down:
                    value = action_config.get("down_value", 1.0)
                else:
                    value = action_config.get("up_value", 0.0)
                self.axis_positions[group][axis_name] = value
                self.run_axis_action(group, self.axis_positions[group]["x"], self.axis_positions[group]["y"])
            elif down:
                self.run_action(action)
