mkdir ~/.pirobot-remote/
cp keyboard.config.json ~/.pirobot-remote/
pyinstaller -n piremote -F --add-data config/*:config --add-data pics/*:pics -w --icon pics/logo_small.ico main.py
cp dist/piremote.exe ~/Desktop/