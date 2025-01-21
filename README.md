<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

# MQGasSensors

A robust Arduino library for interfacing with MQ-series gas sensors, enabling accurate gas concentration measurements with ease. Supports calibration, resistance calculations, and real-time gas concentration derivation for various gases.

## Features

- Preheat and baseline calibration for MQ sensors.
- Calculate sensor resistance (Rs) and baseline resistance (R0).
- Derive gas concentration (PPM) using datasheet-provided regression models.
- Support for multiple MQ-series sensors (e.g., MQ-2, MQ-7, MQ-135).
  Works with Arduino, Genuino, ESP8266, ESP-32 boards whose references are MQ2, MQ3, MQ4, MQ5, MQ6, MQ7, MQ8, MQ9, MQ131, MQ135, MQ303A, MQ309A.

<!-- TABLE OF CONTENTS -->

## Table of Contents

- [Getting Started](#Getting-Started)
- [Wiring](#Wiring)
  - [Sensor](#Sensor)
  - [Arduino](#Arduino)
  - [ESP8266 or ESP-32](#ESP8266-ESP32)
- [User Manual](#Manuals)
- [Sensor manufacturers](#Sensor-manufacturers)
- [Contributing](#Contributing)
- [Authors](#Authors)

## Getting Started

```
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
// Setup
MQ4.setRegressionMethod("Exponential"); //_PPM =  a*ratio^b
MQ4.setA(1012.7); MQ4.setB(-2.786); // Configure the equation to to calculate CH4 concentration
MQ4.setR0(3.86018237); // Value getted on calibration
// Loop
MQ4.init();
MQ4.update();
float ppmCH4 = MQ4.readSensor();
```

## Usage

## Hardware Setup

### Sensor Considerations

**Important points:**

Sensor pins:

- VCC -> 5V Power supply (+) wire
- GND -> GND Ground (-) wire
- AO -> Analog Output of the sensor

![Wiring_MQSensor](docs/static/img/Points_explanation.jpeg)

Sensor characteristics:

- Find your RL Value in KOhms
  - From datasheet of your sensor
- Find your RS/R0 (Clean air - English)
  - Note: RS/R0 is equal to Ratio variable on the program
  - From datasheet of your sensor

![Graph from datasheet](docs/static/img/Graph_Explanation.jpeg)


![Arduino_Wiring_MQSensor](docs/static/img/MQ_Arduino.PNG)

### Wiring Hookup

#### MQ-7 / MQ-309A

**Note**: MQ-7 and MQ-309 needs two different voltages for heater, they can be supplied by PWM and DC Signal controlled by your controller, another option is to use two different power sources, you should use the best option for you, next i will show the PWM option and on the examples this will be the way.

![MQ-7_MQ-309](docs/static/img/MQ-309_MQ-7.PNG)

#### ESP Wiring

![ESP8266_Wiring_MQSensor](docs/static/img/MQ_ESP8266.PNG)

#### ESP32 WROOM 32D

The ESP32 WROOM 32D does not need an external power supply. A0 goes to PIN36, Vcc to 3v3 and GND to any GND port on the board. Check the **ESP2/ESP32_WROOM_32** folder to fixing the measuring issue when connecting to wifi.

## Serial debug (optional)

If your sensor is an **MQ2** (Same for others sensors):

- To enable on setup wrote

```
MQ2.serialDebug(true);
```

- And on Loop Wrote

```
MQ2.serialDebug();
```

- Result:

![Serial debug output](https://github.com/CameronBrooks11/MQGasSensors_Docs/blob/master/static/img/Serial_Mon_Explanation.jpeg?raw=true)

## Sensor Manufacturers

| Sensor  | Manufacture        | URL Datasheet                                                                                                   |
| ------- | ------------------ | --------------------------------------------------------------------------------------------------------------- |
| MQ-2    | HANWEI Electronics | [datasheet](https://www.pololu.com/file/0J309/MQ2.pdf)                                                          |
| MQ-3    | HANWEI Electronics | [datasheet](https://www.sparkfun.com/datasheets/Sensors/MQ-3.pdf)                                               |
| MQ-4    | HANWEI Electronics | [datasheet](https://www.sparkfun.com/datasheets/Sensors/Biometric/MQ-4.pdf)                                     |
| MQ-5    | HANWEI Electronics | [datasheet](https://www.parallax.com/sites/default/files/downloads/605-00009-MQ-5-Datasheet.pdf)                |
| MQ-6    | HANWEI Electronics | [datasheet](https://www.sparkfun.com/datasheets/Sensors/Biometric/MQ-6.pdf)                                     |
| MQ-7    | HANWEI Electronics | [datasheet](https://www.sparkfun.com/datasheets/Sensors/Biometric/MQ-7.pdf)                                     |
| MQ-8    | HANWEI Electronics | [datasheet](https://dlnmh9ip6v2uc.cloudfront.net/datasheets/Sensors/Biometric/MQ-8.pdf)                         |
| MQ-9    | HANWEI Electronics | [datasheet](http://www.haoyuelectronics.com/Attachment/MQ-9/MQ9.pdf)                                            |
| MQ-131  | HANWEI Electronics | [datasheet](http://www.sensorsportal.com/DOWNLOADS/MQ131.pdf)                                                   |
| MQ-135  | HANWEI Electronics | [datasheet](https://www.electronicoscaldas.com/datasheet/MQ-135_Hanwei.pdf)                                     |
| MQ-136  | HANWEI Electronics | [datasheet](https://github.com/CameronBrooks11/MQGasSensors_Docs/blob/master/Datasheets/MQ136%20-%20Hanwei.pdf) |
| MQ-303A | HANWEI Electronics | [datasheet](http://www.kosmodrom.com.ua/pdf/MQ303A.pdf)                                                         |
| MQ-309A | HANWEI Electronics | [datasheet](http://www.sensorica.ru/pdf/MQ-309A.pdf)                                                            |


Review WPDigitalizer [folder](docs/WPDigitalizer/README.md) [website](https://automeris.io/WebPlotDigitizer/)

### Installing

Clone this repository into your desktop machine

```
git clone https://github.com/CameronBrooks11/MQGasSensors
```

## Running the tests

Use calibration systems if you have several sensors that read the same gas.

### Break down into end to end tests

These tests can re-adjust values defined previously and you can contribute to improve conditions or features obtained from particular scenes.

```
Examples/MQ-3
```

### And coding style tests

These tests may generate statistics validation using descriptive tools for quantitative variables.

```
Examples/MQ-board.ino
```

## Built With

- [Data sheets](https://github.com/CameronBrooks11/MQGasSensors_Docs/tree/master/Datasheets) - Curves and behavior for each sensor, using logarithmic graphs.
- [Main purpose](https://github.com/CameronBrooks11/MQGasSensors_Docs/blob/master/static/img/bg.jpg) - Every sensor has high sensibility for a specific gas or material.

## Contributing

Please read [CONTRIBUTING.md](https://github.com/CameronBrooks11/MQGasSensors/blob/master/CONTRIBUTING.md) for details on the code of conduct, and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgment

This library is a fork of the original **MQSensorsLib** library, created and maintained by Miguel Angel Califa Urquiza, Ghiordy Contreras Contreras, and Yerson Ramiro Carrillo Amado. Their work laid the foundation for interfacing MQ-series gas sensors with Arduino, and we acknowledge their significant contributions to the community.

Original repository: [miguel5612/MQSensorsLib](https://github.com/miguel5612/MQSensorsLib)  
Cite their work as:

- Califa Urquiza, Miguel Angel, Contreras Contreras, Ghiordy, & Carrillo Amado, Yerson Ramiro. (2019, September 3). CameronBrooks11/MQGasSensors: Arduino Preview V1.03 (Version 1.0.3). Zenodo. [http://doi.org/10.5281/zenodo.3384301](http://doi.org/10.5281/zenodo.3384301)

### Attribution

- **Authors**
  - _Miguel A. Califa U._ - [_GitHub_](https://github.com/CameronBrooks11) - [CV](https://scienti.colciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000050477)
  - _Ghiordy F. Contreras C._ - [_GitHub_](https://github.com/Ghiordy) - [CV](https://scienti.colciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000050476)
  - _Yersson R. Carrillo A._ - [_GitHub_](https://github.com/Yercar18/Dronefenix) - [CV](https://scienti.colciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0001637655)
- **Contributors**
  - _Andres A. Martinez._ - [_Github_](https://github.com/andresmacsi) - [CV](https://www.linkedin.com/in/andr%C3%A9s-acevedo-mart%C3%ADnez-73ab35185/?originalSubdomain=co)
  - _Juan A. Rodríguez._ - [_Github_](https://github.com/Obiot24)
  - _Mario A. Rodríguez O._ - [_GitHub_](https://github.com/MarioAndresR) - [CV](https://scienti.colciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000111304)
- **Reviewers**
- _PhD. Jacipt A Ramón V._ - [CV](https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000512702)

See also the list of [contributors](https://github.com/miguel5612/MQSensorsLib/graphs/contributors) who participated in the original project.

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->

[contributors-shield]: https://img.shields.io/github/contributors/CameronBrooks11/MQGasSensors.svg?style=flat-square
[contributors-url]: https://github.com/CameronBrooks11/MQGasSensors/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/CameronBrooks11/MQGasSensors.svg?style=flat-square
[forks-url]: https://github.com/CameronBrooks11/MQGasSensors/network/members
[stars-shield]: https://img.shields.io/github/stars/CameronBrooks11/MQGasSensors.svg?style=flat-square
[stars-url]: https://github.com/CameronBrooks11/MQGasSensors/stargazers
[issues-shield]: https://img.shields.io/github/issues/CameronBrooks11/MQGasSensors.svg?style=flat-square
[issues-url]: https://github.com/CameronBrooks11/MQGasSensors/issues
[license-shield]: https://img.shields.io/github/license/CameronBrooks11/MQGasSensors.svg?style=flat-square
[license-url]: https://github.com/CameronBrooks11/MQGasSensors/blob/master/LICENSE.txt
