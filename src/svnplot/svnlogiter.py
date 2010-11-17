'''
svnlogiter.py
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

This file implements the iterators to iterate over the subversion log.
This is just a convinience interface over the pysvn module.

It is intended to be used in  python script to convert the Subversion log into
an sqlite database.
'''

import pysvn
import datetime, time
import os, re, string
import StringIO
import urllib, urlparse
import logging
import getpass
import traceback
import types
import tempfile
from os.path import normpath

def convert2datetime(seconds):
    gmt = time.gmtime(seconds)
    return(datetime.datetime(gmt.tm_year, gmt.tm_mon, gmt.tm_mday, gmt.tm_hour, gmt.tm_min, gmt.tm_sec))

def makeunicode(str):
    if type(str) == types.StringType: 
        str = unicode(str, 'utf-8')
    return(str)

def normurlpath(pathstr):
    '''
    normalize url path. I cannot use 'normpath' directory as it changes path seperator to 'os' default path seperator.
    '''
    nrmpath = pathstr
    if( pathstr):
        nrmpath = normpath(pathstr)
        #replace the '\\' to '/' in case 'normpath' call has changed the directory seperator.
        nrmpath = nrmpath.replace('\\', '/')
    return(nrmpath)
    
def getDiffLineCountDict(diff_log):
    diffio = StringIO.StringIO(diff_log)
    addlnCount=0
    dellnCount=0
    curfile=None
    diffCountDict = dict()
    newfilediffstart = 'Index: '
    newfilepropdiffstart = 'Property changes on: '
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
        elif(diffline.find(newfilepropdiffstart)==0):
            #property modification diff has started. Ignore it.
            if(curfile != None):
                diffCountDict[curfile] = (addlnCount, dellnCount)
            curfile = None
        elif(diffline.find('---')==0 or diffline.find('+++')==0 or diffline.find('@@')==0 or diffline.find('===')==0):                
            continue
        elif(diffline.find('-')==0):
            dellnCount = dellnCount+1                
        elif(diffline.find('+')==0):
             addlnCount = addlnCount+1
    
    #update last file stat in the dictionary.
    if( curfile != None):
        diffCountDict[curfile] = (addlnCount, dellnCount)
    return(diffCountDict)
    
class SVNLogClient:
    def __init__(self, svnrepourl,binaryext=[], username=None,password=None):
        self.svnrooturl = None
        self.tmppath = None
        self.username = None
        self.password = None
        self._updateTempPath()
        self.svnrepourl = svnrepourl
        self.svnclient = pysvn.Client()
        self.svnclient.callback_get_login = self.get_login
        self.svnclient.callback_ssl_server_trust_prompt = self.ssl_server_trust_prompt
        self.svnclient.callback_ssl_client_cert_password_prompt = self.ssl_client_cert_password_prompt
        self.setbinextlist(binaryext)
        self.set_user_password(username, password)
        
    def setbinextlist(self, binextlist):
        '''
        set extensionlist for binary files with some cleanup if required.
        '''
        binaryextlist = []
        for binext in binextlist:
            binext = binext.strip()
            binext = '.' + binext
            binaryextlist.append(binext)
            binext = binext.upper()
            binaryextlist.append(binext)
        self.binaryextlist = tuple(binaryextlist)

    def set_user_password(self,username, password):
        if( username != None and username != ''):
            self.username = username
            self.svnclient.set_default_username(self.username)
        if( password != None):
            self.password = password
            self.svnclient.set_default_password(self.password)
        
    def get_login(self, realm, username, may_save):
        logging.debug("This is a svnclient.callback_get_login event. ")
        if( self.username == None):
            self.username = raw_input("username for %s:" % realm)
        #save = True
        if( self.password == None):
            self.password = getpass.getpass()
        if(self.username== None or self.username ==''): 
            retcode = False
        else:
            retcode = True
        return retcode, self.username, self.password, may_save

    def ssl_server_trust_prompt( self, trust_dict ):
        retcode=True
        accepted_failures = 1
        save=1
        print "trusting: "
        print trust_dict
        return retcode, accepted_failures, save
        
    def ssl_client_cert_password_prompt(self, realm, may_save):
        """callback_ssl_client_cert_password_prompt is called each time subversion needs a password in the realm to use a client certificate and has no cached credentials. """
        logging.debug("callback_ssl_client_cert_password_prompt called to gain password for subversion in realm %s ." %(realm))
        password = getpass.getpass()
        return retcode, password, may_save    
    
    def _updateTempPath(self):
        #Get temp directory
        self.tmppath = tempfile.gettempdir()
        #Bugfix for line count update problems.
        #pysvn Client.diff() call documentation says
        #diff uses tmp_path to form the filename when creating any temporary files needed. The names are formed using tmp_path + unique_string + ".tmp".
        #For example tmp_path=/tmp/diff_prefix will create files like /tmp/diff_prefix.tmp and /tmp/diff_prefix1.tmp.
        #Hence i assumed that passing the temppath as '/tmp/svnplot' will create temporary files like '/tmp/svnplot1.tmp' etc.
        #However 'diff' function tries to create temporary files as '/tmp/svnplot/tempfile.tmp'. Since '/tmp/svnplot' folder doesnot exist
        #temporary file cannot be created and the 'diff' call fails. Hence I am changing it just 'tmpdir' path. -- Nitin (20 July 2009)
        #self.tmppath = os.path.join(self.tmppath, "svnplot")
        
    def getHeadRevNo(self):
        revno = 0
        headrev = self._getHeadRev()
        
        if( headrev != None):
            revno = headrev.revision.number
        else:
            print "Unable to find head revision for the repository"
            print "Check the firewall settings, network connection and repository path"
            
        return(revno)

    def _getHeadRev(self, enddate=None):
        rooturl = self.getRootUrl()
        logging.debug("Trying to get head revision rooturl:%s" % rooturl)
        
        headrevlog = None
        headrev = pysvn.Revision( pysvn.opt_revision_kind.head )
            
        revlog = self.svnclient.log( rooturl,
             revision_start=headrev, revision_end=headrev, discover_changed_paths=False)
                
        #got the revision log. Now break out the multi-try for loop
        if( revlog != None and len(revlog) > 0):
            revno = revlog[0].revision.number
            logging.debug("Found head revision %d" % revno)
            headrevlog = revlog[0]            
            
            if( enddate != None and enddate < headrevlog.date):
                headrevlog = self.getLastRevForDate(enddate, rooturl, False)
            
        return(headrevlog)
    
    def getStartEndRevForRepo(self, startdate=None, enddate=None):
        '''
        find the start and end revision data for the entire repository.
        '''
        rooturl = self.getRootUrl()
        headrev = self._getHeadRev(enddate)
        
        firstrev = self.getLog(1, url=rooturl, detailedLog=False)
        if (startdate!= None and firstrev.date < startdate):
            firstrev = self.getFirstRevForDate(startdate,rooturl,False)
            
        if( firstrev and headrev):            
            assert(firstrev.revision.number <= headrev.revision.number)
        
        return(firstrev, headrev)
        
    def findStartEndRev(self, startdate=None, enddate=None):
        #Find svn-root for the url
        url = self.getUrl('')
        
        #find the start and end revision numbers for the entire repository.
        firstrev, headrev = self.getStartEndRevForRepo(startdate, enddate)
        startrevno = firstrev.revision.number
        endrevno = headrev.revision.number
                
        if( not self.isRepoUrlSameAsRoot()):
            #if the url is not same as 'root' url. Then we need to find first revision for
            #given URL.        
        
            #headrev and first revision of the repository is found
            #actual start end revision numbers for given URL will be between these two numbers
            #Since svn log doesnot have a direct way of determining the start and end revisions
            #for a given url, I am using headrevision and first revision time to get those
            starttime = firstrev.date
            revstart = pysvn.Revision(pysvn.opt_revision_kind.date, starttime)
            logging.debug("finding start end revision for %s" % url)
            startrev = self.svnclient.log( url,
                         revision_start=revstart, revision_end=headrev.revision, limit = 1, discover_changed_paths=False)
            
            if( startrev != None and len(startrev) > 0):
                startrevno = startrev[0].revision.number
                
        return(startrevno, endrevno)
        
    def getFirstRevForDate(self, revdate, url, detailedlog=False):
        '''
        find the first log entry for the given date.
        '''
        revlog = None
        revstart = pysvn.Revision(pysvn.opt_revision_kind.date, revdate)
        revloglist = self.svnclient.log( url,
                         revision_start=revstart, limit = 1, discover_changed_paths=False)
        if( revloglist != None and len(revloglist) > 0):
            revlog = revloglist[0]
        return(revlog)
    
    def getLastRevForDate(self, revdate, url, detailedlog=False):
        '''
        find the first log entry for the given date.
        '''
        revlog = None
        revstart = pysvn.Revision(pysvn.opt_revision_kind.date, revdate)
        #seconds per day is 24*60*60. revend is revstart+1 day
        revend = pysvn.Revision(pysvn.opt_revision_kind.date, revdate+(24*60*60))
        revloglist = self.svnclient.log( url,
                         revision_start=revstart, revision_end=revend, discover_changed_paths=False)
        if( revloglist != None and len(revloglist) > 0):
            revlog = revloglist[-1]
        return(revlog)
        
    def getLog(self, revno, url=None, detailedLog=False):
        log=None
        if( url == None):
            url = self.getUrl('')
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
                
        logging.debug("Trying to get revision log. revno:%d, url=%s" % (revno, url))
        revlog = self.svnclient.log( url,
             revision_start=rev, revision_end=rev, discover_changed_paths=detailedLog)
        log = revlog[0]
                
        return(log)

    def getLogs(self, startrevno, endrevno, cachesize=1, detailedLog=False):
        revlog =None
        startrev = pysvn.Revision(pysvn.opt_revision_kind.number, startrevno)
        endrev = pysvn.Revision(pysvn.opt_revision_kind.number, endrevno)
        url = self.getUrl('')
                
        logging.debug("Trying to get revision logs [%d:%d]" % (startrevno, endrevno))
        revlog = self.svnclient.log( url,
             revision_start=startrev, revision_end=endrev, limit=cachesize,
                                     discover_changed_paths=detailedLog)
        return(revlog)
    
    def getRevDiff(self, revno):
        rev1 = pysvn.Revision(pysvn.opt_revision_kind.number, revno-1)
        rev2 = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl('')
        diff_log = None
        
        logging.info("Trying to get revision diffs url:%s" % url)
        diff_log = self.svnclient.diff(self.tmppath, url, revision1=rev1, revision2=rev2,
                        recurse=True,ignore_ancestry=True,ignore_content_type=False,
                               diff_deleted=True)
        return diff_log

    def getRevFileDiff(self, path, revno,prev_path=None,prev_rev=None):
        if( prev_path == None):
            prev_path = path

        rev1 = prev_rev or pysvn.Revision(pysvn.opt_revision_kind.number, revno-1)
        rev2 = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(path)
        prevurl = self.getUrl(prev_path)
        diff_log = None
        
        logging.debug("Getting filelevel revision diffs")
        logging.debug("revision : %d, url=%s" % (revno, url))
        logging.debug("prev url=%s" % (prevurl))
        
        diff_log = self.svnclient.diff(self.tmppath, url, revision1=rev1, revision2=rev2,
                    recurse=True, ignore_ancestry=False,ignore_content_type=False,
                               diff_deleted=True)
        
        return(diff_log)
    
    def getInfo(self, path, revno):
        '''Gets the information about the given path ONLY from the repository.
        Hence recurse flag is set to False.
        '''
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(path)
        entry_list = None
        
        logging.debug("Trying to get file information for %s" % url)
        entry_list = self.svnclient.info2( url,revision=rev,recurse=False)
        
        return(entry_list)
        
    def isChildPath(self, filepath):
        '''
        Check if the given path is a child path of if given svnrepourl. All filepaths are child paths
        if the repository path is same is repository 'root'
        Use while updating/returning changed paths in the a given revision.
        '''
        assert(self.svnrooturl != None)
        fullpath = self.svnrooturl + filepath
                
        return(fullpath.startswith(self.svnrepourl))

    def __isBinaryFileExt(self, filepath):
        '''
        check the extension of filepath and see if the extension is in binary files
        list
        '''
        return(filepath.endswith(self.binaryextlist))        

    def __isTextMimeType(self, fmimetype):
        '''
        check if the mime-type is a text mime-type based on the standard svn text file logic.        
        '''
        textMimeType = False
        if( fmimetype.startswith('text/') or fmimetype == 'image/x-xbitmap' or fmimetype == 'image/x-xpixmap'):
            textMimeType = True
        return(textMimeType)
            
    def __isBinaryFile(self, filepath, revno):
        '''
        detect if file is a binary file using same heuristic as subversion. If the file
        has no svn:mime-type  property, or has a mime-type that is textual (e.g. text/*),
        Subversion assumes it is text. Otherwise it is treated as binary file.
        '''
        logging.debug("Binary file check for file <%s> revision:%d" % (filepath, revno))
        binary = False #if explicit mime-type is not found always treat the file as 'text'                   
        url = self.getUrl(filepath)
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)

        proplist = self.svnclient.proplist(url, revision=rev)        
        if( len(proplist) > 0):
            assert(len(proplist) == 1)
            path, propdict = proplist[0]
            if( 'svn:mime-type' in propdict):
                fmimetype = propdict['svn:mime-type']
                #print "found mime-type file: %s mimetype : %s" % (filepath, fmimetype)
                if( self.__isTextMimeType(fmimetype)==False):
                    #mime type is not a 'text' mime type.
                    binary = True
               
        return(binary)
    
    def isBinaryFile(self, filepath, revno):
        binary = self.__isBinaryFileExt(filepath)
        
        if( binary == False):
            binary = self.__isBinaryFile(filepath, revno)
        return(binary)
    
    def isDirectory(self, revno, changepath, changetype):
        #if the file/dir is deleted in the current revision. Then the status needs to be checked for
        # one revision before that
        logging.debug("isDirectory: path %s change type %s revno %d" % (changepath, changetype, revno))
        if( changetype == 'D'):            
            revno = revno-1
        isDir = False            
        
        try:
            entry = self.getInfo(changepath, revno)
            filename, info_dict = entry[0]
            if( info_dict.kind == pysvn.node_kind.dir):
                isDir = True        
        except pysvn.ClientError, expinst:
            #it is possible that changedpath is deleted (even if changetype is not 'D') and
            # doesnot exist in the revno. In this case, we will get a ClientError exception.
            # this case just return isDir as 'False' and let the processing continue
            pass
                                                    
        return(isDir)
        
    def _getLineCount(self, filepath, revno):
        linecount = 0
        
        logging.info("Trying to get linecount for %s" % (filepath))
        rev = pysvn.Revision(pysvn.opt_revision_kind.number, revno)
        url = self.getUrl(filepath)
        contents = self.svnclient.cat(url, revision = rev)
        matches = re.findall("$", contents, re.M )
        if( matches != None):
            linecount = len(matches)
        logging.debug("%s linecount : %d" % (filepath, linecount))
        
        return(linecount)
    
    def getLineCount(self, filepath, revno):
        linecount = 0        
        if( self.isBinaryFile(filepath, revno) == False):
            linecount = self._getLineCount(filepath, revno)
        
        return(linecount)

    def getRootUrl2(self):
        assert( self.svnrooturl == None)
        #remove the trailing '/' if any
        firstrev = pysvn.Revision( pysvn.opt_revision_kind.number, 1)
        possibleroot = self.svnrepourl        
        if( possibleroot.endswith('/') == False):
            possibleroot = possibleroot+'/'

        #get the last log message for the given path.            
        revlog = self.svnclient.log(possibleroot, limit=1,discover_changed_paths=True)
        
        #Now changed path and subtract the common portion of changed path and possibleroot,
        #Remain ing 'possibleroot' is the actual subversion repository root path
        #This is really a hack. Needs a better/simpler way to do this.
        if( len(revlog) > 0):
            changepathlist = revlog[0].changed_paths
            assert(len(changepathlist) > 0)
            #since single revision can contain changes in multiple paths, we need to iterate
            #over all paths changed in a revision and compare it with possible root path.
            maxmatchlen = 0
            for changedpath in changepathlist:
                changedpath = changedpath['path'].split('/')                
                #split the path components and join them one by one and then find the
                #maximum matched size to get the repository root.
                for cmplen in range(1, len(changedpath)+1):
                    cpath = '/'.join(changedpath[0:cmplen])
                    cpath = cpath+'/'
                    if(possibleroot.endswith(cpath)==True):
                         maxmatchlen=max(maxmatchlen, len(cpath))
                         
            if( maxmatchlen > 0):
                #remove last 'maxmatch' characters.
                self.svnrooturl =possibleroot[0:-maxmatchlen]                
                
    def getRootUrl(self):        
        if( self.svnrooturl == None and self.svnclient.is_url(self.svnrepourl)):
            # for some reason 'root_url_from_path' crashes Python interpreter
            # for http:// urls for PySVN 1.6.3 (python 2.5)
            # hence I need to do jump through hoops to get -- Nitin
            #self.svnrooturl = self.svnclient.root_url_from_path(self.svnrepourl)
            
            #Comment this line if PySVN - root_url_from_path() function works for you.
            self.getRootUrl2()
            
            logging.debug("found rooturl %s" % self.svnrooturl)
            
        #if the svnrooturl is None at this point, then raise an exception
        if( self.svnrooturl == None):
            raise RuntimeError , "Repository Root not found"
            
        return(self.svnrooturl)
    
    def getUrl(self, path):
        url = self.svnrepourl
        if( path.strip() != ""):
            #remember 'path' can be a unicode string            
            try:
                path = path.encode('utf8')
            except:
                #not possible to encode path as unicode. Probably an latin-1 character with value > 127
                #keep path as it is.
                pass
            url = self.getRootUrl() + urllib.pathname2url(path)
        return(url)

    def isRepoUrlSameAsRoot(self):
        repourl = self.svnrepourl.rstrip('/')
        rooturl = self.getRootUrl()
        rooturl = rooturl.rstrip('/')
        return(repourl == rooturl)
    
    def __iter__(self):
        return(SVNRevLogIter(self, 1, self.getHeadRevNo()))

class SVNRevLogIter:
    def __init__(self, logclient, startRevNo, endRevNo, cachesize=50):
        self.logclient = logclient
        self.startrev = startRevNo
        self.endrev = endRevNo
        self.revlogcache = None
        self.cachesize = cachesize
        
    def __iter__(self):
        return(self.next())

    def next(self):
        if( self.endrev == 0):
            self.endrev = self.logclient.getHeadRevNo()
        if( self.startrev == 0):
            self.startrev = self.endrev
        
        while (self.startrev < self.endrev):
            logging.info("updating logs %d to %d" % (self.startrev, self.endrev))
            self.revlogcache = self.logclient.getLogs(self.startrev, self.endrev,
                                                          cachesize=self.cachesize, detailedLog=True)
            if( self.revlogcache == None or len(self.revlogcache) == 0):
                raise StopIteration
            
            self.startrev = self.revlogcache[-1].revision.number+1
            for revlog in self.revlogcache:
                #since reach revision log entry is a dictionary. If the dictionary is empty
                #then log is not available or its end of log entries
                if( len(revlog) == 0):
                    raise StopIteration
                svnrevlog = SVNRevLog(self.logclient, revlog)
                yield svnrevlog

class SVNChangeEntry:
    '''
    one change log entry inside one revision log. One revision can contain multiple changes.
    '''
    def __init__(self, parent, changedpath):
        '''
        changedpath is one changed_path dictionary entry in values returned PySVN::Log calls
        '''
        self.parent = parent
        self.logclient = parent.logclient
        self.revno = parent.getRevNo()
        self.changedpath = changedpath

    def isValidChange(self):
        '''
        check the changed path is valid for the 'given' repository path. All paths are valid
        if the repository path is same is repository 'root'
        '''
        return(self.logclient.isChildPath(self.filepath()))

    def isDirectory(self):
        isDir = False
        path = self.filepath()
        action = self.changedpath['action']
            
        #see if directory check is alredy done on this path. If not, then check with the repository        
        if( 'isdir' not in self.changedpath):
            isDir = self.logclient.isDirectory(self.revno, path, action)
            self.changedpath['isdir'] = isDir
            if( isDir and not path.endswith('/')):
                #if it is directory then add trailing '/' to the path to denote the directory.
                self.changedpath['path'] = path + '/'
        else:
            isDir = self.changedpath['isdir']
        
        return(isDir)

    def change_type(self):
        return(self.changedpath['action'])
    
    def filepath(self):
        nrmpath = normurlpath(self.changedpath['path'])
        return(nrmpath)
    
    def filepath_unicode(self):
        return(makeunicode(self.filepath()))

    def lc_added(self):
        lc = self.changedpath.get('lc_added', 0)
        return(lc)        

    def lc_deleted(self):
        lc = self.changedpath.get('lc_deleted', 0)
        return(lc)        

    def copyfrom(self):
        path = self.changedpath['copyfrom_path']
        path = makeunicode(normurlpath(path))
        rev  = self.changedpath['copyfrom_revision']
        revno = None
        if( rev != None):
            assert(rev.kind == pysvn.opt_revision_kind.number)
            revno = rev.number
        
        return(path,revno)            

    def pathtype(self):
        '''
        path type is (F)ile or (D)irectory
        '''
        pathtype = 'F'
        isdir = self.changedpath.get('isdir', False)
        if( isdir == True):
            pathtype = 'D'
        return(pathtype)

    def isBinaryFile(self):
        '''
        if the change is in a binary file.
        '''
        revno = self.revno
        if( self.change_type() == 'D'):
            #if change type is 'D' then reduce the 'revno' to appropriately detect the binary file type.
            revno = revno - 1
        binary = self.logclient.isBinaryFile(self.filepath(), revno)
        return(binary)    
                                           
    def updateDiffLineCountFromDict(self, diffCountDict):        
        if( 'lc_added' not in self.changedpath):
            linesadded=0
            linesdeleted=0
            filename = self.filepath()
            
            if( diffCountDict!= None and not self.isBinaryFile() and diffCountDict.has_key(filename)):
                linesadded, linesdeleted = diffCountDict[filename]
                self.changedpath['lc_added'] = linesadded
                self.changedpath['lc_deleted'] = linesdeleted
                
                    
    def getDiffLineCount(self):
        added = self.changedpath.get('lc_added', 0)
        deleted = self.changedpath.get('lc_deleted', 0)
            
        if( 'lc_added' not in self.changedpath):
            revno = self.revno
            filepath = self.filepath()
            changetype = self.changedpath['action']
            prev_filepath = self.changedpath.get('copyfrom_path')
            prev_revno = self.changedpath.get('copyfrom_revision')
            filename = filepath

            if( self.isDirectory() == False and not self.isBinaryFile() ):
                #path is added or deleted. First check if the path is a directory. If path is not a directory
                # then process further.
                if( changetype == 'A'):
                    added = self.logclient.getLineCount(filepath, revno)
                elif( changetype == 'D'):
                    deleted = self.logclient.getLineCount(filepath, revno-1)
                else:
                    #change type is 'changetype != 'A' and changetype != 'D'
                    #directory is modified
                    diff_log = self.logclient.getRevFileDiff(filepath, revno,prev_filepath, prev_revno)
                    diffDict = getDiffLineCountDict(diff_log)
                    #for single files the 'diff_log' contains only the 'name of file' and not full path.
                    #Hence to need to 'extract' the filename from full filepath
                    filename = '/'+filepath.rsplit('/', 2)[-1]
                    #The dictionary may not have the filename key if only properties are modfiied.
                    if(diffDict.has_key(filename) == True):
                        added, deleted = diffDict[filename]
                    
            logging.debug("DiffLineCount %d : %s : %s : %d : %d " % (revno, filename, changetype, added, deleted))
            self.changedpath['lc_added'] = added
            self.changedpath['lc_deleted'] = deleted
                  
        return(added, deleted)
        
    
class SVNRevLog:
    def __init__(self, logclient, revnolog):
        self.logclient = logclient
        if( isinstance(revnolog, pysvn.PysvnLog) == False):
            self.revlog = self.logclient.getLog(revnolog, detailedLog=True)
        else:
            self.revlog = revnolog
        assert(self.revlog == None or isinstance(revnolog, pysvn.PysvnLog)==True)

    def isvalid(self):
        '''
        if the revision log is a valid log. Currently the log is invalid if the commit 'date' is not there.        
        '''
        valid = True
        if( self.__getattr__('date') == None):
            valid = False
        return(valid)

    def getChangeEntries(self):
        '''
        get the change entries from each changed path entry
        '''
        for change in self.revlog.changed_paths:
            change_entry = SVNChangeEntry(self, change)
            if( change_entry.isValidChange()):
                yield change_entry
            
    def changedFileCount(self):
        '''includes directory and files. Initially I wanted to only add the changed file paths.
        however it is not possible to detect if the changed path is file or directory from the
        svn log output
        bChkIfDir -- If this flag is false, then treat all changed paths as files.
           since isDirectory function calls the svn client 'info' command, treating all changed
           paths as files will avoid calls to isDirectory function and speed up changed file count
           computations
        '''
        filesadded = 0
        fileschanged = 0
        filesdeleted = 0
        logging.debug("Changed path count : %d" % len(self.revlog.changed_paths))
        
        for change in self.getChangeEntries():
                isdir = change.isDirectory()
                if( isdir == False):
                    action = change.change_type()                
                    if( action == 'M'):
                        fileschanged = fileschanged +1
                    elif(action == 'A'):
                        filesadded = filesadded+1
                    elif(action == 'D'):
                        filesdeleted = filesdeleted+1
        return(filesadded, fileschanged, filesdeleted)
                    
    def getDiffLineCount(self, bUpdLineCount=True):
        """
        Returns a list of tuples containing filename, lines added and lines modified
        In case of binary files, lines added and deleted are returned as zero.
        In case of directory also lines added and deleted are returned as zero
        """                        
        diffCountDict = None
        if( bUpdLineCount == True):
            diffCountDict = self.__updateDiffCount()
            
        diffCountList = []
        for change in self.getChangeEntries():
            change.updateDiffLineCountFromDict(diffCountDict)
            filename=change.filepath()
            changetype=change.change_type()
            linesadded=change.lc_added()
            linesdeleted = change.lc_deleted()
            logging.debug("%d : %s : %s : %d : %d " % (self.revno, filename, change.change_type(), linesadded, linesdeleted))
            yield change                    
            
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
            msg = None
                
            try:
                msg = makeunicode(self.revlog.message)
            except:
                msg = u''
            return(msg)
        elif(name == 'date'):
            try:
                dt = convert2datetime(self.revlog.date)
            except:
                dt = None
            return(dt)
        elif(name == 'revno'):
            return(self.revlog.revision.number)
        elif(name == 'changedpathcount'):
            filesadded, fileschanged, filesdeleted = self.changedFileCount()
            return(filesadded+fileschanged+filesdeleted)
        return(None)
    
    def __useFileRevDiff(self):
        '''
        file level revision diff requires less memory but more calls to repository.
        Hence for large sized repositories, repository with many large commits, and
        repositories which are local file system, it is better to use file level revision
        diff. For other cases it is better to query diff of entire revision at a time.
        '''
        # repourl is not same as repository root (e.g. <root>/trunk) then we have to
        # use the file revision diffs.
        usefilerevdiff = True
        if( self.logclient.isRepoUrlSameAsRoot()):
            usefilerevdiff = False
        rooturl = self.logclient.getRootUrl()
        if( rooturl.startswith('file://')):
            usefilerevdiff=True
        return(usefilerevdiff)
        
    def __updateDiffCount(self):
        diffcountdict = dict()            
        try:
            revno = self.getRevNo()                            
            logging.debug("Updating line count for revision %d" % revno)
            if( self.__useFileRevDiff()):
                logging.debug("Using file level revision diff")
                for change in self.getChangeEntries():
                    filename = change.filepath()
                    diffcountdict[filename] = change.getDiffLineCount()
            else:                
                #if the svnrepourl and root url are same then we can use 'revision level' diff calls
                # get 'diff' of multiple files included in a 'revision' by a single svn api call.
                # As All the changes are 'modifications' (M type) then directly call the 'getRevDiff'.
                #getRevDiff fails if there are files added or 'deleted' and repository path is not
                # the root path.
                logging.debug("Using entire revision diff at a time")
                revdiff_log = self.logclient.getRevDiff(revno)                
                diffcountdict = getDiffLineCountDict(revdiff_log)
            
        except Exception, expinst:            
            logging.error("Error %s" % expinst)
            
        return(diffcountdict)
                 
