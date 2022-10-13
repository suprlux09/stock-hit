import datetime
import pickle
import schedule
import sqlite3
import telegram
import time
import traceback
import sys
import os
import yfinance as yf
from telegram.ext import Updater, CommandHandler, MessageHandler, ConversationHandler, Filters
from threading import Thread
from difflib import SequenceMatcher
from queue import PriorityQueue

db = sqlite3.connect("reqlist.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS request_list(key INTEGER, symbol TEXT, user INTEGER, target FLOAT, isLower INTEGER)")


# get telegram bot token
token = os.environ.get('STOCK_HIT_TOKEN')


updater = Updater(token, use_context=True)
bot = updater.bot


# db의 index를 설정
cursor.execute("SELECT MAX(key) FROM request_list")
tmp = cursor.fetchone()[0]
next_key = tmp+1 if tmp else 1


# /start
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    context.bot.send_message(chat_id=update.effective_chat.id,
                            text="To set the stock price alarm,\n"
                                "enter {stock symbol} {target price}")
    context.bot.send_message(chat_id=update.effective_chat.id, 
                            text="Enter /show to see the list of your alarms\n"
                                "Enter /del to remove every alarms you set\n"
                                "Enter /start to see this message again")                        


# {symbol} {target price} 입력
def set_alarm(update, context):
    global next_key
    args = update.message.text.split(" ")
    print(f"set_alarm: {update.message}")

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

        except ValueError:
            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text="Stock price should be a number")
        except IndexError:
            with open("data/nasdaq_symbols.pickle", "rb") as fr:
                known_symbols = pickle.load(fr);
            with open("data/nyse_symbols.pickle", "rb") as fr:
                known_symbols += pickle.load(fr);   

            queue = PriorityQueue()
            for another_symbol in known_symbols:
                rat = SequenceMatcher(None, symbol, another_symbol).ratio()
                queue.put((-rat, another_symbol))
            
            modified_symbols = []
            while len(modified_symbols) < 3:
                rat, tmp = queue.get()
                if not yf.Ticker(tmp).history(period='1d').empty:
                    modified_symbols.append((tmp, round(yf.Ticker(tmp).history(period='1d')['Close'][0], 2)))

            context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Stock symbol {symbol} is not available..\n"
                                          "Do you mean these?")
            
            tmp_text = ""
            for modified_symbol, mdf_symbol_price in modified_symbols:
                tmp_text += f"{modified_symbol} {mdf_symbol_price}\n"
            context.bot.send_message(chat_id=update.effective_chat.id, text=tmp_text.rstrip())
            
        else:
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


# /show
def show_alarm(update, context):
    print(f"show_alarm: {update.message}")
    cursor.execute(f"SELECT symbol, target FROM request_list WHERE user = {update.effective_chat.id}")
    reply = ["  ".join((req[0], str(req[1]), str(round(yf.Ticker(req[0]).history(period='1d')['Close'][0], 3)), '\n'))
                for req in cursor.fetchall()]
    if reply:
        context.bot.send_message(chat_id=update.effective_chat.id, text="".join(reply))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No alarm exists")
        

# /del
def del_alarm(update, context):
    print(f"del_alarm: {update.message}")
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Every alarm you have set will be deleted. Are you sure?\n"
                                  "Enter 'Yes' to continue, or anything else to cancelation.")
    return 0


# /del에서 Yes 입력 -> db에서 삭제 수행
def do_delete(update, context):
    cursor.execute(f"DELETE FROM request_list WHERE user = {update.effective_chat.id}")
    db.commit()
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Your alarms have been successfully deleted!")
    return -1


# /del에서 Yes 이외 입력 -> 삭제 취소
def cancel_delete(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Deletion canceled")
    return -1


# 스레드에 올릴 함수
def real_time_work(bot):

    # 주가 확인 후 사용자에게 메세지 보내고 db에서 삭제
    def alarm(bot):
        current_time = datetime.datetime.utcnow()
        print(current_time)
        if current_time.hour < 14 or current_time.hour >= 21:
            return

        cursor.execute("SELECT DISTINCT(symbol) FROM request_list")
        symbols = cursor.fetchall()

        delete_key_list = []
        for symbol in symbols:
            symbol = symbol[0]
            print(f"{symbol}")
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
            except Exception:
                traceback.print_exc()
                
            
            for key in delete_key_list:
                cursor.execute(f"DELETE FROM request_list WHERE key={key}")
        
        db.commit()


    # 1분마다 주가 확인, 사용자에게 알림 보냄
    schedule.every(3).minutes.do(alarm, bot)
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



# 사용자에게 주가 알림을 보내는 작업을 다른 스레드에 올린다
thread = Thread(target=real_time_work, args=(bot,))
thread.start()

updater.start_polling()
updater.idle()
