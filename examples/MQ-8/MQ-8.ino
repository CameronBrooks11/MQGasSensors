/*
  MQGasSensor Library - reading an MQ8

  Demonstrates the use a MQ8 sensor.
  Library originally added 01 may 2019
  by Miguel A Califa, Yersson Carrillo, Ghiordy Contreras, Mario Rodriguez
 
  Added example
  modified 23 May 2019
  by Miguel Califa 

  Updated library usage
  modified 26 March 2020
  by Miguel Califa 

  Wiring:
  https://github.com/CameronBrooks11/MQGasSensors/blob/main/docs/img/MQ_Arduino.PNG
  Please make sure arduino A0 pin represents the analog input configured on #define pin

 This example code is in the public domain.

*/

//Include the library
#include <MQGasSensor.h>

//Definitions
#define placa "Arduino UNO"
#define Voltage_Resolution 5
#define pin A0 //Analog input 0 of your arduino
#define type "MQ-8" //MQ8
#define ADC_Bit_Resolution 10 // For arduino UNO/MEGA/NANO
#define RatioMQ8CleanAir 69.5 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define calibration_button 13 //Pin to calibrate your sensor

//Declare Sensor
MQGasSensor MQ8(placa, Voltage_Resolution, ADC_Bit_Resolution, pin, type);

void setup() {
  //Init the serial port communication - to debug the library
  Serial.begin(9600); //Init serial port

  //Set math model to calculate the PPM concentration and the value of constants
  MQ8.setRegressionMethod(1); //_PPM =  a*ratio^b
  MQ8.setA(973.62); MQ8.setB(-0.6902); // Configure the equation to to calculate H2 concentration

  /*
    Exponential regression:
  Gas     | a          | b
  alcohol | 48842      | -1.691
  CH4     | 8.3559e+13 | -6.675
  CO      | 2.0195e+16 | -7.606
  H2      | 973.62     | -0.6902
  LPG     | 8.3383e+07 | -3.767
  From docs/coefficients.md, the fits to the mq-8-hanwei-2009 datasheet.
  */
  
  /*****************************  MQ Init ********************************************/ 
  //Remarks: Configure the pin of arduino as input.
  /************************************************************************************/ 
  MQ8.init();   
  /* 
    //If the RL value is different from 10K please assign your RL value with the following method:
    MQ8.setRL(10);
  */
  /*****************************  MQ CAlibration ********************************************/ 
  // Explanation: 
   // In this routine the sensor will measure the resistance of the sensor supposedly before being pre-heated
  // and on clean air (Calibration conditions), setting up R0 value.
  // We recommend executing this routine only on setup in laboratory conditions.
  // This routine does not need to be executed on each restart, you can load your R0 value from eeprom.
  // Acknowledgements: https://jayconsystems.com/blog/understanding-a-gas-sensor
  Serial.print("Calibrating please wait.");
  float calcR0 = 0;
  for(int i = 1; i<=10; i ++)
  {
    MQ8.update(); // Update data, the arduino will read the voltage from the analog pin
    calcR0 += MQ8.calibrate(RatioMQ8CleanAir);
    Serial.print(".");
  }
  MQ8.setR0(calcR0/10);
  Serial.println("  done!.");
  
  if(isinf(calcR0)) {Serial.println("Warning: Connection issue, R0 is infinite (Open circuit detected) please check your wiring and supply"); while(1);}
  if(calcR0 == 0){Serial.println("Warning: Connection issue found, R0 is zero (Analog pin shorts to ground) please check your wiring and supply"); while(1);}
  /*****************************  MQ CAlibration ********************************************/ 
  MQ8.serialDebug(true);
}

void loop() {
  MQ8.update(); // Update data, the arduino will read the voltage from the analog pin
  float correctionFactor = 0; // Optional environmental correction
  MQ8.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  MQ8.serialDebug(); // Will print the table on the serial port
  delay(500); //Sampling frequency
}