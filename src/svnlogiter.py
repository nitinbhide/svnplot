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
import os, re, string
import StringIO
import urllib

def covert2datetime(seconds):
    gmt = time.gmtime(seconds)
    return(datetime.datetime(gmt.tm_year, gmt.tm_mon, gmt.tm_mday, gmt.tm_hour, gmt.tm_min, gmt.tm_sec))

def getDiffLineCountDict(diff_log):
    diffio = StringIO.StringIO(diff_log)
    addlnCount=0
    dellnCount=0
    curfile=None
    diffCountDict = dict()
    newfilediffstart = 'Index: '
    for diffline in diffio:
        #remove the newline characters near the end of line
        diffline = diffline.rstrip()
        if(diffline.find(newfilediffstart)==0):
            #diff for new file has started update the old filename.
            if(curfile != None):
                diffCountDict[curfile] = (addlnCount, dellnCount)
            #reset the linecounts and current filename
            addlnCount = 0
            dellnCount = 0
            #Index line entry doesnot have '/' as start of file path. Hence add the '/'
            #so that path entries in revision log list match with the names in the 'diff count' dictionary
            curfile = '/'+diffline[len(newfilediffstart):]
        elif(diffline.find('---')==0 or diffline.find('+++')==0 or diffline.find('@@')==0 or diffline.find('===')==0):                
            continue
        elif(diffline.find('-')==0):
            dellnCount = dellnCount+1                
        elif(diffline.find('+')==0):
             addlnCount = addlnCount+1
    
    #update last file stat in the dictionary.
    diffCountDict[curfile] = (addlnCount, dellnCount)
    return(diffCountDict)
    
class SVNLogClient:
    def __init__(self, svnrepourl):
        self.svnrepourl = svnrepourl
        self.svnclient = pysvn.Client()
        self.tmppath = None
        self._updateTempPath()
        self.maxTryCount = 3
        
    def _updateTempPath(self):
        #Get temp directory
        if os.environ.has_key('TEMP'):
            self.tmppath = os.environ['TEMP']
        elif os.environ.has_key('TMPDIR'):
            self.tmppath= os.environ['TMPDIR']
        elif os.environ.has_key('TMP'):
            self.tmppath= os.environ['TMP']
        elif os.path.exists( '/usr/tmp' ):
            self.tmppath= '/usr/tmp'
        elif os.path.exists( '/tmp' ):
            self.tmppath= '/tmp'
        elif os.path.exists('c:\\temp'):
            self.tmppath = 'c:\\temp'
            
    def getHeadRevNo(self):
        revno = 0
        headrev = pysvn.Revision( pysvn.opt_revision_kind.head )            
        url = self.getUrl('')
                
        for trycount in range(0, self.maxTryCount):
            try:
                revlog = self.svnclient.log( url,
                     revision_start=headrev, revision_end=headrev, discover_changed_paths=False)
                #got the revision log. Now break out the multi-try for loop
                revno = revlog[0].revision.number
                break
            except:
                continue
            
        return(revno)

    def getLog(self, revno, briefLog=False):
        log=None
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl('')
                
        for trycount in range(0, self.maxTryCount):
            try:
                revlog = self.svnclient.log( url,
                     revision_start=rev, revision_end=rev, discover_changed_paths=briefLog)
                log = revlog[0]
                break
            except:
                continue
        return(log)

    def getRevDiff(self, revno):
        rev1 = pysvn.Revision(pysvn.opt_revision_kind.number, revno-1)
        rev2 = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl('')
        diff_log = None
        for trycount in range(0, self.maxTryCount):
            try:
                diff_log = self.svnclient.diff(self.tmppath, url, revision1=rev1, revision2=rev2,
                                recurse=True,ignore_ancestry=True,ignore_content_type=False,
                                       diff_deleted=True)
                break
            except:
                continue
        return diff_log

    def getRevFileDiff(self, path, revno):
        rev1 = pysvn.Revision(pysvn.opt_revision_kind.number, revno-1)
        rev2 = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(path)
        diff_log = None
        for trycount in range(0, self.maxTryCount):
            try:
                diff_log = self.svnclient.diff(self.tmppath, url, revision1=rev1, revision2=rev2,
                            recurse=True, ignore_ancestry=False,ignore_content_type=False,
                                       diff_deleted=True)
                break
            except:
                continue
            
        return(diff_log)
    
    def getInfo(self, path, revno):
        '''Gets the information about the given path ONLY from the repository.
        Hence recurse flag is set to False.
        '''
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(path)
        entry_list = None
        for trycount in range(0, self.maxTryCount):
            try:
                entry_list = self.svnclient.info2( url,revision=rev,recurse=False)
                break
            except:
                continue
        return(entry_list)

    def isBinaryFile(self, filepath, revno):
        '''
        detect if file is a binary file using same heuristic as subversion. If the file
        has no svn:mime-type  property, or has a mime-type that is textual (e.g. text/*),
        Subversion assumes it is text. Otherwise it is treated as binary file.
        '''
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(path)
        binary = None
        for trycount in range(0, self.maxTryCount):
            try:
                (revision, propdict) = self.svnclient.revproplist(url, revision=rev)
                binary = False
                if( 'svn:mime-type' in propdict):
                    mimetype = propdict['svn:mime-type']
                    if( mimetype.find('text') < 0):
                        #mime type is not a 'text' mime type.
                        binary = True
                break
            except:
                continue
        
        return(binary)

    def _getLineCount(self, filepath, revno):
        linecount = 0
        for trycount in range(0, self.maxTryCount):
            try:
                rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
                url = self.getUrl(path)
                contents = self.svnclient.cat(url, revision = rev)
                matches = re.findall("$", contents, re.M )
                if( matches != None):
                    linecount = len(matches)
                break
            except:
                continue
        return(linecount)
    
    def getLineCount(self, filepath, revno):
        linecount = 0
        if( self.isBinaryFile(filepath, revno) == False):
            linecount = self._getLineCount(filepath, revno)
        
        return(linecount)

    def getUrl(self, path):
        url = self.svnrepourl + urllib.pathname2url(path)
        return(url)
        
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
        '''includes directory and files. Initially I wanted to only add the changed file paths.
        however it is not possible to detect if the changed path is file or directory from the
        svn log output
        '''
        filesadded = 0
        fileschanged = 0
        filesdeleted = 0
        for change in self.revlog.changed_paths:
            isdir = self.isDirectory(change)
            change['isdir'] = isdir
            action = change['action']
            if( isdir == False):
                if( action == 'M'):
                    fileschanged = fileschanged +1
                elif(action == 'A'):
                    filesadded = filesadded+1
                elif(action == 'D'):
                    filesdeleted = filesdeleted+1
                    
        return(filesadded, fileschanged, filesdeleted)
        
    def isDirectory(self, change):
        path = change['path']
        action = change['action']
        isDir = False

        #see if directory check is alredy done on this path. If not, then check with the repository        
        if( 'isdir' not in change):
            revno = self.getRevNo()
            #if the file/dir is deleted in the current revision. Then the status needs to be checked for
            # one revision before that
            if( action == 'D'):            
                revno = revno-1
            entry = self.logclient.getInfo(path, revno)
            filename, info_dict = entry[0]
            
            if( info_dict.kind == pysvn.node_kind.dir):
                isDir = True
        else:
            isDir = change['isdir']
            
        return(isDir)
        
    def getDiffLineCount(self):
        """
        Returns a list of tuples containing filename, lines added and lines modified
        In case of binary files, lines added and deleted are returned as zero.
        In case of directory also lines added and deleted are returned as zero
        """                        
        diffCountDict = self._updateDiffCount()
        diffCountList = []
        for change in self.revlog.changed_paths:
            linesadded = 0
            linesdeleted = 0
            filename = change['path']
            if( diffCountDict.has_key(filename)):
                linesadded, linesdeleted = diffCountDict[filename]
                                
            diffCountList.append((filename, change['action'],linesadded, linesdeleted))
            #print "%d : %s : %s : %d : %d " % (self.revno, filename, change['action'], linesadded, linesdeleted)        
        return(diffCountList)
        
    def getDiffLineCountForPath(self, change):
        added = 0
        deleted = 0
        revno = self.getRevNo()
        filename = change['path']
        changetype = change['action']
        if( changetype != 'A' and changetype != 'D'):
            #file or directory is modified
            diff_log = self.logclient.getRevFileDiff(filename, revno)
            diffDict = getDiffLineCountDict(diff_log)
            assert(diffDict.has_key(filename) != False)
            added, deleted = diffDict[filename]
        elif( self.isDirectory(change) == False):
            #path is added or deleted. First check if the path is a directory. If path is not a directory
            # then process further.
            if( changetype == 'A'):
                added = self.logclient.getLineCount(filename, revno)
            elif( changetype == 'D'):
                deleted = self.logclient.getLineCount(filename, revno-1)
            
        return(filename, changetype, added, deleted)

    def getRevNo(self):
        return(self.revlog.revision.number)
    
    def __getattr__(self, name):
        if(name == 'author'):
            author = ''
            #in case the author information is not available, then revlog object doesnot
            # contain 'author' attribute. This case needs to be handled. I am returning
            # empty string as author name.
            try:
                author =self.revlog.author
            except:
                pass
            return(author)
        elif(name == 'message'):
            return(self.revlog.message )
        elif(name == 'date'):
            return(covert2datetime(self.revlog.date))
        elif(name == 'revno'):
            return(self.revlog.revision.number)
        elif(name == 'changedpathcount'):
            filesadded, fileschanged, filesdeleted = self.changedFileCount()
            return(filesadded+fileschanged+filesdeleted)
        return(None)
    
    def _updateDiffCount(self):
        revno = self.getRevNo()
        revdiff_log = self.logclient.getRevDiff(revno)
        return(getDiffLineCountDict(revdiff_log))
                 
