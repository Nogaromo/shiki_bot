import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
import requests
from bs4 import BeautifulSoup
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
import json
from string import punctuation
import warnings
from pandas.core.common import SettingWithCopyWarning
warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)


def data_processing(df):
    possible_genres = ['Сёнен',
     'Сёнен-ай',
     'Сэйнэн',
     'Сёдзё',
     'Сёдзё-ай',
     'Дзёсей',
     'Комедия',
     'Романтика',
     'Школа',
     'Безумие',
     'Боевые искусства',
     'Вампиры',
     'Военное',
     'Гарем',
     'Гурман',
     'Демоны',
     'Детектив',
     'Детское',
     'Драма',
     'Игры',
     'Исторический',
     'Космос',
     'Магия',
     'Машины',
     'Меха',
     'Музыка',
     'Пародия',
     'Повседневность',
     'Полиция',
     'Приключения',
     'Психологическое',
     'Работа',
     'Самураи',
     'Сверхъестественное',
     'Спорт',
     'Супер сила',
     'Ужасы',
     'Фантастика',
     'Фэнтези',
     'Экшен',
     'Этти',
     'Триллер',
     'Эротика',
     'Хентай',
     'Яой',
     'Юри']
    df[possible_genres] = 0
    for i in range(df.shape[0]):
        for j in df['Жанры'][i]:
            df.at[i, j] = 1
    df = df.drop('Жанры', axis=1)
    df = df.dropna()
    rating_dict = {'G': 0, 'PG': 1, 'PG-13': 2, 'R-17': 3, 'R+': 4, 'Rx': 5}
    type_dict = {'TV Сериал': 0, 'Фильм': 1, 'ONA': 2, 'Спешл': 3, 'OVA': 4, 'Клип': 5}
    types = []
    for elem in df['Тип']:
        for key in type_dict:
            if elem == key:
                elem = type_dict[key]
                types.append(elem)
    df['Тип'] = types
    ratings = []
    for elem in df['Рейтинг']:
        for key in rating_dict:
            if elem == key:
                elem = rating_dict[key]
                ratings.append(elem)
    df['Рейтинг'] = ratings
    processed_data = df.copy()
    return processed_data


def get_anime_info(anime_url):

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0'}
    genres_all = []
    anime_type = ''
    special_anime_types = ['Фильм', 'Спешл', 'Клип']
    page = requests.get(url=anime_url, headers=headers)
    soup = BeautifulSoup(page.text, "lxml")
    if soup.find('span', class_='confirm') is None:
        try:
            anime_info = soup.find_all('div', class_='value')
            anime_type = anime_info[0].text
            genres = soup.find_all('span', class_='genre-ru')
            g = []
            for genre in genres:
                g.append(genre.text)
            genres_all.append(g)
            if anime_type in special_anime_types:
                episodes_number = '1'
            else:
                try:
                    episodes_number = anime_info[1].text
                except IndexError:
                    episodes_number = '1'
            if anime_type == 'OVA' and len(episodes_number) > 4:
                episodes_number = '1'
            age_rt = soup.find_all('div', class_='line-container')
            filter = []
            for row in age_rt:
                col = row.find('span', class_='b-tooltipped')
                if col is not None:
                    filter.append(col.text)
            if episodes_number.endswith('мин.'):
                episodes_number = '1'
            try:
                if set('PGR') & set(filter[-1]):
                    age_rating = filter[-1]
                else:
                    age_rating = np.nan
            except IndexError:
                age_rating = np.nan
            try:
                anime_score = soup.find('div', class_='score-value').text
            except AttributeError:
                anime_score = np.nan
        except IndexError:
            pass
        anime_vec = pd.DataFrame({
            'Тип': anime_type,
            'Эпизоды': episodes_number,
            'Рейтинг': age_rating,
            'Оценка сайта': anime_score,
            'Жанры': genres_all
        })
        return anime_vec


def get_anime_name(anime_url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0'}
    page = requests.get(url=anime_url, headers=headers)
    soup = BeautifulSoup(page.text, "lxml")
    anime_name = soup.find('h1').text
    name_tmp = soup.find('header', class_='head')
    name = name_tmp.find('meta').get('content')
    return name


async def params(data, msg, bot):
    X = data.drop('Оценка пользователя', axis=1)
    y = data['Оценка пользователя']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    grid = [range(2, 9), range(2, 9)]
    best_params = []
    best_score = -1
    i = 0
    for depth in grid[0]:
        for l2 in grid[1]:
            i += 1
            model = CatBoostClassifier(
                iterations=2500,
                loss_function='MultiClass',
                depth=depth,
                l2_leaf_reg=l2,
                learning_rate=0.01
            )
            model.fit(
                X_train, y_train,
                use_best_model=False,
                verbose=False,
                plot=False)
            pred = model.predict(X_test)
            score = f1_score(y_test, pred, average="weighted")
            progress = round(100 * i / 49, 7)
            await bot.edit_message_text(
                f'Обучаем модель.\nПрогресс: {progress}%',
                chat_id=msg.chat.id, message_id=msg.message_id)
            if score > best_score:
                best_score = score
                best_params = [[depth, l2]]
    return best_params


async def learning_and_saving(data, fname, saved_models, nick, msg, bot):
    X = data.drop('Оценка пользователя', axis=1)
    y = data['Оценка пользователя']
    p = await params(data, msg, bot)
    best_depth, best_l2 = p[0][0], p[0][1]
    model = CatBoostClassifier(iterations=2500, learning_rate=0.1, depth=best_depth, l2_leaf_reg=best_l2,
                               loss_function='MultiClass', logging_level='Silent')
    model.fit(X, y)
    model.save_model(fname, format="cbm", export_parameters=None, pool=None)
    with open('list_of_saved_models.json', 'w', encoding='utf-8') as file:
        nicks = saved_models['saved models']
        if nick in nicks:
            data_json = {'saved models': nicks}
            json.dump(data_json, file, ensure_ascii=False, indent=4)
        else:
            nicks.append(nick)
            data_json = {'saved models': nicks}
            json.dump(data_json, file, ensure_ascii=False, indent=4)
    return model


async def pred_res(nick, anime_url, msg, bot, retrain='False'):
    nick_fused = nick.translate(str.maketrans('', '', punctuation))
    fname = f'user_data\\{nick_fused}\\{nick_fused}-model'
    model_load = CatBoostClassifier()
    df = pd.read_json(f'user_data\\{nick_fused}\\{nick_fused}-anime_list_data.json')
    data = data_processing(df)
    anime_vector = data_processing(get_anime_info(anime_url))
    with open('list_of_saved_models.json', 'r', encoding='utf-8') as file:
        saved_models = json.load(file)
    if retrain == 'False':
        if nick in saved_models['saved models']:
            model = model_load.load_model(fname, format="cbm")
        else:
            model = await learning_and_saving(data, fname, saved_models, nick, msg, bot)
    else:
        model = await learning_and_saving(data, fname, saved_models, nick, msg, bot)
    pred = model.predict(anime_vector)[0][-1]
    anime_name = get_anime_name(anime_url)
    return int(pred), anime_name
