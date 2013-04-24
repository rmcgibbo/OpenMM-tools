import math
import simtk.unit as unit
from statedatareporter import StateDataReporter


class ElongationReporter(StateDataReporter):
    def __init__(self, file, reportInterval, index1, index2, **kwargs):
        super(ElongationReporter, self).__init__(file, reportInterval, **kwargs)
        self._index1 = index1
        self._index2 = index2
        self._needsPositions = True

    def _headers(self):
        headers = super(ElongationReporter, self)._headers()
        headers.append('%s-%s Elongation (nm)' % (self._index1, self._index2))
        return headers
    
    def _constructReportValues(self, simulation, state):
        values = super(ElongationReporter, self)._constructReportValues(simulation, state)
        values.append(self._calculateElongation(state))
        return values
    
    def _calculateElongation(self, state):
        positions = state.getPositions(asNumpy=True)
        displacement = positions[self._index1] - positions[self._index2]
        distance = unit.sqrt(unit.sum(displacement**2))
        return distance.value_in_unit(unit.nanometers)
        