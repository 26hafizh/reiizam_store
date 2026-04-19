import re

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add TypeHandler to imports
content = re.sub(
    r'(from telegram\.ext import \()',
    r'\1\n    TypeHandler,',
    content
)

# 2. Replace the data loading section
data_load_section_start = content.find('# =========================================================\n# DATA PRODUK')
data_load_section_end = content.find('# =========================================================\n# SESSION STATE')

new_data_load_section = """# =========================================================
# DATA PRODUK - Loaded from admin/products.json
# =========================================================
import json

LAST_CONFIG_MTIME = 0.0
LAST_PRODUCTS_MTIME = 0.0

PRODUCTS = {}
CATEGORY_LOGOS = {}
ITEM_LOOKUP = {}
ITEM_ALIASES = {}

def load_products():
    products_path = BASE_DIR / 'admin' / 'products.json'
    if products_path.exists():
        try:
            with open(products_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning('Failed to load products.json: %s', e)
    return {}

def load_config():
    global STORE_NAME, WA_NUMBER, RESTART_DELAY_SECONDS, IDLE_RESET_SECONDS
    config_path = BASE_DIR / 'admin' / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                STORE_NAME = data.get('STORE_NAME', STORE_NAME)
                WA_NUMBER = data.get('WA_NUMBER', WA_NUMBER)
                RESTART_DELAY_SECONDS = max(int(data.get('RESTART_DELAY_SECONDS', RESTART_DELAY_SECONDS)), 1)
                IDLE_RESET_SECONDS = max(int(data.get('IDLE_RESET_SECONDS', IDLE_RESET_SECONDS)), 60)
        except Exception as e:
            logger.warning('Failed to load config.json: %s', e)

def reload_data_if_needed():
    global LAST_CONFIG_MTIME, LAST_PRODUCTS_MTIME
    global PRODUCTS, CATEGORY_LOGOS, ITEM_LOOKUP, ITEM_ALIASES
    
    config_path = BASE_DIR / 'admin' / 'config.json'
    products_path = BASE_DIR / 'admin' / 'products.json'
    
    config_mtime = config_path.stat().st_mtime if config_path.exists() else 0.0
    products_mtime = products_path.stat().st_mtime if products_path.exists() else 0.0
    
    needs_reload = False
    if config_mtime != LAST_CONFIG_MTIME:
        LAST_CONFIG_MTIME = config_mtime
        load_config()
        needs_reload = True
        
    if products_mtime != LAST_PRODUCTS_MTIME:
        LAST_PRODUCTS_MTIME = products_mtime
        PRODUCTS = load_products()
        
        # Rebuild logos
        CATEGORY_LOGOS.clear()
        for cat_key, cat_data in PRODUCTS.items():
            if logo_rel := cat_data.get('logo', ''):
                CATEGORY_LOGOS[cat_key] = BASE_DIR / logo_rel

        # Rebuild lookups
        ITEM_LOOKUP.clear()
        ITEM_ALIASES.clear()
        for category_key, category_data in PRODUCTS.items():
            for item in category_data.get('items', []):
                item_data = {
                    'category_key': category_key,
                    'category_title': category_data.get('title', ''),
                    'category_icon': category_data.get('icon', ''),
                    **item,
                }
                ITEM_LOOKUP[item['id']] = item_data
                aliases = {
                    normalize_text(item['id']),
                    normalize_text(f"{category_data.get('title', '')} {item['name']}"),
                    normalize_text(f"{category_data.get('title', '')} {item['name']} {item.get('duration', '')}"),
                    normalize_text(f"{item['name']} {item.get('duration', '')}"),
                }
                plain_name = normalize_text(item['name'])
                if plain_name not in GENERIC_ITEM_ALIASES:
                    aliases.add(plain_name)
                ITEM_ALIASES[item['id']] = aliases
                
        needs_reload = True
        
    if needs_reload:
        main_menu_keyboard.cache_clear()
        category_menu_keyboard.cache_clear()
        netflix_choice_keyboard.cache_clear()
        item_menu_keyboard.cache_clear()
        order_keyboard.cache_clear()
        welcome_text.cache_clear()
        catalog_intro_text.cache_clear()
        help_text.cache_clear()
        netflix_prompt_text.cache_clear()
        format_category_text.cache_clear()
        format_item_text.cache_clear()
        idle_reset_text.cache_clear()

BOT_COMMANDS = [
    ('start', 'Buka menu utama'),
    ('menu', 'Tampilkan menu'),
    ('produk', 'Lihat katalog produk'),
    ('help', 'Cara pakai bot'),
]

CATEGORY_ALIASES = {
    'canva': ['canva'],
    'chatgpt': ['chatgpt', 'chat gpt', 'gpt', 'openai'],
    'youtube': ['youtube', 'youtube premium', 'yt'],
    'netflix_harian': ['netflix harian', 'netflix daily', 'harian netflix'],
    'netflix_bulanan': ['netflix bulanan', 'netflix monthly', 'bulanan netflix'],
    'apple_music': ['apple music', 'music apple'],
    'alight_motion': ['alight motion', 'alight'],
    'wink': ['wink'],
    'capcut': ['capcut', 'cap cut'],
    'getcontact': ['getcontact', 'get contact'],
    'zoom': ['zoom'],
    'spotify': ['spotify', 'spoti'],
    'duolingo': ['duolingo', 'duo lingo'],
    'google_drive': ['google drive', 'gdrive', 'drive google'],
}

GENERIC_ITEM_ALIASES = {
    'owner',
    'member pro',
    'private',
    'head',
    'famplan',
    'indplan',
    'student',
    'sharing',
    'jaspay',
}

def normalize_text(text: str) -> str:
    return ' '.join(''.join(ch.lower() if ch.isalnum() else ' ' for ch in text).split())

def matches_alias(normalized_text: str, alias: str) -> bool:
    alias = normalize_text(alias)
    return bool(alias and ((' ' in alias and alias in normalized_text) or alias in normalized_text.split()))

# Initial load
reload_data_if_needed()


"""

content = content[:data_load_section_start] + new_data_load_section + content[data_load_section_end:]

# 3. Add middleware before error_handler
middleware_code = """
async def reload_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reload_data_if_needed()

"""
content = content.replace("async def error_handler(", middleware_code + "async def error_handler(")

# 4. Register TypeHandler
register_code = """def register_handlers(app: Application) -> None:
    app.add_handler(TypeHandler(Update, reload_middleware), group=-1)"""
content = content.replace("def register_handlers(app: Application) -> None:", register_code)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied.")
