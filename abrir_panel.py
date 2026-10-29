"""Abrir una vista local. El servicio vive mientras esta terminal esté abierta."""
import argparse
import threading
import webbrowser
from configuracion import add_options, load_config
from puente_memoria import create_server


def main():
    parser = add_options(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    with create_server(load_config(args.config, args.demo), args.port) as server:
        url = f'http://127.0.0.1:{server.server_port}/panel.html'
        print(url, flush=True)
        if not args.no_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
