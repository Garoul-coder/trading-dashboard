import requests
import urllib3
from bs4 import BeautifulSoup
from .utils import get_valeur, getTables, getTablesFich

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
}


def _get_session_and_viewstate(link):
    """GET the page first to get ASP.NET session cookies + hidden form fields."""
    session = requests.Session()
    res = session.get(link, headers=_HEADERS, verify=False, timeout=6)
    soup = BeautifulSoup(res.content, 'html.parser')
    form_data = {}
    for field in ['__VIEWSTATE', '__VIEWSTATEGENERATOR', '__EVENTVALIDATION']:
        el = soup.find('input', {'name': field})
        if el:
            form_data[field] = el.get('value', '')
    return session, form_data


def getCours(name):
    code = get_valeur(name)
    link = "https://www.casablanca-bourse.com/bourseweb/Societe-Cote.aspx?codeValeur=" + code + "&cat=7"
    session, form_data = _get_session_and_viewstate(link)
    form_data["__EVENTTARGET"] = "SocieteCotee1$LBIndicCle"
    res = session.post(link, data=form_data, headers=_HEADERS, verify=False, timeout=6).content
    soup = BeautifulSoup(res, 'html.parser')
    return getTables(soup)


def getKeyIndicators(name, decode='utf-8'):
    code = get_valeur(name)
    link = "https://www.casablanca-bourse.com/bourseweb/Societe-Cote.aspx?codeValeur=" + code + "&cat=7"
    session, form_data = _get_session_and_viewstate(link)
    form_data["__EVENTTARGET"] = "SocieteCotee1$LBFicheTech"
    res = session.post(link, data=form_data, headers=_HEADERS, verify=False, timeout=6).content.decode(decode)
    soup = BeautifulSoup(res, 'html.parser')
    return getTablesFich(soup)
