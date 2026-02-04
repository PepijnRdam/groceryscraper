import requests
import re
from bs4 import BeautifulSoup
from thefuzz import process, fuzz
import json
import os
import streamlit as st
# Get the directory where the current script is located
base_path = os.path.dirname(__file__)
json_path = os.path.join(base_path, "normalize.json")
json_path2 = os.path.join(base_path, "store_search_terms.json")
# load the synonyms
with open(json_path, "r", encoding="utf-8") as f:
    product_synonyms = json.load(f)

with open(json_path2, "r", encoding="utf-8") as f:
    STORE_SEARCH_TERMS = json.load(f)
st.title('Economisch Hoogstandje')
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
lijst = st.text_input('Typ hier je boodschappenlijst in de format (5 komkommers, 1 cola, ...) svp: ')
parsed_list =parse_input(lijst)
print(parsed_list)
boodschappen = lijst.split(', ')
print('De desbetreffende boodschappen zijn:', boodschappen)

def calculate_unit_price(price, size_text):
    """
    Converts size strings to a normalized price per 1kg, 1L, or 1 piece.
    Examples: '500 g', '1 kg', '750 ml', '1.5 l', '10 stuks', '6 st'
    """
    try:
        # 1. Clean the string and handle European decimal commas (e.g., '1,5' -> '1.5')
        size_text = size_text.lower().replace(',', '.')
        if "per stuk" in size_text or "los" in size_text:
            return round(price, 2)
        # 2. Regex to find the number and the unit
        # Matches: (digits/decimals) + (optional space) + (letters)
        match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', size_text)
        
        if not match:
            return price # Fallback: if we can't parse it, return the raw price

        value = float(match.group(1))
        unit = match.group(2)

        # 3. Conversion Logic
        # Weight (Target: 1 kg)
        if unit in ['g', 'gr', 'gram']:
            factor = value / 1000
        elif unit in ['kg', 'kilo']:
            factor = value
            
        # Volume (Target: 1 L)
        elif unit in ['ml', 'cl']:
            factor = value / 1000 if unit == 'ml' else value / 100
        elif unit in ['l', 'liter']:
            factor = value
            
        # Pieces (Target: 1 piece)
        elif unit in ['st', 'stuks', 'stuks/pack']:
            factor = value
            
        else:
            factor = value # Default fallback

        # 4. Return price per unit (1kg, 1L, or 1 piece)
        return round(price / factor, 2) if factor > 0 else price

    except Exception as e:
        print(f"Error parsing size '{size_text}': {e}")
        return price

def normalize_product(user_input):
    user_input = user_input.lower()
    best_match = None
    highest_score = 0
    assigned_internal_key = None

    for internal_key, variants in product_synonyms.items():
        # process.extractOne finds the best match within the list of variants
        match, score = process.extractOne(user_input, variants, scorer=fuzz.token_sort_ratio)
        
        if score > highest_score:
            highest_score = score
            best_match = match
            assigned_internal_key = internal_key

    # If the similarity is high enough (e.g., > 75), return the key
    if highest_score > 75:
        return assigned_internal_key
    
    # Fallback if no good match is found
    return user_input

def get_store_specific_query(normalized_name, store_name):
    """
    Looks up the specific search term for a specific store.
    """
    store_data = STORE_SEARCH_TERMS.get(store_name.lower())
    if store_data:
        # Return the store's specific term, or the name itself if not found
        return store_data.get(normalized_name, normalized_name)
    return normalized_name

# 1. Process the user input into the normalized list (Your existing logic)
normalized_list = [{'name': normalize_product(item['raw_name']), 'qty': item['qty']} 
    for item in parsed_list]
print(normalized_list)

# 2. Create a final "Scrape Plan"
# This organizes everything by store so your scraper knows exactly what to do.
scrape_plan = {}

for store in STORE_SEARCH_TERMS.keys():
    scrape_plan[store] = []
    for item in normalized_list:
        # Get the specific name the store understands
        search_term = get_store_specific_query(item['name'], store)
        
        scrape_plan[store].append({
            "search_for": search_term,
            "quantity": item['qty']
        })


def get_scrape_results(scrape_plan):
    """
    This function acts as the manager. It looks at the plan 
    and calls the right scraper for each store.
    """
    all_results = {}

    for store, items in scrape_plan.items():
        st.write(f"\n--- Scraping Store: {store.upper()} ---")
        all_results[store] = []
        total_store_price = 0.0

        for item in items:
            search_query = item['search_for']
            qty = item['quantity']
            
            result = None
            try:
                if store == "ah":
                    result = download_ah(search_query)
                elif store == "jumbo":
                    result = download_jumbo(search_query)
                # Add lidl/aldi here later
                
                if result:
                    line_total = result['prijs'] * qty
                    result['totaal'] = line_total
                    result['gevraagd_aantal'] = qty
                    all_results[store].append(result)
                    total_store_price += line_total
                    st.write(f"  ✅ Found: {result['naam']} | {qty}x €{result['prijs']} = €{line_total:.2f}")
            except Exception as e:
                st.write(f"  ❌ Error scraping '{search_query}' at {store}: {e}")

        st.write(f"TOTAL FOR {store.upper()}: €{total_store_price:.2f}")
    
    return all_results

def download_jumbo(id_list):
    results =[]
    # # make a get request to the website
    for product_id in id_list:
        header = {'User-agent': 'Mozilla/5.0'} # with the user agent, we let Python know for which browser version to retrieve the website
        web_request = requests.get(f'https://www.jumbo.com/producten/?searchType=keyword&searchTerms={product_id}', headers = header)

        # return the source code from the request object
        soup =  BeautifulSoup(web_request.text, features= 'lxml')
        
        resultset = soup.find('div', attrs={'data-testid': 'results-list'})
        firstproduct = resultset.find_all('article', attrs={'class': 'product-container'})[0]
        bonus = firstproduct.find('div', attrs={'class': 'card-promotion'})
        if bonus is not None:
            prijs2 = soup.find_all('div', attrs={'data-testid': 'product-price'})[0]
            prijs = prijs2.find('div', attrs={'class': 'current-price'})
            heleprijs = prijs.find('span', attrs={'class': 'whole'}).get_text()
            nadekomma = prijs.find('span', attrs={'class': 'fractional'}).get_text()
            
            prijs = float((heleprijs + '.' + nadekomma))
            bonustext = soup.find('div', attrs={'class': 'product-tags'}).get_text()
            price_per_unit = prijs2.find('div', attrs={'class': 'price-per-unit'}).findNext('span').get_text()
            price_per_unit = float(price_per_unit.replace(",", "."))


        else:
            prijs2 = soup.find_all('div', attrs={'data-testid': 'product-price'})[0]
        
            prijs = prijs2.find('div', attrs={'class': 'current-price'})
            heleprijs = prijs.find('span', attrs={'class': 'whole'}).get_text()
            nadekomma = prijs.find('span', attrs={'class': 'fractional'}).get_text()
            
            prijs = float((heleprijs + '.' + nadekomma))
            bonustext = 'Geen Bonus'
            price_per_unit = prijs2.find('div', attrs={'class': 'price-per-unit'}).findNext('span').get_text()
            price_per_unit = float(price_per_unit.replace(",", "."))

        print(bonustext)
        print(price_per_unit)
        hoeveelheid = soup.find_all('div', attrs={'data-testid': 'jum-card-subtitle'})[0].get_text()
        product = soup.find_all('a', attrs={'class': 'title-link'})[0].get_text()
        
        results.append({"naam": product, "prijs": prijs, "hoeveelheid": hoeveelheid, "unit_price": price_per_unit, "bonus_info": bonus})

        st.write(f'Prijs van {product} is: {prijs}. De hoeveelheid is: {hoeveelheid}')
        
    return min(results, key=lambda x: x['unit_price'])



def download_ah(id_list):
    results = []
    for product_id in id_list:
        # AH product pages often follow this URL structure
        url = f"https://www.ah.nl/producten/product/{product_id}"
        header = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=header)
        
        soup = BeautifulSoup(res.text, 'lxml')
        
        try:
            name = soup.find('h1').get_text()
            
            
            bonus_container = soup.find('div', class_ = re.compile("product-card-hero_tieredOffers"))
            if bonus_container and bonus_container.get_text():
                bonus = bonus_container.get_text()
                size = soup.find_all('span', attrs={'data-testhook': 'product-unit-size'})[0].get_text()
                price = float(soup.find_all('div', attrs={'data-testid': 'price-amount'})[1].get_text())
            else:
                bonus = "Geen Bonus"
                size = soup.find('span', attrs={'data-testhook': 'product-unit-size'}).get_text()
                price = float(soup.find('div', attrs={'data-testid': 'price-amount'}).get_text())
            
           # print(bonus)
           # print(size)
            price_per_unit = calculate_unit_price(price, size)
           # print(price)
           # print(price_per_unit)
            results.append({"naam": name, "prijs": price, "hoeveelheid": size, "unit_price": price_per_unit, "bonus_info": bonus})
           # print(price_per_unit, name)
        except Exception as e:
            # Printing the error helps you see WHY it skipped
            print(f"Skipped {product_id} because: {e}")
            continue
            
    # Return only the cheapest one from your list
    return min(results, key=lambda x: x['unit_price'])




total_basket_price = 0.0

final_results = get_scrape_results(scrape_plan)


# --- 5. Display Final Comparison ---
st.write("\n" + "="*30)
st.write("EINDRESULTAAT VERGELIJKING")
st.write("="*30)

for store, products in final_results.items():
    store_total = sum(p['totaal'] for p in products)
    st.write(f"{store.upper()}: €{store_total:.2f}")
    for p in products:
        st.write(f"  - {p['gevraagd_aantal']}x {p['naam']}: €{p['totaal']:.2f}")