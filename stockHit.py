import collections
import datetime
import schedule
import sqlite3
import telegram
import time
import yfinance as yf
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
from threading import Thread


db = sqlite3.connect("reqlist.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS request_list(key INTEGER, symbol TEXT, user INTEGER, target FLOAT, isLower INTEGER)")


 # get telegram bot token
with open('token', 'r') as f:
    token = f.readline()

updater = Updater(token, use_context=True)
bot = updater.bot


# db의 index를 설정
cursor.execute("SELECT MAX(key) FROM request_list")
tmp = cursor.fetchone()[0]
next_key = tmp+1 if tmp else 1


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    context.bot.send_message(chat_id=update.effective_chat.id,
                            text="To set the stock price alarm,\n"
                                "enter {stock symbol} {stock price}")


def set_alarm(update, context):
    global next_key
    args = update.message.text.split(" ")

    if len(args) == 2:
        try:
            symbol = args[0].upper()
            ticker = yf.Ticker(symbol)
            user = update.message.from_user.id
            target = float(args[1])
            if target < ticker.history(period='1d')['Close'][0]:
                isLower = 1
            else:
                isLower = 0

        except IndexError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Stock symbol {symbol} is not available")
        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text="Stock price should be a number")
        else:
            print(f"add alarm\nINSERT INTO request_list VALUES({symbol}, {user}, {target}, {isLower})")
            cursor.execute(f"INSERT INTO request_list VALUES({next_key}, '{symbol}', {user}, {target}, {isLower})")
            next_key += 1
            db.commit()
            
            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Your request ({symbol}, ${target}) was successfully submitted!")
            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"The alarm will be sent to you if {symbol}(${str(round(ticker.history(period='1d')['Close'][0], 2))}) hits that price..")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Input form should be\n'{stock symbol} {stock price}'\n"
                                    "Example: MSFT 350")


def show_alarm(update, context):
    cursor.execute(f"SELECT symbol, target FROM request_list WHERE user = {update.effective_chat.id}")
    reply = ["  ".join((req[0], str(req[1]), str(round(yf.Ticker(req[0]).history(period='1d')['Close'][0], 3)), '\n'))
                for req in cursor.fetchall()]
    if reply:
        context.bot.send_message(chat_id=update.effective_chat.id, text="".join(reply))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No alarm exists")
        

def del_alarm(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Every alarm you have set will be deleted. Are you sure?\n"
                                  "Enter 'Yes' to continue, or anything else to cancelation.")
    return 0


def do_delete(update, context):
    cursor.execute(f"DELETE FROM request_list WHERE user = {update.effective_chat.id}")
    db.commit()
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Your alarms have been successfully deleted!")
    return -1


def cancel_delete(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Deletion was not performed!")
    return -1


def real_time_work(bot):
    # 주가 확인 후 사용자에게 메세지 보내고 db에서 삭제
    def alarm(bot):
        current_time = datetime.datetime.now()
        # if current_time.hour < 14 or current_time >= 21:
        #     return

        cursor.execute("SELECT DISTINCT(symbol) FROM request_list")
        symbols = cursor.fetchall()

        delete_key_list = []
        for symbol in symbols:
            symbol = symbol[0]
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period='1d')['Close'][0]
            
            cursor.execute(f"SELECT key, user, target, isLower FROM request_list WHERE symbol='{symbol}'")
            reqs = cursor.fetchall()
            try:
                for req in reqs:
                    key, user, target, isLower = req[0], req[1], req[2], req[3]
                    if isLower and target >= current_price:
                        bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                             f"{symbol}(${str(round(current_price, 2))}) hit the target price ${target}! \n"
                                             f"Discount chance?")
                        delete_key_list.append(key)
                    elif (not isLower) and target <= current_price:
                        bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                             f"{symbol}(${str(round(current_price, 2))}) hit the target price ${target}! \n"
                                             f"Time to sell?")
                        delete_key_list.append(key)
            except telegram.error.Unauthorized:
                pass
            
            for key in delete_key_list:
                cursor.execute(f"DELETE FROM request_list WHERE key={key}")
        
        db.commit()


    schedule.every().minutes.do(alarm, bot)

    while True:
        schedule.run_pending()
        time.sleep(1)


dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('show', show_alarm))
dispatcher.add_handler(ConversationHandler(
        entry_points=[CommandHandler('del', del_alarm)],
        states={0: [MessageHandler(Filters.regex('^Yes$'), do_delete)]},
        fallbacks=[MessageHandler(Filters.text | Filters.command & ~(Filters.regex('^Yes$')), cancel_delete)],
))
dispatcher.add_handler(MessageHandler(Filters.text, set_alarm))


thread = Thread(target=real_time_work, args=(bot,))
thread.start()

updater.start_polling()
updater.idle()
