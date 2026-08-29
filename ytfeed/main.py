"""ytfeed entrypoint: HTTP server + internal scheduler in one process."""
import logging
import os
import secrets
import sys
import threading

from .config import load_config, ConfigError, DEFAULT_CONFIG_PATH
from .state import State
from . import scheduler, server


class App:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,  # docker logs
        )
        self.log = logging.getLogger("ytfeed")
        self.config_path = DEFAULT_CONFIG_PATH
        self.cfg = None
        self.reload_config()

        data = (self.cfg or {}).get("data_dir") or os.environ.get("YTFEED_DATA", "/data")
        self.state = State(os.path.join(data, "state.json"))

        self.setup_token = os.environ.get("YTFEED_SETUP_TOKEN", "")
        if not self.setup_token:
            self.setup_token = secrets.token_urlsafe(16)
            self.log.warning(
                "YTFEED_SETUP_TOKEN not set; generated one for this run: %s",
                self.setup_token)

    def reload_config(self):
        try:
            self.cfg = load_config(self.config_path)
            if self.cfg is None:
                self.log.warning("No config at %s -- setup-only mode "
                                 "(visit /setup?token=...).", self.config_path)
            else:
                self.log.info("Config loaded from %s.", self.config_path)
        except ConfigError as e:
            self.log.error("Invalid config: %s -- setup-only mode.", e)
            self.cfg = None


def main():
    app = App()
    port = int(os.environ.get("YTFEED_PORT",
               (app.cfg or {}).get("server", {}).get("port", 8091)))
    t = threading.Thread(target=scheduler.loop, args=(app,), daemon=True)
    t.start()
    server.serve(app, port)


if __name__ == "__main__":
    main()
