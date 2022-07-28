import requests
from bs4 import BeautifulSoup
import json
from aiogram import Bot, types
import config
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from data import predict_anime_score, shiki_parser
from aiogram.contrib.fsm_storage.memory import MemoryStorage


def check_nickname(nick):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0'}
    url = f'https://shikimori.one/{nick}'
    page = requests.get(url, headers=headers)
    soup = BeautifulSoup(page.text, "lxml")
    p = soup.find('p', class_='error-404')
    return p.text

storage = MemoryStorage()
bot = Bot(token=config.TOKEN)
dp = Dispatcher(bot, storage=storage)


class Nickname(StatesGroup):
    wait_for_nick = State()
    wait_for_url = State()


class Find(StatesGroup):
    wait_for_nick = State()
    wait_for_url = State()


'''async def on_startup(dp):
    await bot.set_webhook(config.URl_APP)


async def on_shutdown(dp):
    await bot.delete_webhook()
'''


@dp.message_handler(commands='start')
async def commands_start(message: types.Message):
    instruction = 'Инструкция по пользованию ботом:' \
                      '\n1) Введите ник пользователя с сайта https://shikimori.one, для которого хотите сделать предсказание' \
                      '\n2) Введите ссылку на аниме'
    start_buttons = ['Найти', 'Загрузить', 'Исходный код']
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*start_buttons)
    await message.answer(instruction, reply_markup=keyboard)


@dp.message_handler(Text(equals='Исходный код'))
async def hello1(message: types.Message):
    start_buttons = ['Найти', 'Загрузить', 'Исходный код']
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*start_buttons)
    await message.answer('https://github.com/Nogaromo/shiki_bot', reply_markup=keyboard)


@dp.message_handler(Text(equals='Загрузить'), state=None)
async def hello2(message: types.Message):
    await message.answer('Введите ник', reply_markup=types.ReplyKeyboardRemove())
    await Nickname.wait_for_nick.set()


@dp.message_handler(state=Nickname.wait_for_nick)
async def nick_got(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['nick'] = message.text
    nick = data['nick']
    p = check_nickname(nick)
    print(p)
    if p == 404:
        await message.answer('Такого пользователя не существует.\nПроверьте введеный ник')
        await state.finish()
    msg = await message.answer('Начинаем обработку списка')
    await shiki_parser.Shikiparser(nick=nick).do(bot, msg)
    await Nickname.next()
    await message.answer('Введите ссылку')


@dp.message_handler(state=Nickname.wait_for_url)
async def url_got(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['url'] = message.text
    url = data['url']
    nick = data['nick']
    await state.finish()
    msg = await message.answer('Обучаем модель.\nОбычно 10-20 мин.')
    score, anime_name = await predict_anime_score.pred_res(nick=nick, anime_url=url, msg=msg, bot=bot, retrain='')
    await message.answer(f'Согласно предсказанию {nick} поставил бы "{anime_name}": {score}')


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(hello2, commands="nick", state="*")
    dp.register_message_handler(nick_got, state=Nickname.wait_for_nick)
    dp.register_message_handler(url_got, state=Nickname.wait_for_url)
    dp.register_message_handler(hello3, commands="nick_find", state="*")
    dp.register_message_handler(nick_find, state=Find.wait_for_nick)
    dp.register_message_handler(url_find, state=Find.wait_for_url)


@dp.message_handler(state=Find.wait_for_nick)
async def nick_find(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['nick'] = message.text
    nick = data['nick']
    with open('list_of_saved_models.json', 'r', encoding='utf-8') as file:
        saved_models = json.load(file)
    if nick in saved_models['saved models']:
        await message.answer('Модель найдена')
        await Find.next()
        await message.answer('Введите ссылку')
    else:
        await state.finish()
        start_buttons = ['Найти', 'Загрузить', 'Исходный код']
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(*start_buttons)
        await message.answer('Модель не найдена. Выберите "Загрузить", чтобы загрузить данные и обучить модель',
                             reply_markup=keyboard)


@dp.message_handler(state=Find.wait_for_url)
async def url_find(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['url'] = message.text
    url = data['url']
    nick = data['nick']
    await state.finish()
    msg = await message.answer('Получаем оценку.')
    score, anime_name = await predict_anime_score.pred_res(nick=nick, anime_url=url, msg=msg, bot=bot)
    await message.answer(f'Согласно предсказанию {nick} поставил бы "{anime_name}": {score}')


@dp.message_handler(Text(equals='Найти'), state=None)
async def hello3(message: types.Message):
    await message.answer('Введите ник', reply_markup=types.ReplyKeyboardRemove())
    await Find.wait_for_nick.set()


executor.start_polling(dispatcher=dp, skip_updates=True)

