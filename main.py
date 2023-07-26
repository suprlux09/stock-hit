import asyncio
import os
import signal

from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters

from cncr import *
from handlers import *


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

    print("Terminate stock-hit...")


if __name__ == '__main__':
    asyncio.run(main())
