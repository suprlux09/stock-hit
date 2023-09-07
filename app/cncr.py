import asyncio
import datetime
import traceback

import logging
import logging.handlers

import yfinance as yf

from db_resource import *


cursor = db.cursor()
gotSig = False

logger = logging.getLogger(__name__)
fileHandler = logging.FileHandler('./log/cncr.log')
streamHandler = logging.StreamHandler()

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(formatter)
streamHandler.setFormatter(formatter)


def set_gotSig_True():
    global gotSig
    gotSig = True


async def notify(bot):
    """Send the target reached notifications to the user and delete them from the database. This work will be performed in every 30 minutes."""
    while True:
        for i in range(900):
            await asyncio.sleep(2)
            if gotSig:
                break
        
        logger.info("Perform notification work..")

        await lock.acquire()
        current_time = datetime.datetime.utcnow()

        cursor.execute("SELECT DISTINCT(symbol) FROM request_list")
        symbols = cursor.fetchall()

        delete_key_list = []
        try:
            for symbol in symbols:
                symbol = symbol[0]

                ticker = yf.Ticker(symbol)
                current_price = ticker.history(period='1d')['Close'][0]

                cursor.execute(f"SELECT key, user_id, target, is_lower FROM request_list WHERE symbol='{symbol}'")
                reqs = cursor.fetchall()
                for req in reqs:
                    key, user, target, is_lower = req[0], req[1], req[2], req[3]
                    if is_lower and target >= current_price:
                        await bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                            f"{symbol} hit the target price ${target}!\n"
                                            f"Current Price: {str(round(current_price, 2))}\n"
                                            f"Discount chance?")
                        logger.info(f"Notification sent: {user} {symbol} {target} {current_price}")
                        delete_key_list.append(key)
                    elif (not is_lower) and target <= current_price:
                        await bot.sendMessage(chat_id=user,
                                        text=f"{current_time.strftime('%Y/%m/%d %H:%M:%S')} (UTC)\n"
                                            f"{symbol} hit the target price ${target}!\n"
                                            f"Current Price: {str(round(current_price, 2))}\n"
                                            f"Time to sell?")
                        logger.info(f"Notification sent: {user} {symbol} {target} {current_price}")
                        delete_key_list.append(key)
                    else:
                        cursor.execute(f"UPDATE request_list SET recent={current_price} WHERE key={key}")

            for key in delete_key_list:
                cursor.execute(f"DELETE FROM request_list WHERE key={key}")

        except Exception:
            logger.error(traceback.format_exc())

        finally:
            db.commit()
            lock.release()
            logger.info("Notification work done!")

        if gotSig:
            logger.info("Terminate notification service..")
            return
