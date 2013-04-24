from simtk.unit import sqrt, sum, Quantity
from simtk.unit import nanometer, kilojoules_per_mole
from simtk.openmm import CustomBondForce

class PullingForceWrapper(object):
    def __init__(self, pdb, k=1000*kilojoules_per_mole/nanometer**2):
        self.atom1, self.atom2, self._r0 = self.end_to_end_CA_distance(
            pdb.topology, pdb.getPositions(asNumpy=True))
        self.k = k.in_units_of(kilojoules_per_mole/nanometer**2)

        self.force = CustomBondForce("0.5*pullingforce_k*(r-pullingforce_r0)^2")
        self.force.addGlobalParameter('pullingforce_k', self.k)
        self.force.addGlobalParameter('pullingforce_r0', self._r0)
        self.force.addBond(self.atom1, self.atom2, [])


    def end_to_end_CA_distance(self, topology, positions):
        residues = list(topology.residues())
        # get the index of the first and last alpha carbons
        i1 = [a.index for a in residues[0].atoms() if a.name == 'CA'][0]
        i2 = [a.index for a in residues[-1].atoms() if a.name == 'CA'][0]

        # get the current distanc be between the two alpha carbons
        return i1, i2, sqrt(sum((positions[i1] - positions[i2])**2))
    
    def get_r0(self):
        return self._r0
    
    def set_r0(self, value, context):
        value = value.in_units_of(nanometer)
        self._r0 = value
        context.setParameter('pullingforce_r0', value)
        
    def add_to_system(self, system):
        system.addForce(self.force)
