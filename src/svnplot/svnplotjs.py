#!/usr/bin/env python
'''
svnplotjs.py
Copyright (C) 2009 Nitin Bhide nitinbhide@gmail.com

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

Generate various graphs from the Subversion log data in the sqlite database.
It assumes that the sqlite file is generated using the 'svnlog2sqlite.py' script.

Graph types to be supported
1. Activity by hour of day bar graph (commits vs hour of day) 
2. Activity by day of week bar graph (commits vs day of week) 
3. Author Activity horizontal bar graph (author vs adding+commiting percentage) 
4. Commit activity for each developer - scatter plot (hour of day vs date) 
5. Contributed lines of code line graph (loc vs dates). Using different colour line
   for each developer 
6. total loc line graph (loc vs dates) 
7. file count vs dates line graph 
8. file type vs number of files horizontal bar chart 
9. average file size vs date line graph 
10. directory size vs date line graph. Using different coloured lines for each directory
11. directory size pie chart (latest status) 
12. Directory file count pie char(latest status) 
13. Loc and Churn graph (loc vs date, churn vs date)- Churn is number of lines touched
	(i.e. lines added + lines deleted + lines modified) 
14. Repository Activity Index (using exponential decay) 
15. Repository heatmap (treemap)
16. Tag cloud of words in commit log message.

To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''

from optparse import OptionParser
import sqlite3
import os.path
import sys
import string
import pdb
import math
import shutil
import json

from svnstats import *
from svnplotbase import *
from graphbase import *

HTMLBasicStatsTmpl = '''
<table align="center">
<tr><td>Head Revision Number</td><td>:</td><td>$LastRev</td></tr>
<tr><td>First Revision Number</td><td>:</td><td>$FirstRev</td></tr>
<tr><td>Last Commit Date</td><td>:</td><td>$LastRevDate</td></tr>
<tr><td>First Commit Date</td><td>:</td><td>$FirstRevDate</td></tr>
<tr><td>Revision Count</td><td>:</td><td>$NumRev</td></tr>
<tr><td>Author Count</td><td>:</td><td>$NumAuthors</td></tr>
<tr><td>File Count</td><td>:</td><td>$NumFiles</td></tr>
<tr><td>LoC</td><td>:</td><td>$LoC</td></tr> 
</table>
'''

HTMLIndexTemplate ='''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <!--[if IE]><script type="text/javascript" src="excanvas.compiled.js"></script><![endif]-->	
    <title>Subversion Stats Plot for $RepoName</title>
    <style type="text/css">
	    h3 {background-color: lightgrey;margin:2;text-align:center;}
	    h4 {background-color: lightgrey;margin:1}
        div.graph { margin:10px; padding:25px; border:1px solid; height:500px;}        
        div#LogMsgCloud, div#AuthorCloud { height:360px; }

	</style>
    <link type="text/css" rel="stylesheet" href="nv.d3.css"></link>
    <script type="text/javascript" src="d3.v3.js"></script>
    <script type="text/javascript" src="d3.layout.cloud.js"></script>
    <script type="text/javascript" src="nv.d3.js"></script>    
    <script type="text/javascript">			 
        function showCloud(cloudData, idSel){
            var fill = d3.scale.category20();

            var selElem = d3.select(idSel);
            var w = parseInt(selElem.style("width"))-10;
            var h = parseInt(selElem.style("height"))-10;
            
            d3.layout.cloud()
                .size([w, h])
                .words(cloudData.map(function(x) {
                        return {text: x[0], size: x[1]};
                        }))
                .padding(2)
                .rotate(function() { return 0;})
                .font("Impact")
                .fontSize(function(d) { return d.size;})
                .on("end", draw)
                .start();

            function draw(words) {
                    d3.select(idSel).append("svg")
                    .append("g")
                        .attr("transform", "translate(" + [w/2, h/2] + ")") 
                    .selectAll("text")
                        .data(words)
                    .enter().append("text")
                        .style("font-size", function(d) { return d.size + "px"; })
                        .style("font-family", "Impact")
                        .style("fill", function(d, i) {return fill(i);})
                        .on("mouseover", function(){d3.select(this).style("fill", "black");})
                        .on("mouseout", function(d, i){d3.select(this).style("fill", fill(i));})
                        .attr("text-anchor", "middle")
                        .attr("transform", function(d) {
                            return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
                        })
                        .text(function(d) { return d.text; });
                }
        };     
        
        function showTagClouds() {
            var logMsgCloudData = $TagCloud;
            showCloud(logMsgCloudData, '#LogMsgCloud');
            var authCloudData = $AuthCloud;
            showCloud(authCloudData, "#AuthorCloud");
        }   
	</script>
</head>
<body>
<table align="center" frame="box" width="100%">
    <caption><h1 align="center">Subversion Statistics for $RepoName</h1></caption>
    <tr>
        <th colspan=3 align="center"><h3>General Statistics</h3></th>
    </tr>
    <tr>
        <td colspan=3>
        $BasicStats
        </td>
    </tr>
    <tr>
    <tr>
        <th colspan=3 align="center"><h3>Top 10 Hot List $SEARCHPATH</h3></th>
    </tr>
    <tr>
        <td colspan=3>
            <table width="100%">
            <tr>
                <td width="50%">
                <p align='center'><b>Top 10 Active Files</b></p>
                $ActiveFiles
                </td>
                <td>
                <p align='center'><b>Top 10 Active Authors</b></p>
                $ActiveAuthors
                </td>
            </tr>
            </table>
        </td>
    </tr>
    </table>
    $GRAPH_HTML    
    <div>
        <h3>Log Message Tag Cloud</h3>
        <div id="LogMsgCloud"></div>
        <h3>Author Cloud</h3>    
        <div id="AuthorCloud"></div>
    </div>
<script>
    // graph javascript
    $GRAPH_JS    
    showTagClouds();
</script>

</body>
</html>
'''

class SVNPlotJS(SVNPlotBase):
    '''
    Javascript based plots from subversion log data
    '''
    #list of graphs (function names)
    GRAPHS_LIST = [
        #LoC graphs
        'LocGraph', 'AvgFileLocGraph','LoCDevContributionGraph', 'WasteEffortTrend',
        # File Count Graphs
        'FileCountGraph', 'FileTypesGraph',
        #Directory Size Graphs
        'DirectorySizeLineGraph','DirectorySizePieGraph', 'DirFileCountPieGraph',
        #Commit Activity Graphs
        'CommitActivityIdxGraph', 'DailyCommitCountGraph', 
        'ActivityByWeekdayAll', 'ActivityByWeekdayRecent', 'ActivityByTimeOfDayAll', 'ActivityByTimeOfDayRecent',
        'AuthorsCommitTrend'] 
    def __init__(self, svnstats, template=None):
        SVNPlotBase.__init__(self, svnstats)
        self.commitGraphHtPerAuthor = 2 #In inches
        self.authorsToDisplay = 10
        self.fileTypesToDisplay = 20
        self.dirdepth = 2
        self.template = HTMLIndexTemplate
        
        if( template != None):
            self.setTemplate(template)
        
    def setTemplate(self, template):
        assert(template != None)
        with open(template, "r") as f:
            self.template = f.read()
 
                
    def AllGraphs(self, dirpath, svnsearchpath='/', thumbsize=200, maxdircount = 10, copyjs=True):
        self.svnstats.SetSearchPath(svnsearchpath)
        #LoC and FileCount Graphs
        graphParamDict = self._getGraphParamDict(thumbsize, maxdircount)
        
        htmlidxname = os.path.join(dirpath, "index.htm")
        htmlidxTmpl = string.Template(self.template)
        outstr = htmlidxTmpl.safe_substitute(graphParamDict)
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(outstr.encode('utf-8'))
        htmlfile.close()
        if( copyjs == True):
            self.__copyJSFiles(dirpath)
    
    def ActivityByWeekdayAll(self):
        self._printProgress("Calculating Activity by day of week graph")
        
        data, labels = self.svnstats.getActivityByWeekday()
        y_axis = GraphAxisData()
        graph = GraphBar("ActivityByWeekdayAll", y_axis=y_axis, title="Activity By Weekday")
        graph.data(zip(labels, data))
        
        return graph

    def ActivityByWeekdayRecent(self, months=3):
        self._printProgress("Calculating Activity by day of week graph")
        
        data, labels = self.svnstats.getActivityByWeekday(months)
        assert(len(data) == len(labels))
        
        title = "Activity By Weekday (%d months)" % months
        y_axis = GraphAxisData()
        graph = GraphBar("ActivityByWeekdayRecent", y_axis=y_axis, title=title)
        graph.data(zip(labels, data))
        return graph                
    
    def ActivityByTimeOfDayAll(self):
        self._printProgress("Calculating Activity by time of day graph")
        
        data, labels = self.svnstats.getActivityByTimeOfDay()
        assert(len(data) == len(labels))
        
        title = "Activity By Time of Day"
        y_axis = GraphAxisData()
        graph = GraphBar("ActivityByTimeOfDay", y_axis=y_axis, title=title)
        graph.data(zip(labels, data))
        return graph
                
    def ActivityByTimeOfDayRecent(self, months=3):
        self._printProgress("Calculating Activity by time of day graph")
        
        data, labels = self.svnstats.getActivityByTimeOfDay(months)
        assert(len(data) == len(labels))
        
        title = "Activity By Time of Day (%d months)" % months
        y_axis = GraphAxisData()
        graph = GraphBar("ActivityByTimeOfDayRecent", y_axis=y_axis, title=title)
        graph.data(zip(labels, data))
        
        return graph

    def CommitActivityIdxGraph(self):
        '''
        commit activity index over time graph. Commit activity index is calculated as 'hotness/temperature'
        of repository using the newtons' law of cooling.
        '''
        self._printProgress("Calculating Commit Activity Index by time of day graph")
        cmdates, temperaturelist = self.svnstats.getRevActivityTemperature()
        
        title = "Commit Activity Index"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("CommitActIdx", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.data(zip(cmdates, temperaturelist))
        return graph
        
    def LocGraph(self):
        self._printProgress("Calculating LoC graph")
        
        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))

        title = "Lines of Code"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("LocGraph", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.data(zip(dates, loc))
        return graph

    def LoCDevContributionGraph(self):
        self._printProgress("Calculating Developer Contribution graph")
        
        authList = self.svnstats.getAuthorList(self.authorsToDisplay)
        authLabelList = []
        
        title = "Contributed Lines of Code"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("LoCDevContributionGraph", x_axis=x_axis, y_axis=y_axis, title=title)
                 
        for author in authList:
            dates, loc = self.svnstats.getLoCTrendForAuthor(author)
            if( len(dates) > 0):
                graph.addDataSeries(author, zip(dates, loc))                
                    
        return graph
                
    def LocChurnGraph(self):
        self._printProgress("Calculating LoC and Churn graph")
       
        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))
        dates, churnlist = self.svnstats.getChurnStats()

         
        pass
        
    def FileCountGraph(self):
        self._printProgress("Calculating File Count graph")
            
        dates, fclist = self.svnstats.getFileCountStats()            
        assert(len(dates) == len(fclist))
        
        title = "File Count"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("FileCount", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.data(zip(dates, fclist))
        
        return graph

    def FileTypesGraph(self):
        self._printProgress("Calculating File Types graph")
        
        #first get the file types and
        ftypelist, ftypecountlist = self.svnstats.getFileTypesStats(self.fileTypesToDisplay)
        assert(len(ftypelist) == len(ftypecountlist))
        
        title = "File Types"
        y_axis = GraphAxisData()        
        graph = GraphHorizontalBar("FileTypesCount", y_axis=y_axis, title=title)
        graph.data(zip(ftypelist, ftypecountlist))
        
        return graph
            
    def AvgFileLocGraph(self):
        self._printProgress("Calculating Average File Size graph")
        
        dates, avgloclist = self.svnstats.getAvgLoC()                
        
        assert(len(dates) == len(avgloclist))
        
        title = "Average File LoC"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("AvgFileLoC", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.data(zip(dates, avgloclist))
        return graph

    def AuthorActivityGraph(self):
        self._printProgress("Calculating Author Activity graph")

        authlist, addfraclist,changefraclist,delfraclist = self.svnstats.getAuthorActivityStats(self.authorsToDisplay)
        authlabellist = [self._getAuthorLabel(author) for author in authlist]
        
        pass
        
    def DirectorySizePieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size pie graph")
        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth, maxdircount)
        
        assert(len(dirlist) == len(dirsizelist))

        title = "Directory Sizes"
        graph = GraphPie("DirSize", title=title)
        graph.data(zip(dirlist, dirsizelist))
        return graph
        
    def DirFileCountPieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory File Count pie graph")

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)

        title = "Directory File Count"
        graph = GraphPie("DirFileCount", title=title)
        graph.data(zip(dirlist, dirsizelist))
        return graph
    
           
    def DirectorySizeLineGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")
        
        #We only want the ten most important directories, the graf gets to blury otherwise
        #dirlist = self.svnstats.getDirnames(depth)
        #dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth)

        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth, maxdircount)
        numDirs = len(dirlist)

        title = "Directory Size(Lines of Code)"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("DirSizeLoC", x_axis=x_axis, y_axis=y_axis, title=title)
                
        for dirname in dirlist:
            dates, loclist = self.svnstats.getDirLocTrendStats(dirname)
            graph.addDataSeries(dirname, zip(dates, loclist))
        return graph

    def AuthorsCommitTrend(self):
        self._printProgress("Calculating Author commits trend histogram graph")

        #hard coded bins based on 'days between two consecutive' commits (approx. log scale)
        # 0, 1hr, 4hrs, 8hr(1day), 2 days
        binsList = [0.0, 1.0/24.0,4.0/24.0, 1.0, 2.0, 4.0, 8.0, 16.0]
        binlabels = ["0-1 hr", "1-4 hrs", "4hrs-1 day", "1-2 days", "2-4 days", "4-8 days", "8-16 days"]
        data = self.svnstats.getAuthorsCommitTrendHistorgram(binsList)
        
        title = "Author Commits Trend"
        y_axis = GraphAxisData()
        graph = GraphBar("AuthorCommitsTrend", y_axis=y_axis, title=title)
        graph.data(zip(binlabels, data))
        return graph
    
    def DailyCommitCountGraph(self):
        self._printProgress("Calculating Daily commit count graph")
                
        datelist, cmitcountlist = self.svnstats.getDailyCommitCount()        
        
        title = "Daily Commit Count"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("DailyCommitCount", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.data(zip(datelist,cmitcountlist))
        return graph
    
    def WasteEffortTrend(self):
        self._printProgress("Calculating Waste effort trend graph")
        
        datelist, linesadded, linesdeleted, wasteratio = self.svnstats.getWasteEffortStats()        
        
        title = "Wasted Effort Trend"
        x_axis = GraphTimeAxisData()
        x_axis.setTimeFormat('%b %y')
        y_axis = GraphAxisData()
        graph = GraphLine("WastedEffort", x_axis=x_axis, y_axis=y_axis, title=title)
        graph.addDataSeries("Lines Added", zip(datelist,linesadded))
        graph.addDataSeries("Lines Deleted", zip(datelist,linesdeleted))
        graph.addDataSeries("Waste Ratio", zip(datelist,wasteratio))
        return graph
    
    def getGraphJS(self, graphs):
        '''
        generate the javascript code for graphs
        '''
        graph_js_io = StringIO()
        
        for graph in graphs:
            graph_js_io.write(graph.getJS())
                            
        return graph_js_io.getvalue()
    
    def getGraphHTML(self, graphs):
        '''
        generate the HTML code for graphs
        '''
        graph_io = StringIO()
        
        for graph in graphs:
            graph_io.write(graph.getHTML())
            
        return graph_io.getvalue()
    
    def getGraphs(self):
        graphs = []
        for graphfuncName in SVNPlotJS.GRAPHS_LIST:
            graphfunc = getattr(self, graphfuncName, None)
            assert(graphfunc != None)
            print graphfuncName
            graphs.append(graphfunc())
        return graphs
    
    def _getGraphParamDict(self, thumbsize, maxdircount = 10):
        graphParamDict = dict()
            
        graphParamDict["thumbwid"]= "%dpx" % thumbsize
        graphParamDict["thumbht"]="%dpx" % thumbsize
        
        graphParamDict["RepoName"]=self.reponame
        graphParamDict["SEARCHPATH"]=""
        if( self.svnstats.searchpath != None and self.svnstats.searchpath != '/'):
            graphParamDict["SEARCHPATH"]= "(%s)" % self.svnstats.searchpath
        
        graphParamDict["TagCloud"] = self.TagCloud()
        graphParamDict["AuthCloud"] = self.AuthorCloud()
        graphParamDict["BasicStats"] = self.BasicStats(HTMLBasicStatsTmpl)
        graphParamDict["ActiveFiles"] = self.ActiveFiles()
        graphParamDict["ActiveAuthors"] = self.ActiveAuthors()
        
        graphs = self.getGraphs()
        graphParamDict["GRAPH_JS"] = self.getGraphJS(graphs)
        graphParamDict["GRAPH_HTML"] = self.getGraphHTML(graphs)        
        
        return(graphParamDict)
                
    def printAnomalies(self, searchpath='/%'):
        anomalylist = self.svnstats.getAnomalies(searchpath)
        for anomaly in anomalylist:
            #print anomaly
            pass

    def __getGraphScript(self, scriptTemplate, paramDict):
        tmplstr = '<script type="text/javascript">%s</script>' % scriptTemplate        
        scriptTmpl = string.Template(tmplstr)
        locgraph_output = scriptTmpl.safe_substitute(paramDict)
        return(locgraph_output)

    def __copyJSFiles(self, outdir):
        '''
        copy the neccessary javascript files of jquery, excanvas and jqPlot to the output directory        
        '''
        jsFileList = ['excanvas.compiled.js',
                      'd3.v3/d3.v3.js',
                      'd3.v3/d3.layout.cloud.js']
        
        try:
            srcdir = os.path.dirname(os.path.abspath(__file__))
            srcdir = os.path.join(srcdir, 'javascript')
            outdir = os.path.abspath(outdir)
            for jsfile in jsFileList:
                jsfile = os.path.normpath(jsfile)
                srcfile =os.path.join(srcdir, jsfile)
                shutil.copy(srcfile, outdir)
        except Exception, expinst:
            print "Needed javascript files couldnot be copied."
            print "Please copy these files manually at correct location"
            print expinst
    
def RunMain():
    usage = "usage: %prog [options] <svnsqlitedbpath> <graphdir>"
    parser = OptionParser(usage)

    parser.add_option("-n", "--name", dest="reponame",
                      help="repository name")
    parser.add_option("-s","--search", dest="searchpath", default="/",
                      help="search path in the repository (e.g. /trunk)")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="display verbose progress")
    parser.add_option("-t", "--thumbsize", dest="thumbsize", default=200, type="int",
                      help="set the width and heigth of thumbnail display (pixels). Graphs may get distorted if the value is less than 200 pixels")    
    parser.add_option("-p", "--template", dest="template", 
                      action="store", type="string", help="template filename (optional)")
    parser.add_option("-m","--maxdir",dest="maxdircount", default=10, type="int",
                      help="limit the number of directories on the graph to the x largest directories")
    parser.add_option("-j", "--copyjs", dest="copyjs", default=True, action="store_true",
                      help="Copy the required excanvas,jquery and jqPlot javascript and css file to output directory")
    parser.add_option("-l","--lastrev",dest="lastrev", default=None, type="int",
                      help="The last revision number to create plots") 
    parser.add_option("-f","--firstrev",dest="firstrev", default=None, type="int",
                      help="The first revision number to create plots")                                          
    
    
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments. Use svnplot.py --help to see the details."
    else:        
        svndbpath = args[0]
        graphdir  = args[1]
        
        if( options.searchpath.endswith('%') == False):
            options.searchpath +='%'
            
        if( options.verbose == True):
            print "Calculating subversion stat graphs"
            print "Subversion log database : %s" % svndbpath
            print "Graphs will generated in : %s" % graphdir
            print "Repository Name : %s" % options.reponame
            print "Search path inside repository : %s" % options.searchpath
            print "Graph thumbnail size : %s" % options.thumbsize
            print "Maximum dir count: %d" % options.maxdircount
            if( options.template== None):
                print "using default html template"
            else:
                print "using template : %s" % options.template
                
            if (options.lastrev == None):
                print "end in last revision the database has"
            else:
                print "end in %s revision" % options.lastrev
            if (options.firstrev == None):
                print "start from first revision the database has"
            else:
                print "start from %s revision" % options.firstrev
            
            
        svnstats = SVNStats(svndbpath,options.firstrev,options.lastrev)     
        svnplot = SVNPlotJS(svnstats, template=options.template)
        svnplot.SetVerbose(options.verbose)
        svnplot.SetRepoName(options.reponame)
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize, options.maxdircount,copyjs=options.copyjs)
        
if(__name__ == "__main__"):
    RunMain()
    
