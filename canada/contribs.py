import codecs
import csv
import re
import sys
import time

import requests
from bs4 import BeautifulSoup


sys.stdout = codecs.getwriter('utf-8')(sys.stdout)


# set these manually
SEARCHNAME = 'postal-federal-green'
PARTY = True # true if searching by federal party, false if searching by riding association
QUERYID = 'f868943a57244de8b429dfefa8b2cab5'
SESSIONID = '5s0wku3wyqrtktzppohqgsye'
GETPOSTAL = True # true if we are scraping postal codes


PARTY_URI = 'http://www.elections.ca/WPAPPS/WPF/EN/PP/DetailedReport'
ASSOC_URI = 'http://www.elections.ca/WPAPPS/WPF/EN/EDA/DetailedReport'
base_uri = PARTY_URI if PARTY else ASSOC_URI
cookies = {'ASP.NET_SessionId': SESSIONID}
params = {'act': 'C2',
          'returntype': 1,
          'option': 2,
          'part': '2A',
          'period': 0,
          'fromperiod': 2012,
          'toperiod': 2012,
          'queryid': QUERYID
          }
start_time = time.time()

if GETPOSTAL:
    postal_params = params.copy()
    postal_params['displayaddress'] = 'True'

contribs = []


# get list of federal parties or riding associations
html = requests.get(base_uri, params=params, cookies=cookies)
soup = BeautifulSoup(html.text)

select = soup.find('select', id='selectedid')
if not select:
    print 'Error: no selectbox found on page. Try a new query ID.'
    sys.exit()


# prepare output csv
with open('contribs-{}.csv'.format(SEARCHNAME), 'wb', 1) as csvfile:
    writer = csv.writer(csvfile, lineterminator='\n')

    # iterate through list of federal parties or riding associations
    options = select.find_all('option')
    for o, option in enumerate(options):
        params['selectedid'] = option['value']
        party = option.get_text().split(' /', 1)[0]

        print 'Search {0} of {1}:'.format(o + 1, len(options)), party

        page = 1
        pages = 1
        while page <= pages:
            if pages == 1:
                print 'Reading page 1...',
            else:
                print 'Reading page {0} of {1}...'.format(page, pages),

            params['page'] = page
            search_html = requests.get(base_uri, params=params, cookies=cookies)
            print 'done.'

            #print search_html.text
            soup = BeautifulSoup(search_html.text)

            if page == 1:
                # check for multiple pages
                nextlink = soup.find('a', id='next200pagelink')
                if nextlink:
                    m = re.search('totalpages=(\d+)', nextlink['href'])
                    pages = int(m.group(1))
                    print pages, 'page(s) found.'.format(pages)

            table = soup.find('table', class_='DataTable')
            if not table:
                if soup.find(class_='nodatamessage'):
                    print 'No data for this search.'
                    continue

                print 'Error: no table on page. Try a new query ID.'
                sys.exit()

            rows = table.find('tbody').find_all('tr', recursive=False)
            for r, row in enumerate(rows):
                cells = row.find_all('td')

                num = cells[0].get_text().strip()
                # skip empty id numbers
                if not num:
                    continue
                # remove weird decimals from id numbers
                for ch in ',.':
                    if ch in num:
                        num = num.split(ch, 1)[0]


                name = cells[1].get_text().strip()

                if GETPOSTAL:
                    print 'Getting postal code {0} of {1}'.format(r + 1, len(rows))
                    postal_params.update({'addrname': name,
                                          'addrclientid': params['selectedid'],
                                          'page': page,
                                          })
                    postal_html = requests.get(base_uri, params=postal_params, cookies=cookies)
                    postal_soup = BeautifulSoup(postal_html.text)
                    city = postal_soup.find('input', id='city')['value']
                    province = postal_soup.find('input', id='province')['value']
                    postal_code = postal_soup.find('input', id='postalcode')['value'].upper().replace(' ', '')

                contrib = (party,
                           int(num), # number
                           name, # full name
                           cells[2].get_text().strip(), # date
                           int(float(cells[5].get_text().replace(',', '')) * 100), # total amount
                           city,
                           province,
                           postal_code
                           )

                writer.writerow([col.encode('utf-8') if isinstance(col, unicode) else col for col in contrib])

            page += 1



total_time = time.time() - start_time
print 'Total time: {0} minute(s) {1} second(s)'.format(total_time / 60, total_time % 60)
