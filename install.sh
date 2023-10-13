sudo apt-get install libopencv-dev qtbase5-dev python3-pyqt5 python3-opencv
pip install pyinstaller
mkdir ~/.pirobot-remote/
cp keyboard.config.json ~/.pirobot-remote/
pyinstaller -n piremote -F --add-data ./config/*:config --add-data ./pics/*:pics main.py
