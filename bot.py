from __future__ import annotations

import logging
import os
import time
from contextlib import suppress
from html import escape
from pathlib import Path
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
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
WA_NUMBER = os.getenv('WA_NUMBER', '6285126019233').strip()
STORE_NAME = os.getenv('STORE_NAME', 'reiizam store').strip()
RESTART_DELAY_SECONDS = max(get_int_env('RESTART_DELAY_SECONDS', 5), 1)
IDLE_RESET_SECONDS = max(get_int_env('IDLE_RESET_SECONDS', 900), 60)

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================================================
# DATA PRODUK
# =========================================================
PRODUCTS = {
    'canva': {
        'title': 'Canva',
        'icon': '🎨',
        'description': 'Paket desain untuk kebutuhan konten, branding, dan editing harian.',
        'items': [
            {'id': 'canva_01', 'name': 'Member Pro', 'duration': '1 bulan', 'price': 'Rp5.000', 'notes': []},
            {'id': 'canva_02', 'name': 'Member Pro', 'duration': '2 bulan', 'price': 'Rp10.000', 'notes': []},
            {'id': 'canva_03', 'name': 'Owner', 'duration': '1 bulan', 'price': 'Rp25.000', 'notes': []},
        ],
        'category_notes': [],
    },
    'chatgpt': {
        'title': 'ChatGPT',
        'icon': '🤖',
        'description': 'Pilihan paket AI premium untuk kebutuhan chat, ide, dan produktivitas.',
        'items': [
            {
                'id': 'chatgpt_01',
                'name': 'ChatGPT Priv Invite',
                'duration': '1 bulan',
                'price': 'Rp15.000',
                'notes': ['Strong akun', 'Invite pakai email buyer', 'Full garansi'],
            },
            {
                'id': 'chatgpt_02',
                'name': 'ChatGPT Plus Private',
                'duration': '1 bulan',
                'price': 'Rp20.000',
                'notes': [
                    'Akun seller',
                    'Full garansi',
                    'Full garansi jika patuhi S&K',
                    'Owner akun dari seller',
                    'Owner bisa invite 100 member',
                ],
            },
        ],
        'category_notes': [
            '25 - 30 hari dihitung 1 bulan',
            'No rush',
            'Wajib tanyakan stok ke admin',
            'Max invite dibatasi untuk menghindari over seat yang mengakibatkan akun deactivated',
            'Semua transaksi no refund kecuali kesalahan admin',
        ],
    },
    'youtube': {
        'title': 'YouTube',
        'icon': '▶️',
        'description': 'Paket YouTube premium untuk nonton tanpa iklan dengan harga ringan.',
        'items': [
            {'id': 'youtube_01', 'name': 'Famplan (Invite)', 'duration': '1 bulan', 'price': 'Rp4.000', 'notes': []},
            {'id': 'youtube_02', 'name': 'Indplan', 'duration': '1 bulan', 'price': 'Rp7.000', 'notes': []},
            {'id': 'youtube_03', 'name': 'Famhead', 'duration': '1 bulan', 'price': 'Rp10.000', 'notes': ['Bisa invite 5 orang']},
        ],
        'category_notes': [],
    },
    'netflix_harian': {
        'title': 'Netflix Harian',
        'icon': '📺',
        'description': 'Pilihan harian untuk kebutuhan nonton cepat dan fleksibel.',
        'items': [
            {'id': 'neth_01', 'name': '1 Hari 2 User', 'duration': '1 hari', 'price': 'Rp3.000', 'notes': []},
            {'id': 'neth_02', 'name': '1 Hari 1 User', 'duration': '1 hari', 'price': 'Rp5.000', 'notes': []},
            {'id': 'neth_03', 'name': '7 Hari 2 User', 'duration': '7 hari', 'price': 'Rp9.000', 'notes': []},
            {'id': 'neth_04', 'name': '7 Hari 1 User', 'duration': '7 hari', 'price': 'Rp10.000', 'notes': []},
            {'id': 'neth_05', 'name': '7 Hari Semi Private', 'duration': '7 hari', 'price': 'Rp12.000', 'notes': []},
        ],
        'category_notes': [],
    },
    'netflix_bulanan': {
        'title': 'Netflix Bulanan',
        'icon': '🎬',
        'description': 'Paket bulanan buat yang ingin pengalaman nonton lebih nyaman.',
        'items': [
            {
                'id': 'netb_01',
                'name': 'Netflix Semi Private',
                'duration': '1 bulan',
                'price': 'Rp27.000',
                'notes': ['Bisa login 2 device', 'Tidak bisa nonton secara bersamaan'],
            },
            {
                'id': 'netb_02',
                'name': 'Netflix Sultan VIP',
                'duration': '1 bulan',
                'price': 'Rp35.000',
                'notes': [
                    'Jatah 1 profil',
                    'Bisa login 2 device',
                    'Bisa nonton secara bersamaan',
                    'Garansi anti limit',
                ],
            },
        ],
        'category_notes': [],
    },
    'apple_music': {
        'title': 'Apple Music',
        'icon': '🎵',
        'description': 'Paket musik premium untuk pengalaman dengar yang lebih nyaman.',
        'items': [
            {'id': 'apple_01', 'name': 'Famplan', 'duration': '1 bulan', 'price': 'Rp10.000', 'notes': []},
            {'id': 'apple_02', 'name': 'Indplan', 'duration': '1 bulan', 'price': 'Rp12.000', 'notes': []},
            {'id': 'apple_03', 'name': 'Head', 'duration': '1 bulan', 'price': 'Rp20.000', 'notes': ['Bisa invite 5 orang']},
        ],
        'category_notes': [
            'Order harap sabar ya, bisa fast bisa slow',
            'Selalu tanyakan stok kepada admin sebelum payment',
            'Full garansi jika patuhi S&K',
            'Akun dari seller',
            'Head bisa invite 5 orang',
        ],
    },
    'alight_motion': {
        'title': 'Alight Motion',
        'icon': '✨',
        'description': 'Paket editing motion untuk kebutuhan konten dan video kreatif.',
        'items': [
            {'id': 'alight_01', 'name': 'Private - Akun Seller', 'duration': '1 tahun', 'price': 'Rp10.000', 'notes': []},
            {'id': 'alight_02', 'name': 'Private - Akun Buyer', 'duration': '1 tahun', 'price': 'Rp15.000', 'notes': ['Proses slow']},
        ],
        'category_notes': [],
    },
    'wink': {
        'title': 'Wink',
        'icon': '💖',
        'description': 'Pilihan paket Wink dengan opsi sharing, private, dan jaspay.',
        'items': [
            {'id': 'wink_01', 'name': 'Haring', 'duration': '7 hari', 'price': 'Rp8.000', 'notes': []},
            {'id': 'wink_02', 'name': 'Haring', 'duration': '1 bulan', 'price': 'Rp30.000', 'notes': []},
            {'id': 'wink_03', 'name': 'Private', 'duration': '7 hari', 'price': 'Rp15.000', 'notes': []},
            {'id': 'wink_04', 'name': 'Jaspay', 'duration': '7 hari', 'price': 'Rp12.000', 'notes': []},
        ],
        'category_notes': [],
    },
}

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
}

GENERIC_ITEM_ALIASES = {
    'owner',
    'member pro',
    'private',
    'head',
    'famplan',
    'indplan',
}


def normalize_text(text: str) -> str:
    return ' '.join(''.join(ch.lower() if ch.isalnum() else ' ' for ch in text).split())


def matches_alias(normalized_text: str, alias: str) -> bool:
    alias = normalize_text(alias)
    if not alias:
        return False
    if ' ' in alias:
        return alias in normalized_text
    return alias in normalized_text.split()


ITEM_LOOKUP: dict[str, dict] = {}
ITEM_ALIASES: dict[str, set[str]] = {}

for category_key, category_data in PRODUCTS.items():
    for item in category_data['items']:
        item_data = {
            'category_key': category_key,
            'category_title': category_data['title'],
            'category_icon': category_data['icon'],
            **item,
        }
        ITEM_LOOKUP[item['id']] = item_data
        aliases = {
            normalize_text(item['id']),
            normalize_text(f"{category_data['title']} {item['name']}"),
        }
        plain_name = normalize_text(item['name'])
        if plain_name not in GENERIC_ITEM_ALIASES:
            aliases.add(plain_name)
        ITEM_ALIASES[item['id']] = aliases


# =========================================================
# SESSION STATE
# =========================================================

def get_chat_state(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> dict:
    return context.application.chat_data[chat_id]


def touch_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    get_chat_state(context, chat_id)['last_seen'] = time.time()


def is_chat_idle(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    chat_state = get_chat_state(context, chat_id)
    last_seen = float(chat_state.get('last_seen', 0.0) or 0.0)
    now = time.time()
    chat_state['last_seen'] = now
    if not last_seen:
        return False
    return (now - last_seen) >= IDLE_RESET_SECONDS


# =========================================================
# UI HELPERS
# =========================================================


def make_text_box(lines: list[str], title: str | None = None) -> str:
    content = [line.rstrip() for line in lines if line is not None]
    visible_lines = [line for line in content if line]
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

    for line in content:
        if line:
            box_lines.append(f"│ {pad(line)} │")
        else:
            box_lines.append(f"│ {' ' * width} │")

    box_lines.append(f"╰{'─' * width}╯")
    return '\n'.join(box_lines)

def build_admin_url(message: str | None = None) -> str:
    if not message:
        return f'https://wa.me/{WA_NUMBER}'
    return f'https://wa.me/{WA_NUMBER}?text={quote(message)}'


def build_order_message(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    return (
        'Halo admin, saya mau order.\n'
        f"{item['name']} - {item['duration']} - {item['price']}\n"
        'Mohon info stok.'
    )


def chunk_buttons(buttons: list[InlineKeyboardButton], size: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + size] for index in range(0, len(buttons), size)]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('🛍️ Lihat Katalog', callback_data='lihat_kategori')],
            [InlineKeyboardButton('📌 Info Order', callback_data='bantuan')],
        ]
    )


def category_menu_keyboard() -> InlineKeyboardMarkup:
    category_buttons = [
        InlineKeyboardButton(f"{data['icon']} {data['title']}", callback_data=f'cat_{key}')
        for key, data in PRODUCTS.items()
    ]
    rows = chunk_buttons(category_buttons, 2)
    rows.append([InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')])
    return InlineKeyboardMarkup(rows)


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


def item_menu_keyboard(category_key: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in PRODUCTS[category_key]['items']:
        label = f"{item['name']} | {item['price']}"
        if len(label) > 38:
            label = f"{item['duration']} | {item['price']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"item_{item['id']}")])

    rows.append([InlineKeyboardButton('⬅️ Kembali ke Kategori', callback_data='lihat_kategori')])
    rows.append([InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')])
    return InlineKeyboardMarkup(rows)


def order_keyboard(item_id: str) -> InlineKeyboardMarkup:
    item = ITEM_LOOKUP[item_id]
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton('✅ Order via WhatsApp', url=build_admin_url(build_order_message(item_id)))],
            [InlineKeyboardButton('⬅️ Kembali', callback_data=f"cat_{item['category_key']}")],
            [InlineKeyboardButton('🏠 Menu Utama', callback_data='menu')],
        ]
    )


def welcome_text() -> str:
    return (
        f"<b>✦ {escape(STORE_NAME.upper())} ✦</b>\n\n"
        'Mau cari <b>app premium murah dan bergaransi</b>?\n'
        'Disini saja bre, untuk product sebenernya masih banyak,\n'
        'cuma sayanya lagi cape segini dulu aja ya.\n\n'
        'Kalau ada yang mau ditanyakan, <b>sung dm aja ya bre</b>.'
    )


def catalog_intro_text() -> str:
    return (
        '<b>🛍️ Katalog Produk</b>\n'
        '━━━━━━━━━━━━\n\n'
        'Sok dipilih dulu aja ya,\n'
        'kalo udah nemu product yang ingin dibeli,\n'
        'nanti langsung diarahin sama si bot nya ke WA saya ya bre.'
    )


def help_text() -> str:
    return (
        '<b>📌 INFO ORDER</b>\n'
        '━━━━━━━━━━━━\n\n'
        'Sok dipilih dulu aja ya.\n'
        'Kalau udah nemu product yang ingin dibeli,\n'
        'nanti langsung diarahin sama si bot nya ke WA saya ya bre.'
    )


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


def format_category_text(category_key: str) -> str:
    data = PRODUCTS[category_key]
    sections = [
        f"<b>{escape(data['icon'])} {escape(data['title'])}</b>",
        f"<i>{escape(data['description'])}</i>",
        '',
    ]

    for index, item in enumerate(data['items'], start=1):
        box = make_text_box([
            f"{index}. {item['name']}",
            f"Durasi : {item['duration']}",
            f"Harga  : {item['price']}",
        ])
        sections.append(f"<code>{escape(box)}</code>")
        sections.append('')

    if data['category_notes']:
        note_box = make_text_box([f"• {note}" for note in data['category_notes']], title='Catatan')
        sections.append(f"<code>{escape(note_box)}</code>")
        sections.append('')

    sections.append('<i>Tap paket di tombol bawah untuk lihat detail dan lanjut order.</i>')
    return '\n'.join(sections).strip()


def format_item_text(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    category_notes = PRODUCTS[item['category_key']]['category_notes']

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
        note_box = make_text_box([f"• {note}" for note in category_notes], title='Catatan')
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


def idle_reset_text() -> str:
    minutes = max(IDLE_RESET_SECONDS // 60, 1)
    return (
        '<b>🔄 Sesi di-reset otomatis</b>\n'
        '━━━━━━━━━━━━\n\n'
        f'Chat sempat tidak aktif sekitar {minutes} menit, jadi bot balik ke menu utama dulu ya bre.'
    )


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


async def reply_html(message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    await message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def send_main_menu(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_chat(context, message.chat_id)
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    await reply_html(message, welcome_text(), main_menu_keyboard())


async def send_catalog(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_chat(context, message.chat_id)
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    await reply_html(message, catalog_intro_text(), category_menu_keyboard())


async def send_category(message, category_key: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_chat(context, message.chat_id)
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    await reply_html(message, format_category_text(category_key), item_menu_keyboard(category_key))


async def send_item(message, item_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    touch_chat(context, message.chat_id)
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
    await reply_html(message, format_item_text(item_id), order_keyboard(item_id))


async def edit_or_reply(query, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest as exc:
        error_text = str(exc).lower()
        if 'message is not modified' in error_text:
            return
        if "message can't be edited" in error_text or 'there is no text in the message to edit' in error_text:
            if query.message:
                await query.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                return
        raise


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
        touch_chat(context, update.message.chat_id)
        await reply_html(update.message, help_text(), main_menu_keyboard())


async def produk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_catalog(update.message, context)


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    normalized = normalize_text(message.text)

    if is_chat_idle(context, message.chat_id) and not wants_main_menu_reset(message.text):
        await reply_html(message, idle_reset_text(), main_menu_keyboard())
        return

    if not normalized:
        await reply_html(message, fallback_text(), main_menu_keyboard())
        return

    if wants_main_menu_reset(message.text):
        await send_main_menu(message, context)
        return

    if any(matches_alias(normalized, keyword) for keyword in ('produk', 'katalog', 'catalog', 'daftar', 'list')):
        await send_catalog(message, context)
        return

    if matches_alias(normalized, 'netflix') and not matches_alias(normalized, 'harian') and not matches_alias(normalized, 'bulanan'):
        touch_chat(context, message.chat_id)
        await reply_html(message, netflix_prompt_text(), netflix_choice_keyboard())
        return

    item_id = match_item_by_text(normalized)
    if item_id:
        await send_item(message, item_id, context)
        return

    category_key = match_category_by_text(normalized)
    if category_key:
        await send_category(message, category_key, context)
        return

    touch_chat(context, message.chat_id)
    await reply_html(message, fallback_text(), main_menu_keyboard())


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        touch_chat(context, update.message.chat_id)
        await update.message.reply_text(
            text='Perintah belum tersedia. Gunakan menu di bawah ya.',
            reply_markup=main_menu_keyboard(),
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    message = query.message
    chat_id = message.chat_id if message else update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        await query.answer('Chat tidak ditemukan.', show_alert=True)
        return

    if is_chat_idle(context, chat_id):
        await query.answer('Sesi lama di-reset.', show_alert=False)
        await edit_or_reply(query, idle_reset_text(), main_menu_keyboard())
        return

    data = query.data or ''

    if data == 'menu':
        await query.answer('Membuka menu...')
        await edit_or_reply(query, welcome_text(), main_menu_keyboard())
        return

    if data == 'lihat_kategori':
        await query.answer('Menampilkan katalog...')
        await edit_or_reply(query, catalog_intro_text(), category_menu_keyboard())
        return

    if data == 'bantuan':
        await query.answer('Membuka info order...')
        await edit_or_reply(query, help_text(), main_menu_keyboard())
        return

    if data.startswith('cat_'):
        category_key = data.replace('cat_', '', 1)
        if category_key not in PRODUCTS:
            await query.answer('Kategori tidak ditemukan.', show_alert=True)
            return

        await query.answer('Membuka kategori...')
        await edit_or_reply(query, format_category_text(category_key), item_menu_keyboard(category_key))
        return

    if data.startswith('item_'):
        item_id = data.replace('item_', '', 1)
        if item_id not in ITEM_LOOKUP:
            await query.answer('Paket tidak ditemukan.', show_alert=True)
            return

        await query.answer('Menyiapkan detail paket...')
        await edit_or_reply(query, format_item_text(item_id), order_keyboard(item_id))
        return

    await query.answer('Aksi tidak dikenali.', show_alert=True)


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
