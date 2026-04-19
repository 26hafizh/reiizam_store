import re

with open('bot_core.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add imports at top
imports = """
import shared_data
from shared_data import PRODUCTS, CONFIG, ITEM_LOOKUP, ITEM_ALIASES, GENERIC_ITEM_ALIASES, on_data_change_callbacks

def STORE_NAME(): return shared_data.CONFIG.get('STORE_NAME', 'Store')
def WA_NUMBER(): return shared_data.CONFIG.get('WA_NUMBER', '62882000414738')
def IDLE_RESET_SECONDS(): return int(shared_data.CONFIG.get('IDLE_RESET_SECONDS', 900))
"""
content = content.replace("import base64\n", "import base64\n" + imports)

# 2. Remove the config block from load_local_env down to load_products
# We can just remove lines from "def load_local_env" down to "needs_reload = True"
# But regex is easier
content = re.sub(r'def load_local_env\(\).*?if needs_reload:\n', '', content, flags=re.DOTALL)
content = re.sub(r'BOT_TOKEN = os\.getenv.*?MAX_TELEGRAM_CAPTION_LENGTH = 1024', "BOT_TOKEN = os.getenv('BOT_TOKEN')\nMAX_TELEGRAM_CAPTION_LENGTH = 1024", content, flags=re.DOTALL)
content = re.sub(r'LAST_CONFIG_MTIME = 0\.0.*?ITEM_ALIASES = \{\}', '', content, flags=re.DOTALL)

# 3. Replace STORE_NAME with STORE_NAME()
content = content.replace("STORE_NAME", "STORE_NAME()")
content = content.replace("WA_NUMBER", "WA_NUMBER()")
content = content.replace("IDLE_RESET_SECONDS", "IDLE_RESET_SECONDS()")
content = content.replace("STORE_NAME()()", "STORE_NAME()")
content = content.replace("WA_NUMBER()()", "WA_NUMBER()")
content = content.replace("IDLE_RESET_SECONDS()()", "IDLE_RESET_SECONDS()")

# 4. Remove main loop and add clear_caches
main_idx = content.find("def main() -> None:")
if main_idx != -1:
    content = content[:main_idx]

content += """
def clear_caches():
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

on_data_change_callbacks.append(clear_caches)

def get_application():
    app = build_application()
    register_handlers(app)
    return app
"""

with open('bot_core.py', 'w', encoding='utf-8') as f:
    f.write(content)
