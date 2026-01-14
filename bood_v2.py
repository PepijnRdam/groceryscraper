import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
import re 
import requests # let's load the requests library
def parse_input(user_input_str):
    """
    Splits string into items, then splits quantity and name.
    Supports: "2 kipfilet", "melk", "5 pasta"
    """
    clean_list = []
    # Split by comma
    raw_items = user_input_str.split(',')
    
    for item in raw_items:
        item = item.strip()
        if not item: continue
            
        # Regex to find a number at the START (e.g., "2 kipfilet")
        # match group 1 is the number, group 2 is the text
        match = re.match(r"(\d+)\s+(.*)", item)
        
        if match:
            qty = int(match.group(1))
            name = match.group(2)
        else:
            # If no number found, assume 1
            qty = 1
            name = item
            
        clean_list.append({"raw_name": name, "qty": qty})
        
    return clean_list

lijst = input('Typ hier je boodschappenlijst in de format (5 komkommers, 1 cola, aardbeien, ...) svp: ')
parsed_list =parse_input(lijst)
print(parsed_list)
boodschappen = lijst.split(', ')
print('De desbetreffende boodschappen zijn:', boodschappen)

product_synonyms = {
    "kip 300gr": ["kippen borst", "kippenborst", "kip dij", "kipfilet", "kipdij"],
    "melk 1L": ["milk", "volle melk", "halfvolle melk", "melk 1L"],
    "spaghetti 500gr": ["spaghetti", "pasta", "volkoren spaghetti"]
}

def normalize_product(user_input):
    user_input = user_input.lower()
    for normalized, variants in product_synonyms.items():
        for variant in variants:
            if variant in user_input:
                return normalized
    return user_input  # fallback if no match


normalized_list = [{'name': normalize_product(item['raw_name']), 'qty': item['qty']} 
    for item in parsed_list]
print(normalized_list)

def download_data(url):
    # make a get request to the website
    
    header = {'User-agent': 'Mozilla/5.0'} # with the user agent, we let Python know for which browser version to retrieve the website
    web_request = requests.get(f'https://www.ah.nl/zoeken?query={url}', headers = header)

    # return the source code from the request object
    soup =  BeautifulSoup(web_request.text, features= 'lxml')
    #section_prijs = soup.find(class_ = 'product-card-hero-price_root__Cx0SP product-card-hero-compact_price__UfW7Z')
    #print(section_prijs)
    #prize = section_prijs.find_all('div', attrs= {'data-testhook': 'price-amount'})[0]
    bonus = soup.find('div', attrs={'data-testid': 'product-shield'})
    if bonus is not None:
        prijs = soup.find_all('div', attrs={'data-testid': 'price-amount'})[1].get_text()

    else:
        prijs = soup.find_all('div', attrs={'data-testid': 'price-amount'})[0].get_text()
    div = soup.find(class_='product-card-header_unitInfo__ddXw6')
    hoeveelheid = soup.find_all('span', attrs={'data-testid': 'product-unit-size'})[0].get_text()
    product = soup.find_all('span', attrs={'data-testid': 'product-title'})[0].get_text()
    #hoeveelheid = soup.find(class_ = 'product-card-header_unitInfo__ddXw6').get_text()
    prijs = float(prijs)
    print(f'Prijs van {product} is: {prijs}. De hoeveelheid is: {hoeveelheid}')
    print(product)
    return {
        "naam": product,
        "prijs": prijs,
        "hoeveelheid": hoeveelheid
    }
    #print(prize)


#url = 'https://www.ah.nl/producten/product/wi4102/ah-sperziebonen'

#urls = ['wi4102','wi230848', 'wi130273', 'wi210145']

#for url in normalized_list:
    #download_data(url)

total_basket_price = 0.0

for item in normalized_list:
    search_term = item['name']
    quantity = item['qty']
    
    # Run the scraper
    result = download_data(search_term)
    
    if result:
        # Calculate totals using the 'price' key from the returned dictionary
        line_total = result['prijs'] * quantity
        print(line_total)
        total_basket_price += line_total
        
        # Now you can print all the "multiple things" clearly
        print(f"In winkel: {result['naam']}")
        print(f"Aantal: {quantity} x €{result['prijs']:.2f} = €{line_total:.2f}")
        print("-" * 20)

print(f"GRAND TOTAL: €{total_basket_price:.2f}")