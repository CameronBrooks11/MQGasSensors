/*
  MQGasSensor Library - reading an MQ4

  Demonstrates the use a MQ4 sensor.
  Library originally added 01 may 2019
  by Miguel A Califa, Yersson Carrillo, Ghiordy Contreras, Mario Rodriguez
 
  Added example
  modified 23 May 2019
  by Miguel Califa 

  Updated library usage
  modified 26 March 2020
  by Miguel Califa 

  Wiring:
  https://github.com/CameronBrooks11/MQGasSensors/blob/master/docs/img/MQ_Arduino.PNG
  Please make sure arduino A0 pin represents the analog input configured on #define pin

 This example code is in the public domain.

*/

//Include the library
#include <MQGasSensor.h>
/************************Hardware Related Macros************************************/
#define         Board                   ("Arduino UNO")
#define         Pin                     (A4)  //Analog input 4 of your arduino
/***********************Software Related Macros************************************/
#define         Type                    ("MQ-4") //MQ4
#define         Voltage_Resolution      (5)
#define         ADC_Bit_Resolution      (10) // For arduino UNO/MEGA/NANO
#define         RatioMQ4CleanAir        (4.4) //RS / R0 = 60 ppm 
/*****************************Globals***********************************************/
//Declare Sensor
MQGasSensor MQ4(Board, Voltage_Resolution, ADC_Bit_Resolution, Pin, Type);

void setup() {
  //Init the serial port communication - to debug the library
  Serial.begin(9600); //Init serial port

  //Set math model to calculate the PPM concentration and the value of constants
  MQ4.setRegressionMethod(1); //_PPM =  a*ratio^b

  
  /*****************************  MQ Init ********************************************/ 
  //Remarks: Configure the pin of arduino as input.
  /************************************************************************************/ 
  MQ4.init(); 
  /* 
    //If the RL value is different from 10K please assign your RL value with the following method:
    MQ4.setRL(10);
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
    MQ4.update(); // Update data, the arduino will read the voltage from the analog pin
    calcR0 += MQ4.calibrate(RatioMQ4CleanAir);
    Serial.print(".");
  }
  MQ4.setR0(calcR0/10);
  Serial.println("  done!.");
  
  if(isinf(calcR0)) {Serial.println("Warning: Connection issue, R0 is infinite (Open circuit detected) please check your wiring and supply"); while(1);}
  if(calcR0 == 0){Serial.println("Warning: Connection issue found, R0 is zero (Analog pin shorts to ground) please check your wiring and supply"); while(1);}
  /*****************************  MQ CAlibration ********************************************/ 

  Serial.println("*************** Values from MQ-4 **********************");
  Serial.println("|    LPG   |  CH4 |   CO    |    Alcohol    |   Smoke    |");  
}

void loop() {
  MQ4.update(); // Update data, the arduino will read the voltage from the analog pin
  float correctionFactor = 0; // Optional environmental correction
  
  /*
    Exponential regression:
  Gas     | a          | b
  alcohol | 4.7360e+10 | -13.79
  CH4     | 990.22     | -2.826
  CO      | 3.6362e+14 | -19.54
  H2      | 360990     | -5.634
  LPG     | 3736.2     | -3.121
  smoke   | 4.7509e+07 | -8.836
  From docs/coefficients.md, the fits to the mq-4-hanwei-2007 datasheet.
  */
  MQ4.setA(3736.2); MQ4.setB(-3.121); // Configure the equation to to calculate LPG concentration
  float LPG = MQ4.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  
  MQ4.setA(990.22); MQ4.setB(-2.826); // Configure the equation to to calculate CH4 concentration
  float CH4 = MQ4.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  
  MQ4.setA(3.6362e+14); MQ4.setB(-19.54); // Configure the equation to to calculate CO concentration
  float CO = MQ4.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  
  MQ4.setA(4.7360e+10); MQ4.setB(-13.79); // Configure the equation to to calculate alcohol concentration
  float Alcohol = MQ4.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  
  MQ4.setA(4.7509e+07); MQ4.setB(-8.836); // Configure the equation to to calculate smoke concentration
  float Smoke = MQ4.readSensor(false, correctionFactor); // Sensor will read PPM concentration using the model, a and b values set previously or from the setup
  
  Serial.print("|    "); Serial.print(LPG);
  Serial.print("    |    "); Serial.print(CH4);
  Serial.print("    |    "); Serial.print(CO);
  Serial.print("    |    "); Serial.print(Alcohol);
  Serial.print("    |    "); Serial.print(Smoke);
  Serial.println("    |");

  delay(500); //Sampling frequency
}