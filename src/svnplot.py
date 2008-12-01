'''
Generate various graphs from the Subversion log data in the sqlite database.
It assumes that the sqlite file is generated using the 'svnlog2sqlite.py' script.

Graph types to be supported
1. Activity by hour of day bar graph (commits vs hour of day) -- Done
2. Activity by day of week bar graph (commits vs day of week) -- Done
3. Author Activity horizontal bar graph (author vs adding+commiting percentage)
4. Commit activity for each developer - scatter plot (hour of day vs date)
5. Contributed lines of code line graph (loc vs dates). Using different colour line
   for each developer -- Done
6. total loc line graph (loc vs dates) -- Done
7. file count vs dates line graph -- Done
8. average file size vs date line graph -- Done
9. directory size vs date line graph. Using different coloured lines for each directory
10. directory size pie chart (latest status)
11. Loc and Churn graph (loc vs date, churn vs date)- Churn is number of lines touched
	(i.e. lines added + lines deleted + lines modified)
12. Repository heatmap (treemap)

--- Nitin Bhide (nitinbhide@gmail.com)

Part of 'svnplot' project
Available on google code at http://code.google.com/p/svnplot/
Licensed under the 'New BSD License'

To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''

import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
import sqlite3
import calendar, datetime
import os.path

class SVNPlot:
    def __init__(self, svndbpath, dpi=100, format='png'):
        self.svndbpath = svndbpath
        self.dpi = dpi
        self.format = format
        self.dbcon = sqlite3.connect(self.svndbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #self.dbcon.row_factory = sqlite3.Row
        self.cur = self.dbcon.cursor()        

    def __del__(self):
        self.dbcon.close()

    def AllGraphs(self, path):
        self.ActivityByWeekday(os.path.join(path, "actbyweekday.png"));
        self.ActivityByTimeOfDay(os.path.join(path, "actbytimeofday.png"));
        self.LocGraph(os.path.join(path, "loc.png"));
        self.FileCountGraph(os.path.join(path, "filecount.png"));
        self.LocGraphAllDev(os.path.join(path, "locbydev.png"));
        self.AvgFileLocGraph(os.path.join(path, "avgloc.png"));
                               
    def ActivityByWeekday(self, filename):
        self.cur.execute("select strftime('%w', commitdate), count(revno) from SVNLog group by strftime('%w', commitdate)")
        labels =[]
        data = []
        for dayofweek, commitcount in self.cur:
           data.append(commitcount)           
           labels.append(calendar.day_abbr[int(dayofweek)])

        ax = self._drawBarGraph(data, labels,0.5)
        ax.set_ylabel('commits')
        ax.set_xlabel('Day of Week')
        ax.set_title('Activity By Weekday')

        fig = ax.figure                        
        fig.savefig(filename, dpi=self.dpi, format=self.format)        

    def ActivityByTimeOfDay(self, filename):
        self.cur.execute("select strftime('%H', commitdate), count(revno) from SVNLog group by strftime('%H', commitdate)")
        labels =[]
        data = []
        for hourofday, commitcount in self.cur:
           data.append(commitcount)           
           labels.append(int(hourofday))

        ax = self._drawBarGraph(data, labels,0.5)
        ax.set_ylabel('commits')
        ax.set_xlabel('Time of Day')
        ax.set_title('Activity By Time of Day')

        fig = ax.figure                        
        fig.savefig(filename, dpi=self.dpi, format=self.format)        
        
    def LocGraph(self, filename, inpath='/%'):        
        self.cur.execute("select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate),\
                         strftime('%%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s'\
                         group by date(SVNLog.commitdate)" % inpath)
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        ax = self._drawDateLineGraph(dates, loc)
        ax.set_title('LoC')
        ax.set_ylabel('Line Count')
        
        self._closeDateLineGraph(ax, filename)

    def LocGraphAllDev(self, filename, inpath='/%'):
        #Find out the unique developers
        self.cur.execute("select author from SVNLog group by author")
        ax = None
        #get the auhor list and store it. Since LogGraphLineByDev also does an sql query. It will otherwise
        # get overwritten
        authList = [author for author, in self.cur]
        for author in authList:
            ax = self._drawlocGraphLineByDev(author, inpath,  ax)
            
        ax.legend(authList, loc='upper left')
            
        ax.set_title('Contributed LoC by Developer')
        ax.set_ylabel('Line Count')        
        self._closeDateLineGraph(ax, filename)
        
    def LocGraphByDev(self, filename, devname, inpath='/%'):
        ax = self._drawlocGraphLineByDev(devname, inpath)
        ax.set_title('Contributed LoC by Developer')
        ax.set_ylabel('Line Count')
        self._closeDateLineGraph(ax, filename)
            
    def FileCountGraph(self, filename, inpath='/%'): 
        self.cur.execute("select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate),\
                         strftime('%%d', SVNLog.commitdate), sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s'\
                         group by date(SVNLog.commitdate)" % inpath)
        dates = []
        fc = []
        totalfiles = 0
        for year, month, day, fadded,fdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            totalfiles = totalfiles + fadded-fdeleted
            fc.append(float(totalfiles))
        
        ax = self._drawDateLineGraph(dates, fc)
        ax.set_title('File Count')
        ax.set_ylabel('File Count')
        self._closeDateLineGraph(ax, filename)

    def AvgFileLocGraph(self, filename, inpath='/%'): 
        self.cur.execute("select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate),\
                         strftime('%%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted), \
                         sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s'\
                         group by date(SVNLog.commitdate)" % inpath)
        dates = []
        avgloclist = []
        avgloc = 0
        totalFileCnt = 0
        totalLoc = 0
        for year, month, day, locadded, locdeleted, filesadded, filesdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            totalLoc = totalLoc + locadded-locdeleted
            totalFileCnt = totalFileCnt + filesadded - filesdeleted
            avgloclist.append(float(totalLoc)/float(totalFileCnt))
            
        ax = self._drawDateLineGraph(dates, avgloclist)
        ax.set_title('Average LoC of File')
        ax.set_ylabel('LoC')
        
        self._closeDateLineGraph(ax, filename)
        
    def _drawlocGraphLineByDev(self, devname, inpath='/%', ax=None):
        sqlQuery = "select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate),\
                         strftime('%%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s' and SVNLog.author='%s' \
                         group by date(SVNLog.commitdate)" % (inpath, devname)
        print sqlQuery
        self.cur.execute(sqlQuery)
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        ax = self._drawDateLineGraph(dates, loc, ax)
        return(ax)
    
    def _drawBarGraph(self, data, labels, barwid):
        #create dummy locations based on the number of items in data values
        xlocations = [x*barwid*2+barwid for x in range(len(data))]
        xtickloc = [x+barwid/2.0 for x in xlocations]
        xtickloc.append(xtickloc[-1]+barwid)
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.set_xticks(xtickloc)
        ax.set_xticklabels(labels)
        ax.bar(xlocations, data, width=barwid)
        
        return(ax)

    def _closeDateLineGraph(self, ax, filename):
        assert(ax != None)
        ax.autoscale_view()
        years    = YearLocator()   # every year
        months   = MonthLocator(3)  # every 3 month
        yearsFmt = DateFormatter('%Y')
        # format the ticks
        ax.xaxis.set_major_locator(years)
        ax.xaxis.set_major_formatter(yearsFmt)
        ax.xaxis.set_minor_locator(months)
        ax.grid(True)        
        fig = ax.figure
        fig.savefig(filename, dpi=self.dpi, format=self.format)        
        
    def _drawDateLineGraph(self, dates, values, axs= None):
        if( axs == None):
            fig = plt.figure()            
            axs = fig.add_subplot(111)
            axs.set_color_cycle(['b', 'g', 'r', 'c', 'm', 'y', 'k'])                                 
            
        axs.plot_date(dates, values, '-', xdate=True, ydate=False)
        
        return(axs)

if(__name__ == "__main__"):
    #testing
    svndbpath = "D:\\nitinb\\SoftwareSources\\SVNPlot\\svnrepo.db"
    graphfile = "D:\\nitinb\\SoftwareSources\\SVNPlot\\graph.png"
    svnplot = SVNPlot(svndbpath)
    #svnplot.ActivityByTimeOfDay(graphfile)
    #svnplot.LocGraph(graphfile)
    svnplot.AllGraphs("D:\\nitinb\\SoftwareSources\\SVNPlot\\")
    