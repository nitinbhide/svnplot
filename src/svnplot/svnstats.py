'''
svnstats.py
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

This is a helper class for getting the actual subversion statistics from the database.
SVNPlot and other classes will use this to query the data and then render it as
graphs or html tables or json data.
'''
import logging

import sqlite3
import calendar, datetime
import sys
import string, re
import math
import operator
from collections import Counter

from util import *

COOLINGRATE = 0.06/24.0 #degree per hour
TEMPINCREMENT = 10.0 # degrees per commit
AMBIENT_TEMP = 1.1


def getTemperatureAtTime(curTime, lastTime, lastTemp, coolingRate):
    '''
    calculate the new temparature at time 'tm'. given the
    lastTemp - last temperature measurement,
    coolingRate - rate of cool per hour
    '''    
    try:
        if( isinstance(curTime,unicode)==True):
            curTime = datetime.datetime.strptime(curTime[:16], "%Y-%m-%d %H:%M")
        if( isinstance(lastTime,unicode)==True):
            lastTime = datetime.datetime.strptime(lastTime[:16], "%Y-%m-%d %H:%M")
            
        tmdelta = curTime-lastTime
        hrsSinceLastTime = tmdelta.days*24.0+tmdelta.seconds/3600.0
        #since this is cooling rate computation, curTime cannot be smaller than 'lastTime'
        #(i.e. if hrsSinceLastTime is -ve ) then reset hrsSinceLastTime to 0
        if( hrsSinceLastTime < 0.0):
            hrsSinceLastTime = 0.0
        tempFactor = -(coolingRate*hrsSinceLastTime)
        temperature = AMBIENT_TEMP + (lastTemp-AMBIENT_TEMP)*math.exp(tempFactor)
        assert(temperature>=AMBIENT_TEMP)
    except Exception, expinst:
        logging.debug("Error %s" % expinst)
        temperature = 0
        
    return(temperature)    
    
def _sqrt(num):
    return math.sqrt(num)
    
def update_bin(binlist, binvalues, value):
    '''
    return the index of bin from the binlist, where the 'value' belongs.
    '''
    assert(len(binlist) == len(binvalues)+1)
    assert(len(binlist) > 1)
    if( value >= binlist[0]):
        for idx, binmin, binmax in pairwise(binlist):
            if( value >= binmin and value < binmax):
                binvalues[idx] = binvalues[idx]+1
                return
    
def histogram_data(binlist, indata):
    '''
    calculate the histogram data from the binlist and input raw data. Similar to numpy.histogram function.
    '''
    try:
        import numpy
        logging.debug("Using numpy.histogram for bin data computation")
        (binvalues, binsList) = numpy.histogram(indata, bins=binsList,new=True)
    except:
        #NumPy import failed. Now fall back to replacement function.This will be slower than numpy.histogram
        logging.debug("Numpy not found. Using replacement function for histogram bin data computation")
        binvalues = [0]*(len(binlist)-1)

        for value in indata:
            update_bin(binlist, binvalues, value)
            
    return(binvalues)
        

class DeltaStdDev:
    '''
    tries to calculate standard deviation in single pass. It calculates the
    standard deviation value of difference between consecutive rows
    based on http://www.johndcook.com/standard_deviation.html
    '''
    def __init__(self):
        self.m_oldMean = 0.0
        self.m_newMean= 0.0
        self.m_oldS = 0.0
        self.m_newS = 0.0
        self.count = 0
        self.lastval = None

    def step(self, curval):        
        if self.lastval:
            self.count = self.count+1
            value = curval-self.lastval
            if (self.count == 1):
                self.m_oldMean = value
                self.m_newMean = value
                self.m_oldS = 0.0;
            else:
                self.m_newMean = self.m_oldMean + (value - self.m_oldMean)/self.count;
                self.m_newS = self.m_oldS + (value - self.m_oldMean)*(value - self.m_newMean);
        
                #set up for next iteration
                self.m_oldMean = self.m_newMean; 
                self.m_oldS = self.m_newS;            
        self.lastval=curval
        
    def finalize(self):
        stddev = 0.0
        if( self.count > 1):
            avg = self.m_newMean
            variance = self.m_newS/(self.count - 1)             
            stddev = math.sqrt(variance)
        return(stddev)

def sqlite_daynames():
    #calendar.day_abbr starts with Monday while for dayofweek returned by strftime 0 is Sunday.
    # so to get the correct day of week string, the day names list must be corrected in such a way
    # that it starts from Sunday
    daynames = [day for day in calendar.day_abbr]
    daynames = daynames[6:]+daynames[0:6]
    return(daynames)

class SVNStats(object):
    def __init__(self, svndbpath,firstrev=None,lastrev=None):
        self.svndbpath = svndbpath
        self.__searchpath = '/%'
        self.__startRev=None
        self.__endRev = None
        self.__endDate = None
        self.verbose = False        
        self.bugfixkeywords = ['bug', 'fix']
        self.__invalidWordPattern = re.compile("\d+|an|the|me|my|we|you|he|she|it|are|is|am|\
                        |will|shall|should|would|had|have|has|was|were|be|been|this|that|there|\
                        |who|when|how|where|which|\
                        |already|after|by|on|or|so|also|got|get|do|don't|from|all|but|\
                        |yet|to|in|out|of|for|if|yes|no|not|may|can|could|at|as|with|without", re.IGNORECASE)
        self.dbcon = None
        self.initdb(firstrev,lastrev)
        
    def initdb(self,firstrev,lastrev):
        if( self.dbcon != None):
            self.closedb()
            
        #InitSqlite
        self.dbcon = sqlite3.connect(self.svndbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #self.dbcon.row_factory = sqlite3.Row
        
        self.__create_db_functions()
                                    
        self.cur = self.dbcon.cursor()
        #set the LIKE operator to case sensitive behavior
        self.cur.execute("pragma case_sensitive_like(TRUE)")
        
        self.__init_start_end_revisions(firstrev,lastrev)
        
                
    def __create_db_functions(self):
        '''
        create various database and aggregation functions required
        '''
        # Create the function "regexp" for the REGEXP operator of SQLite
        self.dbcon.create_function("dirname", 3, dirname)
        self.dbcon.create_function("filetype", 1, filetype)
        self.dbcon.create_function("getTemperatureAtTime", 4, getTemperatureAtTime)
        self.dbcon.create_function("sqrt", 1, _sqrt)
        self.dbcon.create_aggregate("deltastddev", 1, DeltaStdDev)
        
        #it is possible, index is already there. in such cases ignore the exception
        try:
            #create an index based on author names as we need various author based
            #statistics
            self.cur.execute("CREATE TEMP INDEX SVNLogAuthIdx ON SVNLog (author ASC)")
        except:
            pass
        
    def __init_start_end_revisions(self, firstrev, lastrev):
        '''
        initialize the start and end revision numbers and start/end dates for queries 
        '''
        self.cur.execute("select max(commitdate),min(commitdate) from SVNLog")
        onedaydiff = datetime.timedelta(1)
        row = self.cur.fetchone()
        assert(row[0] != None)
        assert(row[1] != None)
        
        self.__endDate = (datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")+onedaydiff).date()
        self.__startDate = (datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")-onedaydiff).date()
        self.cur.execute("select min(revno), max(revno) from SVNLog")
        row = self.cur.fetchone()
        onerev = row[0]
        headrev = row[1]

        if firstrev == lastrev == None:
            self.__startRev = onerev
            self.__endRev = headrev

        if firstrev == None and lastrev != None:
            if (lastrev > headrev and lastrev < onerev):
                logging.debug("Error: Wrong last revision number")
                exit(-1)
            #set the start date to min date and end date to date of the lastrev revision in database table.
            self.__startRev = onerev
            #self.cur.execute('select commitdate from SVNLog where revno = ?', (lastrev,))
            #row = self.cur.fetchone()
            self.__endRev = lastrev
        if firstrev != None and lastrev == None:
            #set the start date to the date of firstrev revision date and end date to max date in database table.
            if (firstrev > headrev and firstrev < onerev):
                logging.debug("Error: Wrong first revision number")
                exit(-1) 
            self.__endRev = headrev
            #self.cur.execute('select commitdate from SVNLog where revno = ?', (firstrev,))
            #row = self.cur.fetchone()
            self.__startRev = firstrev        
 
        if firstrev != None and lastrev != None:
            #set the start date to the date of firstrev revision date and end date to max date in database table.
            #self.cur.execute('select commitdate from SVNLog where revno = ?', (lastrev,))
            #row = self.cur.fetchone()
            if (firstrev > headrev and firstrev < onerev and lastrev > headrev and lastrev < onerev):
                logging.debug("Error: Wrong revisions number")
                exit(-1)
            self.__endRev = lastrev

            #self.cur.execute('select commitdate from SVNLog where revno = ?', (firstrev,))
            #row = self.cur.fetchone()
            self.__startRev = firstrev    
                
    def closedb(self):
        if( self.dbcon != None):
            self.cur.close()            
            self.dbcon.commit()
            self.dbcon.close()
            self.dbcon = None
            
    def __del__(self):
        self.closedb()
        #base class Object. doesnot have __del__
        #super(SVNStats,self).__del__()        
        
    def SetVerbose(self, verbose):       
        self.verbose = verbose

    def SetSearchPath(self, searchpath = '/'):
        '''
        Set the path for searching the repository data.
        Default value is '/%' which searches all paths in the repository.
        Use self.SetSearchPath('/trunk/%') for searching inside the 'trunk' folder only
        '''
        self.SetSearchParam(searchpath, self.__startRev, self.__endRev)

    def SetSearchParam(self, searchpath='/', startrev=None, endrev=None):
        '''
        The search parameters the statistics generation will be restricted to commits which
        fulfill these parameters.
        searchpath = changed file path should match to the searchpath
            Default value is '/%' which searches all paths in the repository.
            Use self.SetSearchPath('/trunk/%') for searching inside the 'trunk' folder only
        startdate = start date for the analysis (if None, earliest date in the repository)
        enddate = end date for the analysis (if None, last date in the repository)
        '''
        if(searchpath != None and len(searchpath) > 0):
            self.__searchpath = searchpath
        if( self.__searchpath.endswith('%')==True):
            self.__searchpath = self.__searchpath[:-1]
        self._printProgress("Set the search path to %s" % self.__searchpath)
        self.__startRev = startrev
        self.__endRev = endrev
        self.__createSearchParamView()

    def getSearchPathRelName(self, filename):
        '''
        calculate the file name relative to search path (if possible). Basically remove the searchpath from start of filename
        '''
        relfilename = filename
        if( self.__searchpath !=None and self.__searchpath != '/' and filename.startswith(self.__searchpath)):
            relfilename = filename[len(self.__searchpath):]
        return(relfilename)
    
    def __createSearchParamView(self):
        '''
        create temporary view with only the revisions matching the search parameters.
        '''
        assert(self.dbcon != None)
        self.cur.execute("DROP TABLE IF EXISTS search_view")
        selQuery = "SELECT DISTINCT SVNLog.revno as revno from SVNLog, SVNLogDetailVw where (SVNLog.revno = SVNLogDetailVw.revno \
                    and SVNLogDetailVw.changedpath like '%s%%'" % self.__searchpath
        if( self.__startRev != None):
            selQuery = selQuery + "and SVNLog.revno >= %s " % self.__startRev
        if( self.__endRev != None):
            selQuery = selQuery + "and SVNLog.revno <= %s " % self.__endRev
        #print "Sel query : %s" % selQuery

        selQuery = selQuery +")"
        self.cur.execute("CREATE TEMP TABLE search_view AS %s" % selQuery)
        self.cur.execute("CREATE INDEX srchvidx on search_view(revno)")
        self.dbcon.commit()
        
    @property
    def searchpath(self):
        return(self.__searchpath)

    @property    
    def sqlsearchpath(self):
        '''
        return the sql regex search path (e.g. '/trunk/' will be returned as '/trunk/%'
        '''
        return(self.__searchpath + '%')    
    
    def isDateInRange(self, cmdate):
        valid = True
        if( self.__startDate != None and self.__startDate > cmdate):
            valid = False
        if( self.__endDate != None and self.__endDate < cmdate):
            valid = False
        return(valid)
    
    def _printProgress(self, msg):
        if( self.verbose == True):
            print msg

    def __sqlForbugFixKeywordsInMsg(self):
        sqlstr = "( "
        first = True
        for keyword in self.bugfixkeywords:
            if( first == False):
                sqlstr = sqlstr + ' or '
            sqlstr=sqlstr + "svnlog.msg like '%%%s%%'" % keyword
            first = False
        sqlstr = sqlstr + " )"
        return(sqlstr)
    
    def runQuery(self, sqlquery):
        self.cur.execute(sqlquery)
        for row in self.cur:
            yield row
            
    def getAuthorList(self, numAuthors=None):
        #Find out the unique developers and their number of commit sorted in 'descending' order
        self.cur.execute("select SVNLog.author, count(*) as commitcount from SVNLog, search_view \
                        where search_view.revno = SVNLog.revno group by SVNLog.author COLLATE NOCASE order by commitcount desc")
        
        #get the auhor list (ignore commitcount) and store it. Since LogGraphLineByDev also does an sql query. It will otherwise
        # get overwritten
        authList = [author for author,commitcount in self.cur]
        #Keep only top 'numAuthors'
        if( numAuthors != None):
            authList = authList[:numAuthors]
        
        #if there is an empty string in author list, replace it by "unknown"
        authListFinal = []
        for author in authList:
            if( author == ""):
                author='unknown'
            authListFinal.append(author)
        return(authListFinal)
    
    def getActivityByWeekday(self, months=None):
        '''
        returns two lists (commit counts and weekday)
        '''
        if( months == None):
            query= "select strftime('%w', SVNLog.commitdate, 'localtime') as dayofweek, count(SVNLog.revno) from SVNLog, search_view \
                         where search_view.revno=SVNLog.revno group by dayofweek"
            
        else:
            query= "select strftime('%%w', SVNLog.commitdate, 'localtime') as dayofweek, count(SVNLog.revno) from SVNLog, search_view \
                         where search_view.revno=SVNLog.revno and date('%s', '-%d month') < SVNLog.commitdate \
                        group by dayofweek" % (self.__endDate, months)
            
        self.cur.execute(query)

        daynames = sqlite_daynames()
        commits = dict()
        for dayofweek, commitcount in self.cur:
            commits[int(dayofweek)] = commitcount            

        weekdaylist=[]
        commits_list = []
        
        for dayofweek in range(0,7):
            commitcount = commits.get(dayofweek, 0)
            commits_list.append(commitcount)           
            weekdaylist.append(daynames[int(dayofweek)])

        return(commits_list, weekdaylist)
    
    def getActivityByTimeOfDay(self, months=None):
        '''
        returns two lists (commit counts and time of day)
        '''
        if( months == None):
            query= "select strftime('%H', SVNLog.commitdate,'localtime') as hourofday, count(SVNLog.revno) from SVNLog, search_view \
                          where search_view.revno=SVNLog.revno group by hourofday"
            
        else:
            query= "select strftime('%%H', SVNLog.commitdate,'localtime') as hourofday, count(SVNLog.revno) from SVNLog, search_view \
                          where search_view.revno=SVNLog.revno and date('%s', '-%d month') < SVNLog.commitdate \
                          group by hourofday " % (self.__endDate, months)
            
        self.cur.execute(query)
        commits = dict()
        for hourofday, commitcount in self.cur:
            commits[int(hourofday)] = commitcount
                      
        commitlist =[]
        hrofdaylist = []
        for hourofday in range(0,24):
            commitcount = commits.get(hourofday, 0)
            commitlist.append(commitcount)           
            hrofdaylist.append(int(hourofday))
                
        return(commitlist, hrofdaylist)

    def getWeekDayTimeOfDayPivotTable(self):
        '''
        get pivot table of number of commits for weekday and hour combination
        '''
        self.cur.execute("select strftime('%w', SVNLog.commitdate,'localtime') as weekday, \
                         strftime('%H', SVNLog.commitdate,'localtime') as hourofday, \
                         count(SVNLog.revno) from SVNLog, search_view \
                          where search_view.revno=SVNLog.revno group by weekday, hourofday")
        commits = dict()
        for weekday, hrofday, commitcount in self.cur:
            commits[(int(weekday), int(hrofday))] = commitcount
        
        daynames = sqlite_daynames()
        
        commitstable = []
        #now make it into a table.
        for weekday in range(0,7):            
            hrrow = [daynames[weekday]]+[commits.get((weekday, hrofday), 0) for hrofday in range(0,24)]
            commitstable.append(hrrow)
        return(commitstable)
        
    def getFileCountStats(self):
        '''
        returns two lists (dates and total file count on those dates)
        '''
##      This sqlquery gives completely wrong results of File Count stats as SVNLogDetailVw table contains
##        multiple rows with the same 'revno'. Hence where clause matches to multiple rows and final file
##        count returned is completely wrong. :-( I am still learning sql. -- Nitin July 23, 2009
##        self.cur.execute('select date(SVNLog.commitdate,"localtime") as "commitdate [date]", sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
##                         from SVNLog, SVNLogDetailVw \
##                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
##                         group by "commitdate [date]" order by commitdate ASC', (self.sqlsearchpath,))

        #create a temporary view with file counts for given change type for a revision
        self.cur.execute('DROP TABLE IF EXISTS filestats')
        self.cur.execute('CREATE TEMP TABLE filestats AS \
                select SVNLogDetailVw.revno as revno, count(*) as addcount, 0 as delcount from SVNLogDetailVw where changetype= "A" and changedpath like "%s" and pathtype= "F" group by revno\
                UNION \
                select SVNLogDetailVw.revno as revno, 0 as addcount, count(*) as delcount from SVNLogDetailVw where changetype= "D" and changedpath like "%s" and pathtype= "F" group by revno'
                         % (self.sqlsearchpath,self.sqlsearchpath))
        self.cur.execute('CREATE INDEX filestatsidx ON filestats(revno)')
        self.dbcon.commit()
        self.cur.execute('select date(SVNLog.commitdate,"localtime") as "commitdate [date]", \
                    total(filestats.addcount), total(filestats.delcount) \
                    from SVNLog, filestats where SVNLog.revno = filestats.revno \
                    group by "commitdate [date]" order by commitdate')
        dates = []
        fc = []
        totalfiles = 0
        lastdateadded = None
        onedaydiff = datetime.timedelta(1,0,0)
        
        for commitdate, fadded,fdeleted in self.cur:
            prev_filecnt = totalfiles
            totalfiles = totalfiles + fadded-fdeleted
            if( self.isDateInRange(commitdate) == True):
                if( lastdateadded != None and (commitdate-lastdateadded).days > 1):
                    dates.append(commitdate-onedaydiff)                
                    fc.append(float(prev_filecnt))
            
                dates.append(commitdate)
                fc.append(float(totalfiles))
                lastdateadded = commitdate
                
        assert(len(dates) == len(fc))
        if( len(dates) > 0 and dates[-1] < self.__endDate):
            dates.append(self.__endDate)
            fc.append(fc[-1])

        dates, fc = strip_zeros(dates, fc)

        return(dates, fc)            

    def getFileTypesStats(self, numTypes):
        '''
        numTypes - number file types to return depending of number of files of that type.
        returns two lists (file types and number of files of that type. 
        '''
        #first get the file types and         
##        self.cur.execute("select filetype(changedpath) as ftype, count(*) as typecount\
##                         from (select distinct changedpath from SVNLogDetailVw where SVNLogDetailVw.changedpath like ? \
##                         and pathtype == 'F' \
##                         ) group by ftype order by typecount DESC limit 0,?"
##                         , (self.sqlsearchpath,numTypes,))

        self.cur.execute("select ftype, (total(addedfiles)-total(deletedfiles)) as typecount from \
                         (select filetype(changedpath) as ftype, count(*) as addedfiles, 0 as deletedfiles from SVNLogDetailVw \
                         where SVNLogDetailVw.changedpath like ? and pathtype == 'F' and changetype= 'A' group by ftype\
                         UNION ALL \
                         select filetype(changedpath) as ftype, 0 as addedfiles, count(*) as deletedfiles from SVNLogDetailVw \
                         where SVNLogDetailVw.changedpath like ? and pathtype == 'F' and changetype= 'D' group by ftype\
                         ) group by ftype order by typecount DESC limit 0,?"
                         , (self.sqlsearchpath,self.sqlsearchpath,numTypes))

        ftypelist = []
        ftypecountlist = []
        
        for ftype, typecount in self.cur:
            if( ftype==''):
                ftype = '{no ext}'
            ftypelist.append(ftype)
            ftypecountlist.append(float(typecount))
        return(ftypelist, ftypecountlist)

    def getAvgLoC(self):
        '''
        get statistics of how average LoC is changing over time.
        returns two lists (dates and average loc on that date)
        '''
        self.cur.execute('select commitdate as "commitdate [date]", sum(linesadded), sum(linesdeleted), total(addedfiles), total(deletedfiles) from \
                    (select date(SVNLog.commitdate,"localtime") as commitdate, total(SVNLogDetailVw.linesadded) as LinesAdded, total(SVNLogDetailVw.linesdeleted) as LinesDeleted, \
                        0 as addedfiles, 0 as deletedfiles from SVNLogDetailVw, SVNLog where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? group by commitdate \
                        UNION ALL \
                         select commitdate, 0 as linesadded, 0 as linesdeleted, total(addedfiles) as addedfiles, total(deletedfiles) as deletedfiles from \
                             (select date(SVNLog.commitdate,"localtime") as commitdate, count(*) as addedfiles, 0 as deletedfiles from SVNLog, SVNLogDetailVw \
                             where SVNLog.revno=SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.changetype="A" and SVNLogDetailVw.pathtype= "F" group by commitdate \
                            union all \
                            select date(SVNLog.commitdate,"localtime") as commitdate, 0 as addedfiles, count(*) as deletedfiles from SVNLog, SVNLogDetailVw \
                             where SVNLog.revno=SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.changetype="D" and SVNLogDetailVw.pathtype= "F" group by commitdate) group by commitdate) \
                            group by commitdate order by commitdate ASC', (self.sqlsearchpath,self.sqlsearchpath,self.sqlsearchpath))
        dates = []
        avgloclist = []
        avgloc = 0
        totalFileCnt = 0
        totalLoc = 0
        for commitdate, locadded, locdeleted, filesadded, filesdeleted in self.cur:
            totalLoc = totalLoc + locadded-locdeleted
            totalFileCnt = totalFileCnt + filesadded - filesdeleted
            avgloc = 0.0
            if( totalFileCnt > 0.0):
                avgloc = float(totalLoc)/float(totalFileCnt)
            if( self.isDateInRange(commitdate) == True):
                avgloclist.append(avgloc)
                dates.append(commitdate)
            
        assert(len(dates) == len(avgloclist))
        if( len(dates) > 0 and dates[-1] < self.__endDate):
            dates.append(self.__endDate)
            avgloclist.append(avgloclist[-1])

        dates, avgloclist = strip_zeros(dates, avgloclist)        
        return(dates, avgloclist)

    def getAuthorActivityStats(self, numAuthors):
        '''
        numAuthors - number authors to return depending on the contribution of authors. 
        returns four lists (authors, percentage of added files, percentage of changed files and percentage of deleted files)
        '''
        self.cur.execute("select SVNLog.author, sum(SVNLog.addedfiles), sum(SVNLog.changedfiles), \
                         sum(SVNLog.deletedfiles), count(distinct SVNLog.revno) as commitcount from SVNLog, SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                         group by SVNLog.author COLLATE NOCASE order by commitcount DESC LIMIT 0, ?"
                         , (self.sqlsearchpath, numAuthors,))

        authlist = []
        addfraclist = []
        changefraclist=[]
        delfraclist = []
        
        for author, filesadded, fileschanged, filesdeleted,commitcount in self.cur:
            authlist.append(author)
            activitytotal = float(filesadded+fileschanged+filesdeleted)

            addfrac = 0.0
            changefrac = 0.0
            delfrac = 0.0
            if( activitytotal > 0.0):
                addfrac = 100.0*float(filesadded)/activitytotal
                changefrac = 100.0*float(fileschanged)/activitytotal
                delfrac = 100.0*float(filesdeleted)/activitytotal                
            addfraclist.append(addfrac)
            changefraclist.append(changefrac)
            delfraclist.append(delfrac)            

        return(authlist, addfraclist, changefraclist, delfraclist)

    def getDirFileCountStats(self, dirdepth=2, maxdircount=10):
        '''
        dirdepth - depth of directory search relative to search path. Default value is 2
        returns two lists (directory names upto dirdepth and number of files in that directory (including
        files in subdirectories)        
        maxdircount - limits the number of directories on the graph to the x largest directories        
        '''
##        self.cur.execute("select dirname(?, changedpath, ?) as dirpath, count(*) as filecount \
##                    from (select distinct changedpath from SVNLogDetailVw where SVNLogDetailVw.changedpath like ?) \
##                    group by dirpath", (self.searchpath,dirdepth, self.sqlsearchpath,))

        self.cur.execute('select dirpath, total(addedfiles) as addedfiles, total(deletedfiles) as deletedfiles from \
                             (select dirname(?, changedpath, ?) as dirpath, count(*) as addedfiles, 0 as deletedfiles from SVNLog, SVNLogDetailVw \
                             where SVNLog.revno=SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.changetype="A" and SVNLogDetailVw.pathtype= "F" group by dirpath \
                            union all \
                            select dirname(?, changedpath, ?) as dirpath, 0 as addedfiles, count(*) as deletedfiles from SVNLog, SVNLogDetailVw \
                             where SVNLog.revno=SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.changetype="D" and SVNLogDetailVw.pathtype= "F" group by dirpath) \
                            group by dirpath',(self.searchpath,dirdepth, self.sqlsearchpath,self.searchpath,dirdepth, self.sqlsearchpath))
        
        dirinfolist = []
        for dirname, addedfiles,deletedfiles in self.cur:
            fcount = float(addedfiles-deletedfiles)
            dirinfolist.append((dirname, fcount))
            
        if maxdircount > 0 and len(dirinfolist) > maxdircount:   
            '''
            Return only <maxdircount> largest directories
            '''
            dirinfolist.sort(key=lambda dinfo:dinfo[1], reverse=True)
                        
            remainingcount = sum(map(lambda dinfo:dinfo[1], dirinfolist[maxdircount:]), 0)
            dirinfolist = dirinfolist[0:maxdircount]
            dirinfolist.append(('others', remainingcount))
        
        #sort the directories in such a way that similar paths are together
        dirinfolist.sort(key=lambda dinfo:dinfo[0])
        
        #now split in two lists
        dirlist = []
        dirfilecountlist = []
        for name, fcount in dirinfolist:
            dirlist.append(name)
            dirfilecountlist.append(fcount)
        
        return(dirlist, dirfilecountlist)

    def getDirLoCStats(self, dirdepth=2, maxdircount=10, mindirsize_percent =5 ):
        '''
        dirdepth - depth of directory search relative to search path. Default value is 2
        returns two lists (directory names upto dirdepth and total line count of files in that directory (including
        files in subdirectories)        
        maxdircount - limits the number of directories on the graph to the x largest directories 
        '''
        self.cur.execute("select dirname(?, SVNLogDetailVw.changedpath, ?) as dirpath, sum(SVNLogDetailVw.linesadded), \
                         sum(SVNLogDetailVw.linesdeleted) from SVNLog, SVNLogDetailVw \
                    where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                    group by dirpath", (self.searchpath,dirdepth, self.sqlsearchpath,))
            
            
        dirinfolist = []
        totalloc = 0
        for dirname, linesadded, linesdeleted in self.cur:
            dsize = linesadded-linesdeleted
            if( dsize > 0):
                dirinfolist.append((dirname, dsize))
            totalloc = totalloc+dsize
            
        if maxdircount > 0 and len(dirinfolist) > maxdircount: 
            '''
            Return only <maxdircount> largest directories
            '''
            #filter dirinfolist such that all directories with greather 'mindirsize_percent' are retained
            mindirsize = (mindirsize_percent/100.0)*totalloc
            dirinfolist = filter(lambda dinfo: dinfo[1]>mindirsize ,dirinfolist)
            dirinfolist.sort(key=lambda dinfo:dinfo[1], reverse=True)
            
            dirinfolist = dirinfolist[0:maxdircount]
            dsizecount = sum(map(lambda dinfo:dinfo[1], dirinfolist), 0)
            remainingcount = totalloc- dsizecount
            dirinfolist.append(('others', remainingcount))
        
        #sort the directories in such a way that similar paths are together
        dirinfolist.sort(key=lambda dinfo:dinfo[0])
        #now split in two lists
        dirlist = []
        dirsizelist = []
        for name, size in dirinfolist:
            dirlist.append(name)
            dirsizelist.append(size)
            
        return(dirlist, dirsizelist)

    def getDirnames(self, dirdepth=2):
        '''
        gets the directory names upto depth (dirdepth) relative to searchpath.
        returns one list of directory names
        '''
        self.cur.execute("select dirname(?, changedpath, ?) as dirpath from SVNLogDetailVw where changedpath like ? \
                         group by dirpath",(self.searchpath, dirdepth, self.sqlsearchpath,))
        
        dirlist = [dirname for dirname, in self.cur]
        return(dirlist)
    
    def getLoCStats(self):
        '''
        returns two lists (dates and total line count on that date)
        '''
        self.cur.execute('select date(SVNLog.commitdate,"localtime") as "commitdate [date]", sum(SVNLogDetailVw.linesadded), sum(SVNLogDetailVw.linesdeleted) \
                         from SVNLog, SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                         group by "commitdate [date]" order by commitdate ASC', (self.sqlsearchpath,))
        dates = []
        loc = []
        totalloc = 0
        lastdateadded = None
        onedaydiff = datetime.timedelta(1,0,0)
                
        for commitdate, locadded, locdeleted in self.cur:
            prev_loc = totalloc
            totalloc = totalloc + locadded-locdeleted
            if( self.isDateInRange(commitdate) == True):            
                if( lastdateadded != None and (commitdate-lastdateadded).days > 1):
                    dates.append(commitdate-onedaydiff)
                    loc.append(float(prev_loc))
                
                dates.append(commitdate)
                loc.append(float(totalloc))
                lastdateadded = commitdate

        assert(len(dates) == len(loc))
        if( len(dates) > 0 and dates[-1] < self.__endDate):
            dates.append(self.__endDate)
            loc.append(loc[-1])
            
        return(strip_zeros(dates, loc))
    
    def getChurnStats(self):
        '''
        returns two lists (dates and churn data on that date)
        churn - total number of lines modifed (i.e. lines added + lines deleted + lines changed)
        '''
        self.cur.execute('select date(SVNLog.commitdate,"localtime") as "commitdate [date]", sum(SVNLogDetailVw.linesadded+SVNLogDetailVw.linesdeleted) as churn \
                         from SVNLog, SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                         group by "commitdate [date]" order by commitdate ASC', (self.sqlsearchpath,))
        dates = []
        churnloclist = []
        tocalloc = 0
        for commitdate, churn in self.cur:
            if( self.isDateInRange(commitdate) == True):            
                dates.append(commitdate)
                churnloclist.append(float(churn))
            
        return(strip_zeros(dates, churnloclist))

    def getDirLocTrendStats(self, dirname):
        '''
        gets LoC trend data for directory 'dirname'.
        returns two lists (dates and total LoC at that date) for the directory 'dirname'
        '''
        sqlQuery = 'select date(SVNLog.commitdate,"localtime") as "commitdate [date]", \
                        sum(SVNLogDetailVw.linesadded), sum(SVNLogDetailVw.linesdeleted) from SVNLog, SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like "%s%%" \
                         group by "commitdate [date]" order by commitdate ASC' % (dirname)

        self.cur.execute(sqlQuery)
        dates = []
        dirsizelist = []
        dirsize = 0
        lastdateadded = None
        prev_dirsize= 0
        onedaydiff = datetime.timedelta(1)
        for commitdate, locadded, locdeleted in self.cur:
            dirsize= dirsize+locadded-locdeleted
            if( self.isDateInRange(commitdate) == True):            
                if( lastdateadded != None and (commitdate-lastdateadded).days > 1):
                    dates.append(commitdate-onedaydiff)
                    dirsizelist.append(float(prev_dirsize))
                
                dates.append(commitdate)
                dirsize = max(0, float(dirsize))
                dirsizelist.append(dirsize)
                prev_dirsize = dirsize
                lastdateadded = commitdate
            
        assert(len(dates) == len(dirsizelist))
        if( len(dates) > 0 and dates[-1] < self.__endDate):
            dates.append(self.__endDate)
            dirsizelist.append(dirsizelist[-1])
            
        return(strip_zeros(dates, dirsizelist))

    def getAuthorCommitActivityStats(self, author):
        '''
        get the commit activit by hour of day stats for author 'author'
        returns two lists (dates , time at which commits happened on that date) for author.
        '''
        self.cur.execute('select strftime("%H", SVNLog.commitdate,"localtime"), date(SVNLog.commitdate,"localtime") as "commitdate [date]" \
                    from SVNLog, search_view where search_view.revno=SVNLog.revno and SVNLog.author=? group by commitdate order by commitdate ASC' ,(author,))

        dates = []
        committimelist = []
        for hr, commitdate in self.cur:
            dates.append(commitdate)
            committimelist.append(int(hr))
        return(strip_zeros(dates, committimelist))

    def getLoCTrendForAuthor(self, author):
        '''
        get the trend of LoC contributed by the author 'author'
        return two lists (dates and loc on that date) contributed by the author
        '''
        self.cur.execute('select date(SVNLog.commitdate,"localtime") as "commitdate [date]", sum(SVNLogDetailVw.linesadded),\
                        sum(SVNLogDetailVw.linesdeleted) from SVNLog, SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? and SVNLog.author=? \
                         group by "commitdate [date]" order by commitdate ASC',(self.sqlsearchpath, author,))
        dates = []
        loc = []
        totalloc = 0
        lastdateadded = None
        onedaydiff = datetime.timedelta(1,0,0)
        
        for commitdate, locadded, locdeleted in self.cur:
            prev_loc = totalloc
            totalloc = totalloc + locadded-locdeleted
            if( self.isDateInRange(commitdate) == True):            
                if( lastdateadded != None and (commitdate-lastdateadded).days > 1):
                    dates.append(commitdate-onedaydiff)
                    loc.append(float(prev_loc))
            
                dates.append(commitdate)
                loc.append(float(totalloc))
                lastdateadded = commitdate

        assert(len(dates) == len(loc))
        if( len(dates) > 0 and dates[-1] < self.__endDate):
            dates.append(self.__endDate)
            loc.append(loc[-1])
            
        return(strip_zeros(dates, loc))

    def getWasteEffortStats(self):
        '''
        generate the stats for ratio of total effort against wasted effort.
        Deleted Lines are treated as 'wasted' efforts
        Added lines are treated as 'real' efforts. The daily trend of this ratio
        is returned.
        returns 3 lists (date, total linesadded, total lines deleted, waste ratio)        
        '''
        sqlquery = '''select date(SVNLog.commitdate,"localtime") as "commitdate [date]",
            sum(linesadded), sum(linesdeleted) from SVNLog, SVNLogDetailVw
            where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like "%s" 
                        group by "commitdate [date]" order by commitdate ASC'''
        
        sqlquery = sqlquery % self.sqlsearchpath
        
        dates = []
        linesadded = []
        linedeleted = []
        wasteratio = []
        total_linesadded = 0
        total_linesdeleted = 0
        
        self.cur.execute(sqlquery)
        
        for dt, added, deleted in self.cur:
            total_linesadded = total_linesadded+added
            total_linesdeleted = total_linesdeleted+deleted
            dates.append(dt)
            linesadded.append(total_linesadded)
            linedeleted.append(total_linesdeleted)
            if total_linesadded > 0:
                wasteratio.append((total_linesdeleted*1.0/total_linesadded))
            else:
                wasteratio.append(0)
                
        return dates, linesadded, linedeleted, wasteratio
    
    def getBugfixCommitsTrendStats(self):
        '''
        get the trend of bug fix commits over time. Bug fix commit are commit where log message contains words
        like 'bug', 'fix' etc.
        returns three lists (dates, total line count on that date, churn count on that date)
        '''
        sqlquery = 'select date(SVNLog.commitdate,"localtime") as "commitdate [date]", count(*) as commitfilecount \
                         from SVNLog, SVNLogDetailVw where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like "%s" \
                         and %s group by "commitdate [date]" order by commitdate ASC' % (self.sqlsearchpath, self.__sqlForbugFixKeywordsInMsg())
        
        self.cur.execute(sqlquery)
        dates = []
        fc = []
        commitchurn = []
        totalcommits = 0
        for commitdate, commitfilecount in self.cur:
            totalcommits = totalcommits+commitfilecount
            if( self.isDateInRange(commitdate) == True):            
                dates.append(commitdate)
                commitchurn.append(float(commitfilecount))
                fc.append(float(totalcommits))
        return(dates, fc, commitchurn)

    def __isValidWord(self, word):
        valid = True
        if( len(word) < 2 or re.match(self.__invalidWordPattern, word) != None):
            valid = False
        return(valid)

    def __detectStemming(self, wordFreq):
        '''
        detect common stemming patterns and merge those word counts (e.g. close and closed are  merged)
        '''
        wordList = wordFreq.keys()
        
        for word in wordList:            
            wordFreq = self.__mergeStemmingSuffix(wordFreq, word, 'ed')
            wordFreq = self.__mergeStemmingSuffix(wordFreq, word, 'ing')
            wordFreq = self.__mergeStemmingSuffix(wordFreq, word, 's')
            wordFreq = self.__mergeStemmingSuffix(wordFreq, word, 'es')
        
        return(wordFreq)
            
    def __mergeStemmingSuffix(self, wordFreq, word, suffix):
        if( wordFreq.has_key(word) == True and word.endswith(suffix) == True):
            #strip suffix
            stemmedword = word[0:-len(suffix)]
            if( wordFreq.has_key(stemmedword) == True):
                wordFreq[stemmedword] = wordFreq[stemmedword]+wordFreq[word]
                del wordFreq[word]
        return(wordFreq)
            
        
    def getLogMsgWordFreq(self, minWordFreq = 3):
        '''
        get word frequency of log messages. Common words like 'a', 'the' are removed.
        returns a dictionary with words as key and frequency of occurance as value
        '''
        self.cur.execute("select SVNLog.msg from SVNLog, SVNLogDetailVw where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                         group by SVNLogDetailVw.revno",(self.sqlsearchpath,))

        wordFreq = Counter()
        pattern = re.compile('\s+', re.UNICODE)
        
        for msg, in self.cur:
            #split the words in msg
            wordlist = pattern.split(msg)
            for word in filter(self.__isValidWord, wordlist):
                word = word.lower()
                wordFreq[word] += 1
                
        #Filter words with frequency less than minWordFreq
        invalidWords = [word for word,freq in wordFreq.items() if (freq < minWordFreq)]
        for word in invalidWords:
            del wordFreq[word]

        wordFreq = self.__detectStemming(wordFreq)
        
        return(wordFreq)

    def getRevTimeDeltaStats(self, numTopAuthors= None):
        '''
        numTopAuthors - returns the top 'numTopAuthors' in the authors. Remaining author names are replaced
        as 'others'. If the value is 'None' then all authors are returned.
        get the 'time delta' statistics between two revisions.
        returns three lists revision number, author, time difference between this revision and the last revision        
        '''
        authset = set(self.getAuthorList(numTopAuthors))

        self.cur.execute('select SVNLog.revno, SVNLog.author, SVNLog.commitdate as "commitdate [timestamp]" from SVNLog,SVNLogDetailVw \
                         where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like ? \
                         group by SVNLogDetailVw.revno order by SVNLogDetailVw.revno ASC',(self.sqlsearchpath,))

        lastcommitdate = None
        revnolist = []
        authlist = []
        timedeltalist = []
                
        for revno, author, commitdate in self.cur:
            if( lastcommitdate != None):
                revnolist.append(revno)
                if( author not in authset):
                    author = 'others'
                authlist.append(author)
                timediff = commitdate - lastcommitdate
                hrs = timediff.days*24 + timediff.seconds/3600.0
                timedeltalist.append(hrs)         
            lastcommitdate = commitdate

        return(revnolist, authlist, timedeltalist)
    
    def getBasicStats(self):
        '''
        returns a dictinary of basic SVN stats
        stats['LastRev'] -- returns last revision in the searchpath
        stats['FirstRev'] -- first revision number for the given searchpath
        stats['FirstRevDate'] -- first commit date
        stats['LastRevDate'] -- last commit date.
        stats['NumRev'] -- number of revisions in the search path.
        stats['NumFiles'] -- returns total number of files (files added - files deleted)
        stats['NumAuthors'] -- return total number of unique authors
        stats['LoC'] -- total loc
        '''
        stats = dict()
        #get head revision
        #check if SVNLogDetailVw is updated. If yes, use the 'search_view' query
        self.cur.execute('select count(*) from SVNLogDetailVw')
        
        logdetailcount = self.cur.fetchone()[0]
        if logdetailcount > 0:
            self.cur.execute('select min(revno), max(revno), count(*) from \
                              (select search_view.revno as revno from search_view,SVNLogDetailVw \
                                 where search_view.revno == SVNLogDetailVw.revno and \
                                 SVNLogDetailVw.changedpath like ? group by search_view.revno)',(self.sqlsearchpath,))
        else:
            self.cur.execute('select min(revno), max(revno), count(*) from SVNLog')
            
        row = self.cur.fetchone()
        firstrev = row[0]
        lastrev = row[1]
        numrev = row[2]
        stats['LastRev'] = lastrev
        stats['NumRev'] = numrev
        stats['FirstRev'] = firstrev
        #now get first and last revision dates
        self.cur.execute('select datetime(SVNLog.commitdate,"localtime") as "commitdate [timestamp]" from SVNLog \
                        where SVNLog.revno = ?', (firstrev,))
        row = self.cur.fetchone()
        stats['FirstRevDate'] = row[0]
        self.cur.execute('select datetime(SVNLog.commitdate,"localtime") as "commitdate [timestamp]" from SVNLog \
                        where SVNLog.revno = ?', (lastrev,))
        row = self.cur.fetchone()
        stats['LastRevDate'] = row[0]
        #get number of unique paths(files) (added and deleted)
        self.cur.execute('select count(*) from SVNLogDetailVw where SVNLogDetailVw.changetype = "A" \
                        and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.pathtype="F"', (self.sqlsearchpath,))
        row = self.cur.fetchone()
        filesAdded = row[0]
        self.cur.execute('select count(*) from SVNLogDetailVw where SVNLogDetailVw.changetype = "D" \
                        and SVNLogDetailVw.changedpath like ? and SVNLogDetailVw.pathtype="F"', (self.sqlsearchpath,))
        row = self.cur.fetchone()
        filesDeleted = row[0]
        stats['NumFiles'] = filesAdded-filesDeleted
        authors = self.getAuthorList()
        stats['NumAuthors'] = len(authors)
    
        self.cur.execute("select sum(SVNLogDetailVw.linesadded-SVNLogDetailVw.linesdeleted) \
                         from SVNLogDetailVw where SVNLogDetailVw.changedpath like ?"
                         ,(self.sqlsearchpath,))
        row = self.cur.fetchone()
        stats['LoC'] = row[0]
        return(stats)

    def _updateActivityHotness(self):
        '''
        update the file activity as 'temparature' data. Every commit adds 10 degrees. Rate of temperature
        drop is 1 deg/day. The temparature is calculated using the 'newtons law of cooling'
        '''
        if( getattr(self,'_activity_hotness_updated', False)==False):
            #self._printProgress("updating file hotness table")
            self.cur.execute("CREATE TABLE IF NOT EXISTS ActivityHotness(filepath text, lastrevno integer, \
                             temperature real)")
            self.cur.execute("CREATE TABLE IF NOT EXISTS RevisionActivity(revno integer, \
                             temperature real)")
            self.cur.execute("CREATE INDEX IF NOT EXISTS ActHotRevIdx On ActivityHotness(lastrevno ASC)")
            self.cur.execute("CREATE INDEX IF NOT EXISTS ActHotFileIdx On ActivityHotness(filepath ASC)")
            self.cur.execute("CREATE INDEX IF NOT EXISTS RevActivityIdx On RevisionActivity(revno ASC)")
            self.dbcon.commit()
            self.cur.execute("select max(ActivityHotness.lastrevno) from ActivityHotness")
            lastrevno = self.cur.fetchone()[0]         
            if(lastrevno == None):
                lastrevno = 0
                        
            #get the valid revision numbers from SVNLog table from lastrevno 
            self.cur.execute("select revno from SVNLog where revno > ?", (lastrevno,))
            revnolist = [row[0] for row in self.cur]
            
            for revno in revnolist:
                self.cur.execute('select SVNLog.commitdate as "commitdate [timestamp]" from SVNLog \
                                where SVNLog.revno=?', (revno,))
                commitdate = self.cur.fetchone()[0]
                self.cur.execute('select changedpath from SVNLogDetailVw where revno=? and pathtype="F"', (revno,))
                changedpaths = self.cur.fetchall()
                self._updateRevActivityHotness(revno, commitdate, changedpaths)
            setattr(self, '_activity_hotness_updated',True)

    def _updateRevActivityHotness(self, revno, commitdate, changedpaths):
        self._printProgress("updating file activity hotness table for revision %d" % revno)

        #NOTE : in some cases where the subversion repository is created by converting it from other version control
        #systems, the dates can become confusing. 
        
        maxrev_temperature = 0.0
        
        for filepathrow in changedpaths:
            filepath = filepathrow[0]
            temperature = TEMPINCREMENT
            lastrevno = revno            
            self.cur.execute("select temperature, lastrevno from ActivityHotness where filepath=?", (filepath,))
            try:
                row = self.cur.fetchone()
                temperature = row[0]
                lastrevno = row[1]
                #get last commit date
                self.cur.execute('select SVNLog.commitdate as "commitdate [timestamp]" from SVNLog where revno=?', (lastrevno,))
                lastcommitdate = self.cur.fetchone()[0]
                #now calculate the new temperature.
                temperature = TEMPINCREMENT+getTemperatureAtTime(commitdate, lastcommitdate, temperature, COOLINGRATE)
                self.cur.execute("UPDATE ActivityHotness SET temperature=?, lastrevno=? \
                                where lastrevno = ? and filepath=?", (temperature, revno, lastrevno,filepath,))                
            except:
                self.cur.execute("insert into ActivityHotness(temperature, lastrevno, filepath) \
                                values(?,?,?)", (temperature, revno, filepath))
            if( temperature > maxrev_temperature):
                maxrev_temperature = temperature
                
            logging.debug("updated file %s revno=%d temp=%f" % (filepath, revno,temperature))

        self.cur.execute("insert into RevisionActivity(revno, temperature) values(?,?)",(revno, maxrev_temperature))
        self.dbcon.commit()
        return(maxrev_temperature)

    def _getAuthActivityDict(self):
        self._updateActivityHotness()
        self.cur.execute('select SVNLog.author, SVNLog.commitdate as "commitdate [timestamp]" from SVNLog, search_view \
                    where SVNLog.revno = search_view.revno order by commitdate ASC')

        authActivityIdx = dict()                    
        for author, cmdate in self.cur:
            cmtactv = authActivityIdx.get(author)
            revtemp = TEMPINCREMENT
            if( cmtactv != None):                
                revtemp = TEMPINCREMENT+getTemperatureAtTime(cmdate, cmtactv[0], cmtactv[1], COOLINGRATE)
            authActivityIdx[author] = (cmdate, revtemp)
            
        #Now update the activity for current date and time.
        curdate = datetime.datetime.combine(self.__endDate, datetime.time(0))
        for author, cmtactv in authActivityIdx.items():
            authtemp = getTemperatureAtTime(curdate, cmtactv[0], cmtactv[1], COOLINGRATE)
            authActivityIdx[author] = (curdate, authtemp)
        
        return(authActivityIdx)
        
    def getRevActivityTemperature(self):
        '''
        return revision activity as maximum temperature at each revision(using the newton's law of cooling)                                                                         
        '''
        self._updateActivityHotness()
        self.cur.execute('select date(SVNLog.commitdate) as "commitdate [date]", max(RevisionActivity.temperature) \
                    from RevisionActivity, SVNLog where SVNLog.revno = RevisionActivity.revno \
                    group by commitdate order by commitdate ASC')
        cmdatelist = []
        temperaturelist = []
        lastcommitdate = None
        for cmdate, temperature in self.cur:
            revtemp = temperature
            if( lastcommitdate != None):
                temp = getTemperatureAtTime(cmdate, lastcommitdate, lasttemp, COOLINGRATE)
                if( revtemp < temp):
                    revtemp = temp
                
            lastcommitdate = cmdate
            lasttemp = revtemp
            if( self.isDateInRange(cmdate) == True):
                cmdatelist.append(cmdate)
                temperaturelist.append(revtemp)
                        
        return( strip_zeros(cmdatelist,temperaturelist))            

    def getAuthorCloud(self):
        '''
        return the list of tuples of (author, number of revisions commited, activity index) of author.
        These are intended to be used for creating  an author tag cloud. Number of revisions commited will
        determine the size of the author tag and Activity index will determine the color
        '''
        authActivityIdx = self._getAuthActivityDict()
        self.cur.execute("select SVNLog.author, count(SVNLog.revno) as commitcount from SVNLog,search_view where search_view.revno=SVNLog.revno group by SVNLog.author")
        authCloud = []
        for author, commitcount in self.cur:
            activity = authActivityIdx[author]
            authCloud.append((author, commitcount,activity[1]))
            
        return(authCloud)
    
    def getActiveAuthors(self, numAuthors):
        '''
        return top numAthors based on the activity index of commited revisions
        '''
        authActivityIdx = self._getAuthActivityDict()
        #get the authors list for the given search path as 'set' so that searching is faster
        searchpathauthlist = set(self.getAuthorList())
        
        #now update the temperature to current temperature and create a list of tuples for
        #sorting.
        curTime = datetime.datetime.combine(self.__endDate, datetime.time(0))
        authlist = []
        for author, cmtactiv in authActivityIdx.items():
            temperature = getTemperatureAtTime(curTime, cmtactiv[0], cmtactiv[1], COOLINGRATE)
            #if author has modified files in the search path add his name.
            if( author in searchpathauthlist):
                authlist.append((author, temperature))                        

        authlist = sorted(authlist, key=operator.itemgetter(1), reverse=True)        
        return(authlist[0:numAuthors])
    
    def getHotFiles(self, numFiles):
        '''
        get the top 'numfiles' number of hot files.
        returns list of tuples (filepath, temperature)
        '''
        def _getfilecount(fileparams):        
            self.cur.execute("select count(*) from SVNLogDetailVw where \
                         changedpath=? group by changedpath",(fileparams[0],))
            count = self.cur.fetchone()[0]
            return((fileparams[0],fileparams[1], count))
            
        self._updateActivityHotness()
        curTime = datetime.datetime.combine(self.__endDate, datetime.time(0))
        
        self.cur.execute("select ActivityHotness.filepath, \
                getTemperatureAtTime(?,SVNLog.commitdate,ActivityHotness.temperature,?) as hotness \
                from ActivityHotness,SVNLog \
                where ActivityHotness.filepath like ? and ActivityHotness.lastrevno=SVNLog.revno \
                order by hotness DESC LIMIT ?", (curTime,COOLINGRATE,self.sqlsearchpath, numFiles))
        hotfileslist = [(filepath, hotness) for filepath, hotness in self.cur]
        hotfileslist = map(_getfilecount, hotfileslist)
                
        return(hotfileslist)
        
    def getAuthorsCommitTrendMeanStddev(self, months=None):
        '''
        Plot of Mean and standard deviation for time between two consecutive commits by authors.
        months : if none, calculate mean and std deviation for lifetime. If not none, plot mean
        and standard deviation for last so many months.
        '''
        authList = self.getAuthorList(20)
        avg_list     = []
        stddev_list  = []
        finalAuthList = []
        
        #create a query which filters revision log on author and create 'rowid' for each
        #row. These row ids will be used by subsquent queries to calculate the difference between
        #two rows.
    
        author_filter_view = '''CREATE TEMP VIEW IF NOT EXISTS '%(author)s_view' AS
                select (select COUNT(0)
                from SVNLog log_a
                where log_a.revno >= log_b.revno and log_a.author = '%(author)s'
                ) as rownum,  log_b.* from SVNLog log_b where log_b.author='%(author)s'
                ORDER by log_b.commitdate ASC'''
        
        stddev_query = "select deltastddev(julianday(SVNLog.commitdate)) from SVNLog where SVNLog.author= ? \
                    order by SVNLog.commitdate"
        
        author_filter_query = '''SELECT * FROM '%(author)s_view' ORDER by commitdate ASC'''
        
        if months != None:
            author_filter_query = '''SELECT * FROM '%(author)s_view'
                WHERE date('%(endDate)s', '-%(months)s month') < commitdate
                ORDER by commitdate ASC'''
            
            stddev_query = "select deltastddev(julianday(SVNLog.commitdate)) from SVNLog where SVNLog.author= ? \
                    and date('%s', '-%d month') < SVNLog.commitdate \
                    order by SVNLog.commitdate" % (self.__endDate, months)
            
        avg_query_sql = '''SELECT AVG(IFNULL(julianday(SVNLog_B.commitdate) - julianday(SVNLog_A.commitdate), 0)) 
                    FROM (%(auth_query)s) as SVNLog_A 
                    LEFT OUTER JOIN (%(auth_query)s) as SVNLog_B ON SVNLog_A.rownum= (SVNLog_B.rownum+1)
                    order by SVNLog_A.rownum'''

        for auth in authList:
            auth_query = author_filter_view % { 'author':auth, 'endDate' : self.__endDate, 'months' :months}
            self.cur.execute(auth_query)
            
            auth_query = author_filter_query %  { 'author' : auth,'endDate' : self.__endDate, 'months' : months}
            avg_query = avg_query_sql % { 'auth_query' : auth_query}
            self.cur.execute(avg_query)
            
            avg, = self.cur.fetchone()
            self.cur.execute(stddev_query, (auth,))
            stddev, = self.cur.fetchone()
            if( avg != None and stddev != None):
                finalAuthList.append(auth)
                avg_list.append(avg)
                stddev_list.append(stddev)
                
        return(finalAuthList, avg_list, stddev_list)

    def getAuthorsCommitTrend90pc(self,  months=None):
        '''
        get the range of average and 90% confidence interval for author commits.
        '''
        
        avg_list     = []
        confidence_list  = []
        authlist = []
        confidence_factor = 1.28  # 1.28*std_dev gives the 90% confidence interval
        
        data = self.getAuthorsCommitTrendMeanStddev(months)
        for author, average, stddev in zip(*data):
            authlist.append(author)
            avg_list.append(average)
            confidence_list.append(confidence_factor*stddev)
        return authlist, avg_list, confidence_list
        
    def getAuthorsCommitTrendHistorgram(self, binsList):
        '''
        Histogram of time difference between two consecutive commits by same author.
        '''
        maxVal = binsList[-1]
        authList = self.getAuthorList(20)
        deltaList = []
        
        for auth in authList:
            self.cur.execute('select SVNLog.commitdate from SVNLog where SVNLog.author= ? order by SVNLog.commitdate'
                             ,(auth,))
            prevval = None
            for cmdate, in self.cur:
                if( prevval != None):
                    deltaval = timedelta2days(cmdate-prevval)
                    if( deltaval <= maxVal):
                        deltaList.append((deltaval))
                prevval = cmdate
            
        binvals = histogram_data(binsList, deltaList)         

        return(binvals)
    
    def getDailyCommitCount(self):
        '''
        plot daily commit count graph.
        '''
        self.cur.execute('select date(commitdate,"localtime") as "cmdate [date]", count(revno) from SVNLog group by "cmdate [date]" order by "cmdate [date]" ASC')

        datelist = []
        commitcountlist = []
        for cmdate, commitcount in self.cur:
            datelist.append(cmdate)
            commitcountlist.append(commitcount)

        return(strip_zeros(datelist,commitcountlist))
    