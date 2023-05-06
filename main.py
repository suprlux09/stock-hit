import asyncio
import os
from threading import Thread

from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters

from cncr import *
from handlers import *


async def main():
    application = Application.builder().token(os.getenv('BOT_TOKEN')).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('show', show_notification))
    application.add_handler(ConversationHandler(
            entry_points=[CommandHandler('del', del_notification)],
            states={0: [MessageHandler(filters.Regex('^Yes$'), do_delete)]},
            fallbacks=[MessageHandler(filters.Regex('^(?!Yes$).*'), cancel_delete)],
    ))
    application.add_handler(MessageHandler(filters.TEXT, set_notification))

    # Check the stock prices and send the notification to the user
    asyncio.create_task(notify(application.bot))

    # Receive requests from the user
    await application.initialize()

    while True:
        await application.updater.start_polling()
        await application.start()
        await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(main())
