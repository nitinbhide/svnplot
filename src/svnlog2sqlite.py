'''
python script to convert the Subversion log into an sqlite database
The idea is to use the generated SQLite database as input to Matplot lib for
creating various graphs and analysis. The graphs are inspired from graphs
generated by StatSVN/StatCVS.
--- Nitin Bhide (nitinbhide@gmail.com)

Part of 'svnplot' project
Available on google code at http://code.google.com/p/svnplot/
Licensed under the 'New BSD License'

To use, copy the file in Python 'site-packages' directory. Setup is not available
yet.
'''

import svnlogiter
import datetime
import sqlite3

class SVNLog2Sqlite:
    def __init__(self, svnrepopath, sqlitedbpath):
        self.svnclient = svnlogiter.SVNLogClient(svnrepopath)
        self.dbpath =sqlitedbpath
        self.dbcon =None
        
    def convert(self):
        #First check if this a full conversion or a partial conversion
        self.initdb()
        self.CreateTables()        
        laststoredrev = self.getLastStoredRev()
        headrev = self.svnclient.getHeadRevNo()
        self.ConvertRevs(laststoredrev, headrev)
        self.closedb()
        
    def initdb(self):
        self.dbcon = sqlite3.connect(self.dbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.dbcon.row_factory = sqlite3.Row

    def closedb(self):
        self.dbcon.commit()
        self.dbcon.close()
        
    def getLastStoredRev(self):
        cur = self.dbcon.cursor()
        cur.execute("select max(revno) from svnlog")
        lastStoreRev = 0
        
        row = cur.fetchone()
        if( row != None and len(row) > 0 and row[0] != None):
            lastStoreRev = int(row[0])        
        return(lastStoreRev)
               
    def ConvertRevs(self, laststoredrev, headrev):
        if( laststoredrev < headrev):
            cur = self.dbcon.cursor()
            svnloglist = svnlogiter.SVNRevLogIter(self.svnclient, laststoredrev+1, headrev)
            revcount = 0
            for revlog in svnloglist:
                revcount = revcount+1
                cur.execute("INSERT into SVNLog(revno, commitdate, author, msg, changedfilecount) values(?, ?, ?, ?,?)",
                            (revlog.revno, revlog.date, revlog.author, revlog.message, revlog.changedpathcount))
                for filename, changetype, linesadded, linesdeleted in revlog.getDiffLineCount():
                    cur.execute("INSERT into SVNLogDetail(revno, changedpath, changetype, linesadded, linesdeleted) \
                                values(?, ?, ?, ?,?)", (revlog.revno, filename, changetype, linesadded, linesdeleted))
                    #print "%d : %s : %s : %d : %d " % (revlog.revno, filename, changetype, linesadded, linesdeleted)
                #commit after every change
                self.dbcon.commit()            
            print "Number of revisions converted : %d" % revcount
            
    def CreateTables(self):
        cur = self.dbcon.cursor()
        cur.execute("create table if not exists SVNLog(revno integer, commitdate timestamp, author text, msg text, changedfilecount integer)")
        cur.execute("create table if not exists SVNLogDetail(revno integer, changedpath text, changetype text,\
                    linesadded integer, linesdeleted integer)")
        self.dbcon.commit()


if( __name__ == "__main__"):
    #testing
    svnrepopath = "file:///F:/SvnRepoTest/"
    sqlitedb = "D:\\nitinb\\SoftwareSources\\SVNPlot\\svnrepo.db"
    try:
        conv = SVNLog2Sqlite(svnrepopath, sqlitedb)
        conv.convert()
        dbcon = sqlite3.connect(sqlitedb, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        cur = dbcon.cursor()
        cur.execute("select * from SVNLog")
        #for row in cur:
        #    print row
        dbcon.close()
    except:
        del conv
        raise
    