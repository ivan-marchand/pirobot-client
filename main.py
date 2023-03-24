from app import App
import argparse
import sys

from PyQt5.QtWidgets import QApplication

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start PiRemote')
    parser.add_argument('--host', type=str, help='Server host name', required=False)
    parser.add_argument('-f', '--full_screen', action='store_true')
    args = parser.parse_args()

    app = QApplication(sys.argv)

    a = App(hostname=args.host, full_screen=args.full_screen)
    a.show()
    sys.exit(app.exec_())