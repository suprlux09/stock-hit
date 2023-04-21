import os
from threading import Thread

from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters

from cncr import *
from handlers import *


if __name__ == '__main__':
    token = os.getenv('BOT_TOKEN')

    updater = Updater(token, use_context=True)
    bot = updater.bot

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('show', show_notification))
    dispatcher.add_handler(ConversationHandler(
            entry_points=[CommandHandler('del', del_notification)],
            states={0: [MessageHandler(Filters.regex('^Yes$'), do_delete)]},
            fallbacks=[MessageHandler(Filters.text | Filters.command & ~(Filters.regex('^Yes$')), cancel_delete)],
    ))
    dispatcher.add_handler(MessageHandler(Filters.text, set_notification))

    # Check the stock prices and send the notification to the user
    thread = Thread(target=thread_one, args=(bot,))
    thread.start()

    # Receive requests from the user
    updater.start_polling()
    updater.idle()
