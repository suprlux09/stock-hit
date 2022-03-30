import collections
import datetime
import json
import schedule
import telegram
import time
import yfinance as yf
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from threading import Thread


reqlist = {}


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="To set the stock price alarm,\n"
                                  "enter {stock symbol} {stock price}")


def set_alarm(update, context):
    global reqlist

    args = update.message.text.split(" ")

    if len(args) == 2:
        try:
            stock_symbol = args[0].upper()
            ticker = yf.Ticker(stock_symbol)
            req = {}
            req['user'] = update.message.from_user.id
            req['target_price'] = float(args[1])
            if req['target_price'] < ticker.history(period='1d')['Close'][0]:
                req['target_is_lower'] = True
            else:
                req['target_is_lower'] = False
            reqlist[stock_symbol].append(req)


        except IndexError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f"Stock symbol {stock_symbol} is not available")
        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text="Stock price should be a number")
        else:
            print(f"add alarm\n{reqlist}")
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f"Your request ({stock_symbol}, ${req['target_price']}) was successfully submitted!")
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=f"The alarm will be sent to you if {stock_symbol}(${str(round(ticker.history(period='1d')['Close'][0], 2))}) hits that price..")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Input form should be\n'{stock symbol} {stock price}'\n"
                                      "Example: MSFT 350")


def show_alarm(update, context):
    pass


def del_alarm(update, context):
    pass


def real_time_work(bot):
    global reqlist

    def sync_list():
        empty_list = []
        for stock_symbol in reqlist:
            if not reqlist[stock_symbol]:
                empty_list.append(stock_symbol)
        print(f"sync jsonfile\n{reqlist}")
        for stock_symbol in empty_list:
            del reqlist[stock_symbol]
        with open("reqlist.json", "w") as f:
            json.dump(reqlist, f, indent=4)


    def alarm(bot):
        current_time = datetime.datetime.now()
        # if current_time.hour < 14 or current_time >= 21:
        #     return
        for stock_symbol, reqs in reqlist.items():
            ticker = yf.Ticker(stock_symbol)
            current_price = ticker.history(period='1d')['Close'][0]
            reqs_done = []
            try:
                for req in reqs:
                    if req['target_is_lower'] and req['target_price'] >= current_price:
                        bot.sendMessage(chat_id=req['user'],
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                             f"{stock_symbol}(${str(round(current_price, 2))}) hit the target price ${req['target_price']}! \n"
                                             f"target_is_lower chance?")
                        reqs_done.append(req)
                    elif (not req['target_is_lower']) and req['target_price'] <= current_price:
                        bot.sendMessage(chat_id=req['user'],
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                             f"{stock_symbol}(${str(round(current_price, 2))}) hit the target price ${req['target_price']}! \n"
                                             f"Time to sell?")
                        reqs_done.append(req)
            except telegram.error.Unauthorized:
                pass
            for req_done in reqs_done:
                reqs.remove(req_done)

    schedule.every().hour.do(sync_list)
    schedule.every(1).minutes.do(alarm, bot)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    with open('reqlist.json', 'r', encoding='UTF-8') as f:
        reqlist = collections.defaultdict(list, json.load(f))

    # get telegram bot token
    with open('token', 'r') as f:
        token = f.readline()[:-1]

    updater = Updater(token, use_context=True)

    bot = updater.bot

    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('show', show_alarm))
    dp.add_handler(CommandHandler('del', del_alarm))
    dp.add_handler(MessageHandler(Filters.text, set_alarm))

    thread = Thread(target=real_time_work, args=(bot,))
    thread.start()
    
    updater.start_polling()
    updater.idle()

