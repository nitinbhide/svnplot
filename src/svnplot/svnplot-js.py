'''
svnplot.py
Copyright (C) 2009 Nitin Bhide nitinbhide@gmail.com

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

Generate various graphs from the Subversion log data in the sqlite database.
It assumes that the sqlite file is generated using the 'svnlog2sqlite.py' script.

Graph types to be supported
1. Activity by hour of day bar graph (commits vs hour of day) -- Done
2. Activity by day of week bar graph (commits vs day of week) -- Done
3. Author Activity horizontal bar graph (author vs adding+commiting percentage) -- Done
4. Commit activity for each developer - scatter plot (hour of day vs date) -- Done
5. Contributed lines of code line graph (loc vs dates). Using different colour line
   for each developer -- Done
6. total loc line graph (loc vs dates) -- Done
7. file count vs dates line graph -- Done
8. file type vs number of files horizontal bar chart -- Done
9. average file size vs date line graph -- Done
10. directory size vs date line graph. Using different coloured lines for each directory
11. directory size pie chart (latest status) -- Done
12. Directory file count pie char(latest status) -- Done
13. Loc and Churn graph (loc vs date, churn vs date)- Churn is number of lines touched
	(i.e. lines added + lines deleted + lines modified) -- Done
14. Repository Activity Index (using exponential decay) -- Done
15. Repository heatmap (treemap)
16. Tag cloud of words in commit log message.

To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''
from __future__ import with_statement

__revision__ = '$Revision:$'
__date__     = '$Date:$'

from optparse import OptionParser
import sqlite3
import os.path
import sys
import string
import StringIO
import math
import shutil
from svnstats import *
from svnplotbase import *

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

HTMLIndexTemplate ='''
<html>
<head><title>Subversion Stats Plot for $RepoName</title>
    <!--[if IE]><script type="text/javascript" src="excanvas.compiled.js"></script><![endif]-->
	<style type="text/css">
	th {background-color: #F5F5F5; text-align:center}
	/*td {background-color: #FFFFF0}*/
	h3 {background-color: transparent;margin:2}
	h4 {background-color: transparent;margin:1}
	.graph {
        display: block;
        margin-left:auto;margin-right:auto;
        height:$thumbht;width:$thumbwid;
    }
    #GraphPopBox {
        display: none;
		position: fixed;
		top: 15%;
		left: 15%;
		right: 15%;
		bottom: 15%;
		margin:0px;
		padding:0px;
        background-color:#778899;
		z-index:1002;		
		overflow: none;
		#overflow: auto;		
    }
    #Graph_big {
        position:absolute;
        top:40px;
        left:5px;
        bottom:5px;
        right:5px;
        border : 2px solid black;
        padding: 10px;
        background-color: white;
		#border: 16px solid black;		
		}
	#closebtn {
        display:block;
        color:white;
        float:right;
        z-index:1005;
        margin:5px;
        padding:5px;
	}	
	</style>
	<link type="text/css" rel="stylesheet" href="jquery.jqplot.min.css"/>		
	<script type="text/javascript" src="jquery.min.js"></script>
	<script type="text/javascript" src="jquery.jqplot.js"></script>	
	<script type="text/javascript" src="jqplot.dateAxisRenderer.min.js"></script>	
	<script type="text/javascript" src="jqplot.categoryAxisRenderer.min.js"></script>
	<script type="text/javascript" src="jqplot.barRenderer.min.js"></script>
	<script type="text/javascript" src="jqplot.pieRenderer.min.js"></script>
	$LocTable
	$LoCChurnTable	
	$ContriLoCTable
	$AvgLoCTable
	$FileCountTable
	$FileTypeCountTable
	$DirSizePie
	$DirSizeLine
	$DirFileCountPie
	$CommitActIdxTable
	$AuthorsCommitTrend
	$ActivityByWeekdayTable
	$ActivityByTimeOfDayTable
	$AuthorActivityGraph
    <script type="text/javascript">
			 function showAllGraphs(showLegend) {
                    locgraph('LoCGraph', showLegend);
                    /* Not there in this template
					locChurnGraph('LoCChurnGraph', showLegend);*/                    
                    contri_locgraph('ContriLoCGraph', showLegend);
                    avglocgraph('AvgLoCGraph',showLegend);
                    fileCountGraph('FileCountGraph',showLegend);
                    fileTypesGraph('FileTypeCountGraph',showLegend);
                    ActivityByWeekday('ActivityByWeekdayGraph',showLegend);
                    ActivityByTimeOfDay('ActivityByTimeOfDayGraph',showLegend);
                    CommitActivityIndexGraph('CommitActIdxGraph',showLegend);
                    directorySizePieGraph('DirSizePie', showLegend);
                    dirFileCountPieGraph('DirFileCountPie', showLegend);
                    dirSizeLineGraph('DirSizeLine', showLegend);
                    authorsCommitTrend('AuthorsCommitTrend',showLegend);
                    authorActivityGraph('AuthorActivityGraph', showLegend);
                };
                
                function showGraphBox(graphFunc, showLegend) {
                    var graphboxId = 'GraphPopBox';
                    var graphBoxElem = document.getElementById(graphboxId);
                    graphBoxElem.style.display='block';
                    var graphCanvasId = 'Graph_big'
                    var plot = graphFunc(graphCanvasId, showLegend);
                    plot.redraw(true);                                                    
                };
                
                function hideGraphBox() {
                    var graphboxId = 'GraphPopBox';
                    var graphBoxElem = document.getElementById(graphboxId);
                    graphBoxElem.style.display='none';
                }
	</script>	
</head>
<body onLoad="showAllGraphs(false);">
<table align="center" frame="box">
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
<th colspan=3 align="center"><h3>Top 10 Hot List</h3></th>
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
<tr>
<th colspan=3 align="center"><h3>Lines of Code Graphs</h3></th>
</tr>
<tr>
    <td align="center">
    <div id="LoCGraph" class="graph" onclick ="showGraphBox(locgraph, true);"></div>
    </td>
    <td align="center">
    <div id="ContriLoCGraph" class="graph" onclick ="showGraphBox(contri_locgraph, true);"></div>
    </td>
    <td align="center">
    <div id="AvgLoCGraph" class="graph" onclick ="showGraphBox(avglocgraph, true);"></div>
    </td>    
</tr>
<tr>
<th colspan=3 align="center"><h3>File Count Graphs</h3></th>
</tr>
<tr>
    <td align="center">
    <div id="FileCountGraph" class="graph" onclick ="showGraphBox(fileCountGraph, true);"></div>
    </td>
    <td align="center" >
    <div id="FileTypeCountGraph" class="graph" onclick ="showGraphBox(fileTypesGraph, true);"></div>
    </td>
    <td>&nbsp</td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Directory Size Graphs</h3></th>
</tr>
<tr>
   <td align="center">
    <div id="DirSizePie" class="graph" onclick ="showGraphBox(directorySizePieGraph, true);"></div>
    </td>
    <td align="center">
    <div id="DirSizeLine" class="graph" onclick ="showGraphBox(dirSizeLineGraph, true);"></div>
    </td>
    <td align="center">
    <div id="DirFileCountPie" class="graph" onclick ="showGraphBox(dirFileCountPieGraph, true);"></div>
    </td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Commit Activity Graphs</h3></th>
</tr>
<tr>
    <td align="center" >
        <div id="CommitActIdxGraph" class="graph" onclick ="showGraphBox(CommitActivityIndexGraph, true);"></div>
    </td>    
    <td align="center" >
    <div id="ActivityByWeekdayGraph" class="graph" onclick ="showGraphBox(ActivityByWeekday, true);"></div>
    </td>
    <td align="center" >
    <div id="ActivityByTimeOfDayGraph" class="graph" onclick ="showGraphBox(ActivityByTimeOfDay, true);"></div>
    </td>    
</tr>
<tr>
    <td align="center" >
        <div id="AuthorsCommitTrend" class="graph" onclick ="showGraphBox(authorsCommitTrend, true);"></div>
    </td>
    <td align="center">
    <div id="AuthorActivityGraph" class="graph" onclick ="showGraphBox(authorActivityGraph, true);"></div>
    </td>
    <td align="center" >&nbsp;    
    </td>    
</tr>
<th colspan=3 align="center"><h3>Log Message Tag Cloud</h3></th>
</tr>
<tr id='tagcloud'>
<td colspan=3 align="center">$TagCloud</td>
</tr>
<th colspan=3 align="center"><h3>Author Cloud</h3></th>
</tr>
<tr id='authcloud'>
<td colspan=3 align="center">$AuthCloud</td>
</tr>
</table>
    <div id="GraphPopBox">
        <h3 id="closebtn" onClick="hideGraphBox();">Close[X]</h3>
        <div id="Graph_big"></div>
    </div>    
</body>
</html>
'''

class SVNPlotJS(SVNPlotBase):
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
        graphParamDict = self._getGraphParamDict(thumbsize)
        
        htmlidxname = os.path.join(dirpath, "index.htm")
        htmlidxTmpl = string.Template(self.template)
        outstr = htmlidxTmpl.safe_substitute(graphParamDict)
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(outstr.encode('utf-8'))
        htmlfile.close()
        if( copyjs == True):
            self.__copyJSFiles(dirpath)
                               
    def ActivityByWeekday(self):
        self._printProgress("Calculating Activity by day of week graph")
        
        data, labels = self.svnstats.getActivityByWeekday()
        
        template = '''        
            function ActivityByWeekday(divElemId,showLegend) {
            var data = [$DATA];
            var plot = $.jqplot(divElemId, [data], {
                title:'Commit Activity by Day of Week',
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barPadding: 6, barMargin:15}, 
                shadowAngle:135},                
            axes:{
                xaxis:{
                    renderer:$.jqplot.CategoryAxisRenderer,
                    label:'Day of Week'
                    },
                yaxis:{min:0}                 
                }
            });
            return(plot);
        };
        '''
        assert(len(data) == len(labels))
        
        datalist = [ "['%s',%d]" % (wkday, actdata) for actdata, wkday in zip(data, labels)]
        data = ','.join(datalist)

        return(self.__getGraphScript(template, {"DATA":data}))

    def ActivityByTimeOfDay(self):
        self._printProgress("Calculating Activity by time of day graph")
        
        data, labels = self.svnstats.getActivityByTimeOfDay()
        
        template = '''        
            function ActivityByTimeOfDay(divElemId,showLegend) {
            var data = [$DATA];
            var plot = $.jqplot(divElemId, [data], {
                title:'Commit Activity By Hour of Day',
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barPadding: 6, barMargin:15}, 
                shadowAngle:135},                
            axes:{
                xaxis:{
                    renderer:$.jqplot.CategoryAxisRenderer,
                    label:'Time of Day'
                },
                yaxis:{min:0}                 
                }
            });
            return(plot);
        };
        '''
        assert(len(data) == len(labels))

        datalist = ["['%s',%d]" % (tmofday, actdata)  for actdata, tmofday in zip(data, labels)]
                    
        data = ','.join(datalist)

        return(self.__getGraphScript(template, {"DATA":data}))


    def CommitActivityIdxGraph(self):
        '''
        commit activity index over time graph. Commit activity index is calculated as 'hotness/temperature'
        of repository using the newtons' law of cooling.
        '''
        self._printProgress("Calculating Commit Activity Index by time of day graph")
        cmdates, temperaturelist = self.svnstats.getRevActivityTemperature()
        
        template = '''  
        function CommitActivityIndexGraph(divElemId,showLegend) {
            var locdata = [$DATA];
            var plot = $.jqplot(divElemId, [locdata], {
                title:'Commit Activity Index over time',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]}
                );
                return(plot);    
            };
        '''
        
        assert(len(cmdates) == len(temperaturelist))
        datalist = ['[\'%s\', %.4f]' % (date,temperature) for date, temperature in zip(cmdates, temperaturelist)]
        datastr = ',\n'.join(datalist)
        
        return(self.__getGraphScript(template, {"DATA":datastr}))        

        
    def LocGraph(self):
        self._printProgress("Calculating LoC graph")
        
        template = '''  
            function locgraph(divElemId,showLegend) {
            var locdata = [$DATA];
            var plot = $.jqplot(divElemId, [locdata], {
                title:'Lines of Code',
                axes:{
                    xaxis:{renderer:$.jqplot.DateAxisRenderer, label:'LoC'},
                    yaxis:{min:0}
                },
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]}
                );
                return(plot);                   
             };
        '''
        
        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))
        datalist = ['[\'%s\', %d]' % (date,lc) for date, lc in zip(dates, loc)]
        outstr = ',\n'.join(datalist)
        
        return(self.__getGraphScript(template, {"DATA":outstr}))        

    def LocGraphAllDev(self):
        self._printProgress("Calculating Developer Contribution graph")
        template = '''
            function contri_locgraph(divElemId, showLegend) {
            $LOCDATA
             var plot = $.jqplot(divElemId, locdata, {
                legend:{show:showLegend}, 
                title:'Contributed Lines of Code',
                axes:
                {
                    xaxis:{renderer:$.jqplot.DateAxisRenderer, label:'LoC'},
                    yaxis:{min:0}
                },
                series:$SERIESDATA
                });
              return(plot);
            };
        '''
        
        authList = self.svnstats.getAuthorList(self.authorsToDisplay)
        authLabelList = []
        
        outstr = StringIO.StringIO()
        idx =0        
        for author in authList:
            dates, loc = self.svnstats.getLoCTrendForAuthor(author)
            if( len(dates) > 0):
                outstr.write("var auth%dLocData = [" % idx)
                datalist = ['[\'%s\', %d]' % (date,lc) for date, lc in zip(dates, loc)]            
                outstr.write(',\n'.join(datalist))
                outstr.write("];\n")
                authLabelList.append(self._getAuthorLabel(author).replace('\n', '\\n'))
                idx = idx+1
            
        outstr.write("var locdata = [")
        datalist = ["auth%dLocData"% idx for idx in range(0, len(authLabelList))]
        outstr.write(','.join(datalist))
        outstr.write("];\n")
        locdatastr = outstr.getvalue()

        outstr = StringIO.StringIO()
        outstr.write("[")
        datalist = ["{label:'%s', lineWidth:2, markerOptions:{style:'filledCircle',size:2}}" % author for author in authLabelList]
        outstr.write(',\n'.join(datalist))            
        outstr.write("]")
            
        seriesdata = outstr.getvalue()            
        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "SERIESDATA":seriesdata}))
    
            
    def LocChurnGraph(self):
        self._printProgress("Calculating LoC and Churn graph")

        template = '''
            function locChurnGraph(divElemId, showLegend) {
            var locdata = [$LOCDATA];
            var churndata= [$CHURNDATA];
            
            var plot = $.jqplot(divElemId, [locdata, churndata], {
                title:'Lines of Code and Churn Graph',
                legend:{show:showLegend},
                axes:{ xaxis:{renderer:$.jqplot.DateAxisRenderer},
                    yaxis:{label:'LoC', min:0},
                    y2axis:{label:'Churn', min:0} },
                series:[
                    {label:'LoC', lineWidth:2, markerOptions:{style:'filledCircle',size:2}},
                    {label:'Churn',yaxis:'y2axis',lineWidth:2, markerOptions:{style:'filledCircle',size:2}}
                ]
            });
            return(plot);
        };
        '''

        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))
        datalist = ['[\'%s\', %d]' % (date,lc) for date, lc in zip(dates, loc)]        
        locdatastr = ',\n'.join(datalist)
        
        dates, churnlist = self.svnstats.getChurnStats()

        datalist = ['[\'%s\', %d]' % (date,churn) for date, churn in zip(dates, churnlist)]        
        churndatastr = ',\n'.join(datalist)
         
        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "CHURNDATA":churndatastr}))                
        
    def FileCountGraph(self):
        self._printProgress("Calculating File Count graph")

        dates, fc = self.svnstats.getFileCountStats()        

        template = '''        
            function fileCountGraph(divElemId,showLegend) {
            var data = [$DATA];
            var plot = $.jqplot(divElemId, [data], {
                title:'File Count',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]}
                );
              return(plot);
            };
        '''
        
        dates, fclist = self.svnstats.getFileCountStats()        
        
        assert(len(dates) == len(fclist))
        datalist = ['[\'%s\', %d]' % (date,fc) for date, fc in zip(dates, fclist)]            
        outstr = ',\n'.join(datalist)
        
        return(self.__getGraphScript(template, {"DATA":outstr}))        

    def FileTypesGraph(self):
        self._printProgress("Calculating File Types graph")
        template = '''        
            function fileTypesGraph(divElemId,showLegend) {
            var data = [$DATA];
            var plot = $.jqplot(divElemId, [data], {
                title:'File Types',
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barDirection:'horizontal', barPadding: 6, barMargin:15}, 
                shadowAngle:135},
            axes:{
                xaxis:{min:0}, 
                yaxis:{renderer:$.jqplot.CategoryAxisRenderer}
                }
            });
            return(plot);
        };
        '''
        
        #first get the file types and
        ftypelist, ftypecountlist = self.svnstats.getFileTypesStats(self.fileTypesToDisplay)
        assert(len(ftypelist) == len(ftypecountlist))
        
        datalist = ["[%d, '%s']" % (ftcount, ftype) for ftype, ftcount in zip(ftypelist, ftypecountlist)]            
        outstr = ','.join(datalist)

        return(self.__getGraphScript(template, {"DATA":outstr}))
        
            
    def AvgFileLocGraph(self):
        self._printProgress("Calculating Average File Size graph")
            
        template = '''        
            function avglocgraph(divElemId,showLegend) {
            var locdata = [$LOCDATA];
            var plot = $.jqplot(divElemId, [locdata], {
                title:'Average File LoC',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]}
                );
                return(plot);
            };
        '''
        
        dates, avgloclist = self.svnstats.getAvgLoC()                
        
        assert(len(dates) == len(avgloclist))
        datalist = ['[\'%s\', %d]' % (date,lc) for date, lc in zip(dates, avgloclist)]                
        outstr = ',\n'.join(datalist)
                
        return(self.__getGraphScript(template, {"LOCDATA":outstr}))

    def AuthorActivityGraph(self):
        self._printProgress("Calculating Author Activity graph")

        authlist, addfraclist,changefraclist,delfraclist = self.svnstats.getAuthorActivityStats(self.authorsToDisplay)
        authlabellist = [self._getAuthorLabel(author) for author in authlist]
        
        legendlist = ["Adding", "Modifying", "Deleting"]
        template = '''        
            function authorActivityGraph(divElemId, showLegend) {            
            var addData = [$ADDDATA];
            var changeData = [$CHANGEDATA];
            var delData = [$DELDATA];
            var plot = $.jqplot(divElemId, [addData, changeData, delData], {
                stackSeries: true,
                title:'Author Activity',
                legend: {show: showLegend, location: 'ne'},
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barDirection:'horizontal',barPadding: 6, barMargin:15}
                    },
                series: [{label: 'Adding', color:'blue'}, {label: 'Modifying', color:'green'}, {label: 'Deleting', color:'red'}],
                axes:{
                    yaxis:{
                    renderer:$.jqplot.CategoryAxisRenderer,
                    ticks:[$TICKDATA]                    
                    },
                    xaxis:{min:0, max:100.0}                 
                    }
                }
            );
            return(plot);
        }
        '''
        assert(len(authlabellist) == len(addfraclist))
        assert(len(authlabellist) == len(changefraclist))
        assert(len(authlabellist) == len(delfraclist))
                
        addDataList = ['[%.2f,%d]'% (addfrac,idx) for addfrac, idx in zip(addfraclist, itertools.count(1))]
        addDataStr = ','.join(addDataList)

        changeDataList = ['[%.2f,%d]'% (changefrac,idx) for changefrac, idx in zip(changefraclist, itertools.count(1))]
        changeDataStr = ','.join(changeDataList)

        delDataList = ['[%.2f,%d]'% (delfrac,idx) for delfrac, idx in zip(delfraclist, itertools.count(1))]
        delDataStr = ','.join(changeDataList)

        ticksDataList = []

        for author in authlabellist:
            if( len(author) == 0):
                author= " "
            ticksDataList.append('"%s"'% author)        
        ticksDataStr = ','.join(ticksDataList)
        ticksDataStr = ticksDataStr.replace('\n', '\\n')
        
        return(self.__getGraphScript(template, {"TICKDATA":ticksDataStr, "ADDDATA":addDataStr, "CHANGEDATA":changeDataStr,"DELDATA":delDataStr}))
            
    def DirectorySizePieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size pie graph")
        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth, maxdircount)

        template = '''        
            function directorySizePieGraph(divElemId, showLegend) {
            var data = [$DIRSIZEDATA];
            var plot = $.jqplot(divElemId, [data], {
                    title: 'Directory Size (Pie)',
                    legend:{show:showLegend},
                    seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{sliceMargin:8}}                    
            });
            return(plot);
        };
        '''
        
        assert(len(dirlist) == len(dirsizelist))

        dirdatastr = ''
        if( len(dirsizelist) > 0):
            datalist = ["['%s (%d)', %d]" % (dirname,dirsize,dirsize) for dirname, dirsize in zip(dirlist, dirsizelist)]            
            dirdatastr = ',\n'.join(datalist)
            
        return(self.__getGraphScript(template, {"DIRSIZEDATA":dirdatastr}))
    
        
    def DirFileCountPieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory File Count pie graph")

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)
                
        template = '''        
            function dirFileCountPieGraph(divElemId, showLegend) {
            var data = [$DIRSIZEDATA];
            var plot = $.jqplot(divElemId, [data], {
                    title: 'Directory File Count (Pie)',
                    legend:{show:showLegend},
                    seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{sliceMargin:8}}                    
            });
            return(plot);
        };
        '''
        
        assert(len(dirlist) == len(dirsizelist))

        dirdatastr = ''
        if( len(dirsizelist) > 0):
            dirdatalist = ["['%s (%d)', %d]" % (dirname,dirsize,dirsize) for dirname, dirsize in zip(dirlist, dirsizelist)]            
            dirdatastr = ',\n'.join(dirdatalist)
            
        return(self.__getGraphScript(template, {"DIRSIZEDATA":dirdatastr}))
    
           
    def DirectorySizeLineGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")

        template = '''
            function dirSizeLineGraph(divElemId, showLegend) {
            $LOCDATA
            var plot = $.jqplot(divElemId, locdata, {
                legend:{show:showLegend}, 
                title:'Directory Size(Lines of Code)',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:[$SERIESDATA]
                });
                return(plot);
            };
        '''
        
        #We only want the ten most important directories, the graf gets to blury otherwise
        #dirlist = self.svnstats.getDirnames(depth)
        #dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth)

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)
        numDirs = len(dirlist)

        outstr = StringIO.StringIO()
        
        for dirname, idx in zip(dirlist, range(0, numDirs)):
            dates, loclist = self.svnstats.getDirLocTrendStats(dirname)
            outstr.write("var dir%dLocData=[" % idx)
            datalist = ['[\'%s\', %d]' % (date,lc) for date, lc in zip(dates,loclist)]
            outstr.write(',\n'.join(datalist))
            outstr.write("];\n")
        outstr.write("var locdata = [")
        datalist = [ "dir%dLocData" % idx for idx in range(0, numDirs)]
        outstr.write(",".join(datalist))
        outstr.write("];\n")
        locdatastr = outstr.getvalue()

        datalist = ["{label:'%s', lineWidth:2, markerOptions:{style:'filledCircle',size:2}}" % dirname for dirname, idx in zip(dirlist, itertools.count(0))]            
        seriesdata = ',\n'.join(datalist)
        
        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "SERIESDATA":seriesdata}))    

    def AuthorsCommitTrend(self):
        self._printProgress("Calculating Author commits trend histogram graph")

        #hard coded bins based on 'days between two consecutive' commits (approx. log scale)
        # 0, 1hr, 4hrs, 8hr(1day), 2 days
        binsList = [0.0, 1.0/24.0,4.0/24.0, 1.0, 2.0, 4.0, 8.0, 16.0]
        binlabels = ["0-1 hr", "1-4 hrs", "4hrs-1 day", "1-2 days", "2-4 days", "4-8 days", "8-16 days"]
        data = self.svnstats.getAuthorsCommitTrendHistorgram(binsList)
        
        template = '''        
            function authorsCommitTrend(divElemId,showLegend) {
            var data = [$DATA];
            var plot = $.jqplot(divElemId, [data], {
                title:'Authors Commit Trend Histogram',
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barPadding: 6, barMargin:15}, 
                    shadowAngle:135},                
            axes:{
                xaxis:{
                    renderer:$.jqplot.CategoryAxisRenderer,
                    label:'Time Between Consecutive Commits by Same Author (in Days)'
                },
                yaxis:{min:0}                 
            }
            });
            return(plot);
        };
        '''
        assert(len(data) == len(binlabels))
        datalist = ["['%s',%d]" % (label, actdata) for actdata, label in zip(data, binlabels)]            
        data = ','.join(datalist)

        return(self.__getGraphScript(template, {"DATA":data}))
                    
    def _getGraphParamDict(self, thumbsize, maxdircount = 10):
        graphParamDict = dict()
            
        graphParamDict["thumbwid"]= "%dpx" % thumbsize
        graphParamDict["thumbht"]="%dpx" % thumbsize
        
        graphParamDict["RepoName"]=self.reponame
        graphParamDict["TagCloud"] = self.TagCloud()
        graphParamDict["AuthCloud"] = self.AuthorCloud()
        graphParamDict["BasicStats"] = self.BasicStats(HTMLBasicStatsTmpl)
        graphParamDict["ActiveFiles"] = self.ActiveFiles()
        graphParamDict["ActiveAuthors"] = self.ActiveAuthors()
        graphParamDict["LocTable"] = self.LocGraph()
        graphParamDict["ContriLoCTable"]= self.LocGraphAllDev()
        graphParamDict["AvgLoCTable"] = self.AvgFileLocGraph()
        graphParamDict["FileCountTable"] = self.FileCountGraph()
        graphParamDict["FileTypeCountTable"] = self.FileTypesGraph()
        graphParamDict["ActivityByWeekdayTable"] = self.ActivityByWeekday()
        graphParamDict["ActivityByTimeOfDayTable"] = self.ActivityByTimeOfDay()
        graphParamDict["CommitActIdxTable"] = self.CommitActivityIdxGraph()
        graphParamDict["LoCChurnTable"] = self.LocChurnGraph()
        graphParamDict["DirSizePie"] = self.DirectorySizePieGraph(self.dirdepth, maxdircount)
        graphParamDict["DirFileCountPie"] = self.DirFileCountPieGraph(self.dirdepth, maxdircount)
        graphParamDict["DirSizeLine"] = self.DirectorySizeLineGraph(self.dirdepth, maxdircount)
        graphParamDict["AuthorsCommitTrend"] = self.AuthorsCommitTrend()
        graphParamDict["AuthorActivityGraph"] = self.AuthorActivityGraph()
    
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
        jsFileList = ['excanvas.compiled.js', 'jquery.min.js',
                      'jqplot/jquery.jqplot.js', 'jqplot/jquery.jqplot.min.css',
                      'jqplot/plugins/jqplot.dateAxisRenderer.min.js',
                      'jqplot/plugins/jqplot.categoryAxisRenderer.min.js',
                      'jqplot/plugins/jqplot.barRenderer.min.js',
                      'jqplot/plugins/jqplot.dateAxisRenderer.min.js',
                      'jqplot/plugins/jqplot.pieRenderer.min.js']
        
        try:
            srcdir = os.path.dirname(os.path.abspath(__file__))
            srcdir = os.path.join(srcdir, 'javascript')
            outdir = os.path.abspath(outdir)
            for jsfile in jsFileList:
                jsfile = os.path.normpath(jsfile)
                srcfile =os.path.join(srcdir, jsfile)
                shutil.copy(srcfile, outdir)
        except Exception, expinst:
            print "Need jquery, excanvas and jqPlot files couldnot be copied."
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
                
        svnstats = SVNStats(svndbpath)     
        svnplot = SVNPlotJS(svnstats, template=options.template)
        svnplot.SetVerbose(options.verbose)
        svnplot.SetRepoName(options.reponame)
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize, options.maxdircount,copyjs=options.copyjs)
        
if(__name__ == "__main__"):
    RunMain()
    
