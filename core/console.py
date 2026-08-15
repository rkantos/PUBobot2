# -*- coding: utf-8 -*-
import sys
import os
import datetime
from threading import Thread
from multiprocessing import Queue

# Interactive console dependencies
try:
    import rlcompleter
    try:
        import readline
    except ModuleNotFoundError:  # windows support
        import pyreadline as readline
    INTERACTIVE_AVAILABLE = True
except ImportError:
    INTERACTIVE_AVAILABLE = False

from core.config import cfg


LogLevelToInt = {
    'CHAT': 0,
    'DEBUG': 1,
    'COMMANDS': 2,
    'INFO': 3,
    'ERRORS': 4,
    'NOTHING': 5
}


# Enable interactive console locally, disable it on Railway.
#
# You can explicitly override this with:
# INTERACTIVE_CONSOLE=true/false
#
# On Railway, RAILWAY_ENVIRONMENT is normally present, so the
# interactive console is disabled automatically.
_interactive_setting = os.environ.get("INTERACTIVE_CONSOLE")

if _interactive_setting is not None:
    INTERACTIVE_CONSOLE = _interactive_setting.lower() in (
        "1", "true", "yes", "on"
    )
else:
    INTERACTIVE_CONSOLE = (
        "RAILWAY_ENVIRONMENT" not in os.environ
        and INTERACTIVE_AVAILABLE
        and sys.stdin.isatty()
    )


class Log:

    def __init__(self):
        # Create log dir if needed
        if not os.path.exists(os.path.abspath("logs")):
            os.makedirs("logs")

        self.file = open(
            datetime.datetime.now().strftime("logs/log_%Y-%m-%d-%H:%M"),
            'w'
        )

        self.loglevel = LogLevelToInt[cfg.LOG_LEVEL]

    @staticmethod
    def display(string):
        # Have to do this encoding/decoding because Python
        # can fail to encode some symbols depending on the terminal.
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

        string = str(string).encode(
            encoding, 'ignore'
        ).decode(encoding)

        if INTERACTIVE_CONSOLE:
            # Save user input line, print string and then restore
            # the current input line.
            line_buffer = readline.get_line_buffer()

            sys.stdout.write(
                "\r\n\033[F\033[K"
                + string
                + '\r\n>'
                + line_buffer
            )
            sys.stdout.flush()
        else:
            # Railway / non-interactive environment.
            print(string, flush=True)

    def log(self, data, log_level):
        string = str(data).encode(
            getattr(sys.stdout, "encoding", None) or "utf-8",
            'ignore'
        ).decode(
            getattr(sys.stdout, "encoding", None) or "utf-8"
        )

        string = "{}|{}> {}".format(
            datetime.datetime.now().strftime("%d.%m.%Y (%H:%M:%S)"),
            log_level,
            string
        )

        self.display(string)
        self.file.write(string + '\r\n')
        self.file.flush()

    def close(self):
        self.file.close()

    def chat(self, data):
        if self.loglevel <= 0:
            self.log(data, 'CHAT')

    def debug(self, data):
        if self.loglevel == 1:
            self.log(data, 'DEBUG')

    def command(self, data):
        if self.loglevel <= 2:
            self.log(data, 'COMMANDS')

    def info(self, data):
        if self.loglevel <= 3:
            self.log(data, 'INFO')

    def error(self, data):
        if self.loglevel <= 4:
            self.log(data, 'ERROR')


def user_input():
    if not INTERACTIVE_CONSOLE:
        return

    readline.parse_and_bind("tab: complete")

    while alive:
        try:
            input_cmd = input('>')
            user_input_queue.put(input_cmd)
        except (EOFError, KeyboardInterrupt):
            break


def terminate():
    global alive
    alive = False


alive = True
log = Log()
user_input_queue = Queue()


# Init user console only when running interactively.
if INTERACTIVE_CONSOLE:
    thread = Thread(target=user_input, name="user_input")
    thread.daemon = True
    thread.start()
else:
    thread = None