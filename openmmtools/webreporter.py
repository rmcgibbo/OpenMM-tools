"""WebReporter: OpenMM Reporter for live plotting of summary statistics
in the browser, using tornado, websockets, and google charts.

Authors: Robert McGibbon
License: GPLv3
"""
##############################################################################
# Imports
##############################################################################

# stdlib
import sys
import Queue as queue
import uuid
import threading
import json
import inspect
import webbrowser

# openmm
from simtk.unit import (dalton, kilojoules_per_mole, nanometer,
                        gram, item, picosecond)
import simtk.openmm as mm

# external
try:
    import tornado.ioloop
    import tornado.web
    import tornado.websocket
except ImportError:
    print '#'*70
    print 'WebReporter requires the python "tornado" package.'
    print 'It can be installed with:'
    print '    sudo easy_install tornado'
    print ''
    print 'For details, see http://www.tornadoweb.org/en/stable/#installation'
    print '#'*70
    sys.exit(1)


__all__ = ['WebReporter']


##############################################################################
# Classes
##############################################################################


class WebReporter(object):
    def __init__(self, report_interval, observables=None, port=5000, open_browser=True):
        """Create a WebReporter
        
        Parameters
        ----------
        report_interval : int
            The interval (in time steps) at which to plot frames
        observables : list of strings
            A list of the observables you wish to plot. You may select from:
            'kineticEnergy', 'potentialEnergy', 'totalEnergy', 'temperature',
            'volume', or 'density'. You may also use a custom observable,
            as long as you register its functional form with the
            register_observable method.
        port : int
            The port to run this webservice on.
        open_browser : bool
            Boot up your browser and navigate to the page.
        """
        self.port = int(port)
        if not (1000 < self.port < 65535):
            raise ValueError('Port must be between 1000 and 65535')
        
        self.report_interval = int(report_interval)
        self._has_initialized = False
        
        if observables is None:
            self.observables = []
        elif isinstance(observables, basestring):
            self.observables = [observables]
        else:
            self.observables = list(observables)

        if open_browser:
            webbrowser.open('http://localhost:' + str(self.port))
            
        # create the dispatch table with the methods that we currently
        # have, keyed by a se
        self.dispatch = {
            'KE': ('Kinetic Energy [kJ/mol]', self._kinetic_energy),
            'kinetic': ('Kinetic Energy [kJ/mol]', self._kinetic_energy),
            'kinetic_energy': ('Kinetic Energy [kJ/mol]', self._kinetic_energy),
            'kinetic energy': ('Kinetic Energy [kJ/mol]', self._kinetic_energy),
            'kineticEnergy': ('Kinetic Energy [kJ/mol]', self._kinetic_energy),

            'V': ('Potential Energy [kJ/mol]', self._potential_energy),
            'potential': ('Potential Energy [kJ/mol]', self._potential_energy),
            'potential_energy': ('Potential Energy [kJ/mol]', self._potential_energy),
            'potential energy': ('Potential Energy [kJ/mol]', self._potential_energy),
            'potentialEnergy': ('Potential Energy [kJ/mol]', self._potential_energy),

            'total': ('Total Energy [kJ/mol]', self._total_energy),
            'total_energy': ('Total Energy [kJ/mol]', self._total_energy),
            'totalEnergy': ('Total Energy [kJ/mol]', self._total_energy),
            'total energy': ('Total Energy [kJ/mol]', self._total_energy),

            'T': ('Temperature [K]', self._temperature),
            'temp': ('Temperature [K]', self._temperature),
            'temperature': ('Temperature [K]', self._temperature),
            'vol': ('Volume [nm^3]', self._volume),
            'volume': ('Volume [nm^3]', self._volume),

            'rho': ('Density [g/mL]', self._density),
            'density': ('Density [g/mL]', self._density),
        }

        # start the webserver in another thread
        t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()

    def register_observable(self, key, function=None, label=None):
        """Register a new observable
        
        Parameters
        ----------
        key : string
            The name of this obervable.
        function : callable, optional
            If you're registering a NEW observable that WebReporter doesn't
            know about by default, supply the function used to compute it.
            The function should be a callable that accepts a single argument,
            the State, and returns a float.
        label : string, optional
            If you're registering a NEW observable, this is the string that
            will be used as the axis label for the graph.
        """

        if function is not None:
            n_args = len(inspect.getargspec(function)[0])
            if n_args != 1:
                raise ValueError('function must be a callable taking 1 argumente')

            if label is None:
                label = key
            self.dispatch[key] = (label, function)


        if not key in self.dispatch.keys():
            raise ValueError('"%s" is not a valid observable. You may '
                'choose from %s' % (key, ', '.join('"' + e + '"' for e in self.dispatch.keys())))
        self.observables.append(key)

    def describeNextReport(self, simulation):
        steps = self.report_interval - simulation.currentStep%self.report_interval
        return (steps, True, False, False, True)

    def report(self, simulation, state):
        if not self._has_initialized:
            self._initialize_constants(simulation)
            self._has_initialized = True

        message = dict(self.build_message(simulation, state))
        tornado.ioloop.IOLoop.instance().add_callback(lambda: _WSHandler.broadcast(message))

    def build_message(self, simulation, state):
        yield ('Time [ps]', state.getTime().value_in_unit(picosecond))

        for k in self.observables:
            try:
                name, func = self.dispatch[k]
            except KeyError:
                raise ValueError('"%s" is not a valid observable. You may '
                    'choose from %s' % (k, ', '.join('"' + e + '"' for e in self.dispatch.keys())))

            yield (name, func(state))

    def _kinetic_energy(self, state):
        return state.getKineticEnergy().value_in_unit(kilojoules_per_mole)

    def _potential_energy(self, state):
        return state.getPotentialEnergy().value_in_unit(kilojoules_per_mole)

    def _total_energy(self, state):
        return (state.getKineticEnergy()+state.getPotentialEnergy()).value_in_unit(kilojoules_per_mole)

    def _temperature(self, state):
        return (2*state.getKineticEnergy()/(self._dof*0.00831451)).value_in_unit(kilojoules_per_mole)

    def _volume(self, state):
        box = state.getPeriodicBoxVectors()
        volume = box[0][0]*box[1][1]*box[2][2]
        return volume.value_in_unit(nanometer**3)

    def _density(self, state):
        box = state.getPeriodicBoxVectors()
        volume = box[0][0]*box[1][1]*box[2][2]
        return (self._totalMass/volume).value_in_unit(gram/item/milliliter)

    def _initialize_constants(self, simulation):
        """Initialize a set of constants required for the reports

        Parameters
        - simulation (Simulation) The simulation to generate a report for
        """
        system = simulation.system
        # Compute the number of degrees of freedom.
        dof = 0
        for i in range(system.getNumParticles()):
            if system.getParticleMass(i) > 0*dalton:
                dof += 3
        dof -= system.getNumConstraints()
        if any(type(system.getForce(i)) == mm.CMMotionRemover for i in range(system.getNumForces())):
            dof -= 3
        self._dof = dof

        # Compute the total system mass.
        self._totalMass = 0*dalton
        for i in range(system.getNumParticles()):
            self._totalMass += system.getParticleMass(i)

    def _run(self):
        """Run the tornado webserver. This should be run in a separate thread,
        as it'll block"""

        tornado.web.Application([
            (r'/', _MainHandler),
            (r'/ws', _WSHandler),
        ]).listen(self.port)
        tornado.ioloop.IOLoop.instance().start()


class _WSHandler(tornado.websocket.WebSocketHandler):
    clients = {}
    
    def open(self):
        self.id = uuid.uuid4()
        self.clients[self.id] = self

    def on_close(self):
        del self.clients[self.id]

    @classmethod
    def broadcast(cls, message):
        if not isinstance(message, basestring):
            message = json.dumps(message)
            
        for client in cls.clients.itervalues():
            client.write_message(message)


class _MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(_HTML)


_HTML = """
<!DOCTYPE html>
<html>
<head>
<script src="//ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js"></script>
<script src="https://raw.github.com/bgrins/TinyColor/master/tinycolor.js"></script>
<script src="//cdnjs.cloudflare.com/ajax/libs/underscore.js/1.4.4/underscore-min.js"></script>
<script type="text/javascript" src="https://www.google.com/jsapi"></script>
<title>OpenMM Web Reporter</title>
<script type="text/javascript">
main = function() {
    var host = 'ws://' + window.location.origin.split('//')[1] + '/ws';
    var socket = new WebSocket(host);
    var data;
    var x_label = 'Time [ps]';

    var setup_tables = function(msg) {
        data = {};
        var N = _.size(msg);
        var i = 0.0;
        

        for (key in msg) {
            if (key == x_label) continue;
            i += 1.0;
            // assume that it's a y-axis
            var table = new google.visualization.DataTable();
            table.addColumn('number', x_label);
            table.addColumn('number', key);
            var $chart_div = $("<div class='chart'></div>");
            $chart_div.appendTo('body');
            var chart = new google.visualization.LineChart($chart_div[0]);
            
            console.log(i);
            console.log(N);
            
            data[key] = {
                table: table,
                chart: chart,
                options: {
                    title: key + ' vs. ' + x_label,
                    vAxis: {title: key},
                    hAxis: {title: x_label},
                    legend: {position: 'none'},
                    colors: [tinycolor({h:(360.0*(i+1)/N), s:100, v:90}).toHex()]
                }
            };
        }
    };

    socket.onopen = function() {
        console.log('opened');
    };
    
    socket.onmessage = function(packet) {
        console.log
        msg = JSON.parse(packet.data);
        if (data == undefined) setup_tables(msg);
        
        console.log(msg);
        for (key in msg) {
            if (key == x_label) continue;
            data[key].table.addRow([msg[x_label], msg[key]]);
            data[key].chart.draw(data[key].table, data[key].options);
        }
    };
    
    socket.onclose = function() {
        console.log('socket closed');
    };
}
google.load("visualization", "1", {packages:["corechart"]});
google.setOnLoadCallback(main);
</script>
</head>

<body>
<h2 style="text-align: center;">OpenMM Web Reporter</h2>
</body>
</html>
"""
