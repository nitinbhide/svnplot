'''
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
graphbase.py

Implements a base class for common graph types. Derived classes will implement the 
actual graph generation using matplotlib or d3js etc.
'''
import string
import json
import time

class GraphAxisData(object):
    '''
    graph data for one axis
    '''
    
    def __init__(self, name=None, color=None):
        '''
        data : data for the given axis. Usually 'list'
        name : axis name or key
        color : color for displaying this data (in HTML color notation or color name)
        '''
        self.name = name
        self.color = color
        self.tickFormat = '''d3.format(',.0f')'''
        self.axisLabel = ''
        self.type = 'indexed'

    def setTickFormat(self, tickformat):
        '''
        tickformat : is treated as javascript string and directly passed to javascript code.
        '''
        self.tickFormat = tickformat
    
    def setAxisLabel(self, axisLabel):
        self.axisLabel = axisLabel

    def data2json(self, d):
        return d
    
class GraphTimeAxisData(GraphAxisData):
    '''
    graph data for one axis
    '''
    def __init__(self, name=None, color=None):
        super(GraphTimeAxisData, self).__init__(name, color)
        #override the time format function.
        #input time assumed in seconds from EPOCH
        self.setTimeFormat("%%x")
        self.type = 'timeseries'
        
    def setTimeFormat(self, timeformat):
        '''
        timeformat: is treated as javascript string and directly passed to javascript code.
        '''
        #python time format is in seconds and javascript is in milliseconds then multiple
        # 'd' value by 1000
        tickformat = '''function(d) {
            return d3.time.format('%s')(d)
          }'''
        self.setTickFormat(tickformat % timeformat)
    
    def data2json(self, d):
        return time.mktime(d.timetuple())*1000 
    
class GraphXYBase(object):
    '''
    base class for typical one dimension (pie chart) or two dimension (line chart) graph types
    '''
    def __init__(self, name, x_axis=None, y_axis=None, title=''):
        self.name = name #graph name. Used as function name as well
        self.x_axis = x_axis 
        self.y_axis = y_axis
        self.title = title
        self.dataSeries = dict()
        self.dataSeriesProps = dict()
        self.type = 'line'
    
    @property
    def graphClass(self):
        return self.getGraphFuncName()

    def getGraphFuncName(self):
        return self.name;
    
    def addDataSeries(self, name, dt, **kwargs):
        self.dataSeries[name] = dt
        self.dataSeriesProps[name] = dict(kwargs)

    def data(self, dt, name=''):
        self.addDataSeries(name, dt)
        
    def getJS(self):
        raise NotImplementedError

    def data_json(self):
        x2json = lambda d: d
        if self.x_axis:
            x2json = self.x_axis.data2json
        y2json = lambda d: d
        if self.y_axis:
            y2json = self.y_axis.data2json
            
        xs = dict()
        columns = []
        axes = dict()
        for i, (name, data) in enumerate(self.dataSeries.iteritems()):
            props = self.dataSeriesProps[name]
            x_values= ["x%d" % i]+[x2json(d[0]) for d in data]
            y_values = [name]+[y2json(d[1])  for d in data]
            xs[name] = "x%d" % i
            axes["x%d" % i] = 'x'            
            axes[name] = props.get('axis', 'y')
            columns.append(x_values)
            columns.append(y_values)            
        jsdata = { 'xs': xs, 'columns' : columns, 'axes':axes, 'x':'x0', 'type':self.type}
        return json.dumps(jsdata,indent =2)
        
    def get_properties(self):
        '''
        get the dictionary for graph properties like ID, name etc
        '''
        properties = dict()        
        properties['FUNC_NAME'] = self.getGraphFuncName()
        properties['TITLE'] = self.title
        if self.y_axis:
            properties['Y_TICK_FORMAT']  = self.y_axis.tickFormat
            properties['Y_AXISLABEL'] = self.y_axis.axisLabel;
        if self.x_axis:
            properties['X_TICK_FORMAT']  = self.x_axis.tickFormat
            properties['X_AXISLABEL'] = self.x_axis.axisLabel;
            properties['X_TYPE'] = self.x_axis.type
        properties['GRAPH_CLASS'] = self.graphClass

        return properties
        
    def getJS(self):
        template_string = type(self).JS_TEMPLATE
        tmpl = string.Template(template_string)
        values = self.get_properties()
        values['GRAPH_DATA'] = self.data_json()
        return tmpl.substitute(values)    


class GraphLine(GraphXYBase):
    '''
    Line chart with d3js and nvd3.js
    '''
    
    JS_TEMPLATE = '''
    function $FUNC_NAME(id) {
        var elem_sel = "#" + id;
        var graphElem = d3.select(elem_sel);        
        var graphHtml = "<h4>$TITLE</h4>" + 
                "<div class='graphwrapper $GRAPH_CLASS'><div class='graph'></div></div>";
        graphElem.html(graphHtml);
        var graphData = $GRAPH_DATA;
                
        var chart = c3.generate({
            bindto:elem_sel + ' div.graphwrapper .graph',                
            data: graphData,
            axis: {
                x: {
                    type: "$X_TYPE",
                    tick: {
                        count: 8,
                        format: $X_TICK_FORMAT
                    }
                }
            }
        });
                        
        return chart;
    }        
    '''
    def __init__(self, name, x_axis=None, y_axis=None, title=None):
        super(GraphLine, self).__init__(name, x_axis=x_axis, y_axis=y_axis,title=title)

        
class GraphBar(GraphXYBase):
    '''
    Bar char with d3js and nvd3.js
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(id) {
        var elem_sel = "#" + id;
        var graphElem = d3.select(elem_sel);        
        var graphHtml = "<h4>$TITLE</h4>" + 
                "<div class='graphwrapper $GRAPH_CLASS'><div class='graph'></div></div>";
        graphElem.html(graphHtml);
        var graphData = $GRAPH_DATA;
                
        var chart = c3.generate({
            bindto:elem_sel + ' div.graphwrapper .graph',                
            data: graphData,
            bar: {
                width: {
                    ratio: 0.5 // this makes bar width 50% of length between ticks
                }
            },
             axis: {
                x: {
                    type: 'categorized' // this needed to load string x value
                }
            }
        });
                        
        return chart;
    }        
    '''
    def __init__(self, name, y_axis=None, title=None):
        super(GraphBar, self).__init__(name, y_axis=y_axis,title=title)
        self.setValueFormat('''d3.format(',.0f')''')
        self.type = 'bar'
    
    def setValueFormat(self, valueFormat):
        self.valueFormat = valueFormat
    
    def get_properties(self):
        prop = super(GraphBar, self).get_properties()
        prop['VALUE_FORMAT'] = self.valueFormat
        return prop
    
class GraphLineWith2Yaxis(GraphXYBase):
    '''
    combination of line and bar graph
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(id) {
        var elem_sel = "#" + id;
        var graphElem = d3.select(elem_sel);        
        var graphHtml = "<h4>$TITLE</h4>" + 
                "<div class='graphwrapper $GRAPH_CLASS'><div class='graph'></div></div>";
        graphElem.html(graphHtml);
        var graphData = $GRAPH_DATA;
                
        var chart = c3.generate({
            bindto:elem_sel + ' div.graphwrapper .graph',                
            data: graphData,
            axis: {
                x: {
                    type: "$X_TYPE",
                    tick: {
                        count: 8,
                        format: $X_TICK_FORMAT
                    }
                },
                y2: {
                   show: true,
                   inner:true
                }
            }
        });
                        
        return chart;
    }        
    '''
    def __init__(self, name, x_axis=None, y_axis=None, title=None):
        super(GraphLineWith2Yaxis, self).__init__(name, x_axis=x_axis, y_axis=y_axis,title=title)
    
    def addDataSeries(self, name, dt, **kwargs):
        kwargs['axis'] = kwargs.get('axis', 'y')
        super(GraphLineWith2Yaxis, self).addDataSeries(name, dt, **kwargs)

class GraphPie(GraphBar):
    '''
    pie chart with d3js and nvd3.js
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(id) {
        var elem_sel = "#" + id;
        var graphElem = d3.select(elem_sel);        
        var graphHtml = "<h4>$TITLE</h4>" + 
                "<div class='graphwrapper $GRAPH_CLASS'><div class='graph'></div></div>";
        graphElem.html(graphHtml);
        var graphData = $GRAPH_DATA;
                
        var chart = c3.generate({
            bindto:elem_sel + ' div.graphwrapper .graph',                
            data: graphData,
            bar: {
                width: {
                    ratio: 0.5 // this makes bar width 50% of length between ticks
                }
            }
        });
                        
        return chart;
    }        
    '''
    def __init__(self, name, title=None):
        super(GraphPie, self).__init__(name, y_axis=None,title=title)
        self.type = 'pie'
        

class GraphHorizontalBar(GraphBar):
    '''
    Bar char with d3js and nvd3.js
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(id) {
        var elem_sel = "#" + id;
        var graphElem = d3.select(elem_sel);        
        var graphHtml = "<h4>$TITLE</h4>" + 
                "<div class='graphwrapper $GRAPH_CLASS'><div class='graph'></div></div>";
        graphElem.html(graphHtml);
        var graphData = $GRAPH_DATA;
                
        var chart = c3.generate({
            bindto:elem_sel + ' div.graphwrapper .graph',                
            data: graphData,
            bar: {
                width: {
                    ratio: 0.5 // this makes bar width 50% of length between ticks
                }
            },
             axis: {
                x: {
                    type: 'categorized' // this needed to load string x value
                },
                rotated:true
            }
        });
                        
        return chart;
    }        
    '''
    def __init__(self, name, y_axis=None, title=None):
        super(GraphHorizontalBar, self).__init__(name, y_axis=y_axis,title=title)    
        
        