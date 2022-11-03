import pickle
from difflib import SequenceMatcher
from queue import PriorityQueue

import sqlite3
import yfinance as yf


# Load database
db = sqlite3.connect("reqlist.db", check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS request_list(key INTEGER, symbol TEXT, user INTEGER, target FLOAT, isLower INTEGER)")


def start(update, context):
    """Send a greeting message to a user"""
    
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello!")
    context.bot.send_message(chat_id=update.effective_chat.id,
                            text="To set the stock price alarm,\n"
                                "enter {stock symbol} {target price}")
    context.bot.send_message(chat_id=update.effective_chat.id, 
                            text="Enter /show to see the list of your alarms\n"
                                "Enter /del to remove every alarms you set\n"
                                "Enter /start to see this message again")                        


def set_alarm(update, context):
    """ Update user's alarm request in the database
    User input format: {stock symbol} {target stock price}
    """

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
            # Set database row index
            cursor.execute("SELECT MAX(key) FROM request_list")
            tmp = cursor.fetchone()[0]  
            next_key = tmp+1 if tmp else 1

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
    """Show the alarms been set by the user to him/her
    User input format: /show
    """

    print(f"show_alarm: {update.message}")
    cursor.execute(f"SELECT symbol, target FROM request_list WHERE user = {update.effective_chat.id}")
    reply = ["  ".join((req[0], str(req[1]), str(round(yf.Ticker(req[0]).history(period='1d')['Close'][0], 3)), '\n'))
                for req in cursor.fetchall()]
    if reply:
        context.bot.send_message(chat_id=update.effective_chat.id, text="".join(reply))
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="No alarm exists")
        

def del_alarm(update, context):
    """Send a warning message to the user who requests alarm deletion
    User input format: /del
    """

    print(f"del_alarm: {update.message}")
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Every alarm you have set will be deleted. Are you sure?\n"
                                  "Enter 'Yes' to continue, or anything else to cancelation.")
    return 0


def do_delete(update, context):
    """Execute deletion
    This function will run if user enter 'Yes' after '/del'
    """

    cursor.execute(f"DELETE FROM request_list WHERE user = {update.effective_chat.id}")
    db.commit()
    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Your alarms have been successfully deleted!")
    return -1


def cancel_delete(update, context):
    """Inform the user that the deletion is canceled
    This function will run if the user enter anything else except 'Yes' after '/del'
    """

    context.bot.send_message(chat_id=update.effective_chat.id, 
                             text="Deletion canceled")
    return -1
