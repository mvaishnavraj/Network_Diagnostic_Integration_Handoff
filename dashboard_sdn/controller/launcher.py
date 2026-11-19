#!/usr/bin/env python3

import sys
import logging
from os_ken import cfg
from os_ken.base import app_manager


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if len(sys.argv) < 2:
        print("Usage: python -m controller.launcher <controller_app>")
        sys.exit(1)

    app_list = sys.argv[1:]

    try:
        # Load the topology module first so it registers its CLI options.
        for app in app_list:
            if app == "os_ken.topology.switches":
                __import__(app)

        # Enable LLDP-based link discovery.
        cfg.CONF.set_override("observe_links", True)

        app_manager.AppManager.run_apps(app_list)

    except KeyboardInterrupt:
        print("\nController stopped.")


if __name__ == "__main__":
    main()
