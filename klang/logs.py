import sys


def setup_logging():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stdout,
    )
