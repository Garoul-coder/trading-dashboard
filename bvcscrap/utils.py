from bs4 import BeautifulSoup
import requests
from .notation import notation_code, notation_value


def get_code(name):
    for action in notation_code():
        if action["name"] == name:
            return action['ISIN']


def get_valeur(name):
    if name == "MASI":
        print("MASI can't be an argument for this function")
    return notation_value()[name]


def cleanText(text):
    return text.replace(",", ".").replace("%", "").replace("\xa0", "").replace("Â", "")


def getTable1(t):
    cols = ['Cours', 'Variation', 'Ouverture', 'Plus haut', 'Plus bas',
            'Cours de cloture veille', 'Volume', 'Volume en titres',
            'Capitalisation', 'Nombre de titres', 'Devise de cotation']
    t = list(map(cleanText, t))
    return dict(zip(cols, t))


def getTable6(t):
    if len(t) > 4:
        t = t[1:]
    cols = ['Prix achat', 'Quantite_achat', 'Prix de vente', 'Quantite_vente']
    t = list(map(cleanText, t))
    return dict(zip(cols, t))


def getTable7(t):
    a = dict()
    heure, prix, qte = [], [], []
    i = 0
    while i < len(t):
        heure.append(t[i])
        prix.append(t[i + 1])
        qte.append(t[i + 2].replace("\xa0", "").replace("Â", ""))
        i += 3
    a["Heure"] = heure
    a["Prix"] = prix
    a["Quantite"] = qte
    return a


def getTable4(t):
    a = dict()
    Date, Variation, Cloture, Volume, Ouverture, Plus_haut, Plus_bas = [], [], [], [], [], [], []
    i = 0
    while i < len(t):
        Date.append(t[i])
        Variation.append(t[i + 1])
        Cloture.append(t[i + 2])
        Volume.append(t[i + 3])
        Ouverture.append(t[i + 4])
        Plus_haut.append(t[i + 5])
        Plus_bas.append(t[i + 6])
        i += 7
    a["Date"] = list(map(cleanText, Date))
    a["Variation"] = list(map(cleanText, Variation))
    a["Cloture"] = list(map(cleanText, Cloture))
    a["Volume"] = list(map(cleanText, Volume))
    a["Ouverture"] = list(map(cleanText, Ouverture))
    a["Plus_haut"] = list(map(cleanText, Plus_haut))
    a["Plus_bas"] = list(map(cleanText, Plus_bas))
    return a


def getTables(soup):
    tabs = ['table1', "table6", "table7", "table4"]
    result = dict()
    for tab in tabs:
        t = soup.find(id=tab).find_all("span")
        t = [x.get_text() for x in t]
        if tab == 'table1':
            result["Données_Seance"] = getTable1(t)
        elif tab == "table6":
            result["Meilleur_limit"] = getTable6(t)
        elif tab == 'table7':
            result['Dernieres_Tansaction'] = getTable7(t)
        else:
            result["Seance_prec"] = getTable4(t)
    return result


def getTable4Fich(t):
    cols = ["Raison_sociale", "ISIN", "Ticker", "Siege_social", "Secteur_activité",
            "Commissaire_aux_comptes", "Date_de_constitution", "Date_introduction",
            "Durée_Exercice_Social", "Objet_social"]
    t = t[:4] + t[5:11]
    return dict(zip(cols, t))


def getTable3Fich(t):
    a = dict()
    i = 0
    while i < len(t):
        a[t[i]] = t[i + 1].replace(",", ".")
        i += 2
    return a


def getTable6Fich(t):
    cols_chifr = ["Annee", "Comptes_consolide", "Capital_social", "Capitaux_propres",
                  "Nombre_titres", "Chiffre_Affaires", "Resultat_exploitation", "Resultat_net"]
    cols_ratio = ["Annee", "BPA", "ROE", "Payout", "Dividend_yield", "PER", "PBR"]
    if "Chiffre d'Affaires" in t:
        t.remove("Chiffre d'Affaires")
    if "Résultat d'exploitation" in t:
        t.remove("Résultat d'exploitation")
    annee, anne = [], []
    Comptes_consolide, Capital_social, Capitaux_propres, Nombre_titres = [], [], [], []
    Chiffre_Affaires, Resultat_exploitation, Resultat_net = [], [], []
    BPA, ROE, Payout, Dividend_yield, PER, PBR = [], [], [], [], [], []
    chifr = [annee, Comptes_consolide, Capital_social, Capitaux_propres,
             Nombre_titres, Chiffre_Affaires, Resultat_exploitation, Resultat_net]
    ratio = [anne, BPA, ROE, Payout, Dividend_yield, PER, PBR]
    i, j, u = 0, 0, 0
    while i < len(t) and j < len(chifr):
        if i > 5 and not t[i].replace(",", "").isdigit():
            cols_chifr[j] = t[i]
            i += 1
        chifr[j].append(t[i])
        chifr[j].append(t[i + 1])
        chifr[j].append(t[i + 2])
        i += 3
        j += 1
    while i < len(t) and u < len(ratio):
        ratio[u].append(t[i].replace("\xa0", ""))
        ratio[u].append(t[i + 1].replace("\xa0", ""))
        ratio[u].append(t[i + 2].replace("\xa0", ""))
        i += 3
        u += 1
    return [dict(zip(cols_chifr, chifr)), dict(zip(cols_ratio, ratio))]


def getTablesFich(soup):
    tabs = ['table4', "table3", "table6"]
    result = dict()
    for tab in tabs:
        if tab == 'table4':
            t = soup.find(id=tab).find_all("span")
            t = [x.get_text() for x in t]
            result["Info_Societe"] = getTable4Fich(t)
        elif tab == "table3":
            t = soup.find(id="table3").find_all('span')
            t = [x.get_text() for x in t]
            result["Actionnaires"] = getTable3Fich(t)
        elif tab == 'table6':
            t = soup.find(id="table6").find_all("span")
            t1 = soup.find(id="table6").find_all(class_="desc")
            t = [x.get_text().replace("\xa0", "").replace("-", "")
                 for x in t if x not in t1]
            a = getTable6Fich(t)
            result['Chiffres_cles'] = a[0]
            result["Ratio"] = a[1]
    return result
