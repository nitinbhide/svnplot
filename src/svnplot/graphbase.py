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

    def setTickFormat(self, tickformat):
        '''
        tickformat : is treated as javascript string and directly passed to javascript code.
        '''
        self.tickFormat = tickformat
    
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
    
    def setTimeFormat(self, timeformat):
        '''
        timeformat: is treated as javascript string and directly passed to javascript code.
        '''
        #python time format is in seconds and javascript is in milliseconds then multiple
        # 'd' value by 1000
        tickformat = '''function(d) {
            return d3.time.format('%s')(new Date(d*1000))
          }'''
        self.setTickFormat(tickformat % timeformat)
    
    def data2json(self, d):
        return time.mktime(d.timetuple()) 
    
class GraphXYBase(object):
    '''
    base class for typical one dimension (pie chart) or two dimension (line chart) graph types
    '''
    HTML_TEMPLATE='''
    <div class="graphsection">
        <h4>$TITLE</h4>
        <div class="graphwrapper" id="$ID">
            <div class="graph">
                <svg></svg>
            </div>        
        </div>
    </div>
    '''
    def __init__(self, name, x_axis=None, y_axis=None, title=''):
        self.name = name #graph name. Used as function name as well
        self.x_axis = x_axis 
        self.y_axis = y_axis
        self.title = title
        self.dataSeries = dict()
        
    def getGraphFuncName(self):
        return self.name;
    
    def addDataSeries(self, name, dt):
        self.dataSeries[name] = dt

    def data(self, dt):
        self.addDataSeries('', dt)
    
    def getID(self):
        return self.name
    
    def getJS(self):
        raise NotImplementedError

    def data_json(self):
        x2json = lambda d: d
        if self.x_axis:
            x2json = self.x_axis.data2json
        y2json = lambda d: d
        if self.y_axis:
            y2json = self.y_axis.data2json
            
        jsdata = []
        for name, data in self.dataSeries.iteritems():            
            values = [{ 'x' : x2json(d[0]), 'y': y2json(d[1]) } for d in data]
            jsdata.append({ 'key' : name, 'values' : values})
        return json.dumps(jsdata)
        
    def get_properties(self):
        '''
        get the dictionary for graph properties like ID, name etc
        '''
        properties = dict()
        properties['ID'] = self.getID()
        properties['FUNC_NAME'] = self.getGraphFuncName()
        properties['TITLE'] = self.title        
        if self.y_axis:
            properties['Y_TICK_FORMAT']  = self.y_axis.tickFormat
        if self.x_axis:
            properties['X_TICK_FORMAT']  = self.x_axis.tickFormat
        return properties
    
    def getHTML(self):
        template_string = type(self).HTML_TEMPLATE
        tmpl = string.Template(template_string)
        values = self.get_properties()
        return tmpl.substitute(values)
    
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
    function $FUNC_NAME(isthumb) {
        if(isthumb) {
            showTooltip = false;            
        }
        var chart = nv.models.lineChart()
            .tooltips(showTooltip)            
        var elem_sel = "#$ID";
        
        var xtickFormat = $X_TICK_FORMAT;
        var ytickFormat = $Y_TICK_FORMAT;
        chart.xAxis
            .tickFormat(xtickFormat);
        chart.yAxis
            .tickFormat(ytickFormat);

        var graphElem = d3.select(elem_sel);
        
        var graphData = $GRAPH_DATA;        
        graphElem.select('div.graph svg')
            .datum(graphData)            
            .call(chart);

        nv.utils.windowResize(chart.update);

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
    function $FUNC_NAME(isthumbnail) {        
        var showTooltip=true;
        if(isthumbnail) {
            showTooltip=false;
        }
        var chart = nv.models.discreteBarChart()
            .showValues(true)
            .tooltips(showTooltip)
            .valueFormat($VALUE_FORMAT);
        var elem_sel = "#$ID";
        
        chart.yAxis
            .tickFormat($Y_TICK_FORMAT);

        var graphElem = d3.select(elem_sel);
        
        var graphData = $GRAPH_DATA;        
        graphElem.select('div.graph svg')
            .datum(graphData)            
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    }        
    '''
    def __init__(self, name, y_axis=None, title=None):
        super(GraphBar, self).__init__(name, y_axis=y_axis,title=title)
        self.setValueFormat('''d3.format(',.0f')''')
        
    def setValueFormat(self, valueFormat):
        self.valueFormat = valueFormat
    
    def get_properties(self):
        prop = super(GraphBar, self).get_properties()
        prop['VALUE_FORMAT'] = self.valueFormat
        return prop
    
class GraphPie(GraphBar):
    '''
    pie chart with d3js and nvd3.js
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(isthumbnail) {
        var showTooltip=true
        if(isthumbnail) {
            showTooltip = false;
        }
        var chart = nv.models.pieChart()
            .showLabels(true)
            .showLegend(true)
            .tooltips(showTooltip);
        var elem_sel = "#$ID";
        
        var graphElem = d3.select(elem_sel);
        
        var graphData = $GRAPH_DATA[0];        
        graphElem.select('div.graph svg')
            .datum(graphData.values)            
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    }       
    '''
    def __init__(self, name, title=None):
        super(GraphPie, self).__init__(name, y_axis=None,title=title)
        

class GraphHorizontalBar(GraphBar):
    '''
    Bar char with d3js and nvd3.js
    '''
    JS_TEMPLATE = '''
    function $FUNC_NAME(isthumbnail) {        
        var showTooltip=true;
        if(isthumbnail) {
            showTooltip=false;
        }
        var chart = nv.models.multiBarHorizontalChart()
            .showValues(true)
            .showControls(false)
            .showLegend(true)
            .tooltips(showTooltip)
            .valueFormat($VALUE_FORMAT);
        var elem_sel = "#$ID";
        
        chart.yAxis
            .tickFormat($Y_TICK_FORMAT);

        var graphElem = d3.select(elem_sel);
        
        var graphData = $GRAPH_DATA;        
        graphElem.select('div.graph svg')
            .datum(graphData)            
            .call(chart);

        nv.utils.windowResize(chart.update);

        return chart;
    }        
    '''
    def __init__(self, name, y_axis=None, title=None):
        super(GraphHorizontalBar, self).__init__(name, y_axis=y_axis,title=title)    
        
        