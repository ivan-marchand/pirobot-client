from app import App
import argparse
import sys

from PyQt5.QtWidgets import QApplication, QStyleFactory

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Start PiRemote')
    parser.add_argument('--host', type=str, help='Server host name', required=False)
    parser.add_argument('-f', '--full_screen', action='store_true')
    parser.add_argument('-p', '--port', type=int, help='Port used by server', default=8000)
    parser.add_argument('-vp', '--video_port', type=int, help='port used by video server', default=8001)
    parser.add_argument('-s', '--style', type=str, help='QT style used for the app', choices=QStyleFactory.keys())
    args = parser.parse_args()

    app = QApplication(sys.argv)
    if args.style is not None:
        app.setStyle(args.style)

    a = App(hostname=args.host, full_screen=args.full_screen, server_port=args.port, video_server_port=args.video_port)
    a.show()
    sys.exit(app.exec_())
