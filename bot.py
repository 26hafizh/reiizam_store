from __future__ import annotations


import asyncio
import logging
import os
import time
from contextlib import suppress
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import quote
from io import BytesIO
import base64

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    TypeHandler,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================================================
# KONFIGURASI
# =========================================================


def load_local_env() -> None:
    env_candidates = [
        Path('.env'),
        Path(__file__).resolve().with_name('.env'),
    ]

    for env_path in env_candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        return


load_local_env()


def get_int_env(name: str, default: int) -> int:
    raw_value = (os.getenv(name, str(default)) or str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        logging.getLogger(__name__).warning(
            'Nilai %s=%r tidak valid. Menggunakan default %s.',
            name,
            raw_value,
            default,
        )
        return default


BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
WA_NUMBER = os.getenv('WA_NUMBER', '62882000414738').strip()
STORE_NAME = os.getenv('STORE_NAME', 'reiizam store').strip()
RESTART_DELAY_SECONDS = max(get_int_env('RESTART_DELAY_SECONDS', 5), 1)
IDLE_RESET_SECONDS = max(get_int_env('IDLE_RESET_SECONDS', 900), 60)

UI_FEEDBACK_DELAY = 0.28
DOUBLE_CLICK_GUARD_SECONDS = 1.2
MAX_TELEGRAM_CAPTION_LENGTH = 1024

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

BASE_DIR = Path(__file__).resolve().parent
LOGO_DIR = BASE_DIR / 'assets' / 'logos'
CATEGORY_LOGOS = {
    'canva': LOGO_DIR / 'canva.jpg',
    'chatgpt': LOGO_DIR / 'chatgpt.jpg',
    'youtube': LOGO_DIR / 'youtube.jpg',
    'netflix_harian': LOGO_DIR / 'netflix.jpg',
    'netflix_bulanan': LOGO_DIR / 'netflix.jpg',
    'apple_music': LOGO_DIR / 'apple_music.jpg',
    'alight_motion': LOGO_DIR / 'alight_motion.jpg',
    'wink': LOGO_DIR / 'wink.jpg',
}

# =========================================================
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
                logger.info('Successfully loaded %d categories from products.json', len(data))
                return data
        except Exception as e:
            logger.error('Failed to load products.json: %s', e)
    else:
        logger.warning('products.json not found at %s', products_path)
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
            logo_val = cat_data.get('logo', '')
            if not logo_val:
                continue
                
            if logo_val.startswith('data:image/'):
                # Base64 logo
                try:
                    header, encoded = logo_val.split(',', 1)
                    CATEGORY_LOGOS[cat_key] = BytesIO(base64.b64decode(encoded))
                except Exception as e:
                    logger.warning('Failed to decode base64 logo for %s: %s', cat_key, e)
            else:
                # File path logo
                path = BASE_DIR / logo_val
                if path.exists():
                    CATEGORY_LOGOS[cat_key] = path

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
        
        logger.info('Data reloaded: %d items in %d categories.', len(ITEM_LOOKUP), len(PRODUCTS))
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




# =========================================================
# SESSION STATE
# =========================================================

SESSION_STORE_KEY = 'session_states'


def build_session_key(chat_id: int, user_id: int | None = None) -> str:
    if user_id is None:
        return f'chat:{chat_id}'
    return f'chat:{chat_id}:user:{user_id}'


def get_chat_state(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int | None = None,
) -> dict:
    session_store = context.application.bot_data.setdefault(SESSION_STORE_KEY, {})
    session_key = build_session_key(chat_id, user_id)
    return session_store.setdefault(session_key, {})


def reset_chat_state(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int | None = None,
) -> None:
    get_chat_state(context, chat_id, user_id).clear()


def touch_chat(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int | None = None,
) -> None:
    get_chat_state(context, chat_id, user_id)['last_seen'] = time.time()


def is_chat_idle(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int | None = None,
) -> bool:
    chat_state = get_chat_state(context, chat_id, user_id)
    last_seen = float(chat_state.get('last_seen', 0.0) or 0.0)
    now = time.time()
    chat_state['last_seen'] = now
    if not last_seen:
        return False
    return (now - last_seen) >= IDLE_RESET_SECONDS


def get_logo_data(category_key: str):
    logo_data = CATEGORY_LOGOS.get(category_key)
    if isinstance(logo_data, Path):
        return logo_data if logo_data.exists() else None
    return logo_data  # Could be BytesIO or None


async def clear_logo_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int | None = None,
) -> None:
    chat_state = get_chat_state(context, chat_id, user_id)
    chat_state.pop('logo_message_id', None)
    chat_state.pop('logo_category_key', None)


async def ensure_logo_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    category_key: str,
    user_id: int | None = None,
) -> None:
    chat_state = get_chat_state(context, chat_id, user_id)
    if get_logo_data(category_key):
        chat_state['logo_category_key'] = category_key
        return
    chat_state.pop('logo_category_key', None)


# =========================================================
# UI HELPERS
# =========================================================


def build_admin_url(message: str | None = None) -> str:
    if not message:
        return f'https://wa.me/{WA_NUMBER}'
    return f'https://wa.me/{WA_NUMBER}?text={quote(message)}'


def build_order_message(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    return (
        'Hallo min, saya mau order.\n'
        f"*{item['name']}* - *{item['duration']}* - *{item['price']}*\n"
        'Apakah Stok Ready?😁.'
    )


def chunk_buttons(buttons: list[InlineKeyboardButton], size: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + size] for index in range(0, len(buttons), size)]


@lru_cache(maxsize=1)
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('🛍️ List Product', callback_data='lihat_kategori')],
            [InlineKeyboardButton('📌 Cara Order Cepat', callback_data='bantuan')],
        ]
    )


@lru_cache(maxsize=1)
def category_menu_keyboard() -> InlineKeyboardMarkup:
    category_buttons = [
        InlineKeyboardButton(f"{data['icon']} {data['title']}", callback_data=f'cat_{key}')
        for key, data in PRODUCTS.items()
    ]
    rows = chunk_buttons(category_buttons, 2)
    rows.append([InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')])
    return InlineKeyboardMarkup(rows)


@lru_cache(maxsize=1)
def netflix_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('📺 Netflix Harian', callback_data='cat_netflix_harian'),
                InlineKeyboardButton('🎬 Netflix Bulanan', callback_data='cat_netflix_bulanan'),
            ],
            [InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')],
        ]
    )


@lru_cache(maxsize=None)
def item_menu_keyboard(category_key: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in PRODUCTS[category_key]['items']:
        label = f"{item['name']} | {item['price']}"
        if len(label) > 38:
            label = f"{item['duration']} | {item['price']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"item_{item['id']}")])

    rows.extend([
        [InlineKeyboardButton('⬅️ Kembali ke Kategori', callback_data='lihat_kategori')],
        [InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')],
    ])
    return InlineKeyboardMarkup(rows)


@lru_cache(maxsize=None)
def order_keyboard(item_id: str) -> InlineKeyboardMarkup:
    item = ITEM_LOOKUP[item_id]
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('✅ Order via WhatsApp', url=build_admin_url(build_order_message(item_id)))],
            [InlineKeyboardButton('⬅️ Kembali', callback_data=f"cat_{item['category_key']}")],
            [InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')],
        ]
    )


@lru_cache(maxsize=1)
def welcome_text() -> str:
    catalog_items = [data['title'] for data in PRODUCTS.values()][:12]
    if not catalog_items:
        catalog_items = ['Belum ada produk']

    catalog_box = make_text_box(
        [
            'Pilih produk yang kamu cari di bawah ini.',
            '',
            *[f"• {item}" for item in catalog_items],
        ],
        title='KATALOG AKTIF',
    )

    benefit_box = make_text_box(['• Proses Cepat', '• Aman & Legal', '• Garansi Full'], title='KEUNGGULAN')

    return (
        f"<b>♛ {escape(STORE_NAME.upper())} ♛</b>\n"
        '<i>Solusi Premium Apps Murah & Terpercaya.</i>\n\n'
        f"<code>{escape(catalog_box)}</code>\n\n"
        f"<code>{escape(benefit_box)}</code>\n\n"
        '<b>Klik tombol di bawah untuk melihat list lengkap!</b>'
    )


@lru_cache(maxsize=1)
def catalog_intro_text() -> str:
    flow_box = make_text_box([
        '1. Pilih kategori app',
        '2. Pilih paket yang cocok',
        '3. Tekan tombol order',
        '4. Lanjut ke WhatsApp admin',
    ], title='Cara Order')

    return (
        '<b>🛍️ Katalog Produk</b>\n'
        '<i>Pilih app yang kamu butuhin, lalu lanjut ke detail paketnya.</i>\n\n'
        f"<code>{escape(flow_box)}</code>\n\n"
        '<i>Sok dipilih dulu aja ya bre.</i>'
    )


@lru_cache(maxsize=1)
def help_text() -> str:
    order_box = make_text_box([
        '1. Buka katalog',
        '2. Pilih kategori produk',
        '3. Pilih paket yang diinginkan',
        '4. Tekan tombol order ke WhatsApp',
    ], title='Cara Order Cepat')

    return (
        '<b>📌 INFO ORDER</b>\n'
        '<i>Biar cepat, alurnya tinggal begini.</i>\n\n'
        f"<code>{escape(order_box)}</code>\n\n"
        'Kalau udah nemu produk yang ingin dibeli,\n'
        'nanti langsung diarahkan ke WhatsApp admin ya bre.'
    )


@lru_cache(maxsize=1)
def netflix_prompt_text() -> str:
    return (
        '<b>📺 Netflix tersedia dalam dua pilihan</b>\n'
        '━━━━━━━━━━━━\n\n'
        'Pilih versi yang mau kamu lihat dulu:\n'
        '• Harian\n'
        '• Bulanan'
    )


def format_notes(title: str, notes: list[str]) -> list[str]:
    if not notes:
        return []

    lines = [f"<b>{escape(title)}</b>"]
    for note in notes:
        lines.append(f"• {escape(note)}")
    return lines + ['']


def wrap_box_line(text: str, max_width: int) -> list[str]:
    if not text:
        return [""]

    prefix = ""
    continuation_prefix = ""

    if text.startswith("• "):
        prefix = "• "
        continuation_prefix = "  "
    else:
        stripped = text.lstrip()
        leading_spaces = len(text) - len(stripped)
        if stripped and '.' in stripped:
            head, tail = stripped.split('.', 1)
            if head.isdigit() and tail.startswith(' '):
                prefix = (' ' * leading_spaces) + head + '. '
                continuation_prefix = ' ' * len(prefix)

    content = text[len(prefix):] if prefix else text
    words = content.split()
    if not words:
        return [prefix.rstrip() or ""]

    lines: list[str] = []
    current = prefix

    for word in words:
        spacer = "" if current.endswith(" ") or not current.strip() else " "
        trial = f"{current}{spacer}{word}"
        if len(trial) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            next_prefix = continuation_prefix if lines else prefix
            current = f"{next_prefix}{word}"

    if current:
        lines.append(current)

    return lines


def make_text_box(lines: list[str], title: str | None = None) -> str:
    content = [line.rstrip() for line in lines if line is not None]
    wrapped_content: list[str] = []
    for line in content:
        if line:
            wrapped_content.extend(wrap_box_line(line, 34))
        else:
            wrapped_content.append('')

    visible_lines = [line for line in wrapped_content if line]
    max_len = max((len(line) for line in visible_lines), default=0)
    width = max(26, min(max_len + 2, 34))

    def pad(line: str = '') -> str:
        return line + (' ' * max(width - len(line), 0))

    box_lines: list[str] = []
    if title:
        title_text = f' {title} '
        remain = max(width - len(title_text), 0)
        left = remain // 2
        right = remain - left
        box_lines.append(f"╭{'─' * left}{title_text}{'─' * right}╮")
    else:
        box_lines.append(f"╭{'─' * width}╮")

    for line in wrapped_content:
        if line:
            box_lines.append(f"│ {pad(line)} │")
        else:
            box_lines.append(f"│ {' ' * width} │")

    box_lines.append(f"╰{'─' * width}╯")
    return '\n'.join(box_lines)


@lru_cache(maxsize=None)
def format_category_text(category_key: str) -> str:
    data = PRODUCTS[category_key]
    sections = [
        f"<b>{escape(data['icon'])} {escape(data['title'].upper())}</b>",
        f"<i>{escape(data['description'])}</i>",
        '━━━━━━━━━━━━━━━',
        '',
    ]

    for item in data['items']:
        box = make_text_box([
            f"ID: {item['id'].upper()}",
            f"📦 {item['name']}",
            f"⏳ {item['duration']}",
            f"💰 {item['price']}",
        ])
        sections.append(f"<code>{escape(box)}</code>")
        sections.append('')

    sections.append('<i>Tap paket di tombol bawah untuk lanjut order.</i>')
    return '\n'.join(sections).strip()


@lru_cache(maxsize=None)
def format_item_text(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    category_data = PRODUCTS[item['category_key']]
    category_notes = category_data['category_notes']
    category_note_title = category_data.get('category_note_title', 'Catatan')

    summary_box = make_text_box([
        item['name'],
        '',
        f"Kategori : {item['category_title']}",
        f"Durasi   : {item['duration']}",
        f"Harga    : {item['price']}",
        f"Kode     : {item['id'].upper()}",
    ], title='Detail Paket')

    lines = [f"<code>{escape(summary_box)}</code>", '']

    if item['notes']:
        benefit_box = make_text_box([f"• {note}" for note in item['notes']], title='Highlight')
        lines.append(f"<code>{escape(benefit_box)}</code>")
        lines.append('')

    if category_notes:
        note_box = make_text_box([f"• {note}" for note in category_notes], title=category_note_title)
        lines.append(f"<code>{escape(note_box)}</code>")
        lines.append('')

    lines.append('<i>Tekan tombol order untuk mengirim format chat WhatsApp ke admin.</i>')
    return '\n'.join(lines).strip()


def fallback_text() -> str:
    return (
        f"<b>✦ {escape(STORE_NAME.upper())} ✦</b>\n\n"
        'Silakan mulai dari menu utama ya bre.\n'
        'Pilih kategori produk yang ingin kamu lihat di bawah ini.'
    )


@lru_cache(maxsize=1)
def idle_reset_text() -> str:
    minutes = max(IDLE_RESET_SECONDS // 60, 1)
    return (
        '<b>🔄 Sesi di-reset otomatis</b>\n'
        '━━━━━━━━━━━━\n\n'
        f'Chat sempat tidak aktif sekitar {minutes} menit, jadi bot balik ke menu utama dulu ya bre.'
    )


def is_duplicate_callback(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    data: str,
    message_id: int | None,
    user_id: int | None = None,
) -> bool:
    chat_state = get_chat_state(context, chat_id, user_id)
    now = time.time()
    callback_key = f'{message_id or 0}:{data}'
    last_data = str(chat_state.get('last_callback_data', '') or '')
    last_seen = float(chat_state.get('last_callback_at', 0.0) or 0.0)
    chat_state['last_callback_data'] = callback_key
    chat_state['last_callback_at'] = now
    return callback_key == last_data and (now - last_seen) < DOUBLE_CLICK_GUARD_SECONDS


def match_category_by_text(text: str) -> str | None:
    normalized = normalize_text(text)
    for category_key, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if matches_alias(normalized, alias):
                return category_key
    return None


def match_item_by_text(text: str) -> str | None:
    normalized = normalize_text(text)
    for item_id, aliases in ITEM_ALIASES.items():
        for alias in aliases:
            if alias and matches_alias(normalized, alias):
                return item_id
    return None


# =========================================================
# SEND / EDIT HELPERS
# =========================================================

def wants_main_menu_reset(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in {'start', 'menu'} or any(
        matches_alias(normalized, greeting)
        for greeting in ('halo', 'hai', 'hi', 'assalamualaikum')
    )


async def reply_html(
    message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    with_typing_feedback: bool = False,
    category_key: str | None = None,
) -> None:
    if with_typing_feedback:
        with suppress(Exception):
            await message.get_bot().send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
        await asyncio.sleep(UI_FEEDBACK_DELAY)

    await send_view_message(
        bot=message.get_bot(),
        chat_id=message.chat_id,
        text=text,
        reply_markup=reply_markup,
        category_key=category_key,
    )


async def send_main_menu(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = message.from_user.id if message.from_user else None
    reset_chat_state(context, message.chat_id, user_id)
    touch_chat(context, message.chat_id, user_id)
    await clear_logo_message(context, message.chat_id, user_id)
    await reply_html(message, welcome_text(), main_menu_keyboard(), with_typing_feedback=True)


async def send_catalog(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = message.from_user.id if message.from_user else None
    touch_chat(context, message.chat_id, user_id)
    await clear_logo_message(context, message.chat_id, user_id)
    await reply_html(message, catalog_intro_text(), category_menu_keyboard(), with_typing_feedback=True)


async def send_category(message, category_key: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = message.from_user.id if message.from_user else None
    touch_chat(context, message.chat_id, user_id)
    await reply_html(
        message,
        format_category_text(category_key),
        item_menu_keyboard(category_key),
        with_typing_feedback=True,
        category_key=category_key,
    )


async def send_item(message, item_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = message.from_user.id if message.from_user else None
    touch_chat(context, message.chat_id, user_id)
    await reply_html(
        message,
        format_item_text(item_id),
        order_keyboard(item_id),
        with_typing_feedback=True,
        category_key=ITEM_LOOKUP[item_id]['category_key'],
    )


async def send_view_message(
    bot,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    category_key: str | None = None,
) -> object:
    logo_data = get_logo_data(category_key) if category_key else None
    can_send_with_logo = bool(logo_data and len(text) <= MAX_TELEGRAM_CAPTION_LENGTH)

    if can_send_with_logo:
        try:
            # Handle both Path and BytesIO
            photo = logo_data
            if isinstance(logo_data, BytesIO):
                logo_data.seek(0)
            
            sent_message = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_notification=True,
            )
            logger.info('Logo kategori %s berhasil dikirim ke chat %s.', category_key, chat_id)
            return sent_message
        except Exception as e:
            logger.error('Gagal mengirim photo: %s', e)
            # Fallback to normal text message
            pass
        except Exception:
            logger.warning(
                'Gagal mengirim tampilan dengan logo untuk kategori %s. Fallback ke teks.',
                category_key,
                exc_info=True,
            )

    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_notification=True,
    )


async def try_edit_query_message(
    query,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    category_key: str | None = None,
    allow_photo_edit_in_place: bool = False,
) -> bool:
    message = query.message
    if not message:
        return False

    logo_data = get_logo_data(category_key) if category_key else None
    target_is_photo = bool(logo_data and len(text) <= MAX_TELEGRAM_CAPTION_LENGTH)
    current_is_photo = bool(getattr(message, 'photo', None))

    try:
        if current_is_photo and target_is_photo and allow_photo_edit_in_place:
            await query.edit_message_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            return True

        if not current_is_photo and not target_is_photo:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return True
    except BadRequest as exc:
        if 'message is not modified' in str(exc).lower():
            return True
        logger.warning('Gagal mengedit pesan callback secara in-place.', exc_info=True)
    except Exception:
        logger.warning('Gagal mengedit pesan callback secara in-place.', exc_info=True)

    return False


async def replace_query_message(
    query,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    category_key: str | None = None,
    allow_photo_edit_in_place: bool = False,
) -> None:
    message = query.message
    if not message:
        return

    if await try_edit_query_message(
        query,
        text,
        reply_markup=reply_markup,
        category_key=category_key,
        allow_photo_edit_in_place=allow_photo_edit_in_place,
    ):
        return

    await send_view_message(
        bot=message.get_bot(),
        chat_id=message.chat_id,
        text=text,
        reply_markup=reply_markup,
        category_key=category_key,
    )
    try:
        await message.delete()
    except BadRequest:
        return
    except Exception:
        logger.warning('Gagal menghapus pesan lama setelah mengganti tampilan.', exc_info=True)


async def answer_and_replace(
    query,
    answer_text: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    category_key: str | None = None,
    allow_photo_edit_in_place: bool = False,
) -> None:
    await query.answer(answer_text)
    await replace_query_message(
        query,
        text,
        reply_markup,
        category_key=category_key,
        allow_photo_edit_in_place=allow_photo_edit_in_place,
    )


# =========================================================
# HANDLERS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_main_menu(update.message, context)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_main_menu(update.message, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        user_id = update.message.from_user.id if update.message.from_user else None
        touch_chat(context, update.message.chat_id, user_id)
        await clear_logo_message(context, update.message.chat_id, user_id)
        await reply_html(update.message, help_text(), main_menu_keyboard(), with_typing_feedback=True)


async def produk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_catalog(update.message, context)


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    user_id = message.from_user.id if message.from_user else None
    normalized = normalize_text(message.text)

    if is_chat_idle(context, message.chat_id, user_id) and not wants_main_menu_reset(message.text):
        reset_chat_state(context, message.chat_id, user_id)
        touch_chat(context, message.chat_id, user_id)
        await clear_logo_message(context, message.chat_id, user_id)
        await reply_html(message, idle_reset_text(), main_menu_keyboard(), with_typing_feedback=True)
        return

    if not normalized:
        await clear_logo_message(context, message.chat_id, user_id)
        await reply_html(message, fallback_text(), main_menu_keyboard(), with_typing_feedback=True)
        return

    if wants_main_menu_reset(message.text):
        await send_main_menu(message, context)
        return

    if any(matches_alias(normalized, keyword) for keyword in ('produk', 'katalog', 'catalog', 'daftar', 'list')):
        await send_catalog(message, context)
        return

    if matches_alias(normalized, 'netflix') and not matches_alias(normalized, 'harian') and not matches_alias(normalized, 'bulanan'):
        touch_chat(context, message.chat_id, user_id)
        await reply_html(
            message,
            netflix_prompt_text(),
            netflix_choice_keyboard(),
            with_typing_feedback=True,
            category_key='netflix_harian',
        )
        return

    item_id = match_item_by_text(normalized)
    if item_id:
        await send_item(message, item_id, context)
        return

    category_key = match_category_by_text(normalized)
    if category_key:
        await send_category(message, category_key, context)
        return

    touch_chat(context, message.chat_id, user_id)
    await clear_logo_message(context, message.chat_id, user_id)
    await reply_html(message, fallback_text(), main_menu_keyboard(), with_typing_feedback=True)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        user_id = update.message.from_user.id if update.message.from_user else None
        touch_chat(context, update.message.chat_id, user_id)
        await clear_logo_message(context, update.message.chat_id, user_id)
        await reply_html(
            update.message,
            text='Perintah belum tersedia. Gunakan menu di bawah ya.',
            reply_markup=main_menu_keyboard(),
            with_typing_feedback=True,
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    message = query.message
    chat_id = message.chat_id if message else update.effective_chat.id if update.effective_chat else None
    user_id = update.effective_user.id if update.effective_user else None
    if chat_id is None:
        await query.answer('Chat tidak ditemukan.', show_alert=True)
        return

    if is_chat_idle(context, chat_id, user_id):
        reset_chat_state(context, chat_id, user_id)
        touch_chat(context, chat_id, user_id)
        await clear_logo_message(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Sesi lama di-reset.',
            idle_reset_text(),
            main_menu_keyboard(),
        )
        return

    data = query.data or ''
    if is_duplicate_callback(context, chat_id, data, message.message_id if message else None, user_id):
        await query.answer()
        return

    if data == 'menu':
        reset_chat_state(context, chat_id, user_id)
        touch_chat(context, chat_id, user_id)
        await clear_logo_message(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Membuka menu...',
            welcome_text(),
            main_menu_keyboard(),
        )
        return

    if data == 'lihat_kategori':
        touch_chat(context, chat_id, user_id)
        await clear_logo_message(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Menampilkan katalog...',
            catalog_intro_text(),
            category_menu_keyboard(),
        )
        return

    if data == 'bantuan':
        touch_chat(context, chat_id, user_id)
        await clear_logo_message(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Membuka info order...',
            help_text(),
            main_menu_keyboard(),
        )
        return

    if data.startswith('cat_'):
        category_key = data.replace('cat_', '', 1)
        if category_key not in PRODUCTS:
            await query.answer('Kategori tidak ditemukan.', show_alert=True)
            return

        touch_chat(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Membuka kategori...',
            format_category_text(category_key),
            item_menu_keyboard(category_key),
            category_key=category_key,
            allow_photo_edit_in_place=True,
        )
        return

    if data.startswith('item_'):
        item_id = data.replace('item_', '', 1)
        if item_id not in ITEM_LOOKUP:
            await query.answer('Paket tidak ditemukan.', show_alert=True)
            return

        touch_chat(context, chat_id, user_id)
        await answer_and_replace(
            query,
            'Menyiapkan detail paket...',
            format_item_text(item_id),
            order_keyboard(item_id),
            category_key=ITEM_LOOKUP[item_id]['category_key'],
            allow_photo_edit_in_place=True,
        )
        return

    await query.answer('Aksi tidak dikenali.', show_alert=True)



async def reload_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reload_data_if_needed()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception('Unhandled error while processing update', exc_info=context.error)

    if isinstance(update, Update) and update.message:
        with suppress(Exception):
            await update.message.reply_text(
                text='Maaf, bot sedang mengalami gangguan sementara. Silakan coba lagi sebentar ya.',
                reply_markup=main_menu_keyboard(),
            )


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(BOT_COMMANDS)
        logger.info('Bot commands registered.')
    except Exception:
        logger.exception('Gagal set bot commands. Bot tetap dilanjutkan agar tetap online.')


def register_handlers(app: Application) -> None:
    app.add_handler(TypeHandler(Update, reload_middleware), group=-1)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('menu', menu_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('produk', produk_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_error_handler(error_handler)


def build_application() -> Application:
    return (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .http_version('1.1')
        .get_updates_http_version('1.1')
        .concurrent_updates(32)
        .connection_pool_size(64)
        .pool_timeout(10)
        .connect_timeout(10)
        .read_timeout(10)
        .write_timeout(10)
        .get_updates_connect_timeout(10)
        .get_updates_read_timeout(10)
        .get_updates_write_timeout(10)
        .get_updates_pool_timeout(10)
        .post_init(post_init)
        .build()
    )


def run_bot() -> None:
    app = build_application()
    register_handlers(app)
    app.run_polling(
        poll_interval=0.0,
        timeout=10,
        bootstrap_retries=-1,
        drop_pending_updates=True,
    )


def main() -> None:
    reload_data_if_needed()
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN belum diisi. Tambahkan BOT_TOKEN di environment variable atau file .env.')

    while True:
        try:
            logger.info('Starting bot for store: %s', STORE_NAME)
            run_bot()
            logger.warning(
                'Polling loop berhenti. Mencoba menjalankan ulang dalam %s detik.',
                RESTART_DELAY_SECONDS,
            )
        except (KeyboardInterrupt, SystemExit):
            logger.info('Bot dihentikan secara manual.')
            break
        except Exception:
            logger.exception('Bot crash. Mencoba restart ulang dalam %s detik.', RESTART_DELAY_SECONDS)

        time.sleep(RESTART_DELAY_SECONDS)


if __name__ == '__main__':
    main()
