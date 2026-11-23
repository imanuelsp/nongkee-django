# Nongkee untuk web

Aplikasi Django untuk menemukan teman belajar dan ruang kosong di Fasilkom UI. Versi desktop Tkinter mengakses API dari server yang sama sehingga akun, jadwal, dan pertemanan tersinkron. [Repositori desktop](https://github.com/imanuelsp/nongkee-desktop)

## Menjalankan server lokal

Gunakan Python 3.12 atau lebih baru. Dari direktori repositori di PowerShell jalankan:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Buka [Nongkee lokal](http://127.0.0.1:8000/). Jalankan pengujian dengan `python manage.py test` di lingkungan virtual. Pengaturan bawaan ditujukan untuk pengembangan lokal.

## Alur pengguna

- **Open Meets** menampilkan pertemuan yang masih berlangsung atau akan datang. Pilih kartu tambah untuk menentukan judul, topik, aturan bergabung, waktu, dan ruang. Dari kartu detail, peserta bisa bergabung atau mengirim permintaan. Host dapat menerima permintaan atau membatalkan meet.
- **Kelas Kosong** menampilkan ketersediaan berdasarkan hari, jam WIB, gedung, jadwal di `meets/data/timetable.json`, dan reservasi Nongkee. Jadwal berasal dari contoh HTML dan perlu diperbarui saat jadwal kuliah berubah.
- **Friends** memakai username unik (@username). Kartu teman menampilkan rombel dan minat bersama. Penerima menekan **Terima** agar kedua akun tampil sebagai teman.
- Pilih **Sign in → Create account** untuk mendaftar dengan email, nama tampilan, dan kata sandi. Buka **Profil** di kanan atas untuk mengubah username, nama, foto, rombel, dan minat. Kelas berikutnya dihitung dari jadwal mingguan dalam WIB. Untuk akun lama berbasis username, administrator perlu mengisi email unik dari pemilik akun melalui Django admin agar data meet dan pertemanannya tetap terhubung.

## Verifikasi mahasiswa UI

Di Profil, **Verifikasi mahasiswa UI** menjelaskan ketersediaan layanan. Pada rilis ini integrasi resmi belum tersedia dan status selalu **Belum terverifikasi**, termasuk untuk alamat email UI.

Untuk mengaktifkannya, pengelola perlu mendaftarkan aplikasi pada penyelenggara SSO UI, memperoleh protokol serta alamat layanan resmi, mendaftarkan callback HTTPS, dan mendapatkan izin membaca atribut atau layanan resmi yang mengonfirmasi status mahasiswa aktif. Simpan kredensial aplikasi di server sesuai ketentuan penyedia. Implementasikan callback pada backend sesuai protokol yang disetujui, validasi respons resmi dan kaitkan identitas yang dikembalikan ke sesi pengguna yang memulai verifikasi. Simpan hasil positif hanya setelah konfirmasi status mahasiswa. Kedua klien kemudian membaca hasil yang sama dari backend. Konfigurasi saja belum mengaktifkan fitur ini.

## Login Google dengan Firebase Authentication

1. Daftarkan aplikasi Web di Firebase Project Settings. Di Authentication → Sign-in method, aktifkan Google dan pilih email dukungan. Tambahkan hostname aplikasi (atau localhost untuk pengembangan) ke Authorized domains.
2. Isi FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID dan FIREBASE_APP_ID dengan konfigurasi **Web app** dari proyek yang sama. Untuk server lokal, ekspor sebagai environment variables sebelum menjalankan Django. Compose membaca file .env di samping compose.yaml.
3. Sediakan Application Default Credentials di server dengan izin membaca pengguna Firebase Authentication untuk pemeriksaan pencabutan token. Pada infrastruktur Google, gunakan identitas runtime. Untuk server lain, simpan file service account di luar repositori dan berikan path melalui GOOGLE_APPLICATION_CREDENTIALS (atau override Compose di bawah). Jangan menaruh file kredensial di static, Git, atau aplikasi desktop.
4. Buka Sign in → Lanjutkan dengan Google. Email lama harus masuk dengan kata sandi terlebih dahulu dan memilih **Hubungkan Google** di Profil. Firebase UID mengikat login berikutnya. Akun baru memperoleh username sementara yang dapat diganti. Login Google tidak mengubah status mahasiswa UI.
5. Di desktop, autentikasi berjalan di browser sistem. Tempel kode yang ditampilkan ke jendela desktop yang memulai login. Kode berlaku tiga menit, terikat ke permintaan desktop tersebut, dan hanya bisa dipakai sekali.

Panduan resmi: [Google Sign-In](https://firebase.google.com/docs/auth/web/google-signin) dan [verifikasi ID token](https://firebase.google.com/docs/auth/admin/verify-id-tokens).

## Deployment HTTPS dengan Docker Compose

Konfigurasi ini untuk satu server Linux dengan Docker Compose, penyimpanan persisten, dan domain yang DNS-nya mengarah ke server. Buka port 80 dan 443 untuk Caddy. Caddy mengurus sertifikat dan meneruskan HTTPS ke Gunicorn. Django melayani aset melalui WhiteNoise. Database SQLite, foto thumbnail dan sesi disimpan di volume campus_data. Buat backup SQLite konsisten beserta volume sebelum perubahan produksi.

Salin .env.example menjadi .env. Isi DOMAIN dan DJANGO_SECRET_KEY (buat dengan `python -c "import secrets; print(secrets.token_urlsafe(64))"`). Lengkapi konfigurasi Firebase di atas. Jika menggunakan file service account, isi FIREBASE_CREDENTIALS_FILE dengan path absolut file yang bisa dibaca user container UID 10001, kemudian jalankan:

```sh
docker compose -f compose.yaml -f compose.firebase.yaml up --build -d
```

Jika host menyediakan Application Default Credentials, gunakan `docker compose up --build -d`. Migrasi berjalan saat startup. Tanpa konfigurasi Firebase, login email tetap berfungsi. Buka domain melalui HTTPS dan arahkan NONGKEE_URL di klien desktop ke URL tersebut. Untuk menguji rilis, periksa login, hubungkan Google dari akun lama, unggah foto, kirim undangan antar-username dan cocokkan rombel dari dua akun. Jadwal mingguan pada profil berasal dari ekspor lokal, termasuk saat libur akademik.
