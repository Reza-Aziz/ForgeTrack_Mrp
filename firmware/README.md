# Firmware Simulasi Wokwi

Sketch ini adalah "mesin" ForgeTrack. Dia berjalan di Wokwi sebagai ESP32-S2,
lalu mengirim data barang yang lewat ke broker MQTT. Data itu yang nanti
dibaca `backend/subscriber.py` dan disimpan ke Odoo.

## Rangkaian

- ESP32-S2-MINI
- Sensor jarak HC-SR04
- `TRIG` di pin 41, `ECHO` di pin 40, VCC ke 5V, GND ke GND

![Rangkaian Wokwi](../docs/wokwi-esp32-hcsr04.png)

Sensor HC-SR04 terpasang di rangkaian supaya bentuknya realistis. Yang benar
benar dipakai untuk demo adalah **angka simulasi**: sketch membaca jarak acak
yang bergantian di bawah dan di atas 200 cm, jadi barang lewat bisa ditiru
tanpa perangkat keras. Kalau nanti mau pakai sensor sungguhan, ganti isi
`readDistance()` dengan pembacaan `pulseIn()` biasa.

## Logika hitung

Prinsipnya satu pesan untuk satu barang:

1. Jarak di atas 200 cm dan pesan belum dikirim: kirim satu pesan MQTT,
   lalu tandai sudah terkirim.
2. Jarak turun di bawah 200 cm: reset penanda, siap menghitung barang
   berikutnya.
3. Hasilnya tidak ada spam. Satu barang tetap satu pesan walau sensornya
   terbaca berkali-kali.

Isi pesan yang dikirim:

```json
{"device_id":"machine-01","distance_cm":231.40,"status":"counted"}
```

## Yang harus diganti sebelum dijalankan

Wokwi berjalan di browser, jadi dia tidak bisa menghubungi broker di laptop
secara langsung. Sketch ini memakai tunnel TCP dari openport.pw yang diteruskan
ke Mosquitto di WSL. Alamat dan port tunnel bisa berubah tiap sesi:

```cpp
const char* mqttServer = "openport.pw";
const int mqttPort = 43102;
```

Ganti dua baris itu sesuai tunnel yang sedang aktif. Pastikan juga:

- `mqttTopic` sama dengan `MQTT_TOPIC` di `backend/.env`
- `device_id` di payload sama dengan nama mesin di Odoo (`machine-01`)

## Cara memakai di Wokwi

1. Buka https://wokwi.com dan buat proyek baru bertipe ESP32-S2.
2. Tambahkan `diagram.json` dengan sensor HC-SR04, atau susun ulang mengikuti
   gambar di atas.
3. Salin seluruh isi `wokwi-machine-counter.ino` ke tab sketch.
4. Tambahkan library PubSubClient lewat Library Manager.
5. Isi alamat tunnel, lalu start simulasi.
6. Kalau benar, Serial Monitor menampilkan `Barang terhitung & Published`,
   dan data mulai masuk ke terminal subscriber.
