from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent
from dotenv import load_dotenv
from datetime import datetime
import dateparser
import requests
import sqlite3
import random
import string
import time
import os

DEBUG = True
# DEBUG = False
load_dotenv()
#proxies
USER_ID = os.environ.get('BRD_USER_ID')
PASSWORD = os.environ.get('BRD_PASSWORD')
PROXY_URL = "brd.superproxy.io:22225"
#telegram
TOKEN =  os.environ.get('TELEGRAM_BOT_API_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
# bookit it
BOOKITIT_API = os.environ.get('BOOKITIT_API')

# navigation
SITE_URL = "https://www.exteriores.gob.es/Consulados/amsterdam/en/ServiciosConsulares/Paginas/inicio.aspx"
CITA_LINK_SELECTOR = f"a[href='https://app.bookitit.com/es/hosteds/widgetdefault/{BOOKITIT_API}#services']"
INSCRIPCION_LINK_TEXT = "[K]... INSCRIPCIÓN CONSULAR"
DATE_ELEMENT_SELECTOR = "#idDivBktDatetimeSelectedDate"

if not USER_ID or not PASSWORD:
    raise ValueError("Please set the BRD_USER_ID and BRD_PASSWORD environment variables.")

def create_table(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            num_appointments INTEGER,
            server_response_time REAL
        )
    ''')
    conn.commit()

def init_db():
    db_exists = os.path.exists('appointments.db')
    conn = sqlite3.connect('appointments.db')
    if not db_exists:
        create_table(conn)

def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    payload = {'chat_id': CHAT_ID, 'text': text}
    print(url,payload)
    response = requests.post(url, data=payload)
    print(response.json())

def fetch_last_entry():
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    c.execute('''
        SELECT * FROM appointments ORDER BY id DESC LIMIT 1
    ''')
    row = c.fetchone()
    conn.close()
    return row

def insert_data(appointment_date, server_response_time, num_appointments=None):
    conn = sqlite3.connect('appointments.db')
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
    c.execute('''
        INSERT INTO appointments (timestamp, appointment_date, num_appointments, server_response_time)
        VALUES (?, ?, ?, ?)
    ''', (now, appointment_date, num_appointments, server_response_time))
    conn.commit()
    conn.close()


init_db()

with sync_playwright() as p:
    ua = UserAgent()
    random_ua = ua.chrome
    session_id = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    proxy_auth = f"brd-customer-{USER_ID}-zone-datacenter_proxy-session-{session_id}:{PASSWORD}"
    
    # browser = p.chromium.launch(
    #     headless = not DEBUG,
    #     proxy={
    #         'server': f'http://{PROXY_URL}',
    #         'username': proxy_auth.split(":")[0],
    #         'password': PASSWORD
    #     }, 
    #     args=[f'--user-agent={random_ua}']
    # )

    context = p.chromium.launch_persistent_context(
        user_data_dir='./chrome_cache',  # Path where browser data will be stored
         headless = not DEBUG,
        proxy={
            'server': f'http://{PROXY_URL}',
            'username': proxy_auth.split(":")[0],
            'password': PASSWORD
        }, 
        args=[f'--user-agent={random_ua}']
    )

    # context = browser.new_context(cache_path='chrome_cache')
    page = context.new_page()    
    # page = browser.new_page()
    start_time = time.time()
    
    try:
        page.goto(SITE_URL)
        cita_link = page.wait_for_selector(CITA_LINK_SELECTOR)
        cita_link.click()
        
        inscripcion_link = page.wait_for_selector(f"a:visible:text-is('{INSCRIPCION_LINK_TEXT}')", timeout=20000)
        time.sleep(random.uniform(1, 2))
        inscripcion_link.click()
                
        date_element = page.wait_for_selector(DATE_ELEMENT_SELECTOR, timeout=10000)
        date_text = date_element.inner_text()
        print("Extracted Date:", date_text)
        date_obj = dateparser.parse(date_text, languages=['es'])

        new_appointment_date = date_obj.strftime('%Y-%m-%d')
        new_server_response_time = time.time() - start_time
        last_entry = fetch_last_entry()
        if last_entry is None or last_entry[2] != new_appointment_date:
            send_telegram_message(f'Próxima cita: {date_text}')            
        insert_data(new_appointment_date, new_server_response_time)
        if DEBUG:
            page.pause()
            time.sleep(1000)


    except Exception as e:
        print(f"Error: {e}")
    finally:
        page.close()
        context.close()
        # browser.close()


    
