// ===================================================
// REIIZAM ADMIN PANEL - SCRIPT
// ===================================================

// Helper: Convert File to Base64
function toBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

// Helper: Send form data via POST
async function postForm(url, data) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams(data)
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return resp.json();
}

// Helper: Show toast notification
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3 shadow-lg`;
    toast.style.zIndex = '9999';
    toast.style.minWidth = '250px';
    toast.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>${message}`;
    document.body.appendChild(toast);
    setTimeout(() => { toast.remove(); location.reload(); }, 1200);
}

// ===================================================
// LOGO FILE LISTENERS (Add & Edit Category)
// ===================================================

document.addEventListener('change', async (e) => {
    if (e.target.id === 'addCatLogoFile') {
        const file = e.target.files[0];
        if (file) {
            document.getElementById('addCatLogoBase64').value = await toBase64(file);
        }
    }
    if (e.target.id === 'editCatLogoFile') {
        const file = e.target.files[0];
        if (file) {
            document.getElementById('editCatLogoBase64').value = await toBase64(file);
        }
    }
});

// ===================================================
// ADD CATEGORY
// ===================================================

document.getElementById('addCategoryForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const form = new FormData(this);
    try {
        await postForm('/products/add_category', {
            title: form.get('title'),
            icon: form.get('icon') || '📦',
            description: form.get('description') || '',
            logo: document.getElementById('addCatLogoBase64').value || ''
        });
        showToast('Kategori berhasil ditambahkan!');
    } catch (err) {
        alert('Gagal: ' + err.message);
    }
});

// ===================================================
// EDIT CATEGORY (Modal)
// ===================================================

let categoryModal;

function openEditCategory(key, title, icon, description, logo) {
    document.getElementById('editCatKey').value = key;
    document.getElementById('editCatTitle').value = title;
    document.getElementById('editCatIcon').value = icon;
    document.getElementById('editCatDescription').value = description;
    document.getElementById('editCatLogoBase64').value = logo || '';
    document.getElementById('editCatLogoFile').value = '';
    
    if (!categoryModal) {
        categoryModal = new bootstrap.Modal(document.getElementById('categoryEditModal'));
    }
    categoryModal.show();
}

async function saveCategoryEdit() {
    const form = document.getElementById('categoryEditForm');
    const formData = new FormData(form);
    
    try {
        await postForm('/products/edit_category', {
            key: formData.get('key'),
            title: formData.get('title'),
            icon: formData.get('icon'),
            description: formData.get('description'),
            logo: document.getElementById('editCatLogoBase64').value || ''
        });
        categoryModal.hide();
        showToast('Kategori berhasil diperbarui!');
    } catch (err) {
        alert('Gagal: ' + err.message);
    }
}

// ===================================================
// DELETE CATEGORY
// ===================================================

function deleteCategory(catKey) {
    if (!confirm('Yakin ingin menghapus kategori ini beserta semua item di dalamnya?')) return;
    
    postForm('/products/delete_category', { key: catKey })
        .then(() => showToast('Kategori berhasil dihapus!'))
        .catch(err => alert('Gagal: ' + err.message));
}

// ===================================================
// ADD / EDIT ITEM (Shared Modal)
// ===================================================

let productModal;
let currentMode = 'add';  // 'add' or 'edit'

function addProduct(catKey) {
    currentMode = 'add';
    
    // Reset form
    document.getElementById('productForm').reset();
    document.getElementById('modalCatKey').value = catKey;
    document.getElementById('modalItemId').readOnly = false;
    
    // Update modal title
    document.querySelector('#productModal .modal-title').textContent = 'Tambah Item Baru';
    document.querySelector('#productModal .modal-footer .btn-primary').textContent = 'Simpan Item';
    
    if (!productModal) {
        productModal = new bootstrap.Modal(document.getElementById('productModal'));
    }
    productModal.show();
}

function editProduct(catKey, itemId, name, duration, price) {
    currentMode = 'edit';
    
    // Fill form with existing data
    document.getElementById('modalCatKey').value = catKey;
    document.getElementById('modalItemId').value = itemId;
    document.getElementById('modalItemId').readOnly = true;  // ID tidak bisa diubah saat edit
    document.getElementById('modalName').value = name;
    document.getElementById('modalDuration').value = duration;
    document.getElementById('modalPrice').value = price;
    
    // Update modal title
    document.querySelector('#productModal .modal-title').textContent = 'Edit Item';
    document.querySelector('#productModal .modal-footer .btn-primary').textContent = 'Update Item';
    
    if (!productModal) {
        productModal = new bootstrap.Modal(document.getElementById('productModal'));
    }
    productModal.show();
}

function saveProduct() {
    const form = document.getElementById('productForm');
    
    // Validate
    const itemId = document.getElementById('modalItemId').value.trim();
    const name = document.getElementById('modalName').value.trim();
    const duration = document.getElementById('modalDuration').value.trim();
    const price = document.getElementById('modalPrice').value.trim();
    const catKey = document.getElementById('modalCatKey').value;
    
    if (!itemId || !name || !duration || !price) {
        alert('Semua field harus diisi!');
        return;
    }
    
    const endpoint = currentMode === 'add' ? '/products/add_item' : '/products/edit_item';
    
    postForm(endpoint, {
        cat_key: catKey,
        item_id: itemId,
        name: name,
        duration: duration,
        price: price
    })
    .then(() => {
        productModal.hide();
        showToast(currentMode === 'add' ? 'Item berhasil ditambahkan!' : 'Item berhasil diperbarui!');
    })
    .catch(err => alert('Gagal: ' + err.message));
}

// ===================================================
// DELETE ITEM
// ===================================================

function deleteProduct(catKey, itemId) {
    if (!confirm('Yakin ingin menghapus item ini?')) return;
    
    postForm('/products/delete_item', { cat_key: catKey, item_id: itemId })
        .then(() => showToast('Item berhasil dihapus!'))
        .catch(err => alert('Gagal: ' + err.message));
}

// ===================================================
// REFRESH DATA
// ===================================================

function refreshData() {
    location.reload();
}