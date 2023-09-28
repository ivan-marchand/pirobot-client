from app import App
import argparse
import sys

from PyQt5.QtWidgets import QApplication, QStyleFactory

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start PiRemote')
    parser.add_argument('--host', type=str, help='Server host name', required=False)
    parser.add_argument('-f', '--full_screen', action='store_true')
    parser.add_argument('-s', '--style', type=str, help='QT style used for the app', choices=QStyleFactory.keys())
    args = parser.parse_args()

    app = QApplication(sys.argv)
    if args.style is not None:
        app.setStyle(args.style)

    a = App(host=args.host, full_screen=args.full_screen)
    a.show()
    sys.exit(app.exec_())
