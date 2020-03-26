/*
  MQUnifiedsensor Library - smokeDetector
  
  Demonstrates the use a MQ2 sensor.
  Library originally added 01 may 2019
  by Miguel A Califa, Yersson Carrillo, Ghiordy Contreras, Mario Rodriguez
 
  Added example
  modified 23 May 2019
  by Miguel Califa 

 This example code is in the public domain.

*/

//Include the library
#include <MQUnifiedsensor.h>

//Definitions
#define placa "Arduino UNO"
#define Voltage_Resolution 5
#define pin A0 //Analog input 0 of your arduino
#define type "MQ-4" //MQ4
#define ADC_Bit_Resolution 10 // For arduino UNO/MEGA/NANO
//#define calibration_button 13 //Pin to calibrate your sensor

//Declare Sensor
MQUnifiedsensor MQ4(placa, Voltage_Resolution, ADC_Bit_Resolution, pin, type);

void setup() {
  //Init serial port
  Serial.begin(115200);
  //Set math model to calculate the PPM concentration and the value of constants
  MQ4.setRegressionMethod("Exponential"); //_PPM =  a*ratio^b
  MQ4.setA(30000000); MQ4.setB(-2.786); // Configurate the ecuation values to get CH4 concentration
  /*
    Exponential regression:
  Gas    | a      | b
  LPG    | 3811.9 | -3.113
  CH4    | 1012.7 | -2.786
  CO     | 200000000000000 | -19.05
  Alcohol| 60000000000 | -14.01
  smoke  | 30000000 | -8.308
  */
  /*****************************  MQ Init ********************************************/ 
  //Remarks: Configure the pin of arduino as input.
  /************************************************************************************/ 
  MQ4.init(); 
}

  void loop() {
  /*****************************  MQReadSensor  ****************************************
  Input:   Gas - Serial print flag
  Output:  Value in PPM
  Remarks: This function use readPPM to read the value in PPM the gas in the air.
  ************************************************************************************/ 
  //Read the sensor and print in serial port
  //Lecture will be saved in lecture variable
  int lecture =  MQ4.readSensor(); // Return smoke concentration
  Serial.print("MQ4 smoke ppm lecture: ");
  Serial.print(lecture);
  Serial.println(" ppm");
  delay(400);
}
