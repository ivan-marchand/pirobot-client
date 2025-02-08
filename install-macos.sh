pip install pyinstaller
mkdir ~/.pirobot-remote/
cp keyboard.config.json ~/.pirobot-remote/
pyinstaller -n piremote -F --windowed --icon ./pics/logo_small.icns --add-data ./config/*:config --add-data ./pics/*:pics main.py
mkdir ~/Applications
cp -r dist/piremote.app ~/Applications/