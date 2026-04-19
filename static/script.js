// Helper: Convert File to Base64
const toBase64 = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = error => reject(error);
});

// Logo File Listeners
document.addEventListener('change', async (e) => {
    if (e.target.id === 'addCatLogoFile' || e.target.id === 'editCatLogoFile') {
        const file = e.target.files[0];
        if (file) {
            const base64 = await toBase64(file);
            const hiddenInputId = e.target.id === 'addCatLogoFile' ? 'addCatLogoBase64' : 'editCatLogoBase64';
            document.getElementById(hiddenInputId).value = base64;
        }
    }
});

// CRUD Operations for Products

// Add Category Form
document.getElementById('addCategoryForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    const data = {
        title: formData.get('title'),
        icon: formData.get('icon'),
        description: formData.get('description'),
        logo: formData.get('logo')
    };
    
    try {
        const response = await fetch('/products/add_category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(data)
        });
        
        if (response.ok) {
            alert('Kategori berhasil ditambahkan!');
            location.reload();
        } else {
            alert('Gagal menambahkan kategori');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Terjadi kesalahan');
    }
});

// Add Product Modal
let productModal;
let currentMode = 'add';

function addProduct(catKey) {
    currentMode = 'add';
    document.getElementById('modalCatKey').value = catKey;
    document.getElementById('productForm').reset();
    document.getElementById('modalItemId').readOnly = false;
    document.querySelector('#productModal .modal-title').innerText = 'Tambah Item Baru';
    document.querySelector('#productModal .btn-primary').innerText = 'Simpan Produk';
    
    if (!productModal) {
        productModal = new bootstrap.Modal(document.getElementById('productModal'));
    }
    productModal.show();
}

function editProduct(catKey, itemId, name, duration, price) {
    currentMode = 'edit';
    document.getElementById('modalCatKey').value = catKey;
    document.getElementById('modalItemId').value = itemId;
    document.getElementById('modalItemId').readOnly = true;
    document.getElementById('modalName').value = name;
    document.getElementById('modalDuration').value = duration;
    document.getElementById('modalPrice').value = price;
    
    document.querySelector('#productModal .modal-title').innerText = 'Edit Produk';
    document.querySelector('#productModal .btn-primary').innerText = 'Update Produk';
    
    if (!productModal) {
        productModal = new bootstrap.Modal(document.getElementById('productModal'));
    }
    productModal.show();
}

function saveProduct() {
    const formData = new FormData(document.getElementById('productForm'));
    const data = {
        cat_key: formData.get('cat_key'),
        item_id: formData.get('item_id'),
        name: formData.get('name'),
        duration: formData.get('duration'),
        price: formData.get('price')
    };
    
    const endpoint = currentMode === 'add' ? '/products/add_item' : '/products/edit_item';
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(data)
    })
    .then(response => {
        if (response.ok) {
            alert(currentMode === 'add' ? 'Produk berhasil ditambahkan!' : 'Produk berhasil diperbarui!');
            location.reload();
        } else {
            alert('Gagal memproses produk');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Terjadi kesalahan');
    });
    
    productModal.hide();
}

// Delete Category
function deleteCategory(catKey) {
    if (confirm('Yakin ingin menghapus kategori ini?')) {
        fetch('/products/delete_category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ key: catKey })
        })
        .then(response => {
            if (response.ok) {
                alert('Kategori berhasil dihapus!');
                location.reload();
            } else {
                alert('Gagal menghapus kategori');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Terjadi kesalahan');
        });
    }
}

// Delete Product
function deleteProduct(catKey, itemId) {
    if (confirm('Yakin ingin menghapus produk ini?')) {
        fetch('/products/delete_item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ cat_key: catKey, item_id: itemId })
        })
        .then(response => {
            if (response.ok) {
                alert('Produk berhasil dihapus!');
                location.reload();
            } else {
                alert('Gagal menghapus produk');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Terjadi kesalahan');
        });
    }
}

// Category Modal
let categoryModal;
let currentCatMode = 'add';

function openEditCategory(key, title, icon, description, logo) {
    currentCatMode = 'edit';
    document.getElementById('editCatKey').value = key;
    document.getElementById('editCatTitle').value = title;
    document.getElementById('editCatIcon').value = icon;
    document.getElementById('editCatDescription').value = description;
    document.getElementById('editCatLogoBase64').value = logo; // Keep existing logo
    document.getElementById('editCatLogoFile').value = ''; // Reset file input
    
    categoryModal = new bootstrap.Modal(document.getElementById('categoryEditModal'));
    categoryModal.show();
}

async function saveCategoryEdit() {
    const formData = new FormData(document.getElementById('categoryEditForm'));
    const data = {
        key: formData.get('key'),
        title: formData.get('title'),
        icon: formData.get('icon'),
        description: formData.get('description'),
        logo: formData.get('logo')
    };
    
    try {
        const response = await fetch('/products/edit_category', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(data)
        });
        
        if (response.ok) {
            alert('Kategori berhasil diperbarui!');
            location.reload();
        } else {
            alert('Gagal memperbarui kategori');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Terjadi kesalahan');
    }
}

// Refresh data button
function refreshData() {
    location.reload();
}