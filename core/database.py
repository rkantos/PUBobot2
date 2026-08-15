# -*- coding: utf-8 -*-
from asyncio import get_event_loop
from importlib import import_module
from core.config import cfg


def init_db(db_uri, db_capath):
	db_type, db_address = db_uri.split("://", 1)
	adapter = import_module('core.DBAdapters.' + db_type)
	return adapter.Adapter(db_address, get_event_loop(), db_capath)


db = init_db(cfg.DB_URI, cfg.DB_CAPATH)

#from asyncio import get_event_loop
#from importlib import import_module
#from core.config import cfg
#
#
#async def init_db(db_uri):
#	db_type, db_address = db_uri.split("://", 1)
#	adapter_module = import_module('core.DBAdapters.' + db_type)
#	adapter = adapter_module.Adapter(db_address, get_event_loop())
#	await adapter.init_pool()  # Await the async pool initialization
#	return adapter
#
#loop = get_event_loop()
#db = loop.run_until_complete(init_db(cfg.DB_URI))
