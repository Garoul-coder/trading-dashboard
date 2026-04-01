import requests
import urllib3
from bs4 import BeautifulSoup
from .utils import get_valeur, getTables, getTablesFich

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'}


def getCours(name):
    code = get_valeur(name)
    data = {"__EVENTTARGET": "SocieteCotee1$LBIndicCle"}
    link = "https://www.casablanca-bourse.com/bourseweb/Societe-Cote.aspx?codeValeur=" + code + "&cat=7"
    res = requests.post(link, data=data, headers=_HEADERS, verify=False, timeout=10).content
    soup = BeautifulSoup(res, 'html.parser')
    return getTables(soup)


def getKeyIndicators(name, decode='utf-8'):
    code = get_valeur(name)
    data = {"__EVENTTARGET": "SocieteCotee1$LBFicheTech"}
    link = "https://www.casablanca-bourse.com/bourseweb/Societe-Cote.aspx?codeValeur=" + code + "&cat=7"
    res = requests.post(link, data=data, headers=_HEADERS, verify=False, timeout=10).content.decode(decode)
    soup = BeautifulSoup(res, 'html.parser')
    return getTablesFich(soup)
