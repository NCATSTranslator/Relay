import logging
logger = logging.getLogger(__name__)

logger.debug('Initializing module %s...' % __name__)

import pymysql

pymysql.install_as_MySQLdb()
