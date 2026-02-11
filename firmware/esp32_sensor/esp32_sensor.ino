/*
 * たんぼアドバイザー ESP32 センサーユニット
 *
 * ハードウェア:
 *   - ESP32-DevKitC (WROOM-32)
 *   - BME280 (I2C: SDA=21, SCL=22) - 気温/湿度/気圧
 *   - DS18B20 防水 (1-Wire: GPIO 4) - 水温
 *   - 圧力式水位センサー (ADC: GPIO 34) - 水位
 *   - microSD モジュール (SPI: CS=5)
 *
 * 動作: 計測 → CSV書き込み → deep sleep
 * 記録間隔: 通常30分 / いもち病リスク高10分 / 深夜60分
 */

#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_BME280.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <time.h>
#include <WiFi.h>

// --- ピン定義 ---
#define BME_SDA       21
#define BME_SCL       22
#define DS18B20_PIN   4
#define WATER_LEVEL_PIN 34
#define SD_CS_PIN     5

// --- 記録間隔（秒） ---
#define INTERVAL_NORMAL     1800   // 30分
#define INTERVAL_HIGH_RISK  600    // 10分
#define INTERVAL_NIGHT      3600   // 60分

// --- いもち病リスク閾値 ---
#define BLAST_TEMP_MIN   20.0
#define BLAST_TEMP_MAX   28.0
#define BLAST_HUMIDITY   85.0

// --- NTP ---
#define NTP_SERVER "ntp.nict.jp"
#define JST_OFFSET 9 * 3600

// --- Wi-Fi（オプション） ---
// #define WIFI_SSID "your_ssid"
// #define WIFI_PASS "your_password"

// --- グローバルオブジェクト ---
Adafruit_BME280 bme;
OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);

float airTemp = 0;
float humidity = 0;
float pressure = 0;
float waterTemp = 0;
float waterLevel = 0;

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("=== tanbo-adviser sensor unit ===");

  // I2C 初期化
  Wire.begin(BME_SDA, BME_SCL);

  // BME280 初期化
  if (!bme.begin(0x76)) {
    Serial.println("ERROR: BME280 not found!");
    // センサーなしでも続行（水温のみ記録）
  }

  // DS18B20 初期化
  ds18b20.begin();

  // 水位センサー初期化
  analogSetAttenuation(ADC_11db);
  pinMode(WATER_LEVEL_PIN, INPUT);

  // SDカード初期化
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("ERROR: SD card init failed!");
    goToSleep(INTERVAL_NORMAL);
    return;
  }

  // NTP時刻同期（Wi-Fi有効時のみ）
  #ifdef WIFI_SSID
  syncTime();
  #endif

  // CSVヘッダー書き込み（ファイルが存在しない場合）
  if (!SD.exists("/data.csv")) {
    File f = SD.open("/data.csv", FILE_WRITE);
    if (f) {
      f.println("timestamp,air_temp,humidity,pressure,water_temp,water_level");
      f.close();
    }
  }

  // --- 計測 ---
  readSensors();

  // --- CSV書き込み ---
  writeCSV();

  // --- スリープ間隔決定 ---
  int sleepSec = calcSleepInterval();
  Serial.printf("Next wake in %d seconds\n", sleepSec);

  // --- deep sleep ---
  goToSleep(sleepSec);
}

void loop() {
  // deep sleep 使用のため loop() には到達しない
}

// ================== センサー読み取り ==================

void readSensors() {
  // BME280
  airTemp = bme.readTemperature();
  humidity = bme.readHumidity();
  pressure = bme.readPressure() / 100.0;  // hPa

  // DS18B20 水温
  ds18b20.requestTemperatures();
  waterTemp = ds18b20.getTempCByIndex(0);
  if (waterTemp == DEVICE_DISCONNECTED_C) {
    waterTemp = -999;  // エラー値
  }

  // 水位センサー（アナログ値 → cm 変換）
  int rawAdc = analogRead(WATER_LEVEL_PIN);
  waterLevel = adcToWaterLevel(rawAdc);

  Serial.printf("Air: %.1f C, Hum: %.1f %%, Press: %.1f hPa\n", airTemp, humidity, pressure);
  Serial.printf("Water: %.1f C, Level: %.1f cm\n", waterTemp, waterLevel);
}

float adcToWaterLevel(int rawAdc) {
  // 4096段階 → 0-20cm にマッピング（センサー仕様に合わせて調整）
  float voltage = rawAdc * 3.3 / 4095.0;
  // 0.5V = 0cm, 4.5V = 20cm （典型的な圧力式水位センサー）
  // ESP32のADCは3.3Vまでなので分圧回路で調整が必要
  float level = (voltage - 0.5) * 20.0 / (3.3 - 0.5);
  if (level < 0) level = 0;
  if (level > 20) level = 20;
  return level;
}

// ================== CSV書き込み ==================

void writeCSV() {
  String timestamp = getTimestamp();

  File f = SD.open("/data.csv", FILE_APPEND);
  if (!f) {
    Serial.println("ERROR: Cannot open CSV file");
    return;
  }

  f.printf("%s,%.1f,%.1f,%.1f,%.1f,%.1f\n",
    timestamp.c_str(), airTemp, humidity, pressure, waterTemp, waterLevel);
  f.close();

  Serial.println("Data written to SD card");
}

String getTimestamp() {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    char buf[30];
    strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S+09:00", &timeinfo);
    return String(buf);
  }
  // NTP未同期の場合はミリ秒カウンタで代用
  return String("1970-01-01T00:00:00+09:00");
}

// ================== スリープ間隔計算 ==================

int calcSleepInterval() {
  // 現在時刻を取得
  struct tm timeinfo;
  int hour = 12;  // デフォルト
  if (getLocalTime(&timeinfo)) {
    hour = timeinfo.tm_hour;
  }

  // 深夜（22:00-05:00）→ 60分間隔
  if (hour >= 22 || hour < 5) {
    return INTERVAL_NIGHT;
  }

  // いもち病リスク高（気温20-28℃ かつ 湿度>85%）→ 10分間隔
  if (airTemp >= BLAST_TEMP_MIN && airTemp <= BLAST_TEMP_MAX && humidity > BLAST_HUMIDITY) {
    return INTERVAL_HIGH_RISK;
  }

  // 通常 → 30分間隔
  return INTERVAL_NORMAL;
}

// ================== deep sleep ==================

void goToSleep(int seconds) {
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  Serial.println("Entering deep sleep...");
  Serial.flush();
  esp_deep_sleep_start();
}

// ================== Wi-Fi / NTP ==================

#ifdef WIFI_SSID
void syncTime() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    configTime(JST_OFFSET, 0, NTP_SERVER);
    struct tm timeinfo;
    if (getLocalTime(&timeinfo, 5000)) {
      Serial.printf("NTP synced: %04d-%02d-%02d %02d:%02d:%02d\n",
        timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
        timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
    }
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
  } else {
    Serial.println("WiFi connection failed, skipping NTP sync");
  }
}
#endif
