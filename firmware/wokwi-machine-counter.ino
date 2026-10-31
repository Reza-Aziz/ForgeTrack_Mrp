#include <WiFi.h>
#include <PubSubClient.h>

// ==================================================
// [MC] MICROCONTROLLER & SENSOR HC-SR04 (SIMULASI)
// ==================================================

const int TRIG_PIN = 41;
const int ECHO_PIN = 40;

float distanceCm = 0.0;
bool sudahKirimPesan = false;

// Variabel bantu untuk simulasi random bolak-balik (di atas & di bawah 200)
bool stateSimulasi = false; 

float readDistance() {
  // SIMULASI MENGGUNAKAN RANDOM (Tanpa perlu sensor fisik/Wokwi manual)
  // Bergeser antara rentang di bawah 200 (misal 50-150) dan di atas 200 (misal 205-250)
  
  float simulatedDistance;
  
  if (stateSimulasi) {
    // Generate angka acak di bawah 200 cm (misal antara 50.0 hingga 180.0)
    simulatedDistance = (float)(random(500, 1800)) / 10.0;
    // Ubah state agar pembacaan berikutnya mencoba di atas 200
    stateSimulasi = false;
  } else {
    // Generate angka acak di atas 200 cm (misal antara 205.0 hingga 280.0)
    simulatedDistance = (float)(random(2050, 2800)) / 10.0;
    // Ubah state agar pembacaan berikutnya kembali di bawah 200
    stateSimulasi = true;
  }

  // Jeda kecil biar simulasi terlihat natural di Serial Monitor
  delay(500);
  return simulatedDistance;
}

// ==================================================
// [MQTT] WIFI & BROKER CONFIGURATION
// ==================================================

const char* ssid = "Wokwi-GUEST";
const char* wifiPassword = "";

// Isi konfigurasi broker MQTT nanti
const char* mqttServer = "openport.pw";
const int mqttPort = 43102;
const char* mqttUser = "";
const char* mqttPassword = "";

const char* mqttTopic = "factory/machine-01/telemetry";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ==================================================
// [MQTT] CONNECT TO WIFI
// ==================================================

void setupWiFi() {
  Serial.println("Connecting to WiFi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin("Wokwi-GUEST", "", 6);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.print("WiFi connection failed. Status: ");
    Serial.println(WiFi.status());
  }
}

// ==================================================
// [MQTT] CONNECT TO BROKER
// ==================================================

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT...");

    if (mqttClient.connect(
          "esp32-machine-01",
          mqttUser,
          mqttPassword)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, state = ");
      Serial.println(mqttClient.state());
      delay(2000);
    }
  }
}

// ==================================================
// [MC + MQTT] SETUP
// ==================================================

void setup() {
  Serial.begin(115200);

  // Inisialisasi seed random berdasarkan noise analog pin tak terpakai
  randomSeed(analogRead(0));

  // [MC] Configure sensor pins (tetap diinisialisasi meski disimulasikan)
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  // [MQTT] Initialize network and broker
  setupWiFi();
  mqttClient.setServer(mqttServer, mqttPort);
}

// ==================================================
// [MC + MQTT] READ SENSOR & PUBLISH DATA
// ==================================================

void loop() {
  // 1. Pastikan koneksi MQTT tetap terjaga
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();

  // 2. Jalankan logika pengecekan barang & kirim MQTT di sini
  cekDanKirimBarang();

  // Jeda antar pengecekan (misal setiap 1 detik)
  delay(1000); 
}

void cekDanKirimBarang() {
  float distance = readDistance();

  // Jika pembacaan sensor gagal / timeout
  if (distance < 0) {
    Serial.println("Sensor timeout / pembacaan gagal");
    return; 
  }

  // Debugging pembacaan sensor di Serial Monitor
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.println(" cm");

  // --- ATURAN LOGIKA ---
  if (distance > 200.0) {
    // Jika jarak > 200 dan BELUM pernah mengirim pesan
    if (!sudahKirimPesan) {
      
      // Buat payload JSON
      char payload[128];
      snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"machine-01\",\"distance_cm\":%.2f,\"status\":\"counted\"}",
        distance
      );

      // Kirim MQTT publish HANYA SAAT INI (hanya sekali)
      if (mqttClient.publish(mqttTopic, payload)) {
        Serial.print("Barang terhitung & Published: ");
        Serial.println(payload);
      } else {
        Serial.println("MQTT publish failed");
      }
      
      // Tandai bahwa pesan sudah dikirim agar tidak spam
      sudahKirimPesan = true; 
    }
  } 
  else if (distance < 200.0) {
    // Jika jarak turun kembali di bawah 200 cm, reset statusnya
    sudahKirimPesan = false;
  }
}
