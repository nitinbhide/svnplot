'''
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
8. average file size vs date line graph -- Done
9. directory size vs date line graph. Using different coloured lines for each directory
10. directory size pie chart (latest status) -- Done
11. Loc and Churn graph (loc vs date, churn vs date)- Churn is number of lines touched
	(i.e. lines added + lines deleted + lines modified)
12. Repository heatmap (treemap)
13. Bug Commit Trend graph - Number of commits with words like 'bug' or 'fix' in the message

--- Nitin Bhide (nitinbhide@gmail.com)

Part of 'svnplot' project
Available on google code at http://code.google.com/p/svnplot/
Licensed under the 'New BSD License'

To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''

__revision__ = '$Revision:$'
__date__     = '$Date:$'

import matplotlib.pyplot as plt
from optparse import OptionParser
import sqlite3
import calendar, datetime
import os.path, sys
import string
from svnplotbase import *

HTMLIndexTemplate ='''
<html>
<head><title>Subversion Stats Plot for $RepoName</title>
    <style type="text/css">
    th {background-color: #F5F5F5; text-align:center}
    td {background-color: #FFFFF0}
    h3 {background-color: transparent;margin:2}
    h4 {background-color: transparent;margin:1}    
    </style>
</head>
<body>
<table align="center" frame="box">
<caption><h1 align="center">Subversion Statistics for $RepoName</h1></caption>
<tr>
<th colspan=4 align="center"><h3>Lines of Code Graphs</h3></th>
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
    <td align="center" width="25%"><h4>File Count</h4><br/>
    <a href="$FileCount"><img src="$FileCount" width="$thumbwid" height="$thumbht"></a>
    </td>
</tr>
<tr>
<th colspan=4 align="center"><h3>Directory Size Graphs</h3></th>
</tr>
<tr>
   <td align="center"><h4>Current Directory Size</h4><br/>
    <a href="$DirSizePie"><img src="$DirSizePie" width="$thumbwid" height="$thumbht"></a>
    </td>
    <td align="center"><h4>Directory Size</h4><br/>
    <a href="$DirSizeLine"><img src="$DirSizeLine" width="$thumbwid" height="$thumbht"></a>
    </td>
</tr>
<tr>
<th colspan=4 align="center"><h3>Commit Activity Graphs</h3></th>
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
    <td align="center" width="25%"><h4>Developer Commit Activity</h4><br/>
    <a href="$CommitAct"><img src="$CommitAct" width="$thumbwid" height="$thumbht"></a>
    </td>    
</tr>
<tr>
<th colspan=4 align="center"><h3>Bug Pronness Graphs</h3></th>
</tr>
<tr>
   <td span=4 align="center">
       <h4>Bug fix Commits</h4><br/>
       <a href="$BugfixCommitsTrend"><img src="$BugfixCommitsTrend" width="$thumbwid" height="$thumbht"></a>        
   </td>   
</tr>
</table>
</body>
</html>
'''

GraphNameDict = dict(ActByWeek="actbyweekday", ActByTimeOfDay="actbytimeofday",
                     LoC="loc", LoCChurn="churnloc", FileCount="filecount", LoCByDev="localldev",
                     AvgLoC="avgloc", AuthActivity="authactivity",CommitAct="commitactivity",
                     DirSizePie="dirsizepie", DirSizeLine="dirsizeline",
                     BugfixCommitsTrend="bugfixcommits")
                         
class SVNPlot(SVNPlotBase):
    def __init__(self, svndbpath, dpi=100, format='png'):
        SVNPlotBase.__init__(self, svndbpath, dpi,format)
        self.commitGraphHtPerAuthor = 2 #In inches
        self.bugfixkeywords = ['bug', 'fix']
        self.authorsToDisplay = 10
                
    def AllGraphs(self, dirpath, svnsearchpath='/%', thumbsize=100):
        self.SetSearchPath(svnsearchpath) 
        self.ActivityByWeekday(self._getGraphFileName(dirpath, "ActByWeek"));
        self.ActivityByTimeOfDay(self._getGraphFileName(dirpath, "ActByTimeOfDay"));
        self.LocGraph(self._getGraphFileName(dirpath, "LoC"));
        self.LocChurnGraph(self._getGraphFileName(dirpath,"LoCChurn"));
        self.FileCountGraph(self._getGraphFileName(dirpath, "FileCount"));
        self.LocGraphAllDev(self._getGraphFileName(dirpath,"LoCByDev"));
        self.AvgFileLocGraph(self._getGraphFileName(dirpath, "AvgLoC"));
        self.AuthorActivityGraph(self._getGraphFileName(dirpath, "AuthActivity"));
        self.CommitActivityGraph(self._getGraphFileName(dirpath, "CommitAct"));
        self.BugfixCommitsTrend(self._getGraphFileName(dirpath, "BugfixCommitsTrend"));

        depth=2
        self.DirectorySizePieGraph(self._getGraphFileName(dirpath,"DirSizePie"), depth);
        self.DirectorySizeLineGraph(self._getGraphFileName(dirpath, "DirSizeLine"),depth);
        
        graphParamDict = self._getGraphParamDict( thumbsize)
        dict(GraphNameDict)
        graphParamDict["thumbwid"]=str(thumbsize)
        graphParamDict["thumbht"]=str(thumbsize)
        graphParamDict["RepoName"]=self.reponame
        
        htmlidxTmpl = string.Template(HTMLIndexTemplate)        
        htmlidxname = os.path.join(dirpath, "index.htm")
        htmlfile = file(htmlidxname, "w")
        htmlfile.write(htmlidxTmpl.safe_substitute(graphParamDict))
        htmlfile.close()
                               
    def ActivityByWeekday(self, filename):
        self._printProgress("Calculating Activity by day of week graph")
           
        self.cur.execute("select strftime('%w', SVNLog.commitdate), count(SVNLog.revno) from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by strftime('%w', SVNLog.commitdate)", (self.searchpath,))
        labels =[]
        data = []
        for dayofweek, commitcount in self.cur:
           data.append(commitcount)           
           labels.append(calendar.day_abbr[int(dayofweek)])

        ax = self._drawBarGraph(data, labels,0.5)
        ax.set_ylabel('Commits')
        ax.set_xlabel('Day of Week')
        ax.set_title('Activity By Day of Week')

        fig = ax.figure                        
        fig.savefig(filename, dpi=self.dpi, format=self.format)        

    def ActivityByTimeOfDay(self, filename):
        self._printProgress("Calculating Activity by time of day graph")
        
        self.cur.execute("select strftime('%H', SVNLog.commitdate), count(SVNLog.revno) from SVNLog, SVNLogDetail \
                          where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                          group by strftime('%H', SVNLog.commitdate)", (self.searchpath,))
        labels =[]
        data = []
        for hourofday, commitcount in self.cur:
           data.append(commitcount)           
           labels.append(int(hourofday))

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
        authList = self._getAuthorList(self.authorsToDisplay)
        for author in authList:
            ax = self._drawlocGraphLineByDev(author, ax)

        #Add the list of authors as figure legend.
        #axes legend is added 'inside' the axes and overlaps the labels or the graph
        #lines depending on the location 
        self._addFigureLegend(ax, authList)
        
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
        
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.searchpath,))
        dates = []
        fc = []
        totalfiles = 0
        for year, month, day, fadded,fdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            totalfiles = totalfiles + fadded-fdeleted
            fc.append(float(totalfiles))
        
        ax = self._drawDateLineGraph(dates, fc)
        ax.set_title('File Count')
        ax.set_ylabel('Files')
        self._closeDateLineGraph(ax, filename)

    def AvgFileLocGraph(self, filename):
        self._printProgress("Calculating Average File Size graph")
        
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted), \
                         sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.searchpath,))
        dates = []
        avgloclist = []
        avgloc = 0
        totalFileCnt = 0
        totalLoc = 0
        for year, month, day, locadded, locdeleted, filesadded, filesdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            totalLoc = totalLoc + locadded-locdeleted
            totalFileCnt = totalFileCnt + filesadded - filesdeleted
            avgloc = 0.0
            if( totalFileCnt > 0.0):
               avgloc = float(totalLoc)/float(totalFileCnt)
            avgloclist.append(avgloc)
            
        ax = self._drawDateLineGraph(dates, avgloclist)
        ax.set_title('Average File Size (Lines)')
        ax.set_ylabel('LoC/Files')
        
        self._closeDateLineGraph(ax, filename)

    def AuthorActivityGraph(self, filename):
        self._printProgress("Calculating Author Activity graph")
        
        self.cur.execute("select SVNLog.author, sum(SVNLog.addedfiles), sum(SVNLog.changedfiles), \
                         sum(SVNLog.deletedfiles), count(SVNLog.revno) as commitcount from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by SVNLog.author order by commitcount DESC LIMIT 0, ?"
                         , (self.searchpath, self.authorsToDisplay,))

        authlist = []
        addfraclist = []
        changefraclist=[]
        delfraclist = []
        
        for author, filesadded, fileschanged, filesdeleted,commitcount in self.cur:
            authlist.append(author)            
            activitytotal = float(filesadded+fileschanged+filesdeleted)
            
            if( activitytotal > 0.0):
               addfraclist.append(float(filesadded)/activitytotal*100)
               changefraclist.append(float(fileschanged)/activitytotal*100)
               delfraclist.append(float(filesdeleted)/activitytotal*100)
            else:
               addfraclist.append(0.0)
               changefraclist.append(0.0)
               delfraclist.append(0.0)

        dataList = [addfraclist, changefraclist, delfraclist]
        
        barwid = 0.2
        legendlist = ["Adding", "Modifying", "Deleting"]
        ax = self._drawStackedHBarGraph(dataList, authlist, legendlist, barwid)
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
        
        authList = self._getAuthorList(self.authorsToDisplay)
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
        
        self.cur.execute("select dirname(SVNLogDetail.changedpath, ?) as dirpath, sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                    from SVNLog, SVNLogDetail \
                    where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                    group by dirpath", (depth, self.searchpath,))
            
        dirlist = []
        dirsizelist = []        
        for dirname, linesadded, linesdeleted in self.cur:
            dsize = linesadded-linesdeleted
            if( dsize > 0):
                dirlist.append(dirname)
                dirsizelist.append(dsize)
                
        if( len(dirsizelist) > 0):
           axs = self._drawPieGraph(dirsizelist, dirlist)
           axs.set_title('Directory Sizes')        
           fig = axs.figure
           fig.savefig(filename, dpi=self.dpi, format=self.format)
            
    def DirectorySizeLineGraph(self, filename, depth=2):
        '''
        depth - depth of directory search relative to search path. Default value is 2
        '''
        self._printProgress("Calculating Directory size line graph")
        
        self.cur.execute("select dirname(changedpath, ?) as dirpath from SVNLogDetail where changedpath like ? \
                         group by dirpath",(depth, self.searchpath,))
        
        dirlist = [dirname for dirname, in self.cur]
        ax = None
        for dirname in dirlist:
            ax = self._drawDirectorySizeLineGraphByDir(dirname, ax)

        self._addFigureLegend(ax, dirlist, loc="center right", ncol=1)
            
        ax.set_title('Directory Size (Lines of Code)')
        ax.set_ylabel('Lines')        
        self._closeDateLineGraph(ax, filename)
        
    def BugfixCommitsTrend(self, filename):
        self._printProgress("Calculating Bug fix commit trend")
        
        sqlquery = "select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate), \
                         strftime('%%d', SVNLog.commitdate), count(*) as commitfilecount \
                         from SVNLog, SVNLogDetail where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s' \
                         and %s group by date(SVNLog.commitdate)" % (self.searchpath, self._bugFixKeywordsInMsgSql())
        
        self.cur.execute(sqlquery)
        dates = []
        fc = []
        commitchurn = []
        totalcommits = 0
        for year, month, day, commitfilecount in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            commitchurn.append(float(commitfilecount))
            totalcommits = totalcommits+commitfilecount
            fc.append(float(totalcommits))
            
        ax = None
        ax = self._drawDateLineGraph(dates, fc,ax)        
        ax = self._drawDateLineGraph(dates, commitchurn, ax)
        ax.set_title('Bugfix Commits Trend')
        ax.set_ylabel('Commited Files Count')
        ax.legend(("Total Commited Files", "Committed Files Churn"), prop=self._getLegendFont())
        self._closeDateLineGraph(ax, filename)
        
    def _drawLocGraph(self):
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.searchpath,))
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        ax = self._drawDateLineGraph(dates, loc)
        return(ax)
    
    def _drawDailyChurnGraph(self, ax):
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded+SVNLogDetail.linesdeleted) as churn \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.searchpath,))
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, churn in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            loc.append(float(churn))
        
        lines = ax.vlines(dates, [0.1], loc, color='r', label='Churn')
        
        return(ax)
            
    def _drawDirectorySizeLineGraphByDir(self, dirname, ax):
        sqlQuery = "select sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted), \
                    strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate), strftime('%%d', SVNLog.commitdate) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s%%' \
                         group by date(SVNLog.commitdate)" % (dirname)

        self.cur.execute(sqlQuery)
        dates = []
        dirsizelist = []
        dirsize = 0
        for locadded, locdeleted, year, month, day in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            dirsize= dirsize+locadded-locdeleted
            dirsizelist.append(max(0, float(dirsize)))

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
        return(graphParamDict)

    def _drawCommitActivityGraphByAuthor(self, authIdx, authCount, author, axs=None):
        self.cur.execute("select strftime('%H', commitdate), strftime('%Y', SVNLog.commitdate), \
                    strftime('%m', SVNLog.commitdate), strftime('%d', SVNLog.commitdate) \
                    from SVNLog where author=? group by date(commitdate)" ,(author,))

        dates = []
        committimelist = []
        for hr, year, month, day in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            committimelist.append(int(hr))
        #Plot title
        plotTitle = "Author : %s" % author
        axs = self._drawScatterPlot(dates, committimelist, authCount, authIdx, plotTitle, axs)
        
        return(axs)
            
    def _drawlocGraphLineByDev(self, devname, ax=None):
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? and SVNLog.author=? \
                         group by date(SVNLog.commitdate)",(self.searchpath, devname,))
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        ax = self._drawDateLineGraph(dates, loc, ax)
        return(ax)
    
    def _bugFixKeywordsInMsgSql(self):
        sqlstr = "( "
        first = True
        for keyword in self.bugfixkeywords:
            if( first == False):
                sqlstr = sqlstr + ' or '
            sqlstr=sqlstr + "svnlog.msg like '%%%s%%'" % keyword
            first = False
        sqlstr = sqlstr + " )"
        return(sqlstr)
    
        
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
            
        svnplot = SVNPlot(svndbpath, dpi=options.dpi)
        svnplot.SetVerbose(options.verbose)
        svnplot.SetRepoName(options.reponame)
        svnplot.AllGraphs(graphdir, options.searchpath, options.thumbsize)
    
if(__name__ == "__main__"):
    RunMain()
    