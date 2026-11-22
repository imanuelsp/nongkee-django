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
- **Friends** menerima undangan melalui email akun Nongkee. Penerima menekan **Terima** agar kedua akun tampil sebagai teman.
- Pilih **Sign in → Create account** untuk mendaftar dengan email, nama tampilan, dan kata sandi. Buka **Profil** di kanan atas untuk mengubah nama. Untuk akun lama berbasis username, administrator perlu mengisi email unik dari pemilik akun melalui Django admin agar data meet dan pertemanannya tetap terhubung.

## Verifikasi mahasiswa UI

Di Profil, **Verifikasi mahasiswa UI** menjelaskan ketersediaan layanan. Pada rilis ini integrasi resmi belum tersedia dan status selalu **Belum terverifikasi**, termasuk untuk alamat email UI.

Untuk mengaktifkannya, pengelola perlu mendaftarkan aplikasi pada penyelenggara SSO UI, memperoleh protokol serta alamat layanan resmi, mendaftarkan callback HTTPS, dan mendapatkan izin membaca atribut atau layanan resmi yang mengonfirmasi status mahasiswa aktif. Simpan kredensial aplikasi di server sesuai ketentuan penyedia. Implementasikan callback pada backend sesuai protokol yang disetujui, validasi respons resmi dan kaitkan identitas yang dikembalikan ke sesi pengguna yang memulai verifikasi. Simpan hasil positif hanya setelah konfirmasi status mahasiswa. Kedua klien kemudian membaca hasil yang sama dari backend. Konfigurasi saja belum mengaktifkan fitur ini.
