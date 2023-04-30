from datetime import datetime, date
import locale

import pandas as pd
import requests
from alive_progress import alive_bar


def get_inner_html(html_block, class_names, default=''):
    remaining_html = None
    for class_names_start, class_names_end in class_names:
        if class_names_end is None:
            class_names_end = '</'
        start_index = html_block.find(class_names_start)
        if start_index == -1:
            return None, default
        end_index = html_block.find(class_names_end, start_index)
        if remaining_html is None:
            remaining_html = html_block[end_index:]
        html_block = html_block[start_index + len(class_names_start) + 1: end_index]
    return remaining_html, html_block


locale.setlocale(locale.LC_ALL, 'da_dk')
rent = 20000
size = 90
rooms = 3
areas = ['københavn-s', 'københavn-sv', 'københavn-v', 'frederiksberg', 'frederiksberg-c', 'københavn-k']

base_url = f'https://www.boligportal.dk/lejligheder,r%C3%A6kkehuse/k%C3%B8benhavn/{rooms}+-v%C3%A6relser/'
urls = [base_url + area + f'/?max_monthly_rent={rent}&min_size_m2={size}&shareable=1&min_rental_period=0&balcony=1' for
        area in areas]

links = []
for i, url in enumerate(urls):
    print('\nLooking for apartments in', areas[i])
    offset = 0
    with alive_bar(0) as bar:
        while True:
            page_url = url
            page_url += f'&offset={offset}'
            html = str(requests.get(page_url, allow_redirects=True).content)
            if 'Ingen boliger i' in html:
                break
            _, html = get_inner_html(html, [('class="css-16jggh1"', 'class="css-1lrlb33"')])
            while True:
                html, link = get_inner_html(html, [('AdCardSrp__Link css-17x8ssx" href="', '" target')])
                if html is None:
                    break
                links.append('https://www.boligportal.dk/' + link)
                bar()
            offset += 18

apartments = {}
print('Fetching apartment information...')
with alive_bar(len(links)) as bar:
    for link in links:
        html = requests.get(link, allow_redirects=True).text

        _, rent = get_inner_html(html, [('class="css-wi20xz"', 'class="css-1bk8ra8"'), ('class="css-ty9xyk"', None)])
        rent = float(rent.replace('.', ''))

        _, aconto = get_inner_html(html, [
            ('class="css-wi20xz"', 'class="css-1bk8ra8"'),
            ('<span class="css-106rb8p">Månedlig aconto</span>', 'class="css-1xjiks0"'),
            ('class="css-19zssoc"', ' kr')
        ])
        aconto = float(aconto.replace('.', ''))

        _, deposit = get_inner_html(html, [
            ('class="css-wi20xz"', 'class="css-1bk8ra8"'),
            ('<span class="css-106rb8p">Indflytningspris</span>', 'class="css-y8cidf"'),
            ('class="css-19zssoc"', ' kr')
        ])
        deposit = float(deposit.replace('.', ''))

        _, available_from = get_inner_html(html, [
            ('class="css-wi20xz"', 'class="css-1bk8ra8"'),
            ('class="css-1ys1232"', None)
        ], 'Snarest muligt')

        _, apartment_type = get_inner_html(html, [
            ('<span class="css-arxwps">Boligtype</span>', 'class=" temporaryFlexColumnClassName css-etn5cp"'),
            ('class="css-1h46kg2"', None)
        ])

        _, size = get_inner_html(html, [
            ('<span class="css-arxwps">Størrelse</span>', 'class=" temporaryFlexColumnClassName css-etn5cp"'),
            ('class="css-1h46kg2"', 'm²')
        ])
        size = int(size)

        _, rooms = get_inner_html(html, [
            ('<span class="css-arxwps">Værelser</span>', 'class=" temporaryFlexColumnClassName css-etn5cp"'),
            ('class="css-1h46kg2"', None)
        ])
        rooms = int(rooms)

        _, address = get_inner_html(html, [
            ('class="css-tfjtmt"', 'class="css-jwxfhp"'), ('class="css-v49nss"', None)
        ])
        address = address.split(',')
        area_and_floor = address[2].split('-')
        apartments[link] = [link, apartment_type] + address[:-1] + area_and_floor + [size, rooms, rent, aconto, deposit,
                                                                                     available_from]
        bar()

df = pd.DataFrame.from_dict(apartments, orient='index',
                            columns=['Link', 'Apartment Type', 'Road name', 'Post town', 'City area', 'Floor', 'Size',
                                     'Rooms', 'Rent', 'Monthly installment', 'Deposit', 'Available from'])

rent = df['Rent']
aconto = df['Monthly installment']
size = df['Size']

df['Price pr m²'] = [(r + ac) / s for r, ac, s in zip(rent, aconto, size)]

available_from = df['Available from']


def to_date_time(d): return datetime.strptime(d, '%d. %B %Y').strftime("%d. %B %Y")


available_from = [to_date_time(af) if af != 'Snarest muligt' else date.today().strftime("%d. %B %Y") for af in
                  available_from]

df['Available from'] = available_from

df.to_csv('apartments_en.csv', index=False)
df = df.rename(columns={
    'Apartment Type': 'Boligtype', 'Road name': 'Vej navn', 'Post town': 'Post nummer', 'City area': 'Område',
    'Floor': 'Etage', 'Size': 'Størelse', 'Rooms': 'Værelser', 'Rent': 'Månedlig leje',
    'Monthly installment': 'Månedlig aconto', 'Deposit': 'Indflytningspris', 'Available from': 'Ledig fra'
})
df.to_csv('apartments_dk.csv', index=False)
print(df.dtypes)
