/*
  MQGasSensor Library - calibrating an MQ2

  Demonstrates the use a MQ2 sensor.
  Library originally added 01 may 2019
  by Miguel A Califa, Yersson Carrillo, Ghiordy Contreras, Mario Rodriguez
 
  Added example
  modified 27 May 2019
  by Miguel Califa 

 This example code is in the public domain.

*/

//Include the library
#include <MQGasSensor.h>
/************************Hardware Related Macros************************************/
#define         Board                   ("Arduino UNO")
#define         Pin                     (A2)  //Analog input 2 of your arduino
/***********************Software Related Macros************************************/
#define         Type                    ("MQ-2") //MQ2
#define         Voltage_Resolution      (5)
#define         ADC_Bit_Resolution      (10) // For arduino UNO/MEGA/NANO

/*****************************Globals***********************************************/
double          alcoholPPM          =   (0);
//Defaults, uncomment if you need
#define RatioMQ2CleanAir 9.51 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ3CleanAir 59.9 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ4CleanAir 4.43 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ5CleanAir 6.49 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ6CleanAir 9.86 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ7CleanAir 26.1 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ8CleanAir 69.5 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ9CleanAir 9.75 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ131CleanAir (1.0 / 12.0) // Rs/R0 in clean air: the MQ-131 figure gives R0/Rs 12.0
//#define RatioMQ135CleanAir 3.60 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ303CleanAir 1 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
//#define RatioMQ309CleanAir 11.1 // Rs/R0 in clean air, from the datasheet's AIR line (docs/coefficients.md)
unsigned long contador = 0;
/**************************Object_Sensor********************************************/

MQGasSensor MQ2(Board, Voltage_Resolution, ADC_Bit_Resolution, Pin, Type);

void setup() {
  //Init serial port
  Serial.begin(115200);
  MQ2.setRegressionMethod(1); //_PPM =  a*ratio^b
  MQ2.setA(564.77); MQ2.setB(-2.151); // Configure the equation to to calculate LPG concentration
  /* 
    //If the RL value is different from 10K please assign your RL value with the following method:
    MQ3.setRL(10);
  */
  //init the sensor
  MQ2.init(); 
  //Print in serial monitor
  Serial.println("MQ2 - Calibracion");
  Serial.println("Note - Make sure you are in a clean room and the sensor has pre-heated almost 4 hours");
  Serial.println("Autonumeric | lecture (R0)");
}

void loop() {
  MQ2.update();
  //Read the sensor and print in serial port
  float lecture =  MQ2.calibrate(RatioMQ2CleanAir);
  //Print in serial monitor
  Serial.print(contador);
  Serial.print(" | ");
  Serial.println(lecture);
  //Increment counter
  contador++;
  //Wait to measure next sample
  delay(400);
}
