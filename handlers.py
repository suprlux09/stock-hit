import traceback

import logging
import logging.handlers

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
import yfinance as yf

from db_resource import *


cursor = db.cursor()

logger = logging.getLogger(__name__)
fileHandler = logging.FileHandler('./handlers.log')
streamHandler = logging.StreamHandler()

logger.addHandler(fileHandler)
logger.addHandler(streamHandler)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(formatter)
streamHandler.setFormatter(formatter)


async def start(update, context):
    """Send a greeting message to a user"""
    logger.info(f"/start: {update.message}")

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="To set the stock price notification,\n"
                                "enter {stock symbol} {target price}")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="You can also set multiple target prices like\n"
                                "{stock symbol} {target price 1} {target price 2} ...")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="Example: 'TSLA 500', '005930.KS 100000 50000'")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="Enter /show to see the list of your notifications\n"
                                "Enter /delete to remove notification you set\n"
                                "Enter /start to see this message again")


async def set_notification(update, context):
    """ Update user's notification request in the database
    User input format: {stock symbol} {target stock price}
    """
    logger.info(f"set_notification: {update.message}")

    args = update.message.text.split()
    user = update.message.from_user.id
    if len(args) >= 2:
        # Check the validity of the input
        # Stock symbol, get the recent price
        try:
            symbol = args[0].upper()
            ticker = yf.Ticker(symbol)
            recent = ticker.history(period='1d')['Close'][0]
        except IndexError:
              await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text=f"Stock symbol {symbol} is not available\n"
                                             f"Check out /start for the usage")
              return
        except Exception:  # temporary
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"An unexpected error has occurred. Please try later.")
            logger.error(traceback.format_exc())
            return

        # Target prices
        target_prices = args[1:]
        for i in range(0, len(target_prices)):
            try:
                target_prices[i] = float(target_prices[i])
            except ValueError:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text="Stock price should be a number\n"
                                             "Check out /start for the usage")
                return

        # Add notifications to the database
        requests = []
        for target in target_prices:
            is_lower = True if target < recent else False
            
            await lock.acquire()
            cursor.execute("SELECT MAX(key) FROM request_list")
            tmp = cursor.fetchone()[0]
            next_key = tmp+1 if tmp else 1
        
            cursor.execute(f"INSERT INTO request_list VALUES({next_key}, '{symbol}', {user}, {target}, {recent}, {is_lower})")
            next_key += 1

            db.commit()
            lock.release()

            requests.append(f"({symbol}, {target})")

        if len(requests) == 1:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Your request {requests[0]} was successfully submitted!\n"
                                         f"Current price: {str(round(recent, 2))}")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Your request {', '.join(requests)} were successfully submitted!\n"
                                         f"Current price: {str(round(recent, 2))}")            
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text=f"The notification will be sent to you if {symbol} hits that price..")          
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Check out /start for the usage")


async def get_notifications(user_id):
    await lock.acquire()
    cursor.execute(f"SELECT symbol, target, recent FROM request_list WHERE user_id = {user_id}")
    notifications = ["  ".join((req[0], str(req[1]), str(round(req[2], 3)), '\n'))
                for req in cursor.fetchall()]
    lock.release()
    return notifications


async def show(update, context):
    """Show the notifications been set by the user to him/her
    User input format: /show
    """
    logger.info(f"/show: {update.message}")
    
    notifications = await get_notifications(update.effective_chat.id)

    if notifications:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="".join(notifications))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No notification exists")


(
    END,
    OPTION_SELECTED,
    DELETE_ALL,
) = range(-1,2)


async def delete(update, context):
    """Ask the user for the deletion method
    User input format: /delete
    """
    logger.info(f"/del: {update.message}")
    
    notifications = await get_notifications(update.effective_chat.id)

    if notifications:
        return await select_option(update, context)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You have nothing to delete")
        return END


async def select_option(update, context):
    await lock.acquire()
    cursor.execute(f"SELECT DISTINCT(symbol) FROM request_list WHERE user_id = {update.effective_chat.id}")
    symbols = [req[0] for req in cursor.fetchall()]
    lock.release()
    if symbols:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                            reply_markup=ReplyKeyboardMarkup([symbols[i:i+3] for i in range(0, len(symbols), 3)]+[["Delete Every Notifications", "Done!"]], one_time_keyboard=True),
                            text="Select the stock symbol you want to delete")
        return OPTION_SELECTED
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                            reply_markup=ReplyKeyboardRemove(),
                            text="You have nothing to delete")
        return END


async def do_delete(update, context):
    """Execute the deletion method
    """
    if update.message.text == "Delete Every Notifications":
        await context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Are you sure?")
        await context.bot.send_message(chat_id=update.effective_chat.id,
            reply_markup=ReplyKeyboardMarkup(
            [["Yes", "No"]], one_time_keyboard=True
            ), 
            text="Enter 'Yes' to delete all notifications")
        return DELETE_ALL
        
    elif update.message.text == "Done!":
        await context.bot.send_message(chat_id=update.effective_chat.id,
                            reply_markup=ReplyKeyboardRemove(),
                            text="Deletion completed!")
        return END
    else:
        await lock.acquire()
        cursor.execute(f"SELECT symbol, target FROM request_list WHERE user_id = {update.effective_chat.id} AND symbol = '{update.message.text}'")
        deleted_notifications = ["("+", ".join((req[0], str(req[1])))+")" for req in cursor.fetchall()]
        cursor.execute(f"DELETE FROM request_list WHERE user_id = {update.effective_chat.id} AND symbol = '{update.message.text}'")
        lock.release()


        if len(deleted_notifications) == 0:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="No notification exist for this stock symbol")
        elif len(deleted_notifications) == 1:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                text=f"{deleted_notifications[0]} has been successfully deleted!")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, 
                                           text="\n".join(deleted_notifications)+"\nThese notifications have been successfully deleted!")

        return await select_option(update, context)



async def do_delete_all(update, context):
    if update.message.text == "Yes":
        await lock.acquire()
        cursor.execute(f"DELETE FROM request_list WHERE user_id = {update.effective_chat.id}")
        db.commit()
        lock.release()
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Your notifications have been successfully deleted!")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Deletion canceled")
    return END



async def interrupt_by_command(update, context):
    """If the user enter the command during deletion
    """

    await context.bot.send_message(chat_id=update.effective_chat.id,
                            reply_markup=ReplyKeyboardRemove(),
                             text="Deletion canceled, enter the command again to execute it")
    return END
