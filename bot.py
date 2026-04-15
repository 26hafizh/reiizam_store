from __future__ import annotations

import logging
import os
from html import escape
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# =========================================================
# KONFIGURASI
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WA_NUMBER = os.getenv("WA_NUMBER", "6285126019233").strip()
STORE_NAME = os.getenv("STORE_NAME", "reiizam store").strip()

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
        "items": [
            {"id": "alight_01", "name": "Private - Akun Seller", "duration": "1 tahun", "price": "Rp10.000", "notes": []},
            {"id": "alight_02", "name": "Private - Akun Buyer", "duration": "1 tahun", "price": "Rp15.000", "notes": ["Proses slow"]},
        ],
        "category_notes": [],
    },
    "wink": {
        "title": "Wink",
        "icon": "💖",
        "items": [
            {"id": "wink_01", "name": "Haring", "duration": "7 hari", "price": "Rp8.000", "notes": []},
            {"id": "wink_02", "name": "Haring", "duration": "1 bulan", "price": "Rp30.000", "notes": []},
            {"id": "wink_03", "name": "Private", "duration": "7 hari", "price": "Rp15.000", "notes": []},
            {"id": "wink_04", "name": "Jaspay", "duration": "7 hari", "price": "Rp12.000", "notes": []},
        ],
        "category_notes": [],
    },
}

ITEM_LOOKUP = {}
for category_key, category_data in PRODUCTS.items():
    for item in category_data["items"]:
        ITEM_LOOKUP[item["id"]] = {
            "category_key": category_key,
            "category_title": category_data["title"],
            "category_icon": category_data["icon"],
            **item,
        }


def welcome_text() -> str:
    return (
        f"<b>✨ Selamat datang di {escape(STORE_NAME)} ✨</b>\n\n"
        "Bot ini menampilkan katalog produk premium dengan tampilan yang rapi.\n"
        "Pilih kategori, lihat detail paket, lalu lanjut order otomatis ke WhatsApp admin."
    )


def help_text() -> str:
    return (
        "<b>Perintah bot:</b>\n"
        "/start - buka menu utama\n"
        "/produk - lihat kategori produk\n"
        "/admin - buka WhatsApp admin\n"
        "/help - bantuan"
    )


def format_category_text(category_key: str) -> str:
    data = PRODUCTS[category_key]
    lines = [f"<b>{escape(data['icon'])} {escape(data['title'].upper())}</b>", ""]

    for idx, item in enumerate(data["items"], start=1):
        lines.append(f"<b>{idx}. {escape(item['name'])}</b>")
        lines.append(f"└ Durasi: {escape(item['duration'])}")
        lines.append(f"└ Harga: <b>{escape(item['price'])}</b>")
        lines.append("")

    if data["category_notes"]:
        lines.append("<b>ℹ️ Note kategori:</b>")
        for note in data["category_notes"]:
            lines.append(f"• {escape(note)}")
        lines.append("")

    lines.append("<i>Silakan pilih paket di tombol bawah.</i>")
    return "\n".join(lines).strip()


def format_item_text(item_id: str) -> str:
    item = ITEM_LOOKUP[item_id]
    category_notes = PRODUCTS[item["category_key"]]["category_notes"]

    lines = [
        "<b>🛍 Detail Produk</b>",
        "",
        f"<b>Kategori:</b> {escape(item['category_title'])}",
        f"<b>Paket:</b> {escape(item['name'])}",
        f"<b>Durasi:</b> {escape(item['duration'])}",
        f"<b>Harga:</b> {escape(item['price'])}",
        ""
    ]

    if item["notes"]:
        lines.append("<b>✅ Benefit / Keterangan paket:</b>")
        for note in item["notes"]:
            lines.append(f"• {escape(note)}")
        lines.append("")

    if category_notes:
        lines.append("<b>ℹ️ Note kategori:</b>")
        for note in category_notes:
            lines.append(f"• {escape(note)}")
        lines.append("")

    lines.append("<i>Klik tombol di bawah untuk order via WhatsApp.</i>")
    return "\n".join(lines).strip()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Lihat Produk", callback_data="lihat_kategori")],
        [InlineKeyboardButton("📞 Hubungi Admin", url=f"https://wa.me/{WA_NUMBER}")],
        [InlineKeyboardButton("ℹ️ Bantuan", callback_data="bantuan")],
    ])


def category_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, data in PRODUCTS.items():
        buttons.append([InlineKeyboardButton(f"{data['icon']} {data['title']}", callback_data=f"cat_{key}")])
    buttons.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def item_menu_keyboard(category_key: str) -> InlineKeyboardMarkup:
    buttons = []
    for item in PRODUCTS[category_key]["items"]:
        label = f"{item['name']} • {item['price']}"
        if len(label) > 36:
            label = f"{item['duration']} • {item['price']}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"item_{item['id']}")])

    buttons.append([InlineKeyboardButton("⬅️ Kembali ke Kategori", callback_data="lihat_kategori")])
    buttons.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


def order_keyboard(item_id: str) -> InlineKeyboardMarkup:
    item = ITEM_LOOKUP[item_id]
    wa_text = (
        "Halo admin, saya ingin order.\n\n"
        f"Store: {STORE_NAME}\n"
        f"Produk: {item['category_title']} - {item['name']}\n"
        f"Durasi: {item['duration']}\n"
        f"Harga: {item['price']}\n\n"
        "Mohon info stok dan proses ordernya ya."
    )
    wa_url = f"https://wa.me/{WA_NUMBER}?text={quote(wa_text)}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Order via WhatsApp", url=wa_url)],
        [InlineKeyboardButton("⬅️ Kembali ke Produk", callback_data=f"cat_{item['category_key']}")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="menu")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text=welcome_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text=help_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def produk_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text="<b>📂 Pilih kategori produk:</b>",
        reply_markup=category_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        text="Klik tombol di bawah untuk langsung chat admin.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Chat Admin", url=f"https://wa.me/{WA_NUMBER}")],
        ]),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    try:
        if data == "menu":
            await query.edit_message_text(
                text=welcome_text(),
                reply_markup=main_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "lihat_kategori":
            await query.edit_message_text(
                text="<b>📂 Pilih kategori produk:</b>",
                reply_markup=category_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if data == "bantuan":
            await query.edit_message_text(
                text=help_text(),
                reply_markup=main_menu_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return

        if data.startswith("cat_"):
            category_key = data.replace("cat_", "")
            if category_key not in PRODUCTS:
                await query.edit_message_text(
                    text="Kategori tidak ditemukan.",
                    reply_markup=main_menu_keyboard(),
                )
                return

            await query.edit_message_text(
                text=format_category_text(category_key),
                reply_markup=item_menu_keyboard(category_key),
                parse_mode=ParseMode.HTML,
            )
            return

        if data.startswith("item_"):
            item_id = data.replace("item_", "")
            if item_id not in ITEM_LOOKUP:
                await query.edit_message_text(
                    text="Produk tidak ditemukan.",
                    reply_markup=main_menu_keyboard(),
                )
                return

            await query.edit_message_text(
                text=format_item_text(item_id),
                reply_markup=order_keyboard(item_id),
                parse_mode=ParseMode.HTML,
            )
            return
    except BadRequest as exc:
        # Umumnya terjadi saat user menekan tombol yang menghasilkan pesan yang sama.
        logger.warning("BadRequest from Telegram: %s", exc)
        if "Message is not modified" not in str(exc):
            raise


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN belum diisi. Tambahkan BOT_TOKEN di environment variable.")

    logger.info("Starting bot for store: %s", STORE_NAME)
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("produk", produk_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
