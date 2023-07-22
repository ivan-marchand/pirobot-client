from functools import partial

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


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


class RobotConfigManagerPopup(QDialog):
    new_config_signal = pyqtSignal(dict)

    def __init__(self, client):
        super().__init__()
        self.setWindowTitle("Robot Configuration")
        self.client = client

        vbox = QVBoxLayout()
        self.config_layout = QVBoxLayout()
        vbox.addLayout(self.config_layout)

        hbox = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        close_button.setFocus()
        hbox.addWidget(close_button)

        vbox.addLayout(hbox)
        self.setLayout(vbox)

        self.new_config_signal.connect(self.update_config)
        self.client.send_message(dict(type="configuration", action="get"))
        self.client.register_consumer("configuration", self.get_configuration_callback)

    def get_configuration_callback(self, message):
        self.new_config_signal.emit(message)

    def update_config_value(self, config_name, widget):
        if type(widget) == QComboBox:
            config_value = widget.currentText()
        else:
            config_value = widget.text()

        self.client.send_message(
            dict(
                type="configuration",
                action="update",
                args=dict(key=config_name, value=config_value)
            )
        )

    def reset_config_value(self, config_name):
        self.client.send_message(
            dict(type="configuration", action="delete", args=dict(key=config_name))
        )

    def update_config(self, message):
        config = message["config"]
        success = message["success"]
        action = message["action"]

        # Generate config category
        config_by_category = {}
        for config_name, config_item in config.items():
            category = config_item.get("category")
            if category == "debug":
                continue
            if category is None:
                category = "unknown"
            if category not in config_by_category:
                config_by_category[category] = {}
            config_by_category[category][config_name] = config_item

        # Clear config box
        for i in reversed(range(self.config_layout.count())):
            self.config_layout.itemAt(i).widget().deleteLater()

        if not success and action == "update":
            label = QLabel("Unable to update config")
            label.setStyleSheet("color: red; font-weight: bold")
            self.config_layout.addWidget(label)

        # Add config value
        for category in config_by_category.keys():
            category_group_box = QGroupBox(category.upper())
            self.config_layout.addWidget(category_group_box)
            category_config_layout = ConfigLayout()
            category_group_box.setLayout(category_config_layout)
            for config_name, config_item in config_by_category[category].items():
                config_type = config_item["type"]
                # Config Value
                default_value = config_item["default"]
                if config_type == "bool":
                    config_value_widget = QComboBox()
                    config_value_widget.addItems(["Y", "N"])
                    config_value_widget.setCurrentText("Y" if config_item["value"] else "N")
                    default_value = "Y" if config_item["default"] else "N"
                elif "choices" in config_item:
                    config_value_widget = QComboBox()
                    config_value_widget.addItems(config_item["choices"])
                    config_value_widget.setCurrentText(str(config_item["value"]))
                else:
                    config_value_widget = QLineEdit()
                    config_value_widget.setText(str(config_item["value"]))

                # Config Name
                category_config_layout.addWidget(QLabel(f"{config_name} (default: {default_value})"))
                category_config_layout.addWidget(config_value_widget)

                # Update Button
                update_button = QPushButton("Update")
                update_button.clicked.connect(
                    partial(self.update_config_value, config_name, config_value_widget)
                )
                category_config_layout.addWidget(update_button)

                # Reset Button
                reset_button = QPushButton("Reset to default")
                reset_button.clicked.connect(partial(self.reset_config_value, config_name))
                category_config_layout.addWidget(reset_button)
                category_config_layout.newRow()
