import asyncio
import os
import signal

import logging
import logging.handlers

from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters

if not os.path.exists('./log'):
    os.makedirs('./log')

from cncr import *
from handlers import *


if(os.getenv('ENV') == 'dev'):
    logging.basicConfig(level=logging.DEBUG)
elif(os.getenv('ENV') == 'prod'):
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)
fileHandler = logging.FileHandler('./log/main.log')
streamHandler = logging.StreamHandler()

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(formatter)
streamHandler.setFormatter(formatter)


async def terminate(loop):
    set_gotSig_True()
    tasks =[t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    await asyncio.gather(*tasks)
    loop.stop()


async def main():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda l: l.create_task(terminate(l)), loop)

    application = Application.builder().token(os.getenv('BOT_TOKEN')).build()
    application.add_handler(ConversationHandler(
            entry_points=[CommandHandler('delete', delete)],
            states={
                OPTION_SELECTED: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_delete)],
                DELETE_ALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_delete_all)],
            },
            fallbacks=[MessageHandler(filters.COMMAND, interrupt_by_command)],
    ))
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('show', show))
    application.add_handler(MessageHandler(filters.TEXT, set_notification))

    await application.initialize()
    await application.updater.start_polling()
    await application.start()

    notify_task = loop.create_task(notify(application.bot))
    await notify_task

    await application.updater.stop()
    await application.stop()
    await application.shutdown()

    logger.info("Terminate stock-hit...")

if __name__ == '__main__':
    logger.info("Start stock-hit!")
    asyncio.run(main())
