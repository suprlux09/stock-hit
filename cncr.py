import datetime
import time
import traceback

import schedule
import sqlite3
import yfinance as yf


# Load database
db = sqlite3.connect("reqlist.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS request_list(key INTEGER, symbol TEXT, user INTEGER, target FLOAT, isLower INTEGER)")


def thread_one(bot):
    """Concurrent task for sending alarms to the user
    This function runs at the other thread, not the main thread
    and calls the inner function alarm() every 3 minutes
    """


    def alarm(bot):
        """Send the target reached alarms to the user and delete them from the database"""

        current_time = datetime.datetime.utcnow()
        print(current_time)

        # No alarm sending when the us stock market is closed
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
                time.sleep(60)
                
            
            for key in delete_key_list:
                cursor.execute(f"DELETE FROM request_list WHERE key={key}")
        
        db.commit()


    schedule.every(3).minutes.do(alarm, bot)
    while True:
        schedule.run_pending()
        time.sleep(1)
