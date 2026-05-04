import products from "../../data/products.json";

const TELEGRAM_API = "https://api.telegram.org/bot";
const MAX_BUTTON_TEXT = 38;

const GENERIC_ITEM_ALIASES = new Set([
  "sharing",
  "private",
  "jaspay",
  "indplan",
  "famplan",
  "head",
  "member pro",
  "owner",
]);

const EXTRA_CATEGORY_ALIASES = {
  chatgpt: ["chat gpt", "gpt", "openai"],
  youtube: ["youtube premium", "yt"],
  netflix_harian: ["netflix daily", "harian netflix"],
  netflix_bulanan: ["netflix monthly", "bulanan netflix"],
  apple_music: ["music apple"],
  alight_motion: ["alight"],
  capcut: ["cap cut"],
  getcontact: ["get contact"],
  spotify: ["spoti"],
  duolingo: ["duo lingo"],
  google_drive: ["gdrive", "drive google"],
};

const { itemLookup, itemAliases, categoryAliases } = buildLookups(products);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const webhookPath = env.WEBHOOK_PATH || "/telegram/webhook";

    if (request.method === "GET" && url.pathname === "/health") {
      return jsonResponse({
        ok: true,
        service: "reiizam-store-bot-worker",
        products: Object.keys(products).length,
        items: Object.keys(itemLookup).length,
      });
    }

    if (request.method === "GET" && url.pathname === "/debug/getme") {
      if (!isAuthorizedDebugRequest(request, env)) {
        return jsonResponse({ ok: false, error: "forbidden" }, 403);
      }
      if (!env.BOT_TOKEN) {
        return jsonResponse({ ok: false, error: "BOT_TOKEN secret is missing" }, 500);
      }
      const me = await telegram(env, "getMe", {});
      return jsonResponse({
        ok: me.ok,
        bot: me.ok
          ? {
              id: me.result.id,
              username: me.result.username,
              first_name: me.result.first_name,
            }
          : me,
      });
    }

    if (request.method !== "POST" || url.pathname !== webhookPath) {
      return new Response("Not found", { status: 404 });
    }

    if (env.WEBHOOK_SECRET) {
      const header = request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
      if (header !== env.WEBHOOK_SECRET) {
        return jsonResponse({ ok: false, error: "forbidden" }, 403);
      }
    }

    if (!env.BOT_TOKEN) {
      return jsonResponse({ ok: false, error: "BOT_TOKEN secret is missing" }, 500);
    }

    try {
      const update = await request.json();
      await handleUpdate(update, env);
      return jsonResponse({ ok: true });
    } catch (error) {
      console.error("Failed to process Telegram update", error);
      return jsonResponse({ ok: false }, 500);
    }
  },
};

async function handleUpdate(update, env) {
  if (update.callback_query) {
    console.log("Incoming callback", {
      id: update.update_id,
      chat_id: update.callback_query.message?.chat?.id,
      data: update.callback_query.data,
    });
    await handleCallback(update.callback_query, env);
    return;
  }

  if (update.message) {
    console.log("Incoming message", {
      id: update.update_id,
      chat_id: update.message.chat?.id,
      text: update.message.text || "",
    });
    await handleMessage(update.message, env);
  }
}

async function handleMessage(message, env) {
  const chatId = message.chat?.id;
  const text = (message.text || "").trim();
  if (!chatId || !text) {
    return;
  }

  const normalized = normalizeText(text.replace(/^\//, ""));
  const command = normalized.split(" ")[0] || "";

  if (["start", "menu"].includes(command) || wantsMainMenu(normalized)) {
    await sendMessage(env, chatId, welcomeText(env), mainMenuKeyboard());
    return;
  }

  if (command === "help" || command === "bantuan") {
    await sendMessage(env, chatId, helpText(), mainMenuKeyboard());
    return;
  }

  if (command === "produk" || wantsCatalog(normalized)) {
    await sendMessage(env, chatId, catalogIntroText(), categoryMenuKeyboard());
    return;
  }

  if (matchesAlias(normalized, "netflix") && !matchesAlias(normalized, "harian") && !matchesAlias(normalized, "bulanan")) {
    await sendMessage(env, chatId, netflixPromptText(), netflixChoiceKeyboard());
    return;
  }

  const itemId = matchItemByText(normalized);
  if (itemId) {
    await sendMessage(env, chatId, formatItemText(itemId), orderKeyboard(itemId, env));
    return;
  }

  const categoryKey = matchCategoryByText(normalized);
  if (categoryKey) {
    await sendMessage(env, chatId, formatCategoryText(categoryKey), itemMenuKeyboard(categoryKey));
    return;
  }

  await sendMessage(env, chatId, fallbackText(env), mainMenuKeyboard());
}

async function handleCallback(query, env) {
  const data = query.data || "";
  const chatId = query.message?.chat?.id;
  const messageId = query.message?.message_id;

  await answerCallbackQuery(env, query.id);

  if (!chatId) {
    return;
  }

  if (data === "menu") {
    await replaceMessage(env, chatId, messageId, welcomeText(env), mainMenuKeyboard());
    return;
  }

  if (data === "lihat_kategori") {
    await replaceMessage(env, chatId, messageId, catalogIntroText(), categoryMenuKeyboard());
    return;
  }

  if (data === "bantuan") {
    await replaceMessage(env, chatId, messageId, helpText(), mainMenuKeyboard());
    return;
  }

  if (data.startsWith("cat_")) {
    const categoryKey = data.slice(4);
    if (!products[categoryKey]) {
      await answerCallbackQuery(env, query.id, "Kategori tidak ditemukan.", true);
      return;
    }
    await replaceMessage(env, chatId, messageId, formatCategoryText(categoryKey), itemMenuKeyboard(categoryKey));
    return;
  }

  if (data.startsWith("item_")) {
    const itemId = data.slice(5);
    if (!itemLookup[itemId]) {
      await answerCallbackQuery(env, query.id, "Paket tidak ditemukan.", true);
      return;
    }
    await replaceMessage(env, chatId, messageId, formatItemText(itemId), orderKeyboard(itemId, env));
    return;
  }

  await answerCallbackQuery(env, query.id, "Aksi tidak dikenali.", true);
}

function buildLookups(productData) {
  const lookup = {};
  const aliasesByItem = {};
  const aliasesByCategory = {};

  for (const [categoryKey, category] of Object.entries(productData)) {
    const categorySet = new Set([
      normalizeText(categoryKey.replaceAll("_", " ")),
      normalizeText(category.title || ""),
      ...(EXTRA_CATEGORY_ALIASES[categoryKey] || []).map(normalizeText),
    ].filter(Boolean));
    aliasesByCategory[categoryKey] = categorySet;

    for (const item of category.items || []) {
      const itemData = {
        category_key: categoryKey,
        category_title: category.title || "",
        category_icon: category.icon || "",
        ...item,
      };
      lookup[item.id] = itemData;

      const itemSet = new Set([
        normalizeText(item.id),
        normalizeText(`${category.title || ""} ${item.name || ""}`),
        normalizeText(`${category.title || ""} ${item.name || ""} ${item.duration || ""}`),
        normalizeText(`${item.name || ""} ${item.duration || ""}`),
      ].filter(Boolean));

      const plainName = normalizeText(item.name || "");
      if (plainName && !GENERIC_ITEM_ALIASES.has(plainName)) {
        itemSet.add(plainName);
      }

      aliasesByItem[item.id] = itemSet;
    }
  }

  return {
    itemLookup: lookup,
    itemAliases: aliasesByItem,
    categoryAliases: aliasesByCategory,
  };
}

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function matchesAlias(normalizedText, alias) {
  const normalizedAlias = normalizeText(alias);
  if (!normalizedAlias) {
    return false;
  }
  return normalizedAlias.includes(" ")
    ? normalizedText.includes(normalizedAlias)
    : normalizedText.split(" ").includes(normalizedAlias);
}

function wantsMainMenu(normalizedText) {
  return ["start", "menu", "halo", "hai", "hi", "assalamualaikum"].some((keyword) =>
    matchesAlias(normalizedText, keyword)
  );
}

function wantsCatalog(normalizedText) {
  return ["produk", "katalog", "catalog", "daftar", "list"].some((keyword) =>
    matchesAlias(normalizedText, keyword)
  );
}

function matchItemByText(normalizedText) {
  for (const [itemId, aliases] of Object.entries(itemAliases)) {
    for (const alias of aliases) {
      if (matchesAlias(normalizedText, alias)) {
        return itemId;
      }
    }
  }
  return null;
}

function matchCategoryByText(normalizedText) {
  for (const [categoryKey, aliases] of Object.entries(categoryAliases)) {
    for (const alias of aliases) {
      if (matchesAlias(normalizedText, alias)) {
        return categoryKey;
      }
    }
  }
  return null;
}

function storeName(env) {
  return env.STORE_NAME || "reiizam store";
}

function waNumber(env) {
  return env.WA_NUMBER || "6285126019233";
}

function mainMenuKeyboard() {
  return inlineKeyboard([
    [button("List Product", "lihat_kategori")],
    [button("Cara Order Cepat", "bantuan")],
  ]);
}

function categoryMenuKeyboard() {
  const buttons = Object.entries(products).map(([key, data]) =>
    button(`${data.icon || ""} ${data.title || key}`, `cat_${key}`)
  );
  const rows = chunk(buttons, 2);
  rows.push([button("Menu Utama", "menu")]);
  return inlineKeyboard(rows);
}

function netflixChoiceKeyboard() {
  return inlineKeyboard([
    [button("Netflix Harian", "cat_netflix_harian"), button("Netflix Bulanan", "cat_netflix_bulanan")],
    [button("Menu Utama", "menu")],
  ]);
}

function itemMenuKeyboard(categoryKey) {
  const rows = [];
  for (const item of products[categoryKey].items || []) {
    let label = `${item.name} | ${item.price}`;
    if (label.length > MAX_BUTTON_TEXT) {
      label = `${item.duration} | ${item.price}`;
    }
    rows.push([button(label, `item_${item.id}`)]);
  }
  rows.push([button("Kembali ke Kategori", "lihat_kategori")]);
  rows.push([button("Menu Utama", "menu")]);
  return inlineKeyboard(rows);
}

function orderKeyboard(itemId, env) {
  const item = itemLookup[itemId];
  return inlineKeyboard([
    [urlButton("Order via WhatsApp", buildWhatsAppUrl(buildOrderMessage(itemId, env), env))],
    [button("Kembali", `cat_${item.category_key}`)],
    [button("Menu Utama", "menu")],
  ]);
}

function inlineKeyboard(rows) {
  return { inline_keyboard: rows };
}

function button(text, callbackData) {
  return { text, callback_data: callbackData };
}

function urlButton(text, url) {
  return { text, url };
}

function chunk(items, size) {
  const rows = [];
  for (let index = 0; index < items.length; index += size) {
    rows.push(items.slice(index, index + size));
  }
  return rows;
}

function buildWhatsAppUrl(message, env) {
  const phone = waNumber(env);
  return `https://api.whatsapp.com/send/?phone=${phone}&text=${encodeURIComponent(message)}&type=phone_number&app_absent=0`;
}

function buildOrderMessage(itemId, env) {
  const item = itemLookup[itemId];
  const store = storeName(env);
  return [
    `FORM ORDER - ${store.toUpperCase()}`,
    "------------------",
    "",
    "Halo Admin, saya ingin memesan paket berikut:",
    "",
    `Kategori: ${item.category_title}`,
    `Produk: ${item.name}`,
    `Durasi: ${item.duration}`,
    `Harga: ${item.price}`,
    `Kode: ${item.id.toUpperCase()}`,
    "",
    "Apakah stok ready min? Mohon infonya ya, terima kasih!",
  ].join("\n");
}

function welcomeText(env) {
  const catalogItems = Object.values(products).slice(0, 12);
  const lines = [
    `<b>WELCOME TO ${escapeHtml(storeName(env).toUpperCase())}</b>`,
    "<i>Penyedia layanan premium terlengkap dan terjangkau.</i>",
    "",
    "<b>KATALOG PRODUK KAMI</b>",
  ];

  if (!catalogItems.length) {
    lines.push("<i>Belum ada produk tersedia</i>");
  } else {
    for (const item of catalogItems) {
      lines.push(`${escapeHtml(item.icon || "")} ${escapeHtml(item.title || "")}`);
    }
  }

  lines.push(
    "",
    "<b>KEUNGGULAN KAMI:</b>",
    "- Proses cepat",
    "- Legal dan bergaransi",
    "- Harga hemat",
    "",
    "<b>Silakan pilih menu di bawah untuk mulai order.</b>"
  );
  return lines.join("\n");
}

function catalogIntroText() {
  return [
    "<b>Pilih Kategori Produk</b>",
    "<i>Temukan app premium yang kamu butuhkan di sini.</i>",
    "",
    "<b>Cara Order:</b>",
    "1. Pilih kategori app",
    "2. Pilih paket yang cocok",
    "3. Tekan tombol order",
    "4. Lanjut ke WhatsApp",
    "",
    "<i>Silakan pilih kategori di bawah ini.</i>",
  ].join("\n");
}

function helpText() {
  return [
    "<b>Cara Order</b>",
    "",
    "1. Buka katalog produk",
    "2. Pilih kategori",
    "3. Pilih paket yang diinginkan",
    "4. Tap tombol Order WhatsApp",
    "",
    "<i>Setelah tap order, kamu akan diarahkan ke WhatsApp admin secara otomatis.</i>",
  ].join("\n");
}

function netflixPromptText() {
  return [
    "<b>Netflix - Pilih Jenis Paket</b>",
    "<i>Tersedia dua pilihan, sesuaikan dengan kebutuhanmu.</i>",
    "",
    "<b>Harian</b> - Fleksibel, bayar per hari",
    "<b>Bulanan</b> - Lebih hemat, aktif 1 bulan",
    "",
    "<i>Pilih di bawah.</i>",
  ].join("\n");
}

function formatCategoryText(categoryKey) {
  const category = products[categoryKey];
  const lines = [
    `<b>${escapeHtml(category.icon || "")} ${escapeHtml((category.title || "").toUpperCase())} KATEGORI</b>`,
    `<i>"${escapeHtml(category.description || "")}"</i>`,
    "--------------------",
    "",
  ];

  for (const item of category.items || []) {
    lines.push(
      `<b>${escapeHtml(item.name || "")}</b>`,
      `Durasi: <code>${escapeHtml(item.duration || "")}</code>`,
      `Harga: <b>${escapeHtml(item.price || "")}</b>`,
      ""
    );
  }

  lines.push("<i>Pilih paket di bawah untuk detail dan order.</i>");
  return lines.join("\n").trim();
}

function formatItemText(itemId) {
  const item = itemLookup[itemId];
  const category = products[item.category_key] || {};
  const lines = [
    "<b>DETAIL PESANAN</b>",
    "--------------------",
    `<b>Kategori:</b> ${escapeHtml(item.category_title || "")}`,
    `<b>Produk:</b> ${escapeHtml(item.name || "")}`,
    `<b>Durasi:</b> ${escapeHtml(item.duration || "")}`,
    `<b>Harga:</b> ${escapeHtml(item.price || "")}`,
    `<b>Kode:</b> <code>${escapeHtml(String(item.id || "").toUpperCase())}</code>`,
    "--------------------",
    "",
  ];

  if (item.notes?.length) {
    lines.push("<b>Highlight:</b>");
    for (const note of item.notes) {
      lines.push(`- <i>${escapeHtml(note)}</i>`);
    }
    lines.push("");
  }

  if (category.category_notes?.length) {
    const title = category.category_note_title || "Informasi";
    lines.push(`<b>${escapeHtml(title.toUpperCase())}:</b>`);
    for (const note of category.category_notes) {
      lines.push(`- <i>${escapeHtml(note)}</i>`);
    }
    lines.push("");
  }

  lines.push("<i>Tap tombol di bawah untuk kirim format order ke WhatsApp.</i>");
  return lines.join("\n").trim();
}

function fallbackText(env) {
  return [
    `<b>${escapeHtml(storeName(env).toUpperCase())}</b>`,
    "",
    "Silakan mulai dari menu utama ya.",
    "Pilih kategori produk yang ingin kamu lihat di bawah ini.",
  ].join("\n");
}

async function replaceMessage(env, chatId, messageId, text, replyMarkup) {
  if (messageId) {
    const result = await telegram(env, "editMessageText", {
      chat_id: chatId,
      message_id: messageId,
      text,
      parse_mode: "HTML",
      reply_markup: replyMarkup,
      disable_web_page_preview: true,
    });
    if (result.ok) {
      return result;
    }
  }
  return sendMessage(env, chatId, text, replyMarkup);
}

async function sendMessage(env, chatId, text, replyMarkup) {
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    reply_markup: replyMarkup,
    disable_web_page_preview: true,
  });
}

async function answerCallbackQuery(env, callbackQueryId, text = "", showAlert = false) {
  if (!callbackQueryId) {
    return { ok: true };
  }
  return telegram(env, "answerCallbackQuery", {
    callback_query_id: callbackQueryId,
    text,
    show_alert: showAlert,
  });
}

async function telegram(env, method, payload) {
  const response = await fetch(`${TELEGRAM_API}${env.BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({ ok: false }));
  if (!body.ok) {
    console.error(`Telegram ${method} failed`, body);
  }
  return body;
}

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function isAuthorizedDebugRequest(request, env) {
  if (!env.WEBHOOK_SECRET) {
    return false;
  }
  return (request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "") === env.WEBHOOK_SECRET;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
