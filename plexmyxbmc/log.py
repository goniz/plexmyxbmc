import logging


def get_logger(name, _force=False):
    name = '%-20s' % name
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if (0 == len(logger.handlers)) or (_force is True):
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger
