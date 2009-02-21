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
14. Bug Commit Trend graph - Number of commits with words like 'bug' or 'fix' in the message -- Done
15. Repository heatmap (treemap)


To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''

__revision__ = '$Revision:$'
__date__     = '$Date:$'

import matplotlib.pyplot as plt
from optparse import OptionParser
import sqlite3
import os.path, sys
import string,StringIO
import math
from svnplotbase import *

HTMLIndexTemplate ='''
<html>
<head><title>Subversion Stats Plot for $RepoName</title>
    <style type="text/css">
    th {background-color: #F5F5F5; text-align:center}
    /*td {background-color: #FFFFF0}*/
    h3 {background-color: transparent;margin:2}
    h4 {background-color: transparent;margin:1}    
    </style>
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
<th colspan=3 align="center"><h3>Top 10 Active Files</h3></th>
</tr>
<tr>
    <td colspan=3>
    $ActiveFiles
    </td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Lines of Code Graphs</h3></th>
</tr>
<tr>
    <td align="center" width="25%"><h4>Lines of Code</h4><br/>
    <a href="$LoC"><img src="$LoC" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" width="25%"><h4>Contributed Lines of Code</h4><br/>
    <a href="$LoCByDev"><img src="$LoCByDev" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" width="25%"><h4>Average File Size</h4><br/>
    <a href="$AvgLoC"><img src="$AvgLoC" width="$thumbwid" height="$thumbht"></a>
    </td>    
</tr>
<tr>
<th colspan=3 align="center"><h3>File Count Graphs</h3></th>
</tr>
<tr>
    <td align="center" width="25%"><h4>File Count</h4><br/>
    <a href="$FileCount"><img src="$FileCount" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" width="25%"><h4>File Types</h4><br/>
    <a href="$FileTypes"><img src="$FileTypes" width="$thumbwid" height="$thumbht"></a>
    </td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Directory Size Graphs</h3></th>
</tr>
<tr>
   <td align="center"><h4>Current Directory Size</h4><br/>
    <a href="$DirSizePie"><img src="$DirSizePie" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center"><h4>Directory Size</h4><br/>
    <a href="$DirSizeLine"><img src="$DirSizeLine" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center"><h4>Directory Size(FileCount)</h4><br/>
    <a href="$DirFileCountPie"><img src="$DirFileCountPie" width="$thumbwid" height="$thumbht"></a>
    </td>
</tr>
<tr>
<th colspan=3 align="center"><h3>Commit Activity Graphs</h3></th>
</tr>
<tr>
    <td align="center" width="25%"><h4>Commit Activity By Day of Week </h4><br/>
    <a href="$ActByWeek"><img src="$ActByWeek" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" width="25%"><h4>Commit Activity By Hour of Day</h4><br/>
    <a href="$ActByTimeOfDay"><img src="$ActByTimeOfDay" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" width="25%"><h4>Author Activity</h4><br/>
    <a href="$AuthActivity"><img src="$AuthActivity" width="$thumbwid" height="$thumbht"></a>
    </td>
</tr>
<tr>
    <td align="center" width="25%"><h4>Developer Commit Activity</h4><br/>
    <a href="$CommitAct"><img src="$CommitAct" width="$thumbwid" height="$thumbht"></a>
    </td>    
    <td align="center" width="25%"><h4>Time Difference Between Consecutive Revisions</h4><br/>
    <a href="$RevTimeDelta"><img src="$RevTimeDelta" width="$thumbwid" height="$thumbht"></a>
    </td>    
</tr>
<tr>
<th colspan=3 align="center"><h3>Bug Pronness Graphs</h3></th>
</tr>
<tr>
   <td span=4 align="center">
       <h4>Bug fix Commits</h4><br/>
       <a href="$BugfixCommitsTrend"><img src="$BugfixCommitsTrend" width="$thumbwid" height="$thumbht"></a>        
   </td>   
</tr>
<th colspan=3 align="center"><h3>Log Message Tag Cloud</h3></th>
</tr>
<tr id='tagcloud'>
<td colspan=3 align="center">$TagCloud</td>
</tr>
</table>
</body>
</html>
'''

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

GraphNameDict = dict(ActByWeek="actbyweekday", ActByTimeOfDay="actbytimeofday", RevTimeDelta="revtimedelta",
                     LoC="loc", LoCChurn="churnloc", FileCount="filecount", LoCByDev="localldev",
                     AvgLoC="avgloc", AuthActivity="authactivity",CommitAct="commitactivity",
                     DirSizePie="dirsizepie", DirSizeLine="dirsizeline", DirFileCountPie="dirfilecount",
                     BugfixCommitsTrend="bugfixcommits", FileTypes="filetypes")
                         
class SVNPlot(SVNPlotBase):
    def __init__(self, svnstats, dpi=100, format='png'):
        SVNPlotBase.__init__(self, svnstats, dpi,format)
        self.commitGraphHtPerAuthor = 2 #In inches
        self.authorsToDisplay = 10
        self.fileTypesToDisplay = 20
        self.dirdepth = 1
                
    def AllGraphs(self, dirpath, svnsearchpath='/', thumbsize=100):
        self.svnstats.SetSearchPath(svnsearchpath) 
        self.ActivityByWeekday(self._getGraphFileName(dirpath, "ActByWeek"))
        self.ActivityByTimeOfDay(self._getGraphFileName(dirpath, "ActByTimeOfDay"))
        self.AuthorActivityGraph(self._getGraphFileName(dirpath, "AuthActivity"))
        self.CommitActivityGraph(self._getGraphFileName(dirpath, "CommitAct"))
        self.RevTimeDeltaGraph(self._getGraphFileName(dirpath, "RevTimeDelta"))
        self.LocGraph(self._getGraphFileName(dirpath, "LoC"))
        self.LocChurnGraph(self._getGraphFileName(dirpath,"LoCChurn"))
        self.LocGraphAllDev(self._getGraphFileName(dirpath,"LoCByDev"))
        self.AvgFileLocGraph(self._getGraphFileName(dirpath, "AvgLoC"))
        self.FileCountGraph(self._getGraphFileName(dirpath, "FileCount"))
        self.FileTypesGraph(self._getGraphFileName(dirpath, "FileTypes"))
        self.BugfixCommitsTrend(self._getGraphFileName(dirpath, "BugfixCommitsTrend"))

        self.DirectorySizePieGraph(self._getGraphFileName(dirpath,"DirSizePie"), self.dirdepth)
        self.DirectorySizeLineGraph(self._getGraphFileName(dirpath, "DirSizeLine"),self.dirdepth)
        self.DirFileCountPieGraph(self._getGraphFileName(dirpath, "DirFileCountPie"),self.dirdepth)
        
        graphParamDict = self._getGraphParamDict( thumbsize)
        
        htmlidxTmpl = string.Template(HTMLIndexTemplate)        
        htmlidxname = os.path.join(dirpath, "index.htm")
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(htmlidxTmpl.safe_substitute(graphParamDict))
        htmlfile.close()
                               
    def ActivityByWeekday(self, filename):
        self._printProgress("Calculating Activity by day of week graph")
        
        data, labels = self.svnstats.getActivityByWeekday()
        
        ax = self._drawBarGraph(data, labels,0.5)
        ax.set_ylabel('Commits')
        ax.set_xlabel('Day of Week')
        ax.set_title('Activity By Day of Week')

        fig = ax.figure                        
        fig.savefig(filename, dpi=self.dpi, format=self.format)        

    def ActivityByTimeOfDay(self, filename):
        self._printProgress("Calculating Activity by time of day graph")
        
        data, labels = self.svnstats.getActivityByTimeOfDay()
        
        ax = self._drawBarGraph(data, labels,0.5)
        ax.set_ylabel('Commits')
        ax.set_xlabel('Hour of Day')
        ax.set_title('Activity By Hour of Day')

        fig = ax.figure                        
        fig.savefig(filename, dpi=self.dpi, format=self.format)        
        
    def LocGraph(self, filename):
        self._printProgress("Calculating LoC graph")
        ax = self._drawLocGraph()
        ax.set_ylabel('Lines')        
        ax.set_title('Lines of Code')
        self._closeDateLineGraph(ax, filename)

    def LocGraphAllDev(self, filename):
        self._printProgress("Calculating Developer Contribution graph")
        ax = None
        authList = self.svnstats.getAuthorList(self.authorsToDisplay)
        for author in authList:
            ax = self._drawlocGraphLineByDev(author, ax)

        #Add the list of authors as figure legend.
        #axes legend is added 'inside' the axes and overlaps the labels or the graph
        #lines depending on the location
        authLabelList = [self._getAuthorLabel(auth) for auth in authList]
            
        self._addFigureLegend(ax, authLabelList)
        
        ax.set_title('Contributed Lines of Code')
        ax.set_ylabel('Lines')        
        self._closeDateLineGraph(ax, filename)
        
    def LocGraphByDev(self, filename, devname):
        ax = self._drawlocGraphLineByDev(devname)
        ax.set_title('Contributed LoC by %s' % devname)
        ax.set_ylabel('Line Count')
        self._closeDateLineGraph(ax, filename)

    def RevTimeDeltaGraph(self, filename):
        self._printProgress("Calculating graph of time difference between consecutive revisions")
        
        revlist, authlist, timedeltalist = self.svnstats.getRevTimeDeltaStats()
        assert(len(revlist) == len(timedeltalist))
        fig = plt.figure()            
        ax = fig.add_subplot(111)
        #ax.semilogy(revlist, timedeltalist)
        ax.vlines(revlist, [0]*len(revlist), timedeltalist, color='b')
        ax.set_ylim(ymin=0.0)
        #ax.plot(revlist, timedeltalist)
        ax.set_title("Time Difference between consecutive revisions")
        ax.set_xlabel("Revisions")
        ax.set_ylabel("Time Difference (hr)")
        ax.grid(True)
        fig.savefig(filename, dpi=self.dpi, format=self.format)
        
    def RevTimeDeltaGraphAuthClr(self, filename):
        self._printProgress("Calculating graph of time difference between consecutive revisions")

        #number of unique authors to get. 
        numTopAuthors = len(self.clrlist)-1
        revlist, authlist, timedeltalist = self.svnstats.getRevTimeDeltaStats(numTopAuthors)
        assert(len(revlist) == len(timedeltalist) and len(revlist) == len(authlist))
        #create 
        authdatadict = dict()
        for revno, author, timediff in zip(revlist, authlist, timedeltalist):
            authdata= authdatadict.get(author)
            if( authdata == None):
                authdata = ([], [])
                authdatadict[author] = authdata
            authdata[0].append(revno)
            authdata[1].append(timediff)
            
        assert(len(authdatadict) <= len(self.clrlist))
        fig = plt.figure()            
        ax = fig.add_subplot(111)
        ax.set_color_cycle(self.clrlist)
        handlelist = []        
        for authdata, clr in zip(authdatadict.values(), self.clrlist):
            authrevlist = authdata[0]
            authtimedifflist = authdata[1]
            ax.vlines(authrevlist, [0]*len(authrevlist), authtimedifflist, colors=clr)
            #create a dummy line for legend creation
            lines = ax.plot(authrevlist[0:1], authtimedifflist[0:1], color=clr)
            handlelist.append(lines)
            
        ax.legend(handlelist, authdatadict.keys(), loc="upper right", ncol=1, prop=self._getLegendFont())
        ax.set_ylim(ymin=0.0)
        ax.set_title("Time Difference between consecutive revisions")
        ax.set_xlabel("Revisions")
        ax.set_ylabel("Time Difference (hr)")
        ax.grid(True)
        fig.savefig(filename, dpi=self.dpi, format=self.format)
        
    def LocChurnGraph(self, filename):
        self._printProgress("Calculating LoC and Churn graph")
        ax = self._drawLocGraph()
        ax = self._drawDailyChurnGraph(ax)
        ax.set_title('LoC and Churn')
        ax.set_ylabel('Line Count')        
        #ax.legend(loc='center right')
        self._closeDateLineGraph(ax, filename)
        
    def FileCountGraph(self, filename):
        self._printProgress("Calculating File Count graph")

        dates, fc = self.svnstats.getFileCountStats()        
        
        ax = self._drawDateLineGraph(dates, fc)
        ax.set_title('File Count')
        ax.set_ylabel('Files')
        self._closeDateLineGraph(ax, filename)

    def FileTypesGraph(self, filename):
        self._printProgress("Calculating File Types graph")

        #first get the file types and
        ftypelist, ftypecountlist = self.svnstats.getFileTypesStats(self.fileTypesToDisplay)
                
        barwid = 0.2
        ax = self._drawHBarGraph(ftypecountlist, ftypelist, barwid)
        ax.set_xlabel("Number of files")
        ax.set_ylabel("File Type")
        ax.set_title('File Types')
        fig = ax.figure
        fig.savefig(filename, dpi=self.dpi, format=self.format)
            
    def AvgFileLocGraph(self, filename):
        self._printProgress("Calculating Average File Size graph")

        dates, avgloclist = self.svnstats.getAvgLoC()                
            
        ax = self._drawDateLineGraph(dates, avgloclist)
        ax.set_title('Average File Size (Lines)')
        ax.set_ylabel('LoC/Files')
        
        self._closeDateLineGraph(ax, filename)

    def AuthorActivityGraph(self, filename):
        self._printProgress("Calculating Author Activity graph")

        authlist, addfraclist,changefraclist,delfraclist = self.svnstats.getAuthorActivityStats(self.authorsToDisplay)
        dataList = [addfraclist, changefraclist, delfraclist]

        authlabellist = [self._getAuthorLabel(author) for author in authlist]
        
        barwid = 0.2
        legendlist = ["Adding", "Modifying", "Deleting"]
        ax = self._drawStackedHBarGraph(dataList, authlabellist, legendlist, barwid)
        #set the x-axis format.                
        ax.set_xbound(0, 100)
        xfmt = FormatStrFormatter('%d%%')
        ax.xaxis.set_major_formatter(xfmt)
        #set the y-axis format
        plt.setp( ax.get_yticklabels(), visible=True, fontsize='x-small')
        
        ax.set_title('Author Activity')
        fig = ax.figure
        fig.savefig(filename, dpi=self.dpi, format=self.format)

    def CommitActivityGraph(self, filename):
        self._printProgress("Calculating Commit activity graph")
        
        authList = self.svnstats.getAuthorList(self.authorsToDisplay)
        authCount = len(authList)
        
        authIdx = 1
        refaxs = None
        for author in authList:
            axs = self._drawCommitActivityGraphByAuthor(authCount, authIdx, author, refaxs)
            authIdx = authIdx+1
            #first axes is used as reference axes. Since the reference axis limits are shared by
            #all axes, every autoscale_view call on the new 'axs' will update the limits on the
            #reference axes. Hence I am storing xmin,xmax limits and calculating the minimum/maximum
            # limits for reference axis everytime. 
            if( refaxs == None):
                refaxs = axs

        #Set the x axis label on the last graph
        axs.set_xlabel('Date')
        
        #Turn on the xtick display only on the last graph
        plt.setp( axs.get_xmajorticklabels(), visible=True)
        plt.setp( axs.get_xminorticklabels(), visible=True)
        
        #Y axis is always set to 0 to 24 hrs
        refaxs.set_ybound(0, 24)
        hrLocator= FixedLocator([0,6,12,18,24])
        refaxs.yaxis.set_major_locator(hrLocator)
        
        self._closeScatterPlot(refaxs, filename, 'Commit Activity')
        
    def DirectorySizePieGraph(self, filename, depth=2):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory size pie graph")
        
        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth)
        
        if( len(dirsizelist) > 0):
           axs = self._drawPieGraph(dirsizelist, dirlist)
           axs.set_title('Directory Sizes')        
           fig = axs.figure
           fig.savefig(filename, dpi=self.dpi, format=self.format)

    def DirFileCountPieGraph(self, filename, depth=2):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory File Count pie graph")

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth)
                
        if( len(dirsizelist) > 0):
           axs = self._drawPieGraph(dirsizelist, dirlist)
           axs.set_title('Directory Size(File Count)')        
           fig = axs.figure
           fig.savefig(filename, dpi=self.dpi, format=self.format)
           
    def DirectorySizeLineGraph(self, filename, depth=2):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")
        
        ax = None
        dirlist = self.svnstats.getDirnames(depth)
        for dirname in dirlist:
            ax = self._drawDirectorySizeLineGraphByDir(dirname, ax)

        self._addFigureLegend(ax, dirlist, loc="center right", ncol=1)
            
        ax.set_title('Directory Size (Lines of Code)')
        ax.set_ylabel('Lines')        
        self._closeDateLineGraph(ax, filename)
        
    def BugfixCommitsTrend(self, filename):
        self._printProgress("Calculating Bug fix commit trend")
        
        dates, fc, commitchurn = self.svnstats.getBugfixCommitsTrendStats()
        
        ax = None
        ax = self._drawDateLineGraph(dates, fc,ax)        
        ax = self._drawDateLineGraph(dates, commitchurn, ax)
        ax.set_title('Bugfix Commits Trend')
        ax.set_ylabel('Commited Files Count')
        ax.legend(("Total Commited Files", "Committed Files Churn"), prop=self._getLegendFont())
        self._closeDateLineGraph(ax, filename)

    def TagCloud(self, numWords=50):
        self._printProgress("Calculating tag cloud for log messages")
        words = self.svnstats.getLogMsgWordFreq(5)
        #first get sorted wordlist (reverse sorted by frequency)
        tagWordList = sorted(words.items(), key=operator.itemgetter(1),reverse=True)
        #now extract top 'numWords' from the list and then sort it with alphabetical order.
        tagWordList = sorted(tagWordList[0:numWords], key=operator.itemgetter(0))        
        #now calculate the maximum value from the sorted list.
        maxFreq = max(tagWordList, key=operator.itemgetter(1))[1]
        maxFreq = math.log(maxFreq)
        #change the font size between "-2" to "+8" relative to current font size
        tagHtmlStr = ' '.join([('<font size="%+d">%s</font>\n'%(min(-2+math.log(val)*5/maxFreq+0.5, +8), x))
                                   for x,val in tagWordList])                
        return(tagHtmlStr)

    def BasicStats(self, basicStatsTmpl):
        '''
        get the html string for basic repository statistics (like last revision, etc)
        '''
        self._printProgress("Calculating Basic stats")
        basestats = self.svnstats.getBasicStats()
        #replace dates with proper formated date strings
        basestats['FirstRevDate']= basestats['FirstRevDate'].strftime('%b %d, %Y %I:%M %p')
        basestats['LastRevDate']= basestats['LastRevDate'].strftime('%b %d, %Y %I:%M %p')
        statsTmpl = string.Template(basicStatsTmpl)
        statsStr = statsTmpl.safe_substitute(basestats)
        
        return(statsStr)

    def ActiveFiles(self):
        '''
        TODO - template for generating the hot files list. Currently format is hard coded as
        HTML ordered list
        '''
        hotfiles = self.svnstats.getHotFiles(10)
        outstr = StringIO.StringIO()
        outstr.write("<ol>\n")
        for filepath, temperatur in hotfiles:
            outstr.write("<li>%s</li>\n"%filepath)
        outstr.write("</ol>\n")
        return(outstr.getvalue())
        
    def _drawLocGraph(self):
        dates, loc = self.svnstats.getLoCStats()        
        ax = self._drawDateLineGraph(dates, loc)
        return(ax)
    
    def _drawDailyChurnGraph(self, ax):
        dates, churnlist = self.svnstats.getChurnStats()
        lines = ax.vlines(dates, [0.1], churnlist, color='r', label='Churn')
        ax.set_ylim(ymin=0.0)
        return(ax)
            
    def _drawDirectorySizeLineGraphByDir(self, dirname, ax):
        dates, dirsizelist = self.svnstats.getDirLocTrendStats(dirname)
        ax = self._drawDateLineGraph(dates, dirsizelist, ax)
        return(ax)
        
    def _getGraphFileName(self, dirpath, graphname):
        filename = os.path.join(dirpath, GraphNameDict[graphname])
        #now add the extension based on the format
        filename = "%s.%s" % (filename, self.format)
        return(filename)
    
    def _getGraphParamDict(self, thumbsize):
        graphParamDict = dict()
        for graphname in GraphNameDict.keys():
            graphParamDict[graphname] = self._getGraphFileName(".", graphname)
            
        graphParamDict["thumbwid"]=str(thumbsize)
        graphParamDict["thumbht"]=str(thumbsize)
        graphParamDict["RepoName"]=self.reponame
        graphParamDict["TagCloud"] = self.TagCloud()
        graphParamDict["BasicStats"] = self.BasicStats(HTMLBasicStatsTmpl)
        graphParamDict["ActiveFiles"] = self.ActiveFiles()
        
        return(graphParamDict)

    def _drawCommitActivityGraphByAuthor(self, authIdx, authCount, author, axs=None):
        dates,committimelist= self.svnstats.getAuthorCommitActivityStats(author)
        #Plot title
        plotTitle = "Author : %s" % author
        axs = self._drawScatterPlot(dates, committimelist, authCount, authIdx, plotTitle, axs)
        
        return(axs)
            
    def _drawlocGraphLineByDev(self, devname, ax=None):
        dates, loc = self.svnstats.getLoCTrendForAuthor(devname)        
        ax = self._drawDateLineGraph(dates, loc, ax)
        return(ax)    
        
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
    parser.add_option("-r", "--dpi", dest="dpi", default=100, type="int",
                      help="set the dpi of output png images")
    parser.add_option("-t", "--thumbsize", dest="thumbsize", default=100, type="int",
                      help="set the widht and heigth of thumbnail display (pixels)")
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments"
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

        svnstats = SVNStats(svndbpath)     
        svnplot = SVNPlot(svnstats, dpi=options.dpi)
        svnplot.SetVerbose(options.verbose)
        svnplot.SetRepoName(options.reponame)
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize)
    
if(__name__ == "__main__"):
    RunMain()
    