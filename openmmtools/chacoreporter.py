import os
import itertools
import numpy as np

from traits.etsconfig.api import ETSConfig
ETSConfig.toolkit = 'qt4'
from traits.api import HasTraits, String, Bool, Instance, List
from traitsui.api import View, Item, Group, HGroup, spring
from enable.component_editor import ComponentEditor
from chaco.api import Plot, ArrayPlotData, PlotAxis, VPlotContainer

from statedatareporter import StateDataReporter

__all__ = ['ChacoReporter']


def chaco_scatter(dataview, x_name, y_name, x_label=None, y_label=None, color=None):
    """Utility function to build a Chaco scatter plot
    """

    plot = Plot(dataview)
    plot.plot((x_name, y_name), type="scatter", marker='dot', color=color)

    if x_label is None:
        x_label = x_name
    if y_label is None:
        y_label = y_name
    x_axis = PlotAxis(mapper=plot.x_mapper, orientation='bottom', title=x_label)
    y_axis = PlotAxis(mapper=plot.y_mapper, orientation='left', title=y_label)
    plot.underlays.append(x_axis)
    plot.underlays.append(y_axis)
    return plot


class ChacoReporter(StateDataReporter, HasTraits):
    plots = Instance(VPlotContainer)
    labels = List

    traits_view = View(
        Group(Item('plots', editor=ComponentEditor(), show_label=False)),
        width=800, height=600, resizable=True,
        title='OpenMM')

    def construct_plots(self):
        """Build the Chaco Plots. This will be run on the first report
        """
        self.labels = super(ChacoReporter, self)._headers()

        self.plots = VPlotContainer(resizable="hv", bgcolor="lightgray",
                                    fill_padding=True, padding=10)
        # this looks cryptic, but it is equivalent to
        # ArrayPlotData(a=[], b=[], c=[])
        # if the keys are a,b,c. This just does it for all of the keys.
        self.plotdata = ArrayPlotData(**dict(zip(self.labels,
                                      [[]]*len(self.labels))))

        # figure out which key will be the x axis

        x = None
        x_labels = ['Time (ps)', 'Step']
        for possible_x in x_labels:
            if possible_x in self.labels:
                x = possible_x
                break
        if x is None:
            raise ValueError('The reporter published neither the step nor time'
                'count, so I don\'t know what to plot on the x-axis!')

        colors = itertools.cycle(['blue', 'green', 'silver', 'pink', 'lightblue',
                                  'red', 'darkgray', 'lightgreen'])

        for y in set(self.labels).difference(x_labels):
            self.plots.add(chaco_scatter(self.plotdata, x_name=x, y_name=y,
                                         color=colors.next()))

    def _constructReportValues(self, simulation, state):
        values = super(ChacoReporter, self)._constructReportValues(simulation, state)

        for i, label in enumerate(self.labels):
            current = self.plotdata.get_data(label)
            self.plotdata.set_data(label, np.r_[current, float(values[i])])

        return values

    def report(self, simulation, state):
        if not self._hasInitialized:
            self.construct_plots()
        super(ChacoReporter, self).report(simulation, state)
