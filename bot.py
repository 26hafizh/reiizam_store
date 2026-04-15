from __future__ import annotations

import logging
import os
import time
from contextlib import suppress
from html import escape
from pathlib import Path
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
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
        Path(".env"),
        Path(__file__).resolve().with_name(".env"),
    ]

    for env_path in env_candidates:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
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
            "Nilai %s=%r tidak valid. Menggunakan default %s.",
            name,
            raw_value,
            default,
        )
        return default

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WA_NUMBER = os.getenv("WA_NUMBER", "6285126019233").strip()
STORE_NAME = os.getenv("STORE_NAME", "reiizam store").strip()
RESTART_DELAY_SECONDS = max(get_int_env("RESTART_DELAY_SECONDS", 5), 1)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================================================
# DATA PRODUK
# =========================================================
PRODUCTS = {
    "canva": {
        "title": "Canva",
        "icon": "🎨",
        "description": "Paket desain untuk kebutuhan konten, branding, dan editing harian.",
        "items": [
            {"id": "canva_01", "name": "Member Pro", "duration": "1 bulan", "price": "Rp5.000", "notes": []},
            {"id": "canva_02", "name": "Member Pro", "duration": "2 bulan", "price": "Rp10.000", "notes": []},
            {"id": "canva_03", "name": "Owner", "duration": "1 bulan", "price": "Rp25.000", "notes": []},
        ],
        "category_notes": [],
    },
    "chatgpt": {
        "title": "ChatGPT",
        "icon": "🤖",
        "description": "Pilihan paket AI premium untuk kebutuhan chat, ide, dan produktivitas.",
        "items": [
            {
                "id": "chatgpt_01",
                "name": "ChatGPT Priv Invite",
                "duration": "1 bulan",
                "price": "Rp15.000",
                "notes": ["Strong akun", "Invite pakai email buyer", "Full garansi"],
            },
            {
                "id": "chatgpt_02",
                "name": "ChatGPT Plus Private",
                "duration": "1 bulan",
                "price": "Rp20.000",
                "notes": [
                    "Akun seller",
                    "Full garansi",
                    "Full garansi jika patuhi S&K",
                    "Owner akun dari seller",
                    "Owner bisa invite 100 member",
                ],
            },
        ],
        "category_notes": [
            "25 - 30 hari dihitung 1 bulan",
            "No rush",
            "Wajib tanyakan stok ke admin",
            "Max invite dibatasi untuk menghindari over seat yang mengakibatkan akun deactivated",
            "Semua transaksi no refund kecuali kesalahan admin",
        ],
    },
    "youtube": {
        "title": "YouTube",
        "icon": "▶️",
        "description": "Paket YouTube premium untuk nonton tanpa iklan dengan harga ringan.",
        "items": [
            {"id": "youtube_01", "name": "Famplan (Invite)", "duration": "1 bulan", "price": "Rp4.000", "notes": []},
            {"id": "youtube_02", "name": "Indplan", "duration": "1 bulan", "price": "Rp7.000", "notes": []},
            {"id": "youtube_03", "name": "Famhead", "duration": "1 bulan", "price": "Rp10.000", "notes": ["Bisa invite 5 orang"]},
        ],
        "category_notes": [],
    },
    "netflix_harian": {
        "title": "Netflix Harian",
        "icon": "📺",
        "description": "Pilihan harian untuk kebutuhan nonton cepat dan fleksibel.",
        "items": [
            {"id": "neth_01", "name": "1 Hari 2 User", "duration": "1 hari", "price": "Rp3.000", "notes": []},
            {"id": "neth_02", "name": "1 Hari 1 User", "duration": "1 hari", "price": "Rp5.000", "notes": []},
            {"id": "neth_03", "name": "7 Hari 2 User", "duration": "7 hari", "price": "Rp9.000", "notes": []},
            {"id": "neth_04", "name": "7 Hari 1 User", "duration": "7 hari", "price": "Rp10.000", "notes": []},
            {"id": "neth_05", "name": "7 Hari Semi Private", "duration": "7 hari", "price": "Rp12.000", "notes": []},
        ],
        "category_notes": [],
    },
    "netflix_bulanan": {
        "title": "Netflix Bulanan",
        "icon": "🎬",
        "description": "Paket bulanan buat yang ingin pengalaman nonton lebih nyaman.",
        "items": [
            {
                "id": "netb_01",
                "name": "Netflix Semi Private",
                "duration": "1 bulan",
                "price": "Rp27.000",
                "notes": ["Bisa login 2 device", "Tidak bisa nonton secara bersamaan"],
            },
            {
                "id": "netb_02",
                "name": "Netflix Sultan VIP",
                "duration": "1 bulan",
                "price": "Rp35.000",
                "notes": [
                    "Jatah 1 profil",
                    "Bisa login 2 device",
                    "Bisa nonton secara bersamaan",
                    "Garansi anti limit",
                ],
            },
        ],
        "category_notes": [],
    },
    "apple_music": {
        "title": "Apple Music",
        "icon": "🎵",
        "description": "Paket musik premium untuk pengalaman dengar yang lebih nyaman.",
        "items": [
            {"id": "apple_01", "name": "Famplan", "duration": "1 bulan", "price": "Rp10.000", "notes": []},
            {"id": "apple_02", "name": "Indplan", "duration": "1 bulan", "price": "Rp12.000", "notes": []},
            {"id": "apple_03", "name": "Head", "duration": "1 bulan", "price": "Rp20.000", "notes": ["Bisa invite 5 orang"]},
        ],
        "category_notes": [
            "Order harap sabar ya, bisa fast bisa slow",
            "Selalu tanyakan stok kepada admin sebelum payment",
            "Full garansi jika patuhi S&K",
            "Akun dari seller",
            "Head bisa invite 5 orang",
        ],
    },
    "alight_motion": {
        "title": "Alight Motion",
        "icon": "✨",
        "description": "Paket editing motion untuk kebutuhan konten dan video kreatif.",
        "items": [
            {"id": "alight_01", "name": "Private - Akun Seller", "duration": "1 tahun", "price": "Rp10.000", "notes": []},
            {"id": "alight_02", "name": "Private - Akun Buyer", "duration": "1 tahun", "price": "Rp15.000", "notes": ["Proses slow"]},
        ],
        "category_notes": [],
    },
    "wink": {
        "title": "Wink",
        "icon": "💖",
        "description": "Pilihan paket Wink dengan opsi sharing, private, dan jaspay.",
        "items": [
            {"id": "wink_01", "name": "Haring", "duration": "7 hari", "price": "Rp8.000", "notes": []},
            {"id": "wink_02", "name": "Haring", "duration": "1 bulan", "price": "Rp30.000", "notes": []},
            {"id": "wink_03", "name": "Private", "duration": "7 hari", "price": "Rp15.000", "notes": []},
            {"id": "wink_04", "name": "Jaspay", "duration": "7 hari", "price": "Rp12.000", "notes": []},
        ],
        "category_notes": [],
    },
}

BOT_COMMANDS = [
    ("start", "Buka menu utama"),
    ("menu", "Tampilkan menu"),
    ("produk", "Lihat katalog produk"),
    ("admin", "Chat admin WhatsApp"),
    ("help", "Cara pakai bot"),
]

CATEGORY_ALIASES = {
    "canva": ["canva"],
    "chatgpt": ["chatgpt", "chat gpt", "gpt", "openai"],
    "youtube": ["youtube", "youtube premium", "yt"],
    "netflix_harian": ["netflix harian", "netflix daily", "harian netflix"],
    "netflix_bulanan": ["netflix bulanan", "netflix monthly", "bulanan netflix"],
    "apple_music": ["apple music", "music apple"],
    "alight_motion": ["alight motion", "alight"],
    "wink": ["wink"],
}

GENERIC_ITEM_ALIASES = {
    "owner",
    "member pro",
    "private",
    "head",
    "famplan",
    "indplan",
}


def normalize_text(text: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())


def matches_alias(normalized_text: str, alias: str) -> bool:
    alias = normalize_text(alias)
    if not alias:
        return False
    if " " in alias:
        return alias in normalized_text
    return alias in normalized_text.split()


ITEM_LOOKUP = {}
ITEM_ALIASES = {}

for category_key, category_data in PRODUCTS.items():
    for item in category_data["items"]:
        item_data = {
            "category_key": category_key,
            "category_title": category_data["title"],
            "category_icon": category_data["icon"],
            **item,
        }
        ITEM_LOOKUP[item["id"]] = item_data
        aliases = {
            normalize_text(item["id"]),
            normalize_text(f"{category_data['title']} {item['name']}"),
        }
        plain_name = normalize_text(item["name"])
        if plain_name not in GENERIC_ITEM_ALIASES:
            aliases.add(plain_name)
        ITEM_ALIASES[item["id"]] = aliases


def total_item_count() -> int:
    return sum(len(category["items"]) for category in PRODUCTS.values())


def build_admin_url(message: str | None = None) -> str:
    if not message:
        return f"https://wa.me/{WA_NUMBER}"
    return f"https://wa.me/{WA_NUMBER}?text={quote(message)}"


def build_order_message(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    return (
        f"Halo admin, saya mau order.\n"
        f"{item['name']} - {item['duration']} - {item['price']}\n"
        f"Mohon info stok."
    )


def chunk_buttons(buttons: list[InlineKeyboardButton], size: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[index:index + size] for index in range(0, len(buttons), size)]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛍️ Buka Katalog", callback_data="lihat_kategori")],
            [InlineKeyboardButton("📌 Info Order", callback_data="bantuan")],
        ]
    )


def category_menu_keyboard() -> InlineKeyboardMarkup:
    category_buttons = [
        InlineKeyboardButton(f"{data['icon']} {data['title']}", callback_data=f"cat_{key}")
        for key, data in PRODUCTS.items()
    ]
    rows = chunk_buttons(category_buttons, 2)
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def netflix_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📺 Netflix Harian", callback_data="cat_netflix_harian"),
                InlineKeyboardButton("🎬 Netflix Bulanan", callback_data="cat_netflix_bulanan"),
            ],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")],
        ]
    )


def item_menu_keyboard(category_key: str) -> InlineKeyboardMarkup:
    rows = []
    for item in PRODUCTS[category_key]["items"]:
        label = f"{item['name']} | {item['price']}"
        if len(label) > 38:
            label = f"{item['duration']} | {item['price']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"item_{item['id']}")])

    rows.append([InlineKeyboardButton("⬅️ Kembali ke Kategori", callback_data="lihat_kategori")])
    rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def order_keyboard(item_id: str) -> InlineKeyboardMarkup:
    item = ITEM_LOOKUP[item_id]
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Order via WhatsApp", url=build_admin_url(build_order_message(item_id)))],
            [InlineKeyboardButton("⬅️ Kembali", callback_data=f"cat_{item['category_key']}")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")],
        ]
    )


def welcome_text() -> str:
    return (
        f"<b>✦ {escape(STORE_NAME.upper())} ✦</b>\n\n"
        "Mau cari <b>app premium murah dan bergaransi</b>?\n"
        "Disini saja bre, untuk product sebenernya masih banyak, "
        "cuma sayanya lagi cape segini dulu aja ya.\n\n"
        "Kalau ada yang mau ditanyakan, <b>sung DM aja ya bre</b>."
    )


def catalog_intro_text() -> str:
    return (
        "<b>🛍️ Katalog Produk</b>\n"
        "<i>Pilih kategori yang ingin kamu lihat.</i>\n\n"
        f"Tersedia <b>{len(PRODUCTS)}</b> kategori aktif dan <b>{total_item_count()}</b> paket siap ditampilkan."
    )


def help_text() -> str:
    return (
        "<b>📌 INFO ORDER</b>\n\n"
        "Sok dipilih dulu aja ya.\n"
        "Kalau udah nemu product yang ingin dibeli,\n"
        "nanti langsung diarahin sama si bot nya ke WA saya ya bre."
    )


def admin_text() -> str:
    return (
        "<b>💬 Hubungi Admin</b>\n\n"
        "Kalau kamu sudah tahu paket yang mau dibeli, sebaiknya masuk lewat detail produk agar format order lebih rapi.\n\n"
        "Kalau masih mau tanya stok, garansi, atau proses order, kamu juga bisa langsung chat admin dari tombol di bawah."
    )


def netflix_prompt_text() -> str:
    return (
        "<b>📺 Netflix tersedia dalam dua pilihan</b>\n\n"
        "Pilih versi yang mau kamu lihat dulu:\n"
        "• Harian\n"
        "• Bulanan"
    )


def format_notes(title: str, notes: list[str]) -> list[str]:
    if not notes:
        return []

    lines = [f"<b>{escape(title)}</b>"]
    for note in notes:
        lines.append(f"• {escape(note)}")
    lines.append("")
    return lines


def format_category_text(category_key: str) -> str:
    data = PRODUCTS[category_key]
    lines = [
        f"<b>{escape(data['icon'])} {escape(data['title'])}</b>",
        f"<i>{escape(data['description'])}</i>",
        "",
    ]

    for index, item in enumerate(data["items"], start=1):
        lines.append(f"<b>{index}. {escape(item['name'])}</b>")
        lines.append(f"• Durasi: {escape(item['duration'])}")
        lines.append(f"• Harga: <b>{escape(item['price'])}</b>")
        if item["notes"]:
            lines.append(f"• Highlight: {escape(item['notes'][0])}")
        lines.append("")

    lines.extend(format_notes("ℹ️ Catatan kategori", data["category_notes"]))
    lines.append("<i>Tap paket di tombol bawah untuk lihat detail dan lanjut order.</i>")
    return "\n".join(lines).strip()


def format_item_text(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    category_notes = PRODUCTS[item["category_key"]]["category_notes"]

    lines = [
        "<b>🧾 Detail Paket</b>",
        f"<b>{escape(item['name'])}</b>",
        "",
        f"• Kategori: {escape(item['category_title'])}",
        f"• Durasi: {escape(item['duration'])}",
        f"• Harga: <b>{escape(item['price'])}</b>",
        f"• Kode paket: <code>{escape(item['id'].upper())}</code>",
        "",
    ]

    lines.extend(format_notes("✅ Benefit / Keterangan paket", item["notes"]))
    lines.extend(format_notes("ℹ️ Catatan kategori", category_notes))
    lines.append("<i>Tekan tombol order untuk mengirim format chat WhatsApp yang lebih rapi ke admin.</i>")
    return "\n".join(lines).strip()


def fallback_text() -> str:
    return (
        "<b>Pesanmu sudah masuk.</b>\n\n"
        "Supaya lebih cepat, kamu bisa pilih salah satu alur berikut:\n"
        "• buka katalog produk\n"
        "• langsung chat admin\n"
        "• ketik nama produk, misalnya <code>ChatGPT</code> atau <code>Netflix</code>"
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


async def send_main_menu(message) -> None:
    await message.reply_text(
        text=welcome_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def send_catalog(message) -> None:
    await message.reply_text(
        text=catalog_intro_text(),
        reply_markup=category_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def send_admin(message) -> None:
    await message.reply_text(
        text=admin_text(),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("💬 Chat Admin", url=build_admin_url())],
                [InlineKeyboardButton("🛍️ Buka Katalog", callback_data="lihat_kategori")],
            ]
        ),
        parse_mode=ParseMode.HTML,
    )


async def send_category(message, category_key: str) -> None:
    await message.reply_text(
        text=format_category_text(category_key),
        reply_markup=item_menu_keyboard(category_key),
        parse_mode=ParseMode.HTML,
    )


async def send_item(message, item_id: str) -> None:
    await message.reply_text(
        text=format_item_text(item_id),
        reply_markup=order_keyboard(item_id),
        parse_mode=ParseMode.HTML,
    )


async def edit_or_reply(query, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except BadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            return
        if "message can't be edited" in error_text or "there is no text in the message to edit" in error_text:
            if query.message:
                await query.message.reply_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                )
                return
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_main_menu(update.message)


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_main_menu(update.message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            text=help_text(),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )


async def produk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_catalog(update.message)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await send_admin(update.message)


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    normalized = normalize_text(message.text)

    if not normalized:
        await message.reply_text(
            text=fallback_text(),
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    if normalized in {"start", "menu"} or any(matches_alias(normalized, greeting) for greeting in ("halo", "hai", "hi", "assalamualaikum")):
        await send_main_menu(message)
        return

    if any(matches_alias(normalized, keyword) for keyword in ("produk", "katalog", "catalog", "daftar", "list")):
        await send_catalog(message)
        return

    if matches_alias(normalized, "netflix") and not matches_alias(normalized, "harian") and not matches_alias(normalized, "bulanan"):
        await message.reply_text(
            text=netflix_prompt_text(),
            reply_markup=netflix_choice_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return

    item_id = match_item_by_text(normalized)
    if item_id:
        await send_item(message, item_id)
        return

    category_key = match_category_by_text(normalized)
    if category_key:
        await send_category(message, category_key)
        return

    if any(matches_alias(normalized, keyword) for keyword in ("admin", "wa", "whatsapp", "order", "beli", "pesan")):
        await send_admin(message)
        return

    await message.reply_text(
        text=fallback_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            text="Perintah belum tersedia. Gunakan menu di bawah ya.",
            reply_markup=main_menu_keyboard(),
        )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data or ""

    if data == "menu":
        await query.answer("Membuka menu utama...")
        await edit_or_reply(query, welcome_text(), main_menu_keyboard())
        return

    if data == "lihat_kategori":
        await query.answer("Menampilkan katalog...")
        await edit_or_reply(query, catalog_intro_text(), category_menu_keyboard())
        return

    if data == "bantuan":
        await query.answer("Membuka bantuan...")
        await edit_or_reply(query, help_text(), main_menu_keyboard())
        return

    if data.startswith("cat_"):
        category_key = data.replace("cat_", "", 1)
        if category_key not in PRODUCTS:
            await query.answer("Kategori tidak ditemukan.", show_alert=True)
            return

        await query.answer("Kategori dibuka.")
        await edit_or_reply(query, format_category_text(category_key), item_menu_keyboard(category_key))
        return

    if data.startswith("item_"):
        item_id = data.replace("item_", "", 1)
        if item_id not in ITEM_LOOKUP:
            await query.answer("Paket tidak ditemukan.", show_alert=True)
            return

        await query.answer("Detail paket siap.")
        await edit_or_reply(query, format_item_text(item_id), order_keyboard(item_id))
        return

    await query.answer("Aksi tidak dikenali.", show_alert=True)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error while processing update", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        with suppress(Exception):
            await update.effective_message.reply_text(
                text="Maaf, bot sedang mengalami gangguan sementara. Silakan coba lagi sebentar ya.",
                reply_markup=main_menu_keyboard(),
            )


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered.")
    except Exception:
        logger.exception("Gagal set bot commands. Bot tetap dilanjutkan agar tetap online.")


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("produk", produk_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    app.add_error_handler(error_handler)


def build_application() -> Application:
    return (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .http_version("1.1")
        .get_updates_http_version("1.1")
        .concurrent_updates(8)
        .connection_pool_size(16)
        .pool_timeout(30)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(30)
        .post_init(post_init)
        .build()
    )


def run_bot() -> None:
    app = build_application()
    register_handlers(app)
    app.run_polling(
        poll_interval=0.0,
        timeout=30,
        bootstrap_retries=-1,
        drop_pending_updates=False,
    )


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN belum diisi. Tambahkan BOT_TOKEN di environment variable atau file .env."
        )

    while True:
        try:
            logger.info("Starting bot for store: %s", STORE_NAME)
            run_bot()
            logger.warning(
                "Polling loop berhenti. Mencoba menjalankan ulang dalam %s detik.",
                RESTART_DELAY_SECONDS,
            )
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot dihentikan secara manual.")
            break
        except Exception:
            logger.exception(
                "Bot crash. Mencoba restart ulang dalam %s detik.",
                RESTART_DELAY_SECONDS,
            )

        time.sleep(RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    main()
