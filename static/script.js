// ===================================================
// REIIZAM ADMIN - PREMIUM SCRIPT
// ===================================================

const API = {
    post: async (url, data) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams(data)
        });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.error || 'Terjadi kesalahan');
        return result;
    }
};

const toast = (msg, type = 'success') => {
    const el = document.createElement('div');
    el.className = `alert alert-${type} position-fixed top-0 start-50 translate-middle-x m-3 shadow-lg border-0`;
    el.style.zIndex = '9999';
    el.style.minWidth = '280px';
    el.innerHTML = `<div class="d-flex align-items-center"><i class="fa-solid fa-${type==='success'?'check-circle':'triangle-exclamation'} me-2"></i><b>${msg}</b></div>`;
    document.body.appendChild(el);
    setTimeout(() => { el.remove(); location.reload(); }, 1200);
};

// ── Kategori ──────────────────────────────────────────

let categoryModal;
const openAddCategory = () => {
    categoryModal = new bootstrap.Modal(document.getElementById('categoryModal'));
    document.getElementById('catForm').reset();
    document.getElementById('catKey').value = '';
    document.getElementById('catModalTitle').innerText = 'Kategori Baru';
    categoryModal.show();
};

const openEditCategory = (key, title, icon, description, logo) => {
    categoryModal = new bootstrap.Modal(document.getElementById('categoryModal'));
    document.getElementById('catKey').value = key;
    document.getElementById('catTitle').value = title;
    document.getElementById('catIcon').value = icon;
    document.getElementById('catDescription').value = description;
    document.getElementById('catLogo').value = logo;
    document.getElementById('catModalTitle').innerText = 'Edit Kategori';
    categoryModal.show();
};

const saveCategory = async () => {
    const f = new FormData(document.getElementById('catForm'));
    const data = Object.fromEntries(f.entries());
    const url = data.key ? '/api/category/edit' : '/api/category/add';
    try {
        await API.post(url, data);
        toast('Kategori berhasil disimpan!');
    } catch (e) { alert(e.message); }
};

const deleteCategory = async (key) => {
    if (!confirm('Hapus kategori ini? Semua produk di dalamnya akan ikut terhapus.')) return;
    try {
        await API.post('/api/category/delete', { key });
        toast('Kategori berhasil dihapus!');
    } catch (e) { alert(e.message); }
};

// ── Item ──────────────────────────────────────────────

let itemModal;
const openAddItem = (catKey) => {
    itemModal = new bootstrap.Modal(document.getElementById('itemModal'));
    document.getElementById('itemForm').reset();
    document.getElementById('itemCatKey').value = catKey;
    document.getElementById('itemId').readOnly = false;
    document.getElementById('itemModalTitle').innerText = 'Item Baru';
    itemModal.show();
};

const openEditItem = (catKey, id, name, dur, price) => {
    itemModal = new bootstrap.Modal(document.getElementById('itemModal'));
    document.getElementById('itemCatKey').value = catKey;
    document.getElementById('itemId').value = id;
    document.getElementById('itemId').readOnly = true;
    document.getElementById('itemName').value = name;
    document.getElementById('itemDuration').value = dur;
    document.getElementById('itemPrice').value = price;
    document.getElementById('itemModalTitle').innerText = 'Edit Item';
    itemModal.show();
};

const saveItem = async () => {
    const f = new FormData(document.getElementById('itemForm'));
    const data = Object.fromEntries(f.entries());
    const isEdit = document.getElementById('itemId').readOnly;
    const url = isEdit ? '/api/item/edit' : '/api/item/add';
    try {
        await API.post(url, data);
        toast('Item berhasil disimpan!');
    } catch (e) { alert(e.message); }
};

const deleteItem = async (cat_key, item_id) => {
    if (!confirm('Hapus item ini?')) return;
    try {
        await API.post('/api/item/delete', { cat_key, item_id });
        toast('Item berhasil dihapus!');
    } catch (e) { alert(e.message); }
};

// ── Config ────────────────────────────────────────────

document.getElementById('configForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        await API.post('/api/config/save', Object.fromEntries(new FormData(e.target)));
        toast('Konfigurasi disimpan!');
    } catch (e) { alert(e.message); }
});

document.getElementById('passwordForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const res = await API.post('/api/config/password', Object.fromEntries(new FormData(e.target)));
        toast(res.message);
    } catch (e) { alert(e.message); }
});

// ── UI Helpers ────────────────────────────────────────

const showCategory = (key, btn) => {
    document.querySelectorAll('#categoryNav button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    document.querySelectorAll('.category-section').forEach(sec => {
        if (key === 'all' || sec.dataset.key === key) sec.style.display = 'block';
        else sec.style.display = 'none';
    });
};