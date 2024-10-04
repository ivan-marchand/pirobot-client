APP_NAME=piremote

sudo apt-get install libopencv-dev qtbase5-dev python3-pyqt5 python3-opencv
pip install pyinstaller
mkdir ~/.pirobot-remote/
cp keyboard.config.json ~/.pirobot-remote/
pipenv run pyinstaller -n piremote -F --add-data ./config/*:config --add-data ./pics/*:pics main.py

sudo cp dist/$APP_NAME /usr/local/bin/
sudo cp pics/logo_small.svg /usr/share/pixmaps/piremote.svg
sudo cp piremote.desktop /usr/share/applications/
