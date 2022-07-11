from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import os
from aiogram.dispatcher.filters import Text
from data import predict_anime_score, shiki_parser
from aiogram.contrib.fsm_storage.memory import MemoryStorage


storage = MemoryStorage()
bot = Bot(token=os.getenv('TOKEN'))
dp = Dispatcher(bot, storage=storage)


class Nickname(StatesGroup):
    wait_for_nick = State()
    wait_for_url = State()


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
    await message.answer('https://github.com/Nogaromo/shikimori-anime-score-prediction')


@dp.message_handler(Text(equals='Загрузить'), state=None)
async def hello2(message: types.Message):
    await message.answer('Введите ник', reply_markup=types.ReplyKeyboardRemove())
    await Nickname.wait_for_nick.set()


@dp.message_handler(state=Nickname.wait_for_nick)
async def nick_got(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['nick'] = message.text
    nick = data['nick']
    print(nick)
    await message.answer('Начинаем обработку списка')
    await shiki_parser.Shikiparser(nick=nick).do()
    await Nickname.next()
    await message.answer('Введите ссылку')


@dp.message_handler(state=Nickname.wait_for_url)
async def url_got(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['url'] = message.text
    url = data['url']
    nick = data['nick']
    await state.finish()
    print(nick, url)
    await message.answer('Обучаем модель')
    score, anime_name = predict_anime_score.pred_res(nick=nick, anime_url=url)
    await message.answer(f'{nick} predicted score for "{anime_name}": {score}')


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(hello2, commands="nick", state="*")
    dp.register_message_handler(nick_got, state=Nickname.wait_for_nick)
    dp.register_message_handler(url_got, state=Nickname.wait_for_url)


@dp.message_handler(Text(equals='Найти'))
async def hello3(message: types.Message):
    await message.answer('Начинаем поиск данных')


executor.start_polling(dp, skip_updates=True)
