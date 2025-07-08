import logging
import csv
import requests
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from collections import defaultdict
import os

API_TOKEN = os.getenv("API_TOKEN")
ORDER_CHAT_ID = 342035181

GOOGLE_SHEET_CSV_URL = 'https://docs.google.com/spreadsheets/d/18fw1-tjxc59DMQqpH4rTCd4pAQbCwKit1jhT8cDJArM/export?format=csv'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

catalog = defaultdict(list)
user_carts = defaultdict(dict)

def load_catalog():
    catalog.clear()
    r = requests.get(GOOGLE_SHEET_CSV_URL)
    r.encoding = 'utf-8'
    reader = csv.DictReader(r.text.splitlines())
    for row in reader:
        category = row['Категория']
        product = {
            'title': row['Название'],
            'description': row['Описание'],
            'price': row['Цена'],
            'photo': row.get('Ссылка на фото', None)
        }
        catalog[category].append(product)

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    load_catalog()
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for cat in catalog.keys():
        keyboard.add(KeyboardButton(cat))
    await message.answer("Привет! Выбери категорию товаров:", reply_markup=keyboard)

@dp.message_handler(lambda msg: msg.text in catalog.keys())
async def category_handler(message: types.Message):
    category = message.text
    buttons = []
    for i, product in enumerate(catalog[category], start=1):
        buttons.append([InlineKeyboardButton(f"{product['title']} — {product['price']}", callback_data=f"buy_{category}_{i-1}")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(f"Товары в категории {category}:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('buy_'))
async def buy_callback(callback_query: types.CallbackQuery):
    _, category, idx = callback_query.data.split('_')
    idx = int(idx)
    product = catalog[category][idx]
    text = (f"Название: {product['title']}
"
            f"Описание: {product['description']}
"
            f"Цена: {product['price']}

"
            "Нажмите кнопку, чтобы добавить в корзину.")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Добавить в корзину", callback_data=f"addcart_{category}_{idx}"))
    await bot.answer_callback_query(callback_query.id)
    if product['photo']:
        await bot.send_photo(callback_query.from_user.id, product['photo'], caption=text, reply_markup=markup)
    else:
        await bot.send_message(callback_query.from_user.id, text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('addcart_'))
async def add_to_cart_callback(callback_query: types.CallbackQuery):
    _, category, idx = callback_query.data.split('_')
    idx = int(idx)
    user_id = callback_query.from_user.id
    product = catalog[category][idx]
    title = product['title']
    cart = user_carts[user_id]
    cart[title] = cart.get(title, 0) + 1
    await bot.answer_callback_query(callback_query.id, text=f"{title} добавлен(а) в корзину!")
    await bot.send_message(user_id, f"{title} добавлен(а) в вашу корзину.

Для оформления заказа напишите /cart")

@dp.message_handler(commands=['cart'])
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cart = user_carts[user_id]
    if not cart:
        await message.answer("Ваша корзина пуста.")
        return
    text = "Ваша корзина:

"
    total = 0
    for title, qty in cart.items():
        price = 0
        for category in catalog.values():
            for product in category:
                if product['title'] == title:
                    price = int(product['price'])
        total += price * qty
        text += f"{title} — {qty} шт. × {price}₽ = {qty * price}₽
"
    text += f"
Итого: {total}₽"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("Оформить заказ", callback_data="checkout"))
    await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'checkout')
async def checkout(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    cart = user_carts[user_id]
    if not cart:
        await bot.send_message(user_id, "Ваша корзина пуста.")
        return
    text = f"🛒 Новый заказ от @{callback_query.from_user.username or 'без ника'}:

"
    total = 0
    for title, qty in cart.items():
        price = 0
        for category in catalog.values():
            for product in category:
                if product['title'] == title:
                    price = int(product['price'])
        total += price * qty
        text += f"{title} — {qty} шт. × {price}₽ = {qty * price}₽
"
    text += f"
Итого: {total}₽"
    await bot.send_message(ORDER_CHAT_ID, text)
    await bot.send_message(user_id, "Ваш заказ отправлен! Спасибо ❤️")
    user_carts[user_id].clear()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
