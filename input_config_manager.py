import json
import os
from functools import partial
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gamepad import GamePad


def snake_case_to_human(text):
    parts = text.split("_")
    return " ".join([part.title() for part in parts])


class ConfigLayout(QGridLayout):

    def __init__(self):
        super().__init__()
        self.row = 0
        self.col = 0

    def addWidget(self, w):
        super().addWidget(w, self.row, self.col)
        self.col += 1

    def newRow(self):
        self.col = 0
        self.row += 1


class InputConfigManager(object):

    def __init__(self, robot_config):
        self.robot_config = robot_config
        self.config_path = os.path.join(os.path.dirname(__file__), "config")
        self.user_config_path = os.path.join(Path.home(), ".pirobot-remote")
        self.actions = {}
        self.keyboard_mapping = {}
        self.gamepad_mapping = {}

        self.load()

    def is_configured(self, joystick):
        return joystick.get_guid() in self.gamepad_mapping

    def get_action_config(self, action):
        return self.actions.get(action)

    def get_commands_for_action(self, action):
        return self.actions.get(action, {}).get("commands", [])

    def get_keyboard_event_for_action(self, action):
        if action in self.keyboard_mapping:
            return self.keyboard_mapping[action]
        else:
            return None

    def get_action_for_keyboard_event(self, event):
        for action, action_event in self.keyboard_mapping.items():
            if action_event == event:
                return action
        return None

    def get_axis_group_for_keyboard_key(self, key):
        return self.get_action_for_keyboard_event({"type": "key", "key": key})

    def get_gamepad_events_for_action(self, action, joystick):
        events = []
        guid = joystick.get_guid()
        if guid in self.gamepad_mapping:
            axis_group = self.actions.get(action, {}).get("axis_group")
            hat_group = self.actions.get(action, {}).get("hat_group")
            if axis_group is not None and axis_group in self.gamepad_mapping[guid]["axis_group"]:
                events.append(self.gamepad_mapping[guid]["axis_group"][axis_group])
            if hat_group is not None and hat_group in self.gamepad_mapping[guid]["hat_group"]:
                events.append(self.gamepad_mapping[guid]["hat_group"][hat_group])
            if action in self.gamepad_mapping[guid]["actions"]:
                events.append(self.gamepad_mapping[guid]["actions"][action])
        return events

    @staticmethod
    def keyboard_event_to_string(event):
        if event is None:
            return "N/A"
        if event["type"] == "key":
            key = event["key"]
            if key == Qt.Key_Shift:
                key_str = "SHIFT"
            elif key == Qt.Key_Alt:
                key_str = "ALT"
            elif key == Qt.Key_Control:
                key_str = "CONTROL"
            else:
                key_str = QKeySequence(key).toString().upper()
            return key_str

    @staticmethod
    def gamepad_event_to_string(event):
        if event is not None:
            event_type = event["type"]
            if event_type == "button":
                return f"B{event['button']}"
            elif event_type == "axis":
                return f"A{event['axis']}"
            elif event_type == "hat":
                return f"H{event['hat']}"

        return "N/A"

    def set_keyboard_key_for_action(self, action, key):
        event = {"type": "key", "key": key}
        existing_action = self.get_action_for_keyboard_event(event)
        if existing_action is not None:
            del self.keyboard_mapping[existing_action]
        self.keyboard_mapping[action] = event

    def reset_keyboard_event_for_action(self, action):
        if action in self.keyboard_mapping:
            del self.keyboard_mapping[action]

    def get_action_for_gamepad_event(self, joystick, event):
        guid = joystick.get_guid()
        if guid in self.gamepad_mapping:
            for action, action_event in self.gamepad_mapping[guid]["actions"].items():
                if action_event == event:
                    return action
        return None

    def get_action_for_gamepad_button(self, joystick, button):
        return self.get_action_for_gamepad_event(joystick, {"type": "button", "button": button})

    def get_axis_group_for_gamepad_event(self, joystick, event):
        guid = joystick.get_guid()
        if guid in self.gamepad_mapping:
            for axis_group, axis_group_event in self.gamepad_mapping[guid]["axis_group"].items():
                if axis_group_event == event:
                    return axis_group
        return None

    def get_hat_group_for_gamepad_event(self, joystick, event):
        guid = joystick.get_guid()
        if guid in self.gamepad_mapping:
            for hat_group, hat_group_event in self.gamepad_mapping[guid]["hat_group"].items():
                if hat_group_event == event:
                    return hat_group
        return None

    def get_axis_position_for_group(self, joystick, group):
        guid = joystick.get_guid()
        position = {}
        if guid in self.gamepad_mapping:
            for action_config in self.actions.values():
                if group is not None and action_config.get("group") == group:
                    axis_name = action_config.get("axis_name")
                    axis_group = action_config.get("axis_group")
                    if axis_name is not None and axis_group is not None and axis_name not in position:
                        axis = self.gamepad_mapping[guid]["axis_group"].get(axis_group, {}).get("axis")
                        if axis is not None:
                            position[axis_name] = joystick.get_axis(axis)

        return position

    def get_group_for_axis(self, joystick, axis):
        guid = joystick.get_guid()
        axis_group = None
        if guid in self.gamepad_mapping:
            for group, axis_group_event in self.gamepad_mapping[guid]["axis_group"].items():
                if axis_group_event["axis"] == axis:
                    axis_group = group

        if axis_group is not None:
            for action_config in self.actions.values():
                if action_config.get("axis_group") == axis_group:
                    return action_config.get("group")

        return None

    def get_group_for_hat(self, joystick, hat):
        guid = joystick.get_guid()
        hat_group = None
        for group, hat_group_config in self.gamepad_mapping[guid]["hat_group"].items():
            if hat_group_config["hat"] == hat:
                hat_group = group

        if hat_group is not None:
            for action_config in self.actions.values():
                if action_config.get("hat_group") == hat_group:
                    return action_config.get("group")

    def set_gamepad_event_for_action(self, action, joystick, event, axis_group=None, hat_group=None):
        guid = joystick.get_guid()
        if guid not in self.gamepad_mapping:
            self.gamepad_mapping[guid] = {
                "actions": {},
                "axis_group": {},
                "hat_group": {},
                "guid": guid,
                "name": joystick.get_name(),
            }

        if axis_group is not None:
            existing_axis_group = self.get_axis_group_for_gamepad_event(joystick, event)
            if existing_axis_group is not None:
                del self.gamepad_mapping[guid]["axis_group"][existing_axis_group]
            self.gamepad_mapping[guid]["axis_group"][axis_group] = event
        elif hat_group is not None:
            existing_hat_group = self.get_hat_group_for_gamepad_event(joystick, event)
            if existing_hat_group is not None:
                del self.gamepad_mapping[guid]["hat_group"][existing_hat_group]
            self.gamepad_mapping[guid]["hat_group"][hat_group] = event
        else:
            existing_action = self.get_action_for_gamepad_event(joystick, event)
            if existing_action is not None:
                del self.gamepad_mapping[guid]["actions"][existing_action]
            self.gamepad_mapping[guid]["actions"][action] = event

    def set_gamepad_button_for_action(self, action, joystick, button):
        self.set_gamepad_event_for_action(action, joystick, {"type": "button", "button": button})

    def set_gamepad_axis_for_action(self, action, joystick, axis):
        axis_group = self.actions.get(action, {}).get("axis_group")
        if axis_group is not None:
            self.set_gamepad_event_for_action(action, joystick, {"type": "axis", "axis": axis}, axis_group=axis_group)

    def set_gamepad_hat_for_action(self, action, joystick, hat):
        hat_group = self.actions.get(action, {}).get("hat_group")
        if hat_group is not None:
            self.set_gamepad_event_for_action(action, joystick, {"type": "hat", "hat": hat}, hat_group=hat_group)

    def reset_gamepad_event_for_action(self, joystick, action):
        guid = joystick.get_guid()
        if guid in self.gamepad_mapping:
            if action in self.gamepad_mapping[guid]["actions"]:
                del self.gamepad_mapping[guid]["actions"][action]

            if action in self.gamepad_mapping[guid]["axis_group"]:
                del self.gamepad_mapping[guid]["axis_group"][action]

            if action in self.gamepad_mapping[guid]["hat_group"]:
                del self.gamepad_mapping[guid]["hat_group"][action]

    def has_capability(self, action):
        action_config = self.actions.get(action)
        if action_config is not None:
            needs = action_config.get("needs")
            if needs is not None:
                return self.robot_config.get(f"robot_has_{needs}", False)
            else:
                return True
        else:
            return False

    def load(self):
        # Actions
        with open(os.path.join(self.config_path, "actions.json")) as action_file:
            self.actions = json.load(action_file)

        # Keyboard config
        self.keyboard_mapping = {}
        for config_path in [self.user_config_path, self.config_path]:
            config_file_path = os.path.join(config_path, "keyboard.config.json")
            if os.path.isfile(config_file_path):
                with open(config_file_path) as config_file:
                    try:
                        self.keyboard_mapping = json.load(config_file)
                    except:
                        print(f"Unable to open config file {config_file_path}")
                        continue
                    break

        # Gamepad config
        self.gamepad_mapping = {}
        for filename in os.listdir(self.user_config_path):
            if filename.startswith("gamepad.") and filename.endswith(".config.json"):
                with open(os.path.join(self.user_config_path, filename)) as config_file:
                    try:
                        gamepad_config = json.load(config_file)
                        self.gamepad_mapping[gamepad_config["guid"]] = gamepad_config
                    except:
                        print(f"Unable to open config file {config_file_path}")
                        continue

    def save(self):
        # Keyboard config
        if not os.path.isdir(self.user_config_path):
            os.makedirs(self.user_config_path)
        with open(os.path.join(self.user_config_path, "keyboard.config.json"), "w") as keyboard_config_file:
            json.dump(self.keyboard_mapping, keyboard_config_file)
        for guid, gamepad_config in self.gamepad_mapping.items():
            with open(os.path.join(self.user_config_path, f"gamepad.{guid}.config.json"), "w") as gamepad_config_file:
                json.dump(gamepad_config, gamepad_config_file)


class KeyboardCaptureDialog(QDialog):
    def __init__(self, action, callback, config_manager):
        super().__init__()
        self.action = action
        self.callback = callback
        self.config_manager = config_manager
        self.setWindowTitle(f"Defined key for {action}")
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("Press any key..."))
        reset_button = QPushButton("Reset")
        reset_button.setFocusPolicy(Qt.NoFocus)
        reset_button.clicked.connect(self.reset_action)
        self.layout.addWidget(reset_button)

    def reset_action(self):
        self.config_manager.reset_keyboard_event_for_action(action=self.action)
        self.close()
        self.callback()

    def keyPressEvent(self, e):
        self.config_manager.set_keyboard_key_for_action(action=self.action, key=e.key())
        self.close()
        self.callback()


class GamepadCaptureDialog(QDialog):
    def __init__(self, action, callback, joystick, config_manager):
        super().__init__()
        self.action = action
        self.callback = callback
        self.joystick = joystick
        self.config_manager = config_manager
        self.setWindowTitle(f"Defined key for {action}")
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("Press any button..."))
        reset_button = QPushButton("Reset")
        reset_button.setFocusPolicy(Qt.NoFocus)
        reset_button.clicked.connect(self.reset_action)
        self.layout.addWidget(reset_button)
        InputConfigManagerPopup.register_gamepad_event_listener(self)

    def reset_action(self):
        self.config_manager.reset_gamepad_event_for_action(action=self.action, joystick=self.joystick)
        self.close()
        self.callback()

    def button_event_callback(self, joystick, button):
        if joystick.get_guid() == self.joystick.get_guid():
            self.config_manager.set_gamepad_button_for_action(action=self.action, joystick=self.joystick, button=button)
            self.close()
            self.callback()

    def axis_event_callback(self, joystick, axis):
        if joystick.get_guid() == self.joystick.get_guid():
            self.config_manager.set_gamepad_axis_for_action(action=self.action, joystick=self.joystick, axis=axis)
            self.close()
            self.callback()

    def hat_event_callback(self, joystick, hat):
        if joystick.get_guid() == self.joystick.get_guid():
            self.config_manager.set_gamepad_hat_for_action(action=self.action, joystick=self.joystick, hat=hat)
            self.close()
            self.callback()

    def closeEvent(self, e):
        InputConfigManagerPopup.unregister_gamepad_event_listener()


class AssignedEventWidget(QLineEdit):

    def __init__(self, action, config_manager):
        super().__init__()
        self.action = action
        self.config_manager = config_manager
        self.setFixedWidth(80)
        self.setEnabled(False)
        self.update()
        description = self.config_manager.actions.get(action, {}).get("description")
        if description is not None:
            self.setToolTip(description)

    def update(self):
        self.setText(self.get_event_name())

    def get_event_name(self):
        raise NotImplementedError


class AssignedKeyboardEventWidget(AssignedEventWidget):
    widgets = []

    @classmethod
    def clear_all(cls):
        cls.widgets = []

    @classmethod
    def update_all(cls):
        for widget in cls.widgets:
            widget.update()

    def __init__(self, action, config_manager):
        super().__init__(action, config_manager)
        self.widgets.append(self)

    def get_event_name(self):
        return InputConfigManager.keyboard_event_to_string(
            self.config_manager.get_keyboard_event_for_action(self.action)
        )


class AssignedGamepadEventWidget(AssignedEventWidget):
    widgets = {}

    @classmethod
    def clear_all(cls, joystick):
        cls.widgets[joystick.get_guid()] = []

    @classmethod
    def update_all(cls, joystick):
        for widget in cls.widgets.get(joystick.get_guid(), []):
            widget.update()

    def __init__(self, action, config_manager, joystick):
        self.joystick = joystick
        super().__init__(action, config_manager)
        guid = joystick.get_guid()
        if guid not in self.widgets:
            self.widgets[guid] = []
        self.widgets[guid].append(self)

    def get_event_name(self):
        return " ".join([InputConfigManager.gamepad_event_to_string(e) for e in self.config_manager.get_gamepad_events_for_action(self.action, self.joystick)])


class SetButtonWidget(QPushButton):
    def __init__(self, callback):
        super().__init__("Set")
        self.setFixedWidth(50)
        self.clicked.connect(callback)


class InputConfigTab(QWidget):

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        app = QApplication.instance()
        if app.primaryScreen().size().width() < 500:
            # Small screen?
            self.layout = QVBoxLayout(self)
        else:
            self.layout = QHBoxLayout(self)
        self.setLayout(self.layout)

        # Drive controls
        drive_control_frame = QGroupBox("Drive Control")
        self.layout.addWidget(drive_control_frame)
        drive_control_layout = QGridLayout()
        drive_control_layout.setSpacing(0)
        drive_control_frame.setLayout(drive_control_layout)
        # UP
        action = "drive_forward"
        drive_control_layout.addWidget(self.get_assigned_widget(action=action), 0, 2)
        drive_control_layout.addWidget(SetButtonWidget(partial(self.open_capture_dialog, action)), 0, 3)
        # LEFT
        action = "drive_left"
        drive_control_layout.addWidget(self.get_assigned_widget(action=action), 1, 1)
        drive_control_layout.addWidget(SetButtonWidget(partial(self.open_capture_dialog, action)), 1, 0)
        # RIGHT
        action = "drive_right"
        drive_control_layout.addWidget(self.get_assigned_widget(action=action), 1, 4)
        drive_control_layout.addWidget(SetButtonWidget(partial(self.open_capture_dialog, action)), 1, 5)
        # DOWN
        action = "drive_backward"
        drive_control_layout.addWidget(self.get_assigned_widget(action=action), 2, 2)
        drive_control_layout.addWidget(SetButtonWidget(partial(self.open_capture_dialog, action)), 2, 3)

        # Action Panel
        action_frame = QGroupBox("Shortcuts")
        self.layout.addWidget(action_frame)
        self.action_layout = QVBoxLayout()
        action_frame.setLayout(self.action_layout)

        action_by_group = {}
        for action, action_config in self.config_manager.actions.items():
            if not self.config_manager.has_capability(action):
                continue
            group = action_config.get("group", "unknown")
            # Skip drive group
            if group == "drive":
                continue
            if group not in action_by_group:
                action_by_group[group] = {}
            action_by_group[group][action] = action_config

        action_layout = ConfigLayout()

        for group in action_by_group.keys():
            group_label = QLabel(group.upper())
            font = group_label.font()
            font.setBold(True)
            group_label.setFont(font)
            action_layout.addWidget(group_label)
            action_layout.newRow()

            for action, action_config in action_by_group[group].items():
                action_layout.addWidget(QLabel(action_config.get("name", snake_case_to_human(action))))
                action_layout.addWidget(self.get_assigned_widget(action=action))
                action_layout.addWidget(SetButtonWidget(partial(self.open_capture_dialog, action)))
                action_layout.newRow()

        self.action_layout.addLayout(action_layout)

        self.capture_dialog = None

    def closeEvent(self, e):
        if self.capture_dialog is None or not self.capture_dialog.isVisible():
            self.capture_dialog.close()

    def open_capture_dialog(self, action):
        if self.capture_dialog is None or not self.capture_dialog.isVisible():
            self.capture_dialog = self.get_capture_dialog(action)
            self.capture_dialog.show()

    def get_capture_dialog(self, action):
        raise NotImplementedError()

    def get_assigned_widget(self, action):
        raise NotImplementedError()


class KeyboardConfigTab(InputConfigTab):
    def __init__(self, config_manager):
        AssignedKeyboardEventWidget.clear_all()
        super().__init__(config_manager)

    def get_capture_dialog(self, action):
        return KeyboardCaptureDialog(
            action=action, callback=AssignedKeyboardEventWidget.update_all, config_manager=self.config_manager
        )

    def get_assigned_widget(self, action):
        return AssignedKeyboardEventWidget(action=action, config_manager=self.config_manager)


class GamepadConfigTab(InputConfigTab):

    def __init__(self, joystick, config_manager):
        self.joystick = joystick
        AssignedGamepadEventWidget.clear_all(joystick)
        super().__init__(config_manager)

    def get_capture_dialog(self, action):
        return GamepadCaptureDialog(
            action=action,
            callback=partial(AssignedGamepadEventWidget.update_all, self.joystick),
            config_manager=self.config_manager,
            joystick=self.joystick
        )

    def get_assigned_widget(self, action):
        return AssignedGamepadEventWidget(action=action, config_manager=self.config_manager, joystick=self.joystick)


class InputConfigManagerPopup(QMainWindow):
    gamepad_added_signal = pyqtSignal("PyQt_PyObject")
    gamepad_removed_signal = pyqtSignal("PyQt_PyObject")
    gamepad_event_listener = None

    @staticmethod
    def register_gamepad_event_listener(listener):
        InputConfigManagerPopup.gamepad_event_listener = listener

    @staticmethod
    def unregister_gamepad_event_listener():
        InputConfigManagerPopup.gamepad_event_listener = None

    def __init__(self, robot_config, close_callback, selected_joystick):
        super().__init__()
        self.close_callback = close_callback
        self.robot_config = robot_config
        self.selected_joystick = selected_joystick
        self.config_manager = InputConfigManager(robot_config=robot_config)
        self.setWindowTitle("Input Device Configuration")

        # Display tabs
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        #   self.tabs.setFocusPolicy(Qt.NoFocus)
        self.keyboard_tab = KeyboardConfigTab(config_manager=self.config_manager)
        self.gamepad_tabs = []

        # Add tabs
        self.tabs.addTab(self.keyboard_tab, "Keyboard")
        self.layout.addWidget(self.tabs)

        button_box = QHBoxLayout()
        self.layout.addLayout(button_box)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.close)
        button_box.addWidget(cancel_button)
        apply_button = QPushButton("Apply")
        apply_button.setDefault(True)
        apply_button.setFocus()
        apply_button.clicked.connect(self.apply)
        button_box.addWidget(apply_button)
        save_button = QPushButton("Save && Exit")
        save_button.setDefault(True)
        save_button.setFocus()
        save_button.clicked.connect(self.save)
        button_box.addWidget(save_button)

        # Add scroll area
        widget = QWidget()
        widget.setLayout(self.layout)
        app = QApplication.instance()
        if app.primaryScreen().size().width() < 500:
            # Small screen? Use scrolling
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(widget)

            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setCentralWidget(scroll)
        else:
            self.setCentralWidget(widget)

        # Start Gamepad loop
        self.start_gamepad()

    def closeEvent(self, event):
        GamePad.stop_gamepad()
        self.close_callback()

    def start_gamepad(self):
        self.gamepad_added_signal.connect(self.gamepad_added_callback)
        self.gamepad_removed_signal.connect(self.gamepad_removed_callback)
        callback = {
            "axis_motion": self.gamepad_absolute_axis_callback,
            "button": self.gamepad_button_callback,
            "hat_motion": self.gamepad_hat_callback,
            "joystick_added": self.gamepad_added_signal.emit,
            "joystick_removed": self.gamepad_removed_signal.emit
        }
        GamePad.start_gamepad(callback=callback)

    def gamepad_absolute_axis_callback(self, joystick, axis):
        if InputConfigManagerPopup.gamepad_event_listener is not None and abs(joystick.get_axis(axis)) > 0.5:
            InputConfigManagerPopup.gamepad_event_listener.axis_event_callback(joystick, axis)

    def gamepad_hat_callback(self, joystick, hat, x_pos, y_pos):
        if InputConfigManagerPopup.gamepad_event_listener is not None:
            InputConfigManagerPopup.gamepad_event_listener.hat_event_callback(joystick, hat)

    def gamepad_button_callback(self, joystick, button, down):
        if down and InputConfigManagerPopup.gamepad_event_listener is not None:
            InputConfigManagerPopup.gamepad_event_listener.button_event_callback(joystick, button)

    def gamepad_added_callback(self, joystick):
        gamepad_tab = GamepadConfigTab(joystick=joystick, config_manager=self.config_manager)
        self.gamepad_tabs.append(gamepad_tab)
        self.tabs.addTab(gamepad_tab, joystick.get_name())
        if self.selected_joystick is not None and joystick.get_guid() == self.selected_joystick.get_guid():
            self.tabs.setCurrentIndex(self.tabs.indexOf(gamepad_tab))
        else:
            # Select keyboard config
            self.tabs.setCurrentIndex(0)

    def gamepad_removed_callback(self, joystick):
        index = None
        for i, tab in enumerate(self.gamepad_tabs):
            if tab.joystick.get_guid() == joystick.get_guid():
                index = i
        if index is not None:
            self.tabs.removeTab(index + 1)
        del self.gamepad_tabs[index]

    def apply(self):
        self.config_manager.save()

    def save(self):
        self.config_manager.save()
        self.close()

