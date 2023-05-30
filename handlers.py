import yfinance as yf

from db_resource import *

cursor = db.cursor()


async def start(update, context):
    """Send a greeting message to a user"""

    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="To set the stock price notification,\n"
                                "enter {stock symbol} {target price}")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text="Enter /show to see the list of your notifications\n"
                                "Enter /del to remove every notifications you set\n"
                                "Enter /start to see this message again")


async def set_notification(update, context):
    """ Update user's notification request in the database
    User input format: {stock symbol} {target stock price}
    """

    args = update.message.text.split(" ")
    print(f"set_notification: {update.message}")

    if len(args) == 2:
        try:
            symbol = args[0].upper()
            ticker = yf.Ticker(symbol)
            user = update.message.from_user.id
            target = float(args[1])
            if target < ticker.history(period='1d')['Close'][0]:
                is_lower = True
            else:
                is_lower = False

        except ValueError:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text="Stock price should be a number")
        except IndexError:
           await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Stock symbol {symbol} is not available")
        else:
            # Set database row index
            await lock.acquire()
            cursor.execute("SELECT MAX(key) FROM request_list")
            tmp = cursor.fetchone()[0]
            next_key = tmp+1 if tmp else 1

            cursor.execute(f"INSERT INTO request_list VALUES({next_key}, '{symbol}', {user}, {target}, {is_lower})")
            next_key += 1
            db.commit()
            lock.release()
            

            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"Your request ({symbol}, {target}) was successfully submitted!")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text=f"The notification will be sent to you if {symbol}({str(round(ticker.history(period='1d')['Close'][0], 2))}) hits that price..")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Input form should be\n'{stock symbol} {stock price}'\n"
                                    "Example: MSFT 350")


async def show_notification(update, context):
    """Show the notifications been set by the user to him/her
    User input format: /show
    """

    print(f"show_notification: {update.message}")

    await lock.acquire()
    cursor.execute(f"SELECT symbol, target FROM request_list WHERE user_id = {update.effective_chat.id}")
    reply = ["  ".join((req[0], str(req[1]), str(round(yf.Ticker(req[0]).history(period='1d')['Close'][0], 3)), '\n'))
                for req in cursor.fetchall()]
    lock.release()
    
    if reply:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="".join(reply))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No notification exists")


async def del_notification(update, context):
    """Send a warning message to the user who requests notification deletion
    User input format: /del
    """

    print(f"del_notification: {update.message}")
    await context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Every notification you have set will be deleted. Are you sure?\n"
                                  "Enter 'Yes' to continue, or anything else to cancelation.")
    return 0


async def do_delete(update, context):
    """Execute deletion
    This function will run if user enter 'Yes' after '/del'
    """
    await lock.acquire()
    cursor.execute(f"DELETE FROM request_list WHERE user_id = {update.effective_chat.id}")
    db.commit()
    lock.release()

    await context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Your notifications have been successfully deleted!")
    return -1


async def cancel_delete(update, context):
    """Inform the user that the deletion is canceled
    This function will run if the user enter anything else except 'Yes' after '/del'
    """

    await context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Deletion canceled")
    return -1
