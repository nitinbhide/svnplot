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


import matplotlib.pyplot as plt
import matplotlib.mpl as mpl
from optparse import OptionParser
import sqlite3
import os.path, sys
import string,StringIO
import math
from svnplotbase import *
from svnstats import *

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
    <td align="center"><h4>Lines of Code</h4><br/>
    <a href="$LoC"><img src="$LoC" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center"><h4>Contributed Lines of Code</h4><br/>
    <a href="$LoCByDev"><img src="$LoCByDev" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center"><h4>Average File Size</h4><br/>
    <a href="$AvgLoC"><img src="$AvgLoC" width="$thumbwid" height="$thumbht"></a>
    </td>    
</tr>
<tr>
<th colspan=3 align="center"><h3>File Count Graphs</h3></th>
</tr>
<tr>
    <td align="center"><h4>File Count</h4><br/>
    <a href="$FileCount"><img src="$FileCount" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" ><h4>File Types</h4><br/>
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
    <td align="center" ><h4>Commit Activity Index over time</h4><br/>
        <a href="$CommitActivityIdx"><img src="$CommitActivityIdx" width="$thumbwid" height="$thumbht"></a>
    </td>    
    <td align="center" ><h4>Commit Activity By Day of Week </h4><br/>
    <a href="$ActByWeek"><img src="$ActByWeek" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" ><h4>Commit Activity By Hour of Day</h4><br/>
    <a href="$ActByTimeOfDay"><img src="$ActByTimeOfDay" width="$thumbwid" height="$thumbht"></a>
    </td>
    
</tr>
<tr>
    <td align="center"><h4>Author Activity</h4><br/>
    <a href="$AuthActivity"><img src="$AuthActivity" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center" ><h4>Developer Commit Activity</h4><br/>
    <a href="$CommitAct"><img src="$CommitAct" width="$thumbwid" height="$thumbht"></a>
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

MINFONTSIZE=-2
MAXFONTSIZE=8

def getTagFontSize(freq, minFreqLog, maxFreqLog):
    #change the font size between "-2" to "+8" relative to current font size
    #change minFreqLog in such a way smallest log(freq)-minFreqLog is greater than 0
    fontsizevariation = (MAXFONTSIZE-MINFONTSIZE)
    minFreqLog = minFreqLog-(maxFreqLog-minFreqLog)/fontsizevariation
    #now calculate the scaling factor for scaling the freq to fontsize.
    if maxFreqLog == minFreqLog:
	    scalingFactor = 1
    else:
    	scalingFactor = fontsizevariation/(maxFreqLog-minFreqLog)
    fontsize = int(MINFONTSIZE+((math.log(freq)-minFreqLog)*scalingFactor)+0.5)
    #now round off to ensure that font size remains in MINFONTSIZE and MAXFONTSIZE
    assert(fontsize >= MINFONTSIZE and fontsize <= MAXFONTSIZE)
    return(fontsize)

def getActivityClr(actIdx, clrNorm, cmap):
    rgbclr = clrNorm(actIdx)
    rgbclr = cmap(rgbclr)
    clrStr=mpl.colors.rgb2hex(rgbclr[0:3])    
    return(clrStr)

GraphNameDict = dict(ActByWeek="actbyweekday", ActByTimeOfDay="actbytimeofday", CommitActivityIdx="cmtactidx",
                     LoC="loc", LoCChurn="churnloc", FileCount="filecount", LoCByDev="localldev",
                     AvgLoC="avgloc", AuthActivity="authactivity",CommitAct="commitactivity",
                     DirSizePie="dirsizepie", DirSizeLine="dirsizeline", DirFileCountPie="dirfilecount",
                     FileTypes="filetypes", AuthorsCommitTrend="authorscommit")
                         
class SVNPlot(SVNPlotBase):
    def __init__(self, svnstats, dpi=100, format='png',template=None):
        SVNPlotBase.__init__(self, svnstats, dpi,format)
        self.commitGraphHtPerAuthor = 2 #In inches
        self.authorsToDisplay = 10
        self.fileTypesToDisplay = 20
        self.dirdepth = 2
        self.setTemplate(template)
        
    def setTemplate(self, template):
        self.template = HTMLIndexTemplate
        if( template != None):
            with open(template, "r") as f:
                self.template = f.read()
                
    def AllGraphs(self, dirpath, svnsearchpath='/', thumbsize=100):
        self.svnstats.SetSearchPath(svnsearchpath)
        #Commit activity graphs
        self.ActivityByWeekday(self._getGraphFileName(dirpath, "ActByWeek"))
        self.ActivityByTimeOfDay(self._getGraphFileName(dirpath, "ActByTimeOfDay"))
        self.AuthorActivityGraph(self._getGraphFileName(dirpath, "AuthActivity"))
        self.CommitActivityGraph(self._getGraphFileName(dirpath, "CommitAct"))
        self.CommitActivityIdxGraph(self._getGraphFileName(dirpath, "CommitActivityIdx"))
        self.AuthorsCommitTrend(self._getGraphFileName(dirpath, "AuthorsCommitTrend"))
        #LoC and FileCount Graphs
        self.LocGraph(self._getGraphFileName(dirpath, "LoC"))
        self.LocChurnGraph(self._getGraphFileName(dirpath,"LoCChurn"))
        self.LocGraphAllDev(self._getGraphFileName(dirpath,"LoCByDev"))
        self.AvgFileLocGraph(self._getGraphFileName(dirpath, "AvgLoC"))
        self.FileCountGraph(self._getGraphFileName(dirpath, "FileCount"))
        self.FileTypesGraph(self._getGraphFileName(dirpath, "FileTypes"))
        #Directory size graphs
        self.DirectorySizePieGraph(self._getGraphFileName(dirpath,"DirSizePie"), self.dirdepth, maxdircount)
        self.DirectorySizeLineGraph(self._getGraphFileName(dirpath, "DirSizeLine"),self.dirdepth, maxdircount)
        self.DirFileCountPieGraph(self._getGraphFileName(dirpath, "DirFileCountPie"),self.dirdepth, maxdircount)
        
        graphParamDict = self._getGraphParamDict( thumbsize)
        
        htmlidxTmpl = string.Template(self.template)
        htmlidxname = os.path.join(dirpath, "index.htm")
        outstr = htmlidxTmpl.safe_substitute(graphParamDict)
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(outstr.encode('utf-8'))
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

    def CommitActivityIdxGraph(self, filename):
        '''
        commit activity index over time graph. Commit activity index is calculated as 'hotness/temperature'
        of repository using the newtons' law of cooling.
        '''
        self._printProgress("Calculating Commit Activity Index by time of day graph")
        cmdates, temperaturelist = self.svnstats.getRevActivityTemperature()
        
        ax = self._drawDateLineGraph(cmdates, temperaturelist)
        ax.set_title('Commit Activity Index')
        ax.set_ylabel('Activity Index')
        self._closeDateLineGraph(ax, filename)
        
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
        #auto format the date.
        fig = refaxs.figure
        fig.autofmt_xdate()
        
        self._closeScatterPlot(refaxs, filename, 'Commit Activity')
        
    def DirectorySizePieGraph(self, filename, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory size pie graph")
        dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth, maxdircount)
        
        if( len(dirsizelist) > 0):
           axs = self._drawPieGraph(dirsizelist, dirlist)
           axs.set_title('Directory Sizes')        
           fig = axs.figure
           fig.savefig(filename, dpi=self.dpi, format=self.format)

    def DirFileCountPieGraph(self, filename, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating current Directory File Count pie graph")

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)
                
        if( len(dirsizelist) > 0):
           axs = self._drawPieGraph(dirsizelist, dirlist)
           axs.set_title('Directory Size(File Count)')        
           fig = axs.figure
           fig.savefig(filename, dpi=self.dpi, format=self.format)
           
    def DirectorySizeLineGraph(self, filename, depth=2, maxdircount=10):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")
        
        ax = None
        #dirlist = self.svnstats.getDirnames(depth)
        '''
        We only want the ten most important directories, the graf gets to blury otherwise
        '''
        #dirlist, dirsizelist = self.svnstats.getDirLoCStats(depth)

        dirlist, dirsizelist = self.svnstats.getDirFileCountStats(depth, maxdircount)

        for dirname in dirlist:
            ax = self._drawDirectorySizeLineGraphByDir(dirname, ax)

        self._addFigureLegend(ax, dirlist, loc="center right", ncol=1)
            
        ax.set_title('Directory Size (Lines of Code)')
        ax.set_ylabel('Lines')        
        self._closeDateLineGraph(ax, filename)
            
    def TagCloud(self, numWords=50):
        self._printProgress("Calculating tag cloud for log messages")
        words = self.svnstats.getLogMsgWordFreq(5)
        tagHtmlStr = ''
        if( len(words) > 0):
            #first get sorted wordlist (reverse sorted by frequency)
            tagWordList = sorted(words.items(), key=operator.itemgetter(1),reverse=True)
            #now extract top 'numWords' from the list and then sort it with alphabetical order.
            tagWordList = sorted(tagWordList[0:numWords], key=operator.itemgetter(0))        
            #now calculate the maximum value from the sorted list.
            minFreq = min(tagWordList, key=operator.itemgetter(1))[1]
            minFreqLog = math.log(minFreq)
            maxFreq = max(tagWordList, key=operator.itemgetter(1))[1]
            maxFreqLog = math.log(maxFreq)
            #change the font size between "-2" to "+8" relative to current font size
            tagHtmlStr = ' '.join([('<font size="%+d">%s</font>\n'%(getTagFontSize(freq, minFreqLog, maxFreqLog), x))
                                       for x,freq in tagWordList])                
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
        self._printProgress("Calculating Active (hot) files list")
        hotfiles = self.svnstats.getHotFiles(10)
        outstr = StringIO.StringIO()
        outstr.write("<ol>\n")
        for filepath, temperatur in hotfiles:
            outstr.write("<li>%s</li>\n"%filepath)
        outstr.write("</ol>\n")
        return(outstr.getvalue())

    def ActiveAuthors(self):
        '''
        TODO - template for generating the hot files list. Currently format is hard coded as
        HTML ordered list
        '''
        self._printProgress("Calculating Active authors list")
        hotfiles = self.svnstats.getActiveAuthors(10)
        outstr = StringIO.StringIO()
        outstr.write("<ol>\n")
        for author, temperatur in hotfiles:
            outstr.write("<li>%s</li>\n"%author)
        outstr.write("</ol>\n")
        return(outstr.getvalue())
    
    def AuthorCloud(self, maxAuthCount=50):
        self._printProgress("Calculating Author Tag Cloud")
        authCloud = self.svnstats.getAuthorCloud()
        tagHtmlStr = ''
        if( len(authCloud) > 0):
            #sort and extract maximum of the "maxAuthCount" number of author based on the
            #activity index
            authTagList = sorted(authCloud, key=operator.itemgetter(2),reverse=True)
            authTagList = authTagList[0:maxAuthCount]
            #remove elements being zeror or less
            for x in authTagList[:]:
                #if less than or equal zero remove, otherwise clrNorm fails 
                if (x[2] <= 0):
                    authTagList.remove(x)


 
            #now calculate the maximum value from the sorted list.
            minFreq = min(authTagList, key=operator.itemgetter(1))[1]
            minFreqLog = math.log(minFreq)
            maxFreq = max(authTagList, key=operator.itemgetter(1))[1]
            #if there is only one author or minFreq and maxFreq is same, then it will give wrong
            #results later. So make sure there is some difference between min and max freq.
            maxFreq = max(minFreq*1.2, maxFreq)
            maxFreqLog = math.log(maxFreq)
                
            minActivity = min(authTagList, key=operator.itemgetter(2))[2]
            maxActivity = max(authTagList, key=operator.itemgetter(2))[2]
            maxActivity = max(minActivity*1.2, maxActivity)
            clrNorm = mpl.colors.LogNorm(vmin=minActivity, vmax=maxActivity)
            cmap = mpl.cm.jet
            #Now sort the authers by author names
            authTagList = sorted(authTagList, key=operator.itemgetter(0))
            #change the font size between "-2" to "+8" relative to current font size
            tagHtmlStr = ' '.join([('<font size="%+d" color="%s">%s</font>\n'%
                                    (getTagFontSize(freq, minFreqLog, maxFreqLog), getActivityClr(actIdx, clrNorm, cmap), auth))
                                       for auth, freq, actIdx in authTagList])
        return(tagHtmlStr)

##    def AuthorsCommitTrend(self, filename):
##        self._printProgress("Calculating Author commits trend bar graph")
##        
##        labels, data, error = self.svnstats.getAuthorsCommitTrendMeanStddev()
##        
##        ax = self._drawBarGraph(data, labels,0.5,yerr=error)
##        ax.set_ylabel('Avg. Time betn consecutive commits')
##        ax.set_xlabel('Authors')
##        ax.set_title('Authors Commit Trend')
##        for label in ax.get_xticklabels():
##            label.set_rotation(20)
##            label.set_size('x-small')
##            label.set_ha('right')
##            
##        fig = ax.figure
##        fig.savefig(filename, dpi=self.dpi, format=self.format)                

    def AuthorsCommitTrend(self, filename,numbins=50):
        self._printProgress("Calculating Author commits trend histogram graph")
        
        data = self.svnstats.getAuthorsCommitTrendHistorgram()
        
        ax = self._drawHistogram(data,numbins=numbins, logbins=True)
        ax.set_xlabel('Time betn consecutive commits (days)')
        ax.set_ylabel('Number of commits')
        ax.set_title('Authors Commit Trend')
        for label in ax.get_xticklabels():
            label.set_rotation(20)
            label.set_size('x-small')
            label.set_ha('right')
            
        fig = ax.figure
        fig.savefig(filename, dpi=self.dpi, format=self.format)                

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
        graphParamDict["AuthCloud"] = self.AuthorCloud()
        graphParamDict["BasicStats"] = self.BasicStats(HTMLBasicStatsTmpl)
        graphParamDict["ActiveFiles"] = self.ActiveFiles()
        graphParamDict["ActiveAuthors"] = self.ActiveAuthors()
            
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
                      help="set the width and heigth of thumbnail display (pixels)")    
    parser.add_option("-p", "--template", dest="template", default=None,
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
        svnplot = SVNPlot(svnstats, dpi=options.dpi, template=options.template)
        svnplot.SetVerbose(options.verbose)
        svnplot.SetRepoName(options.reponame)
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize, options.maxdircount)
    
if(__name__ == "__main__"):
    RunMain()
    
