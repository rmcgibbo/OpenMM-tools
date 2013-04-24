OpenMM-tools
============
_Additional Tools for the OpenMM toolkit for molecular simulation_

- `WebReporter`: A reporter object that plots the temperature, energy, and other summary statistics
   **LIVE** (i.e. as they're computed) in your browser using [tornado](http://www.tornadoweb.org/en/stable/),
   [websockets](http://slides.html5rocks.com/#web-sockets), and the google [charts API](https://developers.google.com/chart/).

![Screenshot](http://i.imgur.com/IX3ryiN.png)

Example Usage:

```
from openmmtools import webreporter

[... setup simulation ...]

webreporter = WebReporter(report_interval=200, observables=['total', 'temperature', 'kinetic', 'potential'])
simulation.reporters.append(webreporter)
simulation.step(...)
```
