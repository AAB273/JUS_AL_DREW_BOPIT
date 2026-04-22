#include <Adafruit_LSM6DSOX.h>
#include <Wire.h>
#include "mlc.h"

Adafruit_LSM6DSOX sox;

#define START_PIN 4
#define BAUD_RATE 9600
#define LSM_ADDR 0x6A
#define MLC0_SRC 0x70
int signal = 0;
int signal_sent = 0;
int start_signal_sent = 0;


void writeRegister(uint8_t reg, uint8_t val) { //I2C, it requires the Register value first, then writes the data into said register.
    Wire.beginTransmission(LSM_ADDR);
    Wire.write(reg);
    Wire.write(val);
    Wire.endTransmission();
}

void readMLC() {
    // Enable embedded functions access
    writeRegister(0x01, 0x80);
    
    Wire.beginTransmission(LSM_ADDR);
    Wire.write(MLC0_SRC);
    Wire.endTransmission(false);
    Wire.requestFrom(LSM_ADDR, 1);
    uint8_t result = Wire.read();
    
    // Disable embedded functions access
    writeRegister(0x01, 0x00);
    
    if (result == 0x00) signal = 1;
    else if (result == 0x04) signal = 2;
    else if (result == 0x08) signal = 0;
    else Serial.println(result);
}


void setup() {
    Serial.begin(BAUD_RATE);  // Hardware UART to Bluefruit
    delay(1000);

    // Put Bluefruit in data mode (exit AT command mode)
    // Serial.println("+++");
    delay(500);
    if (!sox.begin_I2C()) {
      while (1);  // hang if IMU not found
    }

    sox.setAccelRange(LSM6DS_ACCEL_RANGE_2_G);
    sox.setGyroRange(LSM6DS_GYRO_RANGE_250_DPS);
    sox.setAccelDataRate(LSM6DS_RATE_104_HZ);
    sox.setGyroDataRate(LSM6DS_RATE_104_HZ);

    pinMode(START_PIN, INPUT);

    for(int i = 0; i < MEMS_CONF_ARRAY_LEN(mlc_conf_0); i++){
      writeRegister(mlc_conf_0[i].address, mlc_conf_0[i].data);
    }
}

void loop() {
    sensors_event_t accel, gyro, temp;
    sox.getEvent(&accel, &gyro, &temp);
    readMLC();

    if (signal == 0){
      signal_sent = 0;
    }
    else if (signal == 1 && !signal_sent){
        Serial.println("ATTACK");
        start_signal_sent = 0;
        signal_sent = 1;
    }
    else if (signal == 2 && !signal_sent){
        Serial.println("BLOCK");
        start_signal_sent = 0;
        signal_sent = 1;
    }
    if (digitalRead(START_PIN) && !start_signal_sent){
        Serial.println("START");
        start_signal_sent = 1;
    }
    // CSV format: ax,ay,az,gx,gy,gz
    // if(digitalRead(START_PIN) == HIGH){
    // Serial.print(sensor.rawAccX * 1000, 4);  Serial.print(",");
    // Serial.print(sensor.rawAccY * 1000, 4);  Serial.print(",");
    // Serial.print(sensor.rawAccZ * 1000, 4);  Serial.print(",");
    // Serial.print(sensor.rawGyroX * 1000, 4); Serial.print(",");
    // Serial.print(sensor.rawGyroY * 1000, 4); Serial.print(",");
    // Serial.println(sensor.rawGyroZ * 1000, 4);
    // }

  delay(100);  // ~2.5Hz
}
