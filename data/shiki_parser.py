from bs4 import BeautifulSoup
import requests
import time
import os
import pandas as pd
import numpy as np
from string import punctuation
import logging
import asyncio
import aiohttp
from tqdm import tqdm


class Shikiparser():

    def __init__(self, nick):
        self.nick = nick
        self.url = f'https://shikimori.one/{self.nick}/list/anime/mylist/completed'
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0'}
        self.genres_all = []
        self.anime_type = []
        self.index_to_del = []
        self.rating = []
        self.ep_num = []
        self.shiki_score = []
        self.names_and_grades = []
        self.names_and_urls = []
        self.grades_list = []
        self.url_list = []
        self.special_anime_types = ['Фильм', 'Спешл', 'Клип']

    @property
    def work_with_data(self):
        dictionary = {'Тип': self.anime_type, 'Эпизоды': self.ep_num, 'Жанры': self.genres_all,
                      'Рейтинг': self.rating,
                      'Оценка сайта': self.shiki_score, 'Оценка пользователя': self.grades_list}
        df = pd.DataFrame.from_dict(dictionary)
        df.loc[df['Рейтинг'] == "R-17. В РФ только по достижению 18 лет.", "Рейтинг"] = "R-17"
        df.loc[df['Рейтинг'] == "R+. В РФ только по достижению 18 лет.", "Рейтинг"] = "R+"
        df.loc[df['Рейтинг'] == "PG-13. В РФ только по достижению 18 лет.", "Рейтинг"] = "PG-13"
        nick_fused = self.nick.translate(str.maketrans('', '', punctuation))
        os.makedirs(f'user_data\\{nick_fused}', exist_ok=True)
        df.to_json(f'user_data\\{nick_fused}\\{nick_fused}-anime_list_data.json', force_ascii=False, indent=4)

    async def get_page_data(self, session, url):
        async with session.get(url=url, headers=self.headers) as response:
            response_text = await response.text()
            epn = None
            el_k = -1
            rating = -1
            soup = BeautifulSoup(response_text, 'lxml')
            info = soup.find('div', class_='b-entry-info')
            anime_info_1 = info.find_all('div', class_='key')
            anime_info_2 = info.find_all('div', class_='value')
            if response.status != 200:
                logging.basicConfig(filename='response_status.log', level=logging.INFO)
                h1 = soup.find('h1').text
                logging.info(f'     {response.status}, {h1}')
            for elem in range(len(anime_info_1)):
                if anime_info_1[elem].text == 'Тип:':
                    anime_type = anime_info_2[elem].text
                    self.anime_type.append(anime_type)
                if anime_info_1[elem].text == 'Рейтинг:':
                    rating = anime_info_2[elem].text
                    self.rating.append(rating)
                if anime_info_1[elem].text == 'Эпизоды:':
                    el_k = elem
                if elem == 0:
                    genres = soup.find_all('span', class_='genre-ru')
                    score_value = soup.find('div', class_='score-value').text
                    self.shiki_score.append(score_value)
                    g = []
                    for genre in genres:
                        g.append(genre.text)
                    self.genres_all.append(g)
            if anime_type in self.special_anime_types:
                epn = '1'
            if anime_type == 'OVA' and epn is None:
                epn = '1'
            if el_k != -1:
                epn = anime_info_2[el_k].text
            if rating == -1:
                self.rating.append(np.nan)
            self.ep_num.append(epn)

    async def gather_data(self, bot, msg):
        async with aiohttp.ClientSession() as session:
            page_number = 0
            tasks = []
            for url in tqdm(self.url_list):
                page_number += 1
                task = asyncio.create_task(self.get_page_data(session, url))
                progress = round(100 * page_number / len(self.url_list), 7)
                await bot.edit_message_text(
                    f'Начинаем обработку списка.\nПрогресс: {progress}%',
                    chat_id=msg.chat.id, message_id=msg.message_id)
                tasks.append(task)
                await asyncio.sleep(1.35)
            await asyncio.gather(*tasks)

    @property
    def my_list(self):
        nick = self.nick
        time.sleep(1)
        page_number = 1
        grades = []
        names = []
        hrefs = []
        hnames = []
        while True:
            time.sleep(1)
            url = f'https://shikimori.one/{nick}/list/anime/mylist/completed/order-by/ranked/page/{page_number}'
            page = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(page.text, "lxml")
            if soup.find('p') is not None:
                if soup.find('p').text == 'You are not authorized to access this page.':
                    break
            if soup.find('p', class_='b-nothing_here') is not None:
                break
            all_names = soup.find_all('tr')
            all_grades = soup.find_all('td')
            urls = soup.find_all('a', class_='tooltipped')
            for anime in all_names[2:]:
                name = anime.get('data-target_name')
                names.append(name)
            for anime in all_grades:
                anime_str = str(anime)
                if anime_str.startswith(
                        '<td class="num"><span class="current-value" data-field="score" data-max="10" data-min="0">'):
                    temp_grade = anime_str[90:92].replace('<', '')
                    if temp_grade == '–':
                        grades.append(np.nan)
                    else:
                        grades.append(temp_grade)
            for anime in urls:
                href = anime.get('href')
                hrefs.append(href)

            page_number += 1
        hent_page = 1
        hent_count = 0
        while True:
            time.sleep(1)
            url = f'https://shikimori.one/{nick}/list/anime/rating/rx/mylist/completed/order-by/rate_score/page/{hent_page}'
            page = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(page.text, "lxml")
            if soup.find('p') is not None:
                if soup.find('p').text == 'You are not authorized to access this page.':
                    break
            if soup.find('p', class_='b-nothing_here') is not None:
                break
            hurls = soup.find_all('tr', class_='user_rate')
            for anime in hurls:
                hname = anime.find('a').get('href')
                hnames.append(hname)
            if hent_page == 1:
                hent_count = 1
            hent_page += 1
        for i in range(len(hrefs)):
            if hrefs[i] in hnames:
                hrefs[i] = np.nan
                grades[i] = np.nan
        if hent_count == 1:
            hrefs_ = [v for v in hrefs if v == v]
            self.url_list = ['https://shikimori.one' + x for x in hrefs_]
            self.grades_list = [v for v in grades if v == v]
        else:
            self.url_list = ['https://shikimori.one' + x for x in hrefs]
            self.grades_list = grades

    @property
    def parse_all_animes_in_the_list(self):
        time.sleep(1)
        trouble_urls = []
        for anime_url in tqdm(self.url_list):
            epn = None
            el_k = -1
            rating = -1
            time.sleep(1)
            page = requests.get(url=anime_url, headers=self.headers)
            soup = BeautifulSoup(page.text, "lxml")
            try:
                info = soup.find('div', class_='b-entry-info')
                anime_info_1 = info.find_all('div', class_='key')
                anime_info_2 = info.find_all('div', class_='value')
                for elem in range(len(anime_info_1)):
                    if anime_info_1[elem].text == 'Тип:':
                        anime_type = anime_info_2[elem].text
                        self.anime_type.append(anime_type)
                    if anime_info_1[elem].text == 'Рейтинг:':
                        rating = anime_info_2[elem].text
                        self.rating.append(rating)
                    if anime_info_1[elem].text == 'Эпизоды:':
                        el_k = elem
                    if elem == 0:
                        genres = soup.find_all('span', class_='genre-ru')
                        score_value = soup.find('div', class_='score-value').text
                        self.shiki_score.append(score_value)
                        g = []
                        for genre in genres:
                            g.append(genre.text)
                        self.genres_all.append(g)
                if anime_type in self.special_anime_types:
                    epn = '1'
                if anime_type == 'OVA' and epn is None:
                    epn = '1'
                if el_k != -1:
                    epn = anime_info_2[el_k].text
                if rating == -1:
                    self.rating.append(np.nan)
                self.ep_num.append(epn)
            except AttributeError:
                time.sleep(7)
                trouble_urls.append(anime_url)
                continue

        if len(trouble_urls) != 0:
            for anime_url in tqdm(trouble_urls):
                epn = None
                el_k = -1
                rating = -1
                time.sleep(3)
                page = requests.get(url=anime_url, headers=self.headers)
                soup = BeautifulSoup(page.text, "lxml")
                info = soup.find('div', class_='b-entry-info')
                anime_info_1 = info.find_all('div', class_='key')
                anime_info_2 = info.find_all('div', class_='value')
                for elem in range(len(anime_info_1)):
                    if anime_info_1[elem].text == 'Тип:':
                        anime_type = anime_info_2[elem].text
                        self.anime_type.append(anime_type)
                    if anime_info_1[elem].text == 'Рейтинг:':
                        rating = anime_info_2[elem].text
                        self.rating.append(rating)
                    if anime_info_1[elem].text == 'Эпизоды:':
                        el_k = elem
                    if elem == 0:
                        genres = soup.find_all('span', class_='genre-ru')
                        score_value = soup.find('div', class_='score-value').text
                        self.shiki_score.append(score_value)
                        g = []
                        for genre in genres:
                            g.append(genre.text)
                        self.genres_all.append(g)
                if anime_type in self.special_anime_types:
                    epn = '1'
                if anime_type == 'OVA' and epn is None:
                    epn = '1'
                if el_k != -1:
                    epn = anime_info_2[el_k].text
                if rating == -1:
                    self.rating.append(np.nan)
                self.ep_num.append(epn)

    async def do(self, bot, msg):
        self.my_list
        await self.gather_data(bot=bot, msg=msg)
        self.work_with_data

    async def main(self, method='async'):
        nick_fused = self.nick.translate(str.maketrans('', '', punctuation))
        self.my_list
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(self.gather_data)
        df = self.work_with_data
        os.makedirs(nick_fused, exist_ok=True)
        df.to_json(f'{nick_fused}\\{nick_fused}-anime_list_data.json', force_ascii=False, indent=4)
