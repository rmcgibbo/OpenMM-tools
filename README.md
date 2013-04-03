OpenMM-tools
============
Some extra tools for OpenMM

- `WebReporter`: A reporter object that plots summary statistics dynamically (as they're computed) in
   your browser using `tornado`, websockets, and the google charts API.

![Screenshot](http://i.imgur.com/IX3ryiN.png)

Example Usage:

```
from openmmtools import webreporter

[... setup simulation ...]

webreporter = WebReporter(report_interval=200, observables=['total', 'temperature', 'kinetic', 'potential'])
simulation.reporters.append(webreporter)
simulation.step(...)
```
