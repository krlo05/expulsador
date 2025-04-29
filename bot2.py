import sqlite3
import datetime
import asyncio
import os
import requests
import threading
from flask import Flask
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    ContextTypes,
)

# 🔐 Token de tu bot (directo como pediste)
TOKEN = '7577450285:AAH_X4UtVX4H1gmjif69vHk0LWcoaT8e7TE'

# 📂 Base de datos SQLite
DB_NAME = 'members.db'

# 🌎 URL pública para keep-alive (modifica esto cuando tengas la URL de Railway)
RENDER_URL = os.getenv('telegram-expulsador-bot-production-05e9.up.railway.app') or 'https://google.com'  # Para pruebas

# 🌐 Flask app para mantener servidor activo
app_web = Flask(__name__)

@app_web.route('/')
def index():
    return '✅ Bot funcionando correctamente.'

# 🛠️ Inicializar base de datos
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER,
            chat_id INTEGER,
            join_date TEXT,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    conn.commit()
    conn.close()
    print("📂 Base de datos inicializada.")

# ✅ Guardar nuevos miembros
async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member_update = update.chat_member
    if member_update.new_chat_member.status == ChatMember.MEMBER:
        user = member_update.from_user
        user_id = user.id
        username = user.username or f"id:{user_id}"
        chat_id = member_update.chat.id
        join_date = datetime.datetime.utcnow().isoformat()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO members (user_id, chat_id, join_date)
            VALUES (?, ?, ?)
        ''', (user_id, chat_id, join_date))
        conn.commit()
        conn.close()

        print(f"📥 Nuevo usuario: @{username} en grupo {chat_id} a las {join_date}")

# 🚫 Expulsar miembros que lleven demasiado tiempo
async def check_old_members(app):
    while True:
        now = datetime.datetime.utcnow()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, chat_id, join_date FROM members')
        rows = cursor.fetchall()

        for user_id, chat_id, join_date in rows:
            joined = datetime.datetime.fromisoformat(join_date)
            seconds_in_group = (now - joined).total_seconds()
            print(f"⏳ Usuario {user_id} lleva {seconds_in_group:.0f} segundos en grupo {chat_id}")

            if seconds_in_group >= 120:  # 2 minutos
                try:
                    await app.bot.ban_chat_member(chat_id, user_id)
                    await app.bot.unban_chat_member(chat_id, user_id)  # Permitir que pueda volver luego
                    print(f"🧼 Usuario {user_id} expulsado de {chat_id} por superar límite.")
                    cursor.execute('DELETE FROM members WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Error expulsando usuario {user_id}: {e}")
        conn.close()
        await asyncio.sleep(30)  # Cada 30 segundos revisamos

# 🔄 Ping a servidor para mantenerlo despierto
async def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL)
            print("🔄 Ping enviado al servidor.")
        except Exception as e:
            print(f"⚠️ Error enviando ping: {e}")
        await asyncio.sleep(600)  # Cada 10 minutos

# 🧠 Función principal
async def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Ejecutamos tareas en segundo plano
    asyncio.create_task(check_old_members(app))
    asyncio.create_task(keep_alive())

    print("🤖 Bot corriendo...")

    await app.initialize()  # ✅ NECESARIO
    await app.start()
    await app.updater.start_polling()
    #await app.updater.idle() 
    await asyncio.Event().wait()  # Mantener vivo el bot

# 🚀 Ejecutar todo
if __name__ == '__main__':
    threading.Thread(target=lambda: app_web.run(host='0.0.0.0', port=10000)).start()
    asyncio.run(main())
