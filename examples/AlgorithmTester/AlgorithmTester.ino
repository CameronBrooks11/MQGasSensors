//Include the library
#include <MQGasSensor.h>

// Wiring NOT required, only an arduino or esp8266 board

/*
    This program was made to test the algorithm that from the ratio obtains 
    the PPM (The core of this library), regardless of the plate in which the 
    result is executed should give a small error (ideally less than 5%), is 
    our way of self-evaluation, we tell the library what is the value of the 
    ratio and ask him to calculate the PPM and compare it against the value 
    that should really give, these values were taken from the same datasheet 
    with which the library was made.
*/

//Include the library
#include <MQGasSensor.h>
/************************Hardware Related Macros************************************/
#define         Board                   ("Arduino UNO")
#define         Pin                     (A3)  //Analog input 3 of your arduino
/***********************Software Related Macros************************************/
#define         Type                    ("MQ-3") //MQ3
#define         Voltage_Resolution      (5)
#define         ADC_Bit_Resolution      (10) // For arduino UNO/MEGA/NANO

//Declare Sensor
MQGasSensor mySensor(Board, Voltage_Resolution, ADC_Bit_Resolution, Pin, Type);

/*****************************Globals***********************************************/
double          ratio[4]                = {};
double          expectedValue[4]        = {};
double          calculatedValues[4]     = {};
double          error[4]                = {};
/**************************Object_Sensor********************************************/

void setup()
{
//Init serial port
  Serial.begin(9600);
  //init the sensor
  mySensor.init();

  //Print in serial monitor
  Serial.println("MQ2 to MQ9 - test program");
}

void loop()
{
    // Testing MQ2 LPG
    ratio[0] = 1.8; ratio[1] = 1.05; ratio[2] = 0.8; ratio[3] = 0.5;
    expectedValue[0] = 200; expectedValue[1] = 500; expectedValue[2] = 1000; expectedValue[3] = 3000;
    testSensor("MQ-2", 564.77, -2.151);

    // Testing MQ3 Benzene
    ratio[0] = 4; ratio[1] = 3; ratio[2] = 1; ratio[3] = 0.8;
    expectedValue[0] = 0.1; expectedValue[1] = 0.21; expectedValue[2] = 4; expectedValue[3] = 10;
    testSensor("MQ-3", 4.7380, -2.688);
    
    // Testing MQ4 CH4
    ratio[0] = 1.9; ratio[1] = 1; ratio[2] = 0.6; ratio[3] = 0.42;
    expectedValue[0] = 200; expectedValue[1] = 1000; expectedValue[2] = 5000; expectedValue[3] = 10000;
    testSensor("MQ-4", 990.22, -2.826);

    // Testing MQ5 H2
    ratio[0] = 1.8; ratio[1] = 1.3; ratio[2] = 0.8; ratio[3] = 0.68;
    expectedValue[0] = 200; expectedValue[1] = 500; expectedValue[2] = 3000; expectedValue[3] = 10000;
    testSensor("MQ-5", 1163.2, -3.892);

    // Testing MQ6 CH4
    ratio[0] = 2.6; ratio[1] = 1.9; ratio[2] = 1; ratio[3] = 0.8;
    expectedValue[0] = 200; expectedValue[1] = 500; expectedValue[2] = 2000; expectedValue[3] = 5000;
    testSensor("MQ-6", 2195.3, -2.507);

    // Testing MQ7 CO
    ratio[0] = 1.8; ratio[1] = 1; ratio[2] = 0.4; ratio[3] = 0.25;
    expectedValue[0] = 50; expectedValue[1] = 100; expectedValue[2] = 400; expectedValue[3] = 1000;
    testSensor("MQ-7", 98.691, -1.528);

    // Testing MQ8 H2
    ratio[0] = 2.6; ratio[1] = 1; ratio[2] = 0.21; ratio[3] = 0.03;
    expectedValue[0] = 500; expectedValue[1] = 1000; expectedValue[2] = 3000; expectedValue[3] = 10000;
    testSensor("MQ-8", 973.62, -0.6902);

    // Testing MQ9 LPG
    ratio[0] = 2; ratio[1] = 1.4; ratio[2] = 0.7; ratio[3] = 0.23;
    expectedValue[0] = 200; expectedValue[1] = 500; expectedValue[2] = 2000; expectedValue[3] = 10000;
    testSensor("MQ-9", 971.09, -2.140);

    // Testing MQ131 O3
    ratio[0] = 5; ratio[1] = 2; ratio[2] = 0.7; ratio[3] = 0.5;
    expectedValue[0] = 5; expectedValue[1] = 20; expectedValue[2] = 70; expectedValue[3] = 100;
    testSensor("MQ-131", 24.264, -1.117);

    // Testing MQ135 NH4
    ratio[0] = 2.6; ratio[1] = 1.9; ratio[2] = 1.1; ratio[3] = 0.75;
    expectedValue[0] = 10; expectedValue[1] = 20; expectedValue[2] = 100; expectedValue[3] = 200;
    testSensor("MQ-135", 102.29, -2.484);

    // Testing MQ303 Isobutano
    ratio[0] = 0.4; ratio[1] = 0.3; ratio[2] = 0.19; ratio[3] = 0.08;
    expectedValue[0] = 100; expectedValue[1] = 300; expectedValue[2] = 1000; expectedValue[3] = 10000;
    testSensor("MQ-303", 5.3977, -3.001);

    // Testing MQ309 CO
    ratio[0] = 6; ratio[1] = 5; ratio[2] = 4.3; ratio[3] = 4;
    expectedValue[0] = 1000; expectedValue[1] = 3000; expectedValue[2] = 5000; expectedValue[3] = 7000;
    testSensor("MQ-309", 1.6313e+06, -4.076);

    // Testing linear equation for MQ-4
    mySensor.setRegressionMethod(0); //_PPM =  pow(10, (log10(ratio)-b)/a)
    ratio[0] = 2.5; ratio[1] = 1.5; ratio[2] = 0.9; ratio[3] = 0.65;
    expectedValue[0] = 200; expectedValue[1] = 1000; expectedValue[2] = 5000; expectedValue[3] = 10000;
    testSensor("MQ-4", -0.318, 1.133);

    while(1);
}


void testSensor(String SensorName, float A, float B)
{
    mySensor.setA(A); mySensor.setB(B);
    calculatedValues[0] = mySensor.validateEcuation(ratio[0]);
    calculatedValues[1] = mySensor.validateEcuation(ratio[1]);
    calculatedValues[2] = mySensor.validateEcuation(ratio[2]);
    calculatedValues[3] = mySensor.validateEcuation(ratio[3]);
    error[0] = calculatePercentualError(expectedValue[0], calculatedValues[0]);
    error[1] = calculatePercentualError(expectedValue[1], calculatedValues[1]);
    error[2] = calculatePercentualError(expectedValue[2], calculatedValues[2]);
    error[3] = calculatePercentualError(expectedValue[3], calculatedValues[3]);
    
    Serial.print("Error(%) "); Serial.print(SensorName); Serial.print(": "); 
    Serial.print(error[0]); Serial.print(" ");
    Serial.print(error[1]); Serial.print(" ");
    Serial.print(error[2]); Serial.print(" ");
    Serial.print(error[3]); Serial.print(" | Calculated(PPM): ");
    Serial.print(calculatedValues[0]); Serial.print(" ");
    Serial.print(calculatedValues[1]); Serial.print(" ");
    Serial.print(calculatedValues[2]); Serial.print(" ");
    Serial.print(calculatedValues[3]); Serial.print(" | Expected(PPM): ");
    Serial.print(expectedValue[0]); Serial.print(" ");
    Serial.print(expectedValue[1]); Serial.print(" ");
    Serial.print(expectedValue[2]); Serial.print(" ");
    Serial.print(expectedValue[3]); Serial.println(" | ");
}

double calculatePercentualError(double expectedValue, double calculatedValue)
{
    // Return the diference between two measures
    return abs(calculatedValue-expectedValue)/expectedValue;
}
