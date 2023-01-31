# Artifex-OPMpy
## A python package to connect to the [Artifex OPM500 optical power monitor](https://artifex-engineering.com/de/instrumente/optische-leistungsmonitore/opm500/)

## Needs (tested with):
```
regex       ( 2021.4.4 )
numpy       ( 1.20.1 )
pyserial    ( 3.5 )
```
It is currently WIP, however in a usable state (wavelength calibration and power can be retrieved)

## Known bugs: 
- identify() takes too long to answer, therefore the answer is partially left in the input buffer and read by other methods.
  - Workaround: don't call identify()
  
## How to use 
Check main()
