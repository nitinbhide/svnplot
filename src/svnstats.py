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

import sqlite3
import calendar, datetime
import os.path, sys
import string, re
import math
import operator
import logging

COOLINGRATE = 0.1/24.0 #degree per hour
TEMPINCREMENT = 10.0 # degrees per commit

def filetype(path):
    '''
    get the file type (i.e. extension) from the path
    '''
    (root, ext) = os.path.splitext(path)
    return(ext)

def dirname(searchpath, path, depth):
    '''
    get directory name till given depth (relative to searchpath) from the full file path
    '''
    assert(searchpath != None and searchpath != "")
    #replace the search path and then compare the depth
    path = path.replace(searchpath, "", 1)
    #first split the path and remove the filename
    pathcomp = os.path.dirname(path).split('/')
    #now join the split path upto given depth only
    dirpath = '/'.join(pathcomp[0:depth])
    #Now add the dirpath to searchpath to get the final directory path
    dirpath = searchpath+dirpath
    #print "%s : [%s]" %(path, dirpath)
    return(dirpath)

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
        temperature = lastTemp*math.exp(tempFactor)        
    except Exception, expinst:
        logging.debug("Error %s" % expinst)
        temperature = 0
        
    return(temperature)

class SVNStats:
    def __init__(self, svndbpath):
        self.svndbpath = svndbpath
        self.__searchpath = '/%'
        self.verbose = False
        self.bugfixkeywords = ['bug', 'fix']
        self.__invalidWordPattern = re.compile("\d+|an|the|me|my|we|you|he|she|it|are|is|am|\
                        |will|shall|should|would|had|have|has|was|were|be|been|this|that|there|\
                        |who|when|how|where|which|\
                        |already|after|by|on|or|so|also|got|get|do|don't|from|all|but|\
                        |yet|to|in|out|of|for|if|yes|no|not|may|can|could|at|as|with|without", re.IGNORECASE)
        self.dbcon = None
        self.initdb()
        
    def initdb(self):
        if( self.dbcon != None):
            self.closedb()
            
        #InitSqlite
        self.dbcon = sqlite3.connect(self.svndbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #self.dbcon.row_factory = sqlite3.Row
        # Create the function "regexp" for the REGEXP operator of SQLite
        self.dbcon.create_function("dirname", 3, dirname)
        self.dbcon.create_function("filetype", 1, filetype)
        self.dbcon.create_function("getTemperatureAtTime", 4, getTemperatureAtTime)
        self.cur = self.dbcon.cursor() 

    def closedb(self):
        if( self.dbcon != None):
            self.cur.close()            
            self.dbcon.commit()
            self.dbcon.close()
            self.dbcon = None
            
    def __del__(self):
        self.closedb()
        
    def SetVerbose(self, verbose):       
        self.verbose = verbose

    def SetSearchPath(self, searchpath = '/'):
        '''
        Set the path for searching the repository data.
        Default value is '/%' which searches all paths in the repository.
        Use self.SetSearchPath('/trunk/%') for searching inside the 'trunk' folder only
        '''
        if(searchpath != None and len(searchpath) > 0):
            self.__searchpath = searchpath
        if( self.__searchpath.endswith('%')==True):
            self.__searchpath = self.__searchpath[:-1]
        self._printProgress("Set the search path to %s" % self.__searchpath)

    @property
    def searchpath(self):
        return(self.__searchpath)

    @property    
    def sqlsearchpath(self):
        '''
        return the sql regex search path (e.g. '/trunk/' will be returned as '/trunk/%'
        '''
        return(self.__searchpath + '%')

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
    
    def getAuthorList(self, numAuthors=None):
        #Find out the unique developers and their number of commit sorted in 'descending' order
        self.cur.execute("select author, count(*) as commitcount from SVNLog group by author order by commitcount desc")
        
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

    def getActivityByWeekday(self):
        '''
        returns two lists (commit counts and weekday)
        '''
        self.cur.execute("select strftime('%w', SVNLog.commitdate), count(SVNLog.revno) from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by strftime('%w', SVNLog.commitdate)", (self.sqlsearchpath,))
        weekdaylist=[]
        commits = []
        for dayofweek, commitcount in self.cur:
           commits.append(commitcount)           
           weekdaylist.append(calendar.day_abbr[int(dayofweek)])
           
        return(commits, weekdaylist)

    def getActivityByTimeOfDay(self):
        '''
        returns two lists (commit counts and time of day)
        '''
        self.cur.execute("select strftime('%H', SVNLog.commitdate), count(SVNLog.revno) from SVNLog, SVNLogDetail \
                          where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                          group by strftime('%H', SVNLog.commitdate)", (self.sqlsearchpath,))
        commits =[]
        hrofdaylist = []
        for hourofday, commitcount in self.cur:
           commits.append(commitcount)           
           hrofdaylist.append(int(hourofday))
        return(commits, hrofdaylist)

    def getFileCountStats(self):
        '''
        returns two lists (dates and total file count on those dates)
        '''
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.sqlsearchpath,))
        dates = []
        fc = []
        totalfiles = 0
        for year, month, day, fadded,fdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            totalfiles = totalfiles + fadded-fdeleted
            fc.append(float(totalfiles))

        return(dates, fc)            

    def getFileTypesStats(self, numTypes):
        '''
        numTypes - number file types to return depending of number of files of that type.
        returns two lists (file types and number of files of that type. 
        '''
        #first get the file types and         
        self.cur.execute("select filetype(changedpath) as ftype, count(*) as typecount\
                         from (select distinct changedpath from SVNLogDetail where SVNLogDetail.changedpath like ? \
                         ) group by ftype order by typecount DESC limit 0,?"
                         , (self.sqlsearchpath,numTypes,))

        ftypelist = []
        ftypecountlist = []
        
        for ftype, typecount in self.cur:
            ftypelist.append(ftype)
            ftypecountlist.append(float(typecount))
        return(ftypelist, ftypecountlist)

    def getAvgLoC(self):
        '''
        get statistics of how average LoC is changing over time.
        returns two lists (dates and average loc on that date)
        '''
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted), \
                         sum(SVNLog.addedfiles), sum(SVNLog.deletedfiles) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.sqlsearchpath,))
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
        return(dates, avgloclist)

    def getAuthorActivityStats(self, numAuthors):
        '''
        numAuthors - number authors to return depending on the contribution of authors. 
        returns four lists (authors, percentage of added files, percentage of changed files and percentage of deleted files)
        '''
        self.cur.execute("select SVNLog.author, sum(SVNLog.addedfiles), sum(SVNLog.changedfiles), \
                         sum(SVNLog.deletedfiles), count(SVNLog.revno) as commitcount from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by SVNLog.author order by commitcount DESC LIMIT 0, ?"
                         , (self.sqlsearchpath, numAuthors,))

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
               
        return(authlist, addfraclist, changefraclist, delfraclist)

    def getDirFileCountStats(self, dirdepth=2):
        '''
        dirdepth - depth of directory search relative to search path. Default value is 2
        returns two lists (directory names upto dirdepth and number of files in that directory (including
        files in subdirectories)        
        '''
        self.cur.execute("select dirname(?, changedpath, ?) as dirpath, count(*) as filecount \
                    from (select distinct changedpath from SVNLogDetail where SVNLogDetail.changedpath like ?) \
                    group by dirpath", (self.searchpath,dirdepth, self.sqlsearchpath,))
            
        dirlist = []
        dirfilecountlist = []        
        for dirname, fcount in self.cur:
            dirlist.append(dirname)
            dirfilecountlist.append(float(fcount))
            
        return(dirlist, dirfilecountlist)

    def getDirLoCStats(self, dirdepth=2):
        '''
        dirdepth - depth of directory search relative to search path. Default value is 2
        returns two lists (directory names upto dirdepth and total line count of files in that directory (including
        files in subdirectories)        
        '''
        self.cur.execute("select dirname(?, SVNLogDetail.changedpath, ?) as dirpath, sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                    from SVNLog, SVNLogDetail \
                    where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                    group by dirpath", (self.searchpath,dirdepth, self.sqlsearchpath,))
            
        dirlist = []
        dirsizelist = []        
        for dirname, linesadded, linesdeleted in self.cur:
            dsize = linesadded-linesdeleted
            if( dsize > 0):
                dirlist.append(dirname)
                dirsizelist.append(dsize)
                
        return(dirlist, dirsizelist)

    def getDirnames(self, dirdepth=2):
        '''
        gets the directory names upto depth (dirdepth) relative to searchpath.
        returns one list of directory names
        '''
        self.cur.execute("select dirname(?, changedpath, ?) as dirpath from SVNLogDetail where changedpath like ? \
                         group by dirpath",(self.searchpath, dirdepth, self.sqlsearchpath,))
        
        dirlist = [dirname for dirname, in self.cur]
        return(dirlist)
    
    def getLoCStats(self):
        '''
        returns two lists (dates and total line count on that date)
        '''
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.sqlsearchpath,))
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        return(dates, loc)
    
    def getChurnStats(self):
        '''
        returns two lists (dates and churn data on that date)
        churn - total number of lines modifed (i.e. lines added + lines deleted + lines changed)
        '''
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded+SVNLogDetail.linesdeleted) as churn \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by date(SVNLog.commitdate)", (self.sqlsearchpath,))
        dates = []
        churnloclist = []
        tocalloc = 0
        for year, month, day, churn in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            churnloclist.append(float(churn))
            
        return(dates, churnloclist)

    def getDirLocTrendStats(self, dirname):
        '''
        gets LoC trend data for directory 'dirname'.
        returns two lists (dates and total LoC at that date) for the directory 'dirname'
        '''
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
            
        return(dates, dirsizelist)

    def getAuthorCommitActivityStats(self, author):
        '''
        get the commit activit by hour of day stats for author 'author'
        returns two lists (dates , time at which commits happened on that date) for author.
        '''
        self.cur.execute("select strftime('%H', commitdate), strftime('%Y', SVNLog.commitdate), \
                    strftime('%m', SVNLog.commitdate), strftime('%d', SVNLog.commitdate) \
                    from SVNLog where author=? group by date(commitdate)" ,(author,))

        dates = []
        committimelist = []
        for hr, year, month, day in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            committimelist.append(int(hr))
        return(dates, committimelist)

    def getLoCTrendForAuthor(self, author):
        '''
        get the trend of LoC contributed by the author 'author'
        return two lists (dates and loc on that date) contributed by the author
        '''
        self.cur.execute("select strftime('%Y', SVNLog.commitdate), strftime('%m', SVNLog.commitdate),\
                         strftime('%d', SVNLog.commitdate), sum(SVNLogDetail.linesadded), sum(SVNLogDetail.linesdeleted) \
                         from SVNLog, SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? and SVNLog.author=? \
                         group by date(SVNLog.commitdate)",(self.sqlsearchpath, author,))
        dates = []
        loc = []
        tocalloc = 0
        for year, month, day, locadded, locdeleted in self.cur:
            dates.append(datetime.date(int(year), int(month), int(day)))
            tocalloc = tocalloc + locadded-locdeleted
            loc.append(float(tocalloc))
            
        return(dates, loc)

    def getBugfixCommitsTrendStats(self):
        '''
        get the trend of bug fix commits over time. Bug fix commit are commit where log message contains words
        like 'bug', 'fix' etc.
        returns three lists (dates, total line count on that date, churn count on that date)
        '''
        sqlquery = "select strftime('%%Y', SVNLog.commitdate), strftime('%%m', SVNLog.commitdate), \
                         strftime('%%d', SVNLog.commitdate), count(*) as commitfilecount \
                         from SVNLog, SVNLogDetail where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like '%s' \
                         and %s group by date(SVNLog.commitdate)" % (self.sqlsearchpath, self.__sqlForbugFixKeywordsInMsg())
        
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
        self.cur.execute("select SVNLog.msg from SVNLog, SVNLogDetail where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by SVNLogDetail.revno",(self.sqlsearchpath,))

        wordFreq = dict()
        pattern = re.compile('\W+')
        for msg, in self.cur:
            #split the words in msg
            wordlist = re.split(pattern, msg)
            for word in filter(self.__isValidWord, wordlist):
                word = word.lower()
                count = wordFreq.get(word, 0)        
                wordFreq[word] = count+1
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

        self.cur.execute('select SVNLog.revno, SVNLog.author, SVNLog.commitdate as "commitdate [timestamp]" from SVNLog,SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ? \
                         group by SVNLogDetail.revno order by SVNLogDetail.revno ASC',(self.sqlsearchpath,))

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
        self.cur.execute('select min(SVNLog.revno), max(SVNLog.revno), count(SVNLog.revno) from SVNLog,SVNLogDetail \
                         where SVNLog.revno = SVNLogDetail.revno and SVNLogDetail.changedpath like ?'
                         ,(self.sqlsearchpath,))
        row = self.cur.fetchone()
        firstrev = row[0]
        lastrev = row[1]
        numrev = row[2]
        stats['LastRev'] = lastrev
        stats['NumRev'] = numrev
        stats['FirstRev'] = firstrev
        #now get first and last revision dates
        self.cur.execute('select SVNLog.commitdate as "commitdate [timestamp]" from SVNLog \
                        where SVNLog.revno = ?', (firstrev,))
        row = self.cur.fetchone()
        stats['FirstRevDate'] = row[0]
        self.cur.execute('select SVNLog.commitdate as "commitdate [timestamp]" from SVNLog \
                        where SVNLog.revno = ?', (lastrev,))
        row = self.cur.fetchone()
        stats['LastRevDate'] = row[0]
        #get number of unique paths(files) (added and deleted)
        self.cur.execute('select count(*) from SVNLogDetail where SVNLogDetail.changetype = "A" \
                        and SVNLogDetail.changedpath like ?', (self.sqlsearchpath,))
        row = self.cur.fetchone()
        filesAdded = row[0]
        self.cur.execute('select count(*) from SVNLogDetail where SVNLogDetail.changetype = "D" \
                        and SVNLogDetail.changedpath like ?', (self.sqlsearchpath,))
        row = self.cur.fetchone()
        filesDeleted = row[0]
        stats['NumFiles'] = filesAdded-filesDeleted
        authors = self.getAuthorList()
        stats['NumAuthors'] = len(authors)
    
        self.cur.execute("select sum(SVNLogDetail.linesadded-SVNLogDetail.linesdeleted) \
                         from SVNLogDetail where SVNLogDetail.changedpath like ?"
                         ,(self.sqlsearchpath,))
        row = self.cur.fetchone()
        stats['LoC'] = row[0]
        return(stats)

    def _updateActivityHotness(self):
        '''
        update the file activity as 'temparature' data. Every commit adds 10 degrees. Rate of temperature
        drop is 1 deg/day. The temparature is calculated using the 'newtons law of cooling'
        '''
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
            self.cur.execute('select changedpath from SVNLogDetail where revno=?', (revno,))
            changedpaths = self.cur.fetchall()
            self._updateRevActivityHotness(revno, commitdate, changedpaths)            

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
            
    def getRevActivityTemperature(self):
        '''
        return revision activity as maximum temperature at each revision(using the newton's law of cooling)                                                                         
        '''
        self._updateActivityHotness()
        self.cur.execute('select date(SVNLog.commitdate) as "commitdate [date]", max(RevisionActivity.temperature) from RevisionActivity, SVNLog \
                    where SVNLog.revno = RevisionActivity.revno group by commitdate order by commitdate ASC')
        cmdatelist = []
        temperaturelist = []
        lastcommitdate = None
        for cmdate, temperature in self.cur:
            cmdatelist.append(cmdate)
            revtemp = temperature
            if( lastcommitdate != None):
                temp = getTemperatureAtTime(cmdate, lastcommitdate, lasttemp, COOLINGRATE)
                if( revtemp < temp):
                    revtemp = temp
                
            temperaturelist.append(revtemp)
            lastcommitdate = cmdate
            lasttemp = revtemp
            
        return( cmdatelist,temperaturelist)            

    def getActiveAuthors(self, numAuthors):
        '''
        return top numAthors based on the activity index of commited revisions
        '''
        self._updateActivityHotness()
        self.cur.execute('select SVNLog.author, SVNLog.commitdate as "commitdate [timestamp]", RevisionActivity.temperature from RevisionActivity, SVNLog \
                    where SVNLog.revno = RevisionActivity.revno order by commitdate ASC')

        authActivityIdx = dict()                    
        for author, cmdate, temperature in self.cur:
            cmtactv = authActivityIdx.get(author)
            revtemp = temperature
            if( cmtactv != None):                
                revtemp = temperature+getTemperatureAtTime(cmdate, cmtactv[0], cmtactv[1], COOLINGRATE)
            authActivityIdx[author] = (cmdate, revtemp)

        #now update the temperature to current temperature and create a list of tuples for
        #sorting.
        curTime = datetime.datetime.now()
        authlist = []
        for author, cmtactiv in authActivityIdx.items():
            temperature = getTemperatureAtTime(curTime, cmtactiv[0], cmtactiv[1], COOLINGRATE)
            authlist.append((author, temperature))                        

        authlist = sorted(authlist, key=operator.itemgetter(1), reverse=True)        
        return(authlist[0:numAuthors])
    
    def getHotFiles(self, numFiles):
        '''
        get the top 'numfiles' number of hot files.
        returns list of tuples (filepath, temperature)
        '''
        self._updateActivityHotness()
        curTime = datetime.datetime.now()
        self.cur.execute("select ActivityHotness.filepath, \
                getTemperatureAtTime(?,SVNLog.commitdate,ActivityHotness.temperature,?) as hotness \
                from ActivityHotness,SVNLog \
                where ActivityHotness.lastrevno=SVNLog.revno order by hotness DESC LIMIT ?",
                         (curTime,COOLINGRATE,numFiles))
        hotfileslist = [(filepath, hotness) for filepath, hotness in self.cur]
        
        return(hotfileslist)
        
        
