#!/usr/bin/env python
'''
svnlogdb.py
Copyright (C) 2014 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
Database interface abstraction for svnplot. This class manages the tables, inserts, deletes and query
i.e. basically all database operations
'''
import logging
from contextlib import closing
import sqlite3

class SVNLogDB(object):
    '''
    Database interface abstraction for svnplot. This class manages the tables, inserts, deletes and query
    i.e. basically all database operations. Reimplementing this class will make the code work for different
    database interface (e.g. sqlalachemy or using Django ORM etc)
    First implementation is for sqlite only using the default python DB API interface for sqlite.
    '''
    def __init__(self, **connections_params):
        '''
        connections_params : can be different for different databases. Hence keywoard args
        '''
        self.__dbpath = connections_params['dbpath']
        #initialize all cursor variables to None
        self._updcur = None
        
    def connect(self):
        '''
        connect to database and create the initial tables
        '''
        self.dbcon = sqlite3.connect(self.__dbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        #create a seperate update cursor. If same cursor is used for updates and select(query),
        #then it closes current query and hence gives wrong results
        self._updcur = self.dbcon.cursor()
        self.CreateTables()
    
    def commit(self):
        '''
        commit the running transaction at this point
        '''
        assert(self.dbcon != None)
        self.dbcon.commit()
    
    def rollback(self):
        assert(self.dbcon != None)
        self.dbcon.rollback()
    
    def close(self):
        self.commit()
        self.dbcon.close()

    def CreateTables(self):
        with closing(self.dbcon.cursor()) as cur:
            cur.execute("create table if not exists SVNLog(revno integer, commitdate timestamp, author text, msg text, \
                                addedfiles integer, changedfiles integer, deletedfiles integer)")
            cur.execute("create table if not exists SVNLogDetail(revno integer, changedpathid integer, changetype text, copyfrompathid integer, copyfromrev integer, \
                        pathtype text, linesadded integer, linesdeleted integer, lc_updated char, entrytype char)")
            cur.execute("CREATE TABLE IF NOT EXISTS SVNPaths(id INTEGER PRIMARY KEY AUTOINCREMENT, path text, relpathid INTEGER DEFAULT null)")
            try:
                    #create VIEW IF NOT EXISTS was not supported in default sqlite version with Python 2.5
                    cur.execute("CREATE VIEW SVNLogDetailVw AS select SVNLogDetail.*, ChangedPaths.path as changedpath, CopyFromPaths.path as copyfrompath \
                        from SVNLogDetail LEFT JOIN SVNPaths as ChangedPaths on SVNLogDetail.changedpathid=ChangedPaths.id \
                        LEFT JOIN SVNPaths as CopyFromPaths on SVNLogDetail.copyfrompathid=CopyFromPaths.id")
            except:
                    #you will get an exception if the view exists. In that case nothing to do. Just continue.
                    pass
            #lc_updated - Y means line count data is updated.
            #lc_updated - N means line count data is not updated. This flag can be used to update
            #line count data later        
            cur.execute("CREATE INDEX if not exists svnlogrevnoidx ON SVNLog (revno ASC)")
            cur.execute("CREATE INDEX if not exists svnlogdtlrevnoidx ON SVNLogDetail (revno ASC)")
            cur.execute("CREATE INDEX if not exists svnlogdtlchangepathidx ON SVNLogDetail (changedpathid ASC)")
            cur.execute("CREATE INDEX if not exists svnlogdtlcopypathidx ON SVNLogDetail (copyfrompathid ASC)")
            cur.execute("CREATE INDEX IF NOT EXISTS svnpathidx ON SVNPaths (path ASC)")
            self.dbcon.commit()
            
        #Table structure is changed slightly. I have added a new column in SVNLogDetail table.
        #Use the following sql to alter the old tables
        #ALTER TABLE SVNLogDetail ADD COLUMN lc_updated char
        #update SVNLogDetail set lc_updated ='Y' ## Use 'Y' or 'N' as appropriate.

        #because of some bug in old code sometimes path contains '//' or '.'. Uncomment the line to Fix such paths
        #self.__fixPaths()
        
    def __fixPaths(self):
        '''
        because of some bug in old code sometimes the path contains '//' or '.' etc. Fix such paths
        '''
        with closing(self.dbcon.cursor()) as cur:
            cur.execute("select * from svnpaths")
            pathstofix = []
            for id, path in cur:
                nrmpath = svnlogiter.normurlpath(path)
                if( nrmpath != path):
                    logging.debug("fixing path for %s to %s"%(path, nrmpath))
                    pathstofix.append((id,nrmpath))
            for id, path in pathstofix:
                cur.execute('update svnpaths set path=? where id=?',(path, id))
            self.dbcon.commit()
        #Now fix the duplicate entries created after normalization
        with closing(self.dbcon.cursor()) as cur:
            with closing(self.dbcon.cursor()) as updcur:
                cur.execute("SELECT count(path) as pathcnt, path FROM svnpaths group by path having pathcnt > 1")
                duppathlist = [path for cnt, path in cur]
                for duppath in duppathlist:
                    #query the ids for this path
                    cur.execute("SELECT * FROM svnpaths WHERE path = ? order by id", (duppath,))
                    correctid, duppath1 = cur.fetchone()
                    print "updating path %s" % duppath
                    for pathid, duppath1 in cur:
                        updcur.execute("UPDATE SVNLogDetail SET changedpathid=? where changedpathid=?", (correctid,pathid))
                        updcur.execute("UPDATE SVNLogDetail SET copyfrompathid=? where copyfrompathid=?", (correctid,pathid))
                        updcur.execute("DELETE FROM svnpaths where id=?", (pathid,))
                    self.dbcon.commit()
                #if paths are fixed. Then drop the activity hotness table so that it gets rebuilt next time.
                if( len(duppathlist) > 0):            
                    updcur.execute("DROP TABLE IF EXISTS ActivityHotness")        
                    self.dbcon.commit()        
                    print "fixed paths"
            
    def getLastStoredRev(self):
        with closing(self.dbcon.cursor()) as cur:
            cur.execute("select max(revno) from svnlog")
            lastStoreRev = 0
            
            row = cur.fetchone()
            if( row != None and len(row) > 0 and row[0] != None):
                lastStoreRev = int(row[0])
            
        return(lastStoreRev)

    def getFilePathId(self, filepath):
        '''
        update the filepath id if required.
        '''
        id = None
        if( filepath ):
            with closing(self.dbcon.cursor()) as updcur:
                with closing(self.dbcon.cursor()) as querycur:
                    querycur.execute('select id from SVNPaths where path = ?', (filepath,))
                    resultrow = querycur.fetchone()
                    if( resultrow == None):
                        updcur.execute('INSERT INTO SVNPaths(path) values(?)', (filepath,))
                        querycur.execute('select id from SVNPaths where path = ?', (filepath,))
                        resultrow = querycur.fetchone()
                    id = resultrow[0]
            
        return(id)
    
    def addRevision(self, revlog, addedfiles, changedfiles, deletedfiles):
        '''
        add entry for a new revision in the SVNLog table
        '''
        self._updcur.execute("INSERT into SVNLog(revno, commitdate, author, msg, addedfiles, changedfiles, deletedfiles) \
                                values(?, ?, ?, ?,?, ?, ?)",
                                (revlog.revno, revlog.date, revlog.author, revlog.message, addedfiles, changedfiles, deletedfiles))
                    
    
    def addRevisionDetails(self, revno, change_entry,lc_updated):
        '''
        add the revision details in the SVNlogDetails table
        '''
        filename =change_entry.filepath_unicode()
        changetype = change_entry.change_type()
        linesadded = change_entry.lc_added()
        linesdeleted = change_entry.lc_deleted()
        copyfrompath,copyfromrev = change_entry.copyfrom()
        entry_type = 'R' #Real log entry.
        pathtype = change_entry.pathtype()
        if(pathtype=='D'):
            assert(filename.endswith('/')==True)
        changepathid = self.getFilePathId(filename)
        copyfromid = self.getFilePathId(copyfrompath)
        if (changetype == 'R'):
            logging.debug("Replace linecount (revno : %d): %s %d" % (revno, filename,linesadded))
        self._updcur.execute("INSERT into SVNLogDetail(revno, changedpathid, changetype, copyfrompathid, copyfromrev, \
                            linesadded, linesdeleted, lc_updated, pathtype, entrytype) \
                    values(?, ?, ?, ?,?,?, ?,?,?,?)", (revno, changepathid, changetype, copyfromid, copyfromrev, \
                            linesadded, linesdeleted, lc_updated, pathtype, entry_type))

        
    def updateNumFiles(self,revno, addedfiles,deletedfiles):
        '''
        update the added/deleted files count for a given revision
        '''
        self._updcur.execute("UPDATE SVNLog SET addedfiles=?, deletedfiles=? where revno=?",
                             (addedfiles,deletedfiles,revno))
                        
    def createRevFileListForDir(self, revno, dirname):
        '''
        create the file list for a revision in a temporary table.
        '''
        assert(dirname.endswith('/'))
        self._updcur.execute('DROP TABLE IF EXISTS TempRevDirFileList')
        self._updcur.execute('DROP VIEW IF EXISTS TempRevDirFileListVw')
        self._updcur.execute('CREATE TEMP TABLE TempRevDirFileList(path text, pathid integer, addrevno integer)')
        self._updcur.execute('CREATE INDEX revdirfilelistidx ON TempRevDirFileList (addrevno ASC, path ASC)')
        sqlquery = 'SELECT DISTINCT SVNPaths.path, changedpathid, SVNLogDetail.revno FROM SVNLogDetail,SVNPaths WHERE \
                    pathtype="F" and SVNLogDetail.revno <=%d and (changetype== "A" or changetype== "R") \
                    and SVNLogDetail.changedpathid = SVNPaths.id and \
                    (SVNPaths.path like "%s%%" and SVNPaths.path != "%s")' \
                    % (revno,dirname,dirname)
        
        with closing(self.dbcon.cursor()) as querycur:
            querycur.execute(sqlquery)
            for sourcepath, sourcepathid, addrevno in querycur:
                self._updcur.execute('INSERT INTO TempRevDirFileList(path, pathid, addrevno) \
                            VALUES(?,?,?)',(sourcepath, sourcepathid, addrevno))
            self.dbcon.commit()
            
            #Now delete the already deleted files from the file list.
            sqlquery = 'SELECT DISTINCT SVNPaths.path, SVNLogDetail.changedpathid, SVNLogDetail.revno FROM SVNLogDetail,SVNPaths \
                       WHERE pathtype="F" and SVNLogDetail.revno <=%d and changetype== "D" \
                       and SVNLogDetail.changedpathid = SVNPaths.id \
                        and (SVNPaths.path like "%s%%" and SVNPaths.path!= "%s")' \
                        % (revno,dirname,dirname)
            querycur.execute(sqlquery)
            for sourcepath, sourcepathid, delrevno in querycur:            
                self._updcur.execute('DELETE FROM TempRevDirFileList WHERE path=? and addrevno < ?',(sourcepath, delrevno))
            
            #in rare case there is a possibility of duplicate values in the TempRevFileList
            #hence try to create a temporary view to get the unique values
            updcur.execute('CREATE TEMP VIEW TempRevDirFileListVw AS SELECT DISTINCT \
                path, pathid, addrevno FROM TempRevDirFileList')
            self.dbcon.commit()
    
    def createRevFileList(self, revlog, copied_dirlist, deleted_dirlist):
        '''
        create the file list for a revision for a specific directory in a temporary table.
        '''
        try:
            upd_del_dirlist = deleted_dirlist            
            self._updcur.execute('DROP TABLE IF EXISTS TempRevFileList')
            self._updcur.execute('DROP VIEW IF EXISTS TempRevFileListVw')
            self._updcur.execute('CREATE TEMP TABLE TempRevFileList(path text, addrevno integer, \
                        copyfrom_path text, copyfrom_pathid integer, copyfrom_rev integer)')
            self._updcur.execute('CREATE INDEX revfilelistidx ON TempRevFileList (addrevno ASC, path ASC)')
            
            with closing(self.dbcon.cursor()) as querycur:
                for change in copied_dirlist:
                    copiedfrom_path,copiedfrom_rev = change.copyfrom()
                    #collect all files added to this directory.
                    assert(copiedfrom_path.endswith('/') == change.filepath_unicode().endswith('/'))
                    
                    sqlquery = 'SELECT DISTINCT SVNPaths.path, changedpathid, revno FROM SVNLogDetail, SVNPaths \
                        WHERE pathtype="F" and revno <=%d and (changetype== "A" or changetype== "R") and \
                        SVNPaths.id = SVNLogDetail.changedpathid and \
                        (SVNPaths.path like "%s%%" and SVNPaths.path!= "%s") \
                        ' % (copiedfrom_rev,copiedfrom_path,copiedfrom_path)                
                    querycur.execute(sqlquery)
                    for sourcepath, sourcepathid, addrevno in querycur:
                        path = sourcepath.replace(copiedfrom_path, change.filepath_unicode())                    
                        self._updcur.execute('INSERT INTO TempRevFileList(path, addrevno, copyfrom_path, copyfrom_pathid,copyfrom_rev) \
                            VALUES(?,?,?,?,?)',(path, addrevno, sourcepath,sourcepathid, copiedfrom_rev))
                self.dbcon.commit()
                
                #Now delete the already deleted files from the file list.                
                for change in copied_dirlist:
                    copiedfrom_path,copiedfrom_rev = change.copyfrom()
                    sqlquery = 'SELECT DISTINCT SVNPaths.path, changedpathid, revno FROM SVNLogDetail,SVNPaths WHERE \
                        pathtype="F" and revno <=%d and changetype== "D" and \
                        SVNPaths.id = SVNLogDetail.changedpathid and \
                        (SVNPaths.path like "%s%%" and SVNPaths.path != "%s")'% (copiedfrom_rev,copiedfrom_path,copiedfrom_path)
                    querycur.execute(sqlquery)
                    for sourcepath, sourcepathid, delrevno in querycur:
                        path = sourcepath.replace(copiedfrom_path, change.filepath_unicode())                    
                        self._updcur.execute('DELETE FROM TempRevFileList WHERE path=? and addrevno < ?',(path, delrevno))
                        
                self.dbcon.commit()
                
                #Now delete the entries for which 'real' entry is already created in
                #this 'revision' update.
                for change_entry in revlog.getFileChangeEntries():
                    filepath = change_entry.filepath()
                    self._updcur.execute('DELETE FROM TempRevFileList WHERE path=?',(filepath,))
                    
                upd_del_dirlist = []        
                for change in deleted_dirlist:
                    #first check if 'deleted' directory entry is there in the revision filelist
                    #if yes, remove those rows.
                    querycur.execute('SELECT count(*) FROM TempRevFileList WHERE path like "%s%%"' %change.filepath())
                    count = int(querycur.fetchone()[0])
                    if( count > 0):
                        self._updcur.execute('DELETE FROM TempRevFileList WHERE path like "%s%%"'%change.filepath())
                    else:
                        #if deletion path is not there in the addition path, it has to be
                        #handled seperately. Hence add it into different list
                        upd_del_dirlist.append(change)
            
            #in rare case there is a possibility of duplicate values in the TempRevFileList
            #hence try to create a temporary view to get the unique values
            self._updcur.execute('CREATE TEMP VIEW TempRevFileListVw AS SELECT DISTINCT \
                path, addrevno, copyfrom_path, copyfrom_pathid,copyfrom_rev FROM TempRevFileList \
                group by path having addrevno=max(addrevno)')
                    
            self.dbcon.commit()
            
        except:
            logging.exception("Found error while getting file list for revision")
            
        return(upd_del_dirlist)
    
    def addDummyAdditionDetails(self, revno):        
        addedfiles  = 0
        path_type = 'F'                                    
        changetype = 'A'
        entry_type = 'D'
        lc_updated = 'Y'
        total_lc_added = 0

        with closing(self.dbcon.cursor()) as querycur:
            querycur.execute("SELECT count(*) from TempRevFileListVw")
            logging.debug("Revision file count = %d" % querycur.fetchone()[0])
            
            querycur.execute("SELECT * from TempRevFileListVw")
            for changedpath, addrevno, copyfrompath, copyfrompathid, copyfromrev in querycur.fetchall():                    
                querycur.execute("select sum(linesadded), sum(linesdeleted) from SVNLogDetail \
                        where revno <= ? and changedpathid ==(select id from SVNPaths where path== ?) group by changedpathid",
                         (copyfromrev, copyfrompath))
        
                row = querycur.fetchone()
                #set lines added to current line count
                lc_added = 0
                if row is not None:
                    lc_added = row[0]-row[1]
                            
                if( lc_added < 0):
                    logging.error("Found negative linecount for %s(rev %d)" % (copyfrompath,copyfromrev))
                    lc_added = 0
                #set the lines deleted = 0
                lc_deleted = 0
    
                total_lc_added = total_lc_added+lc_added
                #logging.debug("\tadded dummy addition entry for path %s linecount=%d" % (changedpath,lc_added))
                changedpathid = self.getFilePathId(changedpath)
                copyfrompathid = self.getFilePathId(copyfrompath)
                assert(path_type != 'U')
                self._updcur.execute("INSERT into SVNLogDetail(revno, changedpathid, changetype, copyfrompathid, copyfromrev, \
                                        linesadded, linesdeleted, entrytype, pathtype, lc_updated) \
                                values(?, ?, ?, ?,?,?, ?,?,?,?)", (revno, changedpathid, changetype, copyfrompathid, copyfromrev, \
                                        lc_added, lc_deleted, entry_type,path_type,lc_updated))
                addedfiles = addedfiles+1                    
            #Now commit the changes
            self.dbcon.commit()
        logging.debug("\t Total dummy line count : %d" % total_lc_added)
        return addedfiles
    
    def addDummyDeletionDetails(self, revno, deleted_dir):
        deletedfiles = 0
        addedfiles  = 0
        path_type = 'F'
        #set lines added to 0
        lc_added = 0
        changetype = 'D'
        entry_type = 'D'
        lc_updated = 'Y'
        
        assert(deleted_dir.endswith('/'))
        #now query the deleted folders from the sqlite database and get the
        #file list
        logging.debug("Updating dummy file deletion entries for path %s" % deleted_dir)
        self.createRevFileListForDir(revno, deleted_dir)
        
        with closing(self.dbcon.cursor()) as querycur:        
            querycur.execute('SELECT path FROM TempRevDirFileListVw')
            for changedpath, in querycur.fetchall():
                #logging.debug("\tDummy file deletion entries for path %s" % changedpath)      
                querycur.execute('select sum(linesadded), sum(linesdeleted)  from SVNLogDetail \
                        where revno <= ? and changedpathid ==(select id from SVNPaths where path== ?) group by changedpathid',
                                 (revno,changedpath))
            
                row = querycur.fetchone()
                lc_deleted = 0
                if row != None:                
                    #set lines deleted to current line count
                    lc_deleted = row[0]-row[1]                
                if( lc_deleted < 0):
                    logging.error("Found negative linecount for %s(rev %d)" % (changedpath,revno))
                    lc_deleted = 0
            
                changedpathid = self.getFilePathId(changedpath, updcur)
                self._updcur.execute("INSERT into SVNLogDetail(revno, changedpathid, changetype,  \
                                        linesadded, linesdeleted, entrytype, pathtype, lc_updated) \
                                values(?, ?,?,?, ?,?,?,?)", (revno, changedpathid, changetype,  \
                                        lc_added, lc_deleted, entry_type,path_type,lc_updated))
                deletedfiles = deletedfiles+1
            self.dbcon.commit()
        return deletedfiles

    def getRevsLineCountNotUpdated(self):
        '''
        return list of revision numbers where line count is not updated yet.
        '''
        with closing(self.dbcon.cursor()) as cur:
            cur.execute("CREATE TEMP TABLE IF NOT EXISTS LCUpdateStatus \
                        as select revno, changedpath, changetype from SVNLogDetail where lc_updated='N'")
            self.dbcon.commit()
            cur.execute("select revno, changedpath, changetype from LCUpdateStatus")
            
            yield cur.fetchone()
            
    def updateLineCount(self, revno, changedpath, linesadded,linesdeleted):
        sqlquery = "Update SVNLogDetail Set linesadded=%d, linesdeleted=%d, lc_updated='Y' \
                    where revno=%d and changedpath='%s'" %(linesadded,linesdeleted, revno,changedpath)
        self._updcur.execute(sqlquery)            
        
    