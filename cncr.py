import asyncio
import datetime
import traceback

import yfinance as yf

from db_resource import *


cursor = db.cursor()
gotSig = False


def set_gotSig_True():
    global gotSig
    gotSig = True


async def notify(bot):
    """Send the target reached notifications to the user and delete them from the database. This work will be performed in every 30 minutes."""
    while True:
        for i in range(600):
            await asyncio.sleep(3)
            if gotSig:
                break

        await lock.acquire()
        current_time = datetime.datetime.utcnow()
        print(current_time)

        cursor.execute("SELECT DISTINCT(symbol) FROM request_list")
        symbols = cursor.fetchall()

        delete_key_list = []
        for symbol in symbols:
            symbol = symbol[0]

            try:
                ticker = yf.Ticker(symbol)
                current_price = ticker.history(period='1d')['Close'][0]

                cursor.execute(f"SELECT key, user_id, target, is_lower FROM request_list WHERE symbol='{symbol}'")
                reqs = cursor.fetchall()
                for req in reqs:
                    key, user, target, is_lower = req[0], req[1], req[2], req[3]
                    if is_lower and target >= current_price:
                        await bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                            f"{symbol} hit the target price ${target}! \n"
                                            f"Current Price: ${str(round(current_price, 2))}"
                                            f"Discount chance?")
                        delete_key_list.append(key)
                    elif (not is_lower) and target <= current_price:
                        await bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                            f"{symbol} hit the target price ${target}! \n"
                                            f"Current Price: ${str(round(current_price, 2))}"
                                            f"Time to sell?")
                        delete_key_list.append(key)
                    else:
                        cursor.execute(f"UPDATE request_list SET recent={current_price} WHERE key={key}")
            except Exception:
                traceback.print_exc()
                lock.release()
                return

            for key in delete_key_list:
                cursor.execute(f"DELETE FROM request_list WHERE key={key}")

            db.commit()

        lock.release()

        if gotSig:
            print("Terminate notification service..")
            return
