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
import os.path, sys
import string,StringIO
import math
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
	</style>
	<link type="text/css" rel="stylesheet" href="jquery.jqplot.min.css"/>		
	<script type="text/javascript" src="jquery.min.js"></script>
	<script type="text/javascript" src="jquery.jqplot.min.js"></script>	
	<script type="text/javascript" src="jqplot.dateAxisRenderer.min.js"></script>	
	<script type="text/javascript" src="jqplot.categoryAxisRenderer.min.js"></script>
	<script type="text/javascript" src="jqplot.barRenderer.min.js"></script>
	<script type="text/javascript" src="jqplot.pieRenderer.min.js"></script>
</head>
<body>
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
    <div id="LoCTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $LocTable	
    </td>
    <td align="center">
    <div id="ContriLoCTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $ContriLoCTable
    </td>
    <td align="center">
    <div id="AvgLoCTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $AvgLoCTable
    </td>    
</tr>
<tr>
<th colspan=3 align="center"><h3>File Count Graphs</h3></th>
</tr>
<tr>
    <td align="center">
    <div id="FileCountTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $FileCountTable
    </td>
    <td align="center" >
    <div id="FileTypeCountTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $FileTypeCountTable
    </td>
    <td>&nbsp</td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Directory Size Graphs</h3></th>
</tr>
<tr>
   <td align="center">
    <div id="DirSizePie" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
   $DirSizePie
    </td>
    <td align="center">
    <div id="DirSizeLine" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
   $DirSizeLine
    </td>
    <td align="center">
    <div id="DirFileCountPie" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
   $DirFileCountPie  
    </td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Commit Activity Graphs</h3></th>
</tr>
<tr>
    <td align="center" >
        <div id="CommitActIdxTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
		$CommitActIdxTable
    </td>    
    <td align="center" >
    <div id="ActivityByWeekdayTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $ActivityByWeekdayTable
    </td>
    <td align="center" >
    <div id="ActivityByTimeOfDayTable" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $ActivityByTimeOfDayTable
    </td>    
</tr>
<tr>
    <td align="center" >
        <div id="AuthorsCommitTrend" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
    $AuthorsCommitTrend
    </td>
    <td align="center">
    <div id="AuthorActivityGraph" style="display: block;margin-left:auto;margin-right:auto;height:$thumbht;width:$thumbwid;"></div>
	 $AuthorActivityGraph
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
<script type="text/javascript">
                function showAllGraphs(showLegend) {
                    locgraph();
                    /*locChurnGraph(showLegend);*/
                    contri_locgraph();
                    avglocgraph();
                    fileCountGraph();
                    fileTypesGraph();
                    ActivityByWeekday();
                    ActivityByTimeOfDay();
                    CommitActivityIndexGraph();
                    directorySizePieGraph(showLegend);
                    dirFileCountPieGraph(showLegend);
                    dirSizeLineGraph(showLegend);
                    authorsCommitTrend();
                    authorActivityGraph(showLegend);                    
                };
                
			   $(document).ready(showAllGraphs(false));

	</script>
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
 
                
    def AllGraphs(self, dirpath, svnsearchpath='/', thumbsize=200, maxdircount = 10):
        self.svnstats.SetSearchPath(svnsearchpath)
        #LoC and FileCount Graphs
        print "thumbsize = %d" % thumbsize
        graphParamDict = self._getGraphParamDict(thumbsize)
        
        htmlidxname = os.path.join(dirpath, "index.htm")
        htmlidxTmpl = string.Template(self.template)
        outstr = htmlidxTmpl.safe_substitute(graphParamDict)
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(outstr.encode('utf-8'))
        htmlfile.close()
                               
    def ActivityByWeekday(self):
        self._printProgress("Calculating Activity by day of week graph")
        
        data, labels = self.svnstats.getActivityByWeekday()
        
        template = '''        
            function ActivityByWeekday() {
            data = $DATA;
            $.jqplot('ActivityByWeekdayTable', [data], {
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
        }
        '''
        assert(len(data) == len(labels))
        
        outstr = StringIO.StringIO()
        outstr.write("[")
        for actdata, wkday in zip(data, labels):
            outstr.write("['%s',%d]," % (wkday, actdata))
        outstr.write("]")
        data = outstr.getvalue()

        return(self.__getGraphScript(template, {"DATA":data}))

    def ActivityByTimeOfDay(self):
        self._printProgress("Calculating Activity by time of day graph")
        
        data, labels = self.svnstats.getActivityByTimeOfDay()
        
        template = '''        
            function ActivityByTimeOfDay() {
            data = $DATA;
            $.jqplot('ActivityByTimeOfDayTable', [data], {
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
        }
        '''
        assert(len(data) == len(labels))
        
        outstr = StringIO.StringIO()
        outstr.write("[")
        for actdata, tmofday in zip(data, labels):
            outstr.write("['%s',%d]," % (tmofday, actdata))
        outstr.write("]")
        data = outstr.getvalue()

        return(self.__getGraphScript(template, {"DATA":data}))


    def CommitActivityIdxGraph(self):
        '''
        commit activity index over time graph. Commit activity index is calculated as 'hotness/temperature'
        of repository using the newtons' law of cooling.
        '''
        self._printProgress("Calculating Commit Activity Index by time of day graph")
        cmdates, temperaturelist = self.svnstats.getRevActivityTemperature()
        
        template = '''  
        function CommitActivityIndexGraph() {
            locdata = $DATA;
            $.jqplot('CommitActIdxTable', [locdata], {
                title:'Commit Activity Index over time',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]})
                };
        '''
        
        assert(len(cmdates) == len(temperaturelist))
        outstr = StringIO.StringIO()
        outstr.write("[")
        for date, temperature in zip(cmdates, temperaturelist):
            outstr.write('[\'%s\', %.4f],\n' % (date,temperature))
        outstr.write("]")
        
        return(self.__getGraphScript(template, {"DATA":outstr.getvalue()}))        

        
    def LocGraph(self):
        self._printProgress("Calculating LoC graph")
        
        template = '''  
            function locgraph() {
            locdata = $DATA;
            $.jqplot('LoCTable', [locdata], {
                title:'Lines of Code',
                axes:{
                    xaxis:{renderer:$.jqplot.DateAxisRenderer, label:'LoC'},
                    yaxis:{min:0}
                },
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]});                
             };
        '''
        
        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))
        outstr = StringIO.StringIO()
        outstr.write("[")
        for date, lc in zip(dates, loc):
            outstr.write('[\'%s\', %d],\n' % (date,lc))
        outstr.write("]")
        
        return(self.__getGraphScript(template, {"DATA":outstr.getvalue()}))        

    def LocGraphAllDev(self):
        self._printProgress("Calculating Developer Contribution graph")
        template = '''
            function contri_locgraph(showLegend) {
            $LOCDATA
            $.jqplot('ContriLoCTable', locdata, {
                legend:{show:showLegend}, 
                title:'Contributed Lines of Code',
                axes:
                {
                    xaxis:{renderer:$.jqplot.DateAxisRenderer, label:'LoC'},
                    yaxis:{min:0}
                },
                series:$SERIESDATA
                });
                
                };
        '''
        
        authList = self.svnstats.getAuthorList(self.authorsToDisplay)
        authLabelList = [self._getAuthorLabel(auth) for auth in authList]
        numAuth = len(authList)
        
        outstr = StringIO.StringIO()
        
        for author, idx in zip(authLabelList, range(0, numAuth)):
            dates, loc = self.svnstats.getLoCTrendForAuthor(author)
            outstr.write("auth%dLocData = [" % idx)
            for date, lc in zip(dates, loc):
                outstr.write('[\'%s\', %d],\n' % (date,lc))
            outstr.write("];\n")
        outstr.write("locdata = [")
        for idx in range(0, numAuth):
            outstr.write("auth%dLocData,"% idx)
        outstr.write("];\n")
        locdatastr = outstr.getvalue()

        outstr = StringIO.StringIO()
        outstr.write("[")
        for author, idx in zip(authList, range(0, numAuth)):            
            outstr.write("{label:'%s', lineWidth:2, markerOptions:{style:'filledCircle',size:2}}," % author)
        outstr.write("]")
            
        seriesdata = outstr.getvalue()            
        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "SERIESDATA":seriesdata}))
    
            
    def LocChurnGraph(self):
        self._printProgress("Calculating LoC and Churn graph")

        template = '''
            function locChurnGraph(showLegend) {
            locdata = [$LOCDATA];
            churndata= [$CHURNDATA];
            
            $.jqplot('LoCChurnTable', [locdata, churndata], {
                title:'Lines of Code and Churn Graph',
                legend:{show:showLegend},
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{label:'LoC', min:0},y2axis:{label:'Churn', min:0} },
                series:[
                    {label:'LoC', lineWidth:2, markerOptions:{style:'filledCircle',size:2}},
                    {label:'Churn',yaxis:'y2axis',lineWidth:2, markerOptions:{style:'filledCircle',size:2}}
                ]
            });
        };
        '''

        dates, loc = self.svnstats.getLoCStats()
        assert(len(dates) == len(loc))
        outstr = StringIO.StringIO()
        for date, lc in zip(dates, loc):
            outstr.write('[\'%s\', %d],\n' % (date,lc))
        locdatastr = outstr.getvalue()
        
        dates, churnlist = self.svnstats.getChurnStats()

        outstr = StringIO.StringIO()
        for date, churn in zip(dates, churnlist):
            outstr.write('[\'%s\', %d],\n' % (date,churn))
        churndatastr = outstr.getvalue()

        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "CHURNDATA":churndatastr}))                
        
    def FileCountGraph(self):
        self._printProgress("Calculating File Count graph")

        dates, fc = self.svnstats.getFileCountStats()        

        template = '''        
            function fileCountGraph() {
            data = [$DATA];
            $.jqplot('FileCountTable', data, {
                title:'File Count',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]})
                };
        '''
        
        dates, fclist = self.svnstats.getFileCountStats()        
        
        assert(len(dates) == len(fclist))
        outstr = StringIO.StringIO()
        outstr.write("[")
        for date, fc in zip(dates, fclist):
            outstr.write('[\'%s\', %d],\n' % (date,fc))
        outstr.write("]")
        
        return(self.__getGraphScript(template, {"DATA":outstr.getvalue()}))        

    def FileTypesGraph(self):
        self._printProgress("Calculating File Types graph")
        template = '''        
            function fileTypesGraph() {
            data = $DATA;
            $.jqplot('FileTypeCountTable', [data], {
                title:'File Types',
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barDirection:'horizontal', barPadding: 6, barMargin:15}, 
                shadowAngle:135},                
            axes:{
                xaxis:{min:0}, 
                yaxis:{
                    renderer:$.jqplot.CategoryAxisRenderer, 
                }
            }
        });
        }
        '''
        
        #first get the file types and
        ftypelist, ftypecountlist = self.svnstats.getFileTypesStats(self.fileTypesToDisplay)
        assert(len(ftypelist) == len(ftypecountlist))
        
        outstr = StringIO.StringIO()
        outstr.write("[")
        for ftype, ftcount in zip(ftypelist, ftypecountlist):
            outstr.write("[%d, '%s']," % (ftcount, ftype))
        outstr.write("]")
        data = outstr.getvalue()

        return(self.__getGraphScript(template, {"DATA":data}))
        
            
    def AvgFileLocGraph(self):
        self._printProgress("Calculating Average File Size graph")
            
        template = '''        
            function avglocgraph() {
            locdata = [$LOCDATA];
            $.jqplot('AvgLoCTable', locdata, {
                title:'Average File LoC',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:[{lineWidth:2, markerOptions:{style:'filledCircle',size:2}}]})
                };
        '''
        
        dates, avgloclist = self.svnstats.getAvgLoC()                
        
        assert(len(dates) == len(avgloclist))
        outstr = StringIO.StringIO()
        outstr.write("[")
        for date, lc in zip(dates, avgloclist):
            outstr.write('[\'%s\', %d],\n' % (date,lc))
        outstr.write("]")
                
        return(self.__getGraphScript(template, {"LOCDATA":outstr.getvalue()}))

    def AuthorActivityGraph(self):
        self._printProgress("Calculating Author Activity graph")

        authlist, addfraclist,changefraclist,delfraclist = self.svnstats.getAuthorActivityStats(self.authorsToDisplay)
        authlabellist = [self._getAuthorLabel(author) for author in authlist]
        
        legendlist = ["Adding", "Modifying", "Deleting"]
        template = '''        
            function authorActivityGraph(showLegend) {            
            var addData = [$ADDDATA];
            var changeData = [$CHANGEDATA];
            var delData = [$DELDATA];
            $.jqplot('AuthorActivityGraph', [addData, changeData, delData], {
                stackSeries: true,
                title:'Author Activity',
                legend: {show: showLegend, location: 'ne'},
                seriesDefaults:{
                    renderer:$.jqplot.BarRenderer, 
                    rendererOptions:{barDirection:'horizontal',barPadding: 6, barMargin:15},                    
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
        }
        '''
        assert(len(authlabellist) == len(addfraclist))
        assert(len(authlabellist) == len(changefraclist))
        assert(len(authlabellist) == len(delfraclist))
        
        addData = StringIO.StringIO()
        changeData = StringIO.StringIO()
        delData = StringIO.StringIO()
        ticksData = StringIO.StringIO()

        idx = 1        
        for author, addfrac, changefrac, delfrac in zip(authlabellist, addfraclist, changefraclist,delfraclist):
            addData.write('[%.2f,%d],'% (addfrac,idx))
            changeData.write('[%.2f,%d],'% (changefrac, idx))
            delData.write('[%.2f,%d],'% (delfrac,idx))
            if( len(author) == 0):
                author= " "
            ticksData.write('"%s",'% author)
            idx = idx+1
        
        addDataStr = addData.getvalue()
        changeDataStr = changeData.getvalue()
        delDataStr = delData.getvalue()
        ticksDataStr = ticksData.getvalue()
        ticksDataStr = ticksDataStr.replace('\n', '\\n')
        
        return(self.__getGraphScript(template, {"TICKDATA":ticksDataStr, "ADDDATA":addDataStr, "CHANGEDATA":changeDataStr,"DELDATA":delDataStr}))
            
    def DirectorySizePieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size pie graph")
        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth, maxdircount)

        template = '''        
            function directorySizePieGraph(showLegend) {
            data = [$DIRSIZEDATA];
            $.jqplot('DirSizePie', [data], {
                    title: 'Directory Size (Pie)',
                    legend:{show:showLegend},
                    seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{sliceMargin:8}}                    
            });
        }
        '''
        
        assert(len(dirlist) == len(dirsizelist))

        dirdatastr = ''
        if( len(dirsizelist) > 0):
            outstr = StringIO.StringIO()
            for dirname, dirsize in zip(dirlist, dirsizelist):
                outstr.write("['%s (%d)', %d],\n" % (dirname,dirsize,dirsize))
            dirdatastr = outstr.getvalue()
            
        return(self.__getGraphScript(template, {"DIRSIZEDATA":dirdatastr}))
    
        
    def DirFileCountPieGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory File Count pie graph")

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)
                
        template = '''        
            function dirFileCountPieGraph(showLegend) {
            data = [$DIRSIZEDATA];
            $.jqplot('DirFileCountPie', [data], {
                    title: 'Directory File Count (Pie)',
                    legend:{show:showLegend},
                    seriesDefaults:{renderer:$.jqplot.PieRenderer, rendererOptions:{sliceMargin:8}}                    
            });
        }
        '''
        
        assert(len(dirlist) == len(dirsizelist))

        dirdatastr = ''
        if( len(dirsizelist) > 0):
            outstr = StringIO.StringIO()
            for dirname, dirsize in zip(dirlist, dirsizelist):
                outstr.write("['%s (%d)', %d],\n" % (dirname,dirsize,dirsize))
            dirdatastr = outstr.getvalue()
            
        return(self.__getGraphScript(template, {"DIRSIZEDATA":dirdatastr}))
    
           
    def DirectorySizeLineGraph(self, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")

        template = '''
            function dirSizeLineGraph(showLegend) {
            $LOCDATA
            $.jqplot('DirSizeLine', locdata, {
                legend:{show:showLegend}, 
                title:'Directory Size(Lines of Code)',
                axes:{xaxis:{renderer:$.jqplot.DateAxisRenderer},yaxis:{min:0}},
                series:$SERIESDATA
                }) };
        '''
        
        #We only want the ten most important directories, the graf gets to blury otherwise
        #dirlist = self.svnstats.getDirnames(depth)
        #dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth)

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)
        numDirs = len(dirlist)

        outstr = StringIO.StringIO()
        
        for dirname, idx in zip(dirlist, range(0, numDirs)):
            dates, loclist = self.svnstats.getDirLocTrendStats(dirname)
            outstr.write("dir%dLocData=[" % idx)
            for date, lc in zip(dates,loclist):
                outstr.write('[\'%s\', %d],\n' % (date,lc))
            outstr.write("];\n")
        outstr.write("locdata = [")
        for idx in range(0, numDirs):
            outstr.write("auth%dLocData,"% idx)
        outstr.write("];\n")
        locdatastr = outstr.getvalue()
                
        outstr = StringIO.StringIO()
        outstr.write("[")
        for dirname, idx in zip(dirlist, range(0, numDirs)):
            outstr.write("{label:'%s', lineWidth:2, markerOptions:{style:'filledCircle',size:2}}," % dirname)
        outstr.write("]")
            
        seriesdata = outstr.getvalue()            
        return(self.__getGraphScript(template, {"LOCDATA":locdatastr, "SERIESDATA":seriesdata}))    

    def AuthorsCommitTrend(self):
        self._printProgress("Calculating Author commits trend histogram graph")

        #hard coded bins based on 'days between two consecutive' commits (approx. log scale)
        # 0, 1hr, 4hrs, 8hr(1day), 2 days
        binsList = [0.0, 1.0/24.0,4.0/24.0, 1.0, 2.0, 4.0, 8.0, 16.0]
        binlabels = ["0-1 hr", "1-4 hrs", "4hrs-1 day", "1-2 days", "2-4 days", "4-8 days", "8-16 days"]
        data = self.svnstats.getAuthorsCommitTrendHistorgram(binsList)
        
        template = '''        
            function authorsCommitTrend() {
            data = $DATA;
            $.jqplot('AuthorsCommitTrend', [data], {
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
        }
        '''
        assert(len(data) == len(binlabels))
        
        outstr = StringIO.StringIO()
        outstr.write("[")
        for actdata, label in zip(data, binlabels):
            outstr.write("['%s',%d]," % (label, actdata))
        outstr.write("]")
        data = outstr.getvalue()

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
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize, options.maxdircount)
        
if(__name__ == "__main__"):
    RunMain()
    
