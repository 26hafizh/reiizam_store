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

import shared_data
from shared_data import PRODUCTS, CONFIG, ITEM_LOOKUP, ITEM_ALIASES, GENERIC_ITEM_ALIASES, on_data_change_callbacks

def STORE_NAME(): return shared_data.CONFIG.get('STORE_NAME', 'Store')
def WA_NUMBER(): return shared_data.CONFIG.get('WA_NUMBER', '62882000414738')
def IDLE_RESET_SECONDS(): return int(shared_data.CONFIG.get('IDLE_RESET_SECONDS', 900))

BOT_TOKEN = os.getenv('BOT_TOKEN')
MAX_TELEGRAM_CAPTION_LENGTH = 1024

# =========================================================
# LOGGING
# =========================================================

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

UI_FEEDBACK_DELAY = 0.28
DOUBLE_CLICK_GUARD_SECONDS = 1.2

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
    return (now - last_seen) >= IDLE_RESET_SECONDS()


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
    wa = WA_NUMBER()
    if not message:
        return f'https://wa.me/{wa}'
    return f'https://wa.me/{wa}?text={quote(message)}'


def build_order_message(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    store = STORE_NAME()
    return (
        f"🚀 *FORM ORDER - {store.upper()}*\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Halo Admin, saya ingin memesan paket berikut:\n\n"
        f"📂 *Kategori:* {item['category_title']}\n"
        f"📦 *Produk:* {item['name']}\n"
        f"⏳ *Durasi:* {item['duration']}\n"
        f"💰 *Harga:* {item['price']}\n"
        f"🔑 *Kode:* {item['id'].upper()}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Apakah stok ready min? Mohon infonya ya, terima kasih! 🙏"
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
    catalog_items = [(data['icon'], data['title']) for data in PRODUCTS.values()][:12]
    store = STORE_NAME()
    
    lines = [
        f"<b>✨ WELCOME TO {escape(store.upper())} ✨</b>",
        "<i>Penyedia Layanan Premium Terlengkap & Terjangkau.</i>",
        "",
        "<b>💎 KATALOG PRODUK KAMI</b>",
    ]
    
    if not catalog_items:
        lines.append("<i>  • Belum ada produk tersedia</i>")
    else:
        for icon, title in catalog_items:
            lines.append(f"  {icon} {escape(title)}")
            
    lines += [
        "",
        "<b>🚀 KEUNGGULAN KAMI:</b>",
        "⚡ <i>Proses Kilat</i>",
        "🛡️ <i>Legal & Bergaransi</i>",
        "💰 <i>Harga Termurah</i>",
        "",
        "<b>Silakan pilih menu di bawah untuk mulai order!</b>"
    ]
    return '\n'.join(lines)


@lru_cache(maxsize=1)
def catalog_intro_text() -> str:
    return (
        '<b>🛍️ Pilih Kategori Produk</b>\n'
        '<i>Temukan app premium yang kamu butuhin di sini.</i>\n'
        '\n'
        '┌──────── Cara Order ─────────┐\n'
        '│  1. Pilih kategori app      │\n'
        '│  2. Pilih paket yang cocok  │\n'
        '│  3. Tekan tombol order      │\n'
        '│  4. Lanjut ke WhatsApp      │\n'
        '└─────────────────────────────┘\n'
        '\n'
        '<i>👇 Silakan pilih kategori di bawah ini:</i>'
    )


@lru_cache(maxsize=1)
def help_text() -> str:
    return (
        '<b>📌 Cara Order</b>\n'
        '\n'
        '┌──────────────────────────────────┐\n'
        '│  1. Buka katalog produk          │\n'
        '│  2. Pilih kategori               │\n'
        '│  3. Pilih paket yang diinginkan  │\n'
        '│  4. Tap tombol Order WhatsApp    │\n'
        '└──────────────────────────────────┘\n'
        '\n'
        '<i>Setelah tap order, kamu akan diarahkan ke WhatsApp admin secara otomatis.</i>'
    )


@lru_cache(maxsize=1)
def netflix_prompt_text() -> str:
    return (
        '<b>🎬 Netflix — Pilih Jenis Paket</b>\n'
        '<i>Tersedia dua pilihan, sesuaikan dengan kebutuhanmu.</i>\n'
        '\n'
        '🎟️  <b>Harian</b>  — Fleksibel, bayar per hari\n'
        '📆  <b>Bulanan</b> — Lebih hemat, aktif 1 bulan\n'
        '\n'
        '<i>👇 Pilih di bawah:</i>'
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
    icon = data['icon']
    title = data['title'].upper()
    desc = data['description']
    items = data['items']

    lines = [
        f"<b>{escape(icon)} {escape(title)} KATEGORI</b>",
        f"<i>\"{escape(desc)}\"</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for item in items:
        lines += [
            f"📦 <b>{escape(item['name'])}</b>",
            f"├ ⏳ Durasi: <code>{escape(item['duration'])}</code>",
            f"└ 💰 Harga: <b>{escape(item['price'])}</b>",
            "",
        ]

    lines.append("<i>👇 Pilih paket di bawah untuk detail & order:</i>")
    return '\n'.join(lines).strip()


@lru_cache(maxsize=None)
def format_item_text(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    category_data  = PRODUCTS[item['category_key']]
    category_notes = category_data.get('category_notes', [])
    category_note_title = category_data.get('category_note_title', 'INFORMASI')

    lines = [
        f"<b>📋 DETAIL PESANAN</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📂 <b>Kategori:</b> {escape(item['category_title'])}",
        f"📦 <b>Produk:</b> {escape(item['name'])}",
        f"⏳ <b>Durasi:</b> {escape(item['duration'])}",
        f"💰 <b>Harga:</b> <b>{escape(item['price'])}</b>",
        f"🔑 <b>Kode:</b> <code>{item['id'].upper()}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if item.get('notes'):
        lines.append("<b>✨ HIGHLIGHT:</b>")
        for note in item['notes']:
            lines.append(f"• <i>{escape(note)}</i>")
        lines.append("")

    if category_notes:
        lines.append(f"<b>⚠️ {escape(category_note_title).upper()}:</b>")
        for note in category_notes:
            lines.append(f"• <i>{escape(note)}</i>")
        lines.append("")

    lines.append("<i>✅ Tap tombol di bawah untuk kirim format order ke WhatsApp.</i>")
    return '\n'.join(lines).strip()


def fallback_text() -> str:
    store = STORE_NAME()
    return (
        f'<b>♛ {escape(store.upper())} ♛</b>\n\n'
        'Silakan mulai dari menu utama ya.\n'
        'Pilih kategori produk yang ingin kamu lihat di bawah ini.'
    )


@lru_cache(maxsize=1)
def idle_reset_text() -> str:
    minutes = max(IDLE_RESET_SECONDS() // 60, 1)
    return (
        '<b>⏰ Sesi Kamu Habis</b>\n'
        f'<i>Bot kembali ke menu utama karena tidak ada aktivitas selama {minutes} menit.</i>\n'
        '\n'
        '👇 Silakan mulai lagi dari bawah ya.'
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
