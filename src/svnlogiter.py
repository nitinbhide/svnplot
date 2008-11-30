'''
This file implements the iterators to iterate over the subversion log.
This is just a convinience interface over the pysvn module.

It is intended to be used in  python script to convert the Subversion log into
an sqlite database.
--- Nitin Bhide (nitinbhide@gmail.com)

Part of 'svnplot' project
Available on google code at http://code.google.com/p/svnplot/
Licensed under the 'New BSD License'

To use copy the file in Python 'site-packages' directory Setup is not available
yet.
'''

import pysvn
import datetime, time

def covert2datetime(seconds):
    gmt = time.gmtime(seconds)
    return(datetime.datetime(gmt.tm_year, gmt.tm_mon, gmt.tm_mday, gmt.tm_hour, gmt.tm_min, gmt.tm_sec))
    
class SVNLogClient:
    def __init__(self, svnrepourl):
        self.svnrepourl = svnrepourl
        self.svnclient = pysvn.Client()
        
    def getHeadRevNo(self):
        headrev = pysvn.Revision( pysvn.opt_revision_kind.head )
        revlog = self.svnclient.log( self.svnrepourl,
             revision_start=headrev, revision_end=headrev, discover_changed_paths=False)
        return(revlog[0].revision.number)

    def getLog(self, revno, briefLog=False):
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        revlog = self.svnclient.log( self.svnrepourl,
             revision_start=rev, revision_end=rev, discover_changed_paths=briefLog)
        return(revlog[0])
    
    def __iter__(self):
        return(SVNRevLogIter(self, 1, self.getHeadRevNo()))

class SVNRevLogIter:
    def __init__(self, logclient, startRevNo, endRevNo):
        self.logclient = logclient
        self.startrev = startRevNo
        self.endrev = endRevNo
        self.currev = 0
        
    def __iter__(self):
        return(self)

    def next(self):
        if( self.endrev == 0):
            self.endrev = self.logclient.getHeadRevNo()
        if( self.startrev == 0):
            self.startrev = self.endrev
        if( self.currev == 0):
            self.currev = self.startrev
        if( self.currev> self.endrev):
            raise StopIteration

        revlog = SVNRevLog(self.logclient, self.currev)
        self.currev = self.currev+1
        return(revlog)
        
class SVNRevLog:
    def __init__(self, logclient, revno):
        self.logclient = logclient
        self.revlog = self.logclient.getLog(revno, True)
        
    def changedFileCount(self):
        # if the filename ends with a / then its directory. Hence to be ignored in
        # changed file count
        changedfilecount = 0
        for change in self.revlog.changed_paths:
            filename = change['path']
            if( filename.endswith('/')):
                ++changedfilecount
        return(changedfilecount)
    
    def __getattr__(self, name):
        if(name == 'author'):
            return(self.revlog.author)
        elif(name == 'message'):
            return(self.revlog.message )
        elif(name == 'date'):
            return(covert2datetime(self.revlog.date))
        elif(name == 'revno'):
            return(self.revlog.revision.number)
        elif(name == 'changedfilecount'):
            return(self.changedFileCount())
        return(None)
    
if(__name__ == "__main__"):
    #Run tests
    svnrepopath = "file:///F:/SvnRepoTest/"
    logclient = SVNLogClient(svnrepopath)
    for revlog in logclient:
        print "Date : %s" % revlog.date
    
    