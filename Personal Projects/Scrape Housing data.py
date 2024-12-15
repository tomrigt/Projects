import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
from itertools import cycle


response = requests.get(
  url='https://proxy.scrapeops.io/v1/',
  params={
      'api_key': '93de152a-6219-42e1-a226-4d498aa2b36e',
      'url': 'https://www.idealista.com/nl/alquiler-viviendas/barcelona-barcelona/',
  },
)

soup = BeautifulSoup(response.content, 'html.parser')
results = soup.find_all('article', {'class': "item item-multimedia-container"})
print(results)