# import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import config
import requests
import json
from datetime import datetime
import time
import sqlite3


class DB:
    """
    класс для работы с базой данных
    """

    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.conn.text_factory = sqlite3.OptimizedUnicode

    # создание таблицы
    def create_table(self):
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS Users (id_user TEXT PRIMARY KEY, api_key TEXT, id_group TEXT, last_msg TEXT)")
        self.conn.commit()

    # добавление начальных данных (ид пользователя и api)
    def add_user(self, user, api):
        self.cursor.execute("INSERT OR IGNORE INTO Users (id_user, api_key) VALUES (?, ?)", (str(user), api))
        self.conn.commit()

    # добавление начальных данных (число для сортировки)
    def add_id_group(self, user, group_input):
        self.cursor.execute("UPDATE Users SET id_group=? WHERE id_user=?", (group_input, str(user)))
        self.conn.commit()

    # добавим последнюю компанию и плохую площадку, чтобы не повторять сообщения
    def add_msg(self, id_for_add, name_for_add, user):
        self.cursor.execute("SELECT last_msg FROM Users WHERE id_user=?", [user])
        last_db = str(self.cursor.fetchall()[0])
        print(last_db)
        list_of_companies = last_db + ', ' + str(id_for_add) + ', ' + name_for_add
        self.cursor.execute("UPDATE Users SET last_msg=? WHERE id_user=?", (list_of_companies, user))
        self.conn.commit()

    # возвращаем колонку ключей
    def get_api(self, user):
        self.cursor.execute("SELECT api_key FROM Users WHERE id_user=?", [user])
        return_key = str(self.cursor.fetchall()[0])
        return_key = return_key.replace("('", "").replace("',)", "")
        return return_key

    # возвращаем колонку номера группы
    def get_num_group(self, user):
        self.cursor.execute("SELECT id_group FROM Users WHERE id_user=?", [user])
        return_group = str(self.cursor.fetchall()[0])
        return_group = return_group.replace("('", "").replace("',)", "")
        return return_group

    # возвращаем колонку сообщений
    def get_last(self, user):
        self.cursor.execute("SELECT last_msg FROM Users WHERE id_user=?", [user])
        return_msg = str(self.cursor.fetchall()[0])
        return_msg = return_msg.replace("('", "").replace("',)", "")
        return return_msg

    # очищаем колонку с сообщениями раз в сутки
    def del_last_msg(self):
        self.cursor.execute("UPDATE Users SET last_msg = NULL")
        self.conn.commit()


# logging.basicConfig(level=logging.INFO, filename="bot.log", format='%(asctime)s - %(levelname)s - %(message)s')

API, GROUP = range(2)
for_db = []


def reply_to_start_command(bot, update):
    update.message.reply_text(
        "Привет! Я бот, который поможет заработать тебе много денег =) Нажми /help, чтобы узнать больше обо мне или /setting, чтобы приступить к следующему шагу")


def help(bot, update):
    update.message.reply_text(
        "Этот бот поможет отследить компании, присылая оповещения в телеграм при подозрении площадки. \nДля перезапуска бота используй /start\nДля настройки используй /setting")


def setting(bot, update):
    update.message.reply_text("Напиши свой ключ")
    return API


def get_api(bot, update):
    user_api = update.message.text
    for_db.append(user_api)
    update.message.reply_text("Введи число для сортировке по группе, которое ты можешь увидеть в адресной строке")
    return GROUP


def get_group(bot, update):
    user_group = update.message.text
    for_db.append(user_group)
    chat = update.message.chat_id
    update.message.reply_text("Данные получены, запускаю обработку")
    send_to_db(update, chat, for_db)
    return ConversationHandler.END


def send_to_db(update, chat, for_db):
    class_db.add_user(chat, for_db[0])
    class_db.add_id_group(chat, for_db[1])
    send_msg(update)


def dontknow(bot, update, user_data):
    update.message.reply_text("Не понимаю")


def start_bot():
    my_bot = Updater(config.token)
    dp = my_bot.dispatcher
    dp.add_handler(CommandHandler("start", reply_to_start_command))
    dp.add_handler(CommandHandler("help", help))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("setting", setting)],
        states={
            API: [MessageHandler(Filters.text, get_api)],
            GROUP: [MessageHandler(Filters.text, get_group)],
        },

        fallbacks=[MessageHandler(Filters.text, dontknow, pass_user_data=True)]
    )

    dp.add_handler(conv_handler)
    my_bot.start_polling()
    my_bot.idle()

def send_msg(update):
    while True:
        dateSTR = datetime.strftime(datetime.now(), "%H:%M:%S")
        if dateSTR >= "23:57:00" and dateSTR <= "00:02:00":
            class_db.del_last_msg()
        else:
            check(collect(), update)
            time.sleep(600)



def collect():
    get_collect = requests.get(
        config.url + config.user_group + '&group=' + for_db[1] + config.traffic_source + config.date + config.status +
        for_db[
            0])
    result = get_collect.json()
    dict_id = []
    for item in range(len(result)):
        dict_id.append((result[item]["id"], result[item]["name"]))
    return dict_id


last_msg = []


def check(dict_id, update):
    for i in range(len(dict_id)):
        get_check = requests.get(config.url_campeign + "&camp_id=" + dict_id[i][
            0] + "&order_name=&order_type=ASC&group1=27&group2=1&group3=1&" + for_db[0])
        all_list = get_check.json()
        for item in range(len(all_list)):
            try:
                if int(all_list[item]["leads"]) > 25 or (int(all_list[item]["clicks"]) > 1000 and int(all_list[item]["leads"] == 0)):
                    if (dict_id[i][0], all_list[item]["name"]) not in last_msg:
                        send(dict_id[i][0], dict_id[i][1], all_list[item]["name"], all_list[item]["clicks"],
                             all_list[item]["leads"], update)
                        last_msg.append((dict_id[i][0], all_list[item]["name"]))
            except:
                pass


def send(id_campaign, name_campaign, name, clicks, leads, update):
    chat = update.message.chat_id
    last = class_db.get_last(chat)
    if (id_campaign, name) in last:
        pass
    else:
        update.message.reply_text("В компании ({}) {} найдена подозрительная площадка '{}' c clicks - {} и leads - {}".format(id_campaign, name_campaign, name, clicks, leads))
        class_db.add_msg(id_campaign, name, chat)


class_db = DB("binom.db")
if __name__ == "__main__":
    start_bot()
