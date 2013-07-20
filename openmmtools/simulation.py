import inspect
import threading
import warnings
import weakref

from simtk import unit
from simtk import openmm as mm

class StepFuture(object):
    def __init__(self, thread):
        self._thread_ref = weakref.ref(thread)
        
    def isComplete(self):
        "Have the requested number of steps been completed?"
        thread = self._thread_ref()
        if thread is None:
            return
        return not thread.is_alive()
    
    def wait(self, timeout=None):
        "Block, waiting for the async steps to be completed."
        thread = self._thread_ref()
        if thread is None:
            return
        thread.join(timeout=timeout)


class AsyncSimulation(object):
    @property
    def context(self):
        if self.isBusy():
            warnings.warn('Modification of this context before asyncsteps '
                          'are complete will lead to undefined behavior')
        return self._context

    @context.setter
    def context(self, value):
        self._context = context

    @property
    def integrator(self):
        if self.isBusy():
            warnings.warn('Modification of this integrator before asyncsteps '
                          'are complete will lead to undefined behavior')
        return self._integrator

    @integrator.setter
    def integrator(self, value):
        self._integrator = integrator

    def isBusy(self):
        return self._isBusy

    def wait(self, timeout=None):
        "Block, waiting for any async steps to be completed."
        if self._thread is None:
            return
        self._thread.join(timeout=timeout)

    def __init__(self, topology, system, integrator, platform=None, platformProperties=None):
        """Create a Simulation.

        Parameters:
         - topology (Topology) A Topology describing the the system to simulate
         - system (System) The OpenMM System object to simulate
         - integrator (Integrator) The OpenMM Integrator to use for simulating the System
         - platform (Platform=None) If not None, the OpenMM Platform to use
         - platformProperties (map=None) If not None, a set of platform-specific properties to pass
           to the Context's constructor
        """
        ## The Topology describing the system being simulated
        self.topology = topology
        ## The System being simulated
        self.system = system
        ## The Integrator used to advance the simulation
        self._integrator = integrator
        ## The index of the current time step
        self.currentStep = 0
        ## A list of reporters to invoke during the simulation
        self.reporters = []
        if platform is None:
            ## The Context containing the current state of the simulation
            self._context = mm.Context(system, integrator)
        elif platformProperties is None:
            self._context = mm.Context(system, integrator, platform)
        else:
            self._context = mm.Context(system, integrator, platform, platformProperties)

        ## The thread in which nonblocking steps are carried out
        self._thread = None
        self._isBusy = False


    def minimizeEnergy(self, tolerance=1*unit.kilojoule/unit.mole, maxIterations=0):
        """Perform a local energy minimization on the system.

        Parameters:
         - tolerance (energy=1*kilojoule/mole) The energy tolerance to which the system should be minimized
         - maxIterations (int=0) The maximum number of iterations to perform.  If this is 0, minimization is continued
           until the results converge without regard to how many iterations it takes.
        """
        mm.LocalEnergyMinimizer.minimize(self._context, tolerance, maxIterations)

    def asyncstep(self, steps, callback=None):
        """Nonblocking version of step(), to advance the simulation by integrating
        a specified number of time steps.

        This method immediately returnes a Future object, which is a "promise"
        that the steps will be completed. To block, waiting for the steps
        to complete, you can call wait() on the future. You can also query
        the future, asking if the steps have been completed, by calling
        isComplete() on it.
        """
        if self._isBusy:
            warnings.warn('This simulation cannot simultaniously execute '
                          'more than one asynchronous step. Waiting for '
                          'the previous call to finish (this migh take '
                          'a while)...')
            self._thread.join()
            # Could use a lock instead?

        if callback is None:
            callback = lambda: None
        if not callable(callback):
            raise ValueError('callback must be callable')
        
        argspec = inspect.getargspec(callback)
        nargs = len(argspec.args) - (len(argspec.defaults) if argspec.defaults is not None else 0)
        if nargs > 0:
            raise ValueError('callback must be callable with 0 arguments')

        def run():
            self.step(steps)
            callback()

        self._thread = threading.Thread(target=run)
        self._thread.start()
        return StepFuture(self._thread)

    def step(self, steps):
        """Advance the simulation by integrating a specified number of time steps."""
        if self._isBusy:
            raise ValueError('This simulation is already enganged in a step()')

        self._isBusy = True

        # This code is copied from Simulation, but changed to
        # reference self._context and self._integrator directly, so that
        # it doesn't throw warnings.
        try:
            stepTo = self.currentStep+steps
            nextReport = [None]*len(self.reporters)
            while self.currentStep < stepTo:
                nextSteps = stepTo-self.currentStep
                anyReport = False
                for i, reporter in enumerate(self.reporters):
                    nextReport[i] = reporter.describeNextReport(self)
                    if nextReport[i][0] > 0 and nextReport[i][0] <= nextSteps:
                        nextSteps = nextReport[i][0]
                        anyReport = True
                stepsToGo = nextSteps
                while stepsToGo > 10:
                    self._integrator.step(10) # Only take 10 steps at a time, to give Python more chances to respond to a control-c.
                    stepsToGo -= 10
                self._integrator.step(stepsToGo)
                self.currentStep += nextSteps
                if anyReport:
                    getPositions = False
                    getVelocities = False
                    getForces = False
                    getEnergy = False
                    for reporter, next in zip(self.reporters, nextReport):
                        if next[0] == nextSteps:
                            if next[1]:
                                getPositions = True
                            if next[2]:
                                getVelocities = True
                            if next[3]:
                                getForces = True
                            if next[4]:
                                getEnergy = True
                    state = self._context.getState(getPositions=getPositions, getVelocities=getVelocities, getForces=getForces, getEnergy=getEnergy, getParameters=True, enforcePeriodicBox=(self.topology.getUnitCellDimensions() is not None))
                    for reporter, next in zip(self.reporters, nextReport):
                        if next[0] == nextSteps:
                            reporter.report(self, state)
        finally:
            self._isBusy = False
