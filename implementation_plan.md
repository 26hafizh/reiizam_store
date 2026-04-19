# Rombak UI & Fitur Reset Password

Permintaan ini membutuhkan perombakan *interface* (UI) menjadi lebih elegan, premium, dan dinamis (seperti menggunakan font Google modern, efek *glassmorphism*, gradient, dan mikro-animasi), serta pembaruan logika *backend* FastAPI untuk menyimpan dan mengautentikasi kredensial (username & password) secara dinamis dari file `config.json`.

## User Review Required
> [!IMPORTANT]
> Desain UI akan diubah drastis dari tampilan Bootstrap *default* menjadi desain dengan nuansa premium bergaya dasbor modern (bisa *dark mode* atau skema warna estetis). Jika Anda memiliki preferensi warna tertentu, silakan sebutkan!

## Proposed Changes

### `admin/app.py`
#### [MODIFY] admin/app.py
- Memperbarui model `Config` (Pydantic) dengan penambahan *field* `ADMIN_USER` dan `ADMIN_PASS` (dengan *default* 'admin' / 'admin').
- Memodifikasi fungsi `verify_auth` dan rute `/login` agar mengecek kredensial secara dinamis ke `get_config()` alih-alih menggunakan variabel *hardcoded*.
- Menambahkan rute POST baru, misalnya `/change_password`, untuk memproses pembaruan kredensial dari halaman Config.

### `admin/static/style.css`
#### [MODIFY] admin/static/style.css
- Memasukkan font dari Google Fonts (misal: "Inter" atau "Outfit").
- Menulis ulang seluruh *styling* untuk menyertakan variabel warna CSS (*custom properties*), *shadows*, *border radius* melengkung, efek transisi saat di-*hover*, serta elemen UI interaktif lainnya agar tidak kaku.

### `admin/templates/base.html` & `admin/templates/*.html`
#### [MODIFY] admin/templates/base.html
- Memperbarui struktur *navbar* dan tata letak *container* agar lebih terintegrasi dengan gaya CSS yang baru.
- Menambahkan ikon-ikon (menggunakan FontAwesome) dan mengatur ulang jarak spasi (padding/margin).

#### [MODIFY] admin/templates/config.html
- Memisahkan tampilan ke dalam dua seksi atau dua panel: satu untuk **Pengaturan Bot**, dan satu lagi untuk **Ganti Password**.
- Menambahkan *form* POST terpisah yang mengarah ke `/change_password`.

#### [MODIFY] admin/templates/products.html & login.html
- Menyempurnakan desain struktur kartu (*cards*), tombol aksi (Edit, Delete), dan tabel produk.

## Verification Plan

### Manual Verification
- Cek halaman login: Pastikan UI terlihat memukau dan jauh dari kesan Bootstrap *default*.
- Uji fitur ganti *password*: Coba ubah *password* di halaman Config, lalu lakukan *Logout*. Coba login dengan *password* lama (harus gagal) dan login dengan *password* baru (harus berhasil).
- Cek interaktivitas: Uji efek *hover*, bayangan, dan fungsionalitas CRUD secara keseluruhan di halaman daftar produk.
