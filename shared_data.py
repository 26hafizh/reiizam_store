import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

PRODUCTS_PATH = DATA_DIR / 'products.json'
CONFIG_PATH = DATA_DIR / 'config.json'

# Global State
PRODUCTS = {}
CONFIG = {
    'STORE_NAME': 'Store',
    'WA_NUMBER': '628xxx',
    'RESTART_DELAY_SECONDS': 2,
    'IDLE_RESET_SECONDS': 300,
    'ADMIN_USER': 'admin',
    'ADMIN_PASS': 'admin'
}
ITEM_LOOKUP = {}
ITEM_ALIASES = {}
GENERIC_ITEM_ALIASES = {
    'sharing', 'private', 'jaspay', 'indplan', 'famplan',
    'head', 'member pro', 'owner'
}

# Callbacks to trigger when data changes
on_data_change_callbacks = []

def normalize_text(text: str) -> str:
    """Normalize text for matching (lowercase, no extra spaces)"""
    return ' '.join(text.lower().strip().split())

def load_all_data():
    global PRODUCTS, CONFIG
    
    # Load Config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                CONFIG.update(loaded_config)
                logger.info('Config loaded from %s', CONFIG_PATH)
        except Exception as e:
            logger.error('Failed to load config.json: %s', e)
    else:
        logger.warning('config.json not found, using defaults.')
        save_config(CONFIG) # Create default
        
    # Load Products
    if PRODUCTS_PATH.exists():
        try:
            with open(PRODUCTS_PATH, 'r', encoding='utf-8') as f:
                loaded_products = json.load(f)
                PRODUCTS.clear()
                PRODUCTS.update(loaded_products)
                logger.info('Successfully loaded %d categories from products.json', len(PRODUCTS))
        except Exception as e:
            logger.error('Failed to load products.json: %s', e)
    else:
        logger.warning('products.json not found.')
        PRODUCTS.clear()
        save_products(PRODUCTS) # Create empty

    rebuild_lookups()

def rebuild_lookups():
    global ITEM_LOOKUP, ITEM_ALIASES
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
            
            # Build aliases
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
            
    logger.info('Lookups rebuilt: %d items.', len(ITEM_LOOKUP))

def save_products(products_data):
    PRODUCTS.clear()
    PRODUCTS.update(products_data)
    with open(PRODUCTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(PRODUCTS, f, indent=2, ensure_ascii=False)
    
    rebuild_lookups()
    
    # Notify listeners (e.g. clear bot caches)
    for cb in on_data_change_callbacks:
        cb()

def save_config(config_data):
    CONFIG.update(config_data)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(CONFIG, f, indent=2, ensure_ascii=False)

