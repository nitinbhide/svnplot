#!/usr/bin/env python
'''
svnstatscsv.py
Copyright (C) 2009 Nitin Bhide nitinbhide@gmail.com

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

Export the Subversion repository data in csv format.
Check issue <> for details.
'''
from __future__ import with_statement

from optparse import OptionParser
import sqlite3
import os.path, sys
import string,StringIO
import math
import csv

from svnstats import *

def addcsvcomment(cvswriter, comment):
    '''
    add a comment line in the csv. Comment line start with '#' as first character.
    '''
    comment = '#'+comment
    cvswriter.writerow([comment])
    
class SVNStatsCSV:
    '''
    class to export the svn repository statistics in csv format for processing
    '''
    def __init__(self,svnstats):
        self.svnstats = svnstats
        self.authorsToDisplay = 10
        self.fileTypesToDisplay = 20
        self.dirdepth = 2        
        self.reponame = ""                
        self.verbose = False
        
    def SetVerbose(self, verbose):       
        self.verbose = verbose
        self.svnstats.SetVerbose(verbose)

    def SetRepoName(self, reponame):
        self.reponame = reponame
        
    def _printProgress(self, msg):
        if( self.verbose == True):
            print msg

    def basicStats(self, csvwriter):
        '''
        export basic stats
        '''
        addcsvcomment(csvwriter, "SECTION:Basic stats about the repository")
        addcsvcomment(csvwriter, "FORMAT:stat name, stat data")
        basestats = self.svnstats.getBasicStats()
        csvwriter.writerow(["Repository Name", self.reponame])
        csvwriter.writerow(["Search Path", self.svnstats.searchpath])
        csvwriter.writerow(["First Revision no.", basestats['FirstRev']])
        csvwriter.writerow(["Latest Revision no.", basestats['LastRev']])
        csvwriter.writerow(["First Commit Date", basestats['FirstRevDate'].strftime('%b %d, %Y %I:%M %p')])
        csvwriter.writerow(["Last Commit Date", basestats['LastRevDate'].strftime('%b %d, %Y %I:%M %p')])
        csvwriter.writerow(["Number of Revisions", basestats['NumRev']])
        csvwriter.writerow(["Number of Revisions", basestats['NumRev']])
        csvwriter.writerow(["Number of active files", basestats['NumFiles'] ])
        csvwriter.writerow(["Number of active files", basestats['NumFiles'] ])
        csvwriter.writerow(["Number of authors", basestats['NumAuthors']])
        csvwriter.writerow(["Total Number of Lines", basestats['LoC']])
        
    def activeAuthors(self, csvwriter):
        '''
        get the active authors and its temperature statistics.
        '''
        addcsvcomment(csvwriter, "SECTION:author stats")
        addcsvcomment(csvwriter, "FORMAT:Author name, Author Activity Temperature")
        hotauthors = self.svnstats.getActiveAuthors(10)
        for author, temperatur in hotauthors:
            csvwriter.writerow([author, temperatur])
        
    def activeFiles(self, csvwriter):
        '''
        get the active filename and its temperature statistics.
        '''
        addcsvcomment(csvwriter, "SECTION:file stats")
        addcsvcomment(csvwriter, "FORMAT:file name, File Activity Temperature, revision count")
        hotfiles = self.svnstats.getHotFiles(10)
        for filepath, temperatur,revcount in hotfiles:
            csvwriter.writerow([self.svnstats.getSearchPathRelName(filepath), temperatur,revcount])
        
    def activityByWeekday(self, csvwriter):
        '''
        update the stats for the activity by week day 
        '''
        addcsvcomment(csvwriter, "SECTION:Activity by Weekday")
        addcsvcomment(csvwriter, "FORMAT:day of week, number of commits")
        commitcountlist, weekdaylist = self.svnstats.getActivityByWeekday()
        for commitcount, weekday in zip(commitcountlist,weekdaylist):
            csvwriter.writerow([weekday, commitcount])
            
    def activityByTimeOfDay(self, csvwriter):
        '''
        update the stats for the activity by time of the day
        '''
        addcsvcomment(csvwriter, "SECTION:Activity by Time of Day")
        addcsvcomment(csvwriter, "FORMAT:hr, number of commits")
        commitcountlist, hrofdaylist = self.svnstats.getActivityByTimeOfDay()
        for commitcount, hr in zip(commitcountlist,hrofdaylist):
            csvwriter.writerow([hr, commitcount])
        
    def AllStats(self, csvfilename, searchpath, maxdircount):
        '''
        export all available stats.
        '''
        self.svnstats.SetSearchPath(searchpath)
        with open(csvfilename, "wb") as csvfile:        
            csvwriter = csv.writer(csvfile)
            self.basicStats(csvwriter)
            self.activeAuthors(csvwriter)
            self.activeFiles(csvwriter)            
            self.activityByWeekday(csvwriter)
            self.activityByTimeOfDay(csvwriter)
            
    
def RunMain():
    usage = "usage: %prog [options] <svnsqlitedbpath> <csvfile>"
    parser = OptionParser(usage)

    parser.add_option("-n", "--name", dest="reponame",
                      help="repository name")
    parser.add_option("-s","--search", dest="searchpath", default="/",
                      help="search path in the repository (e.g. /trunk)")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="display verbose progress")
    parser.add_option("-m","--maxdir",dest="maxdircount", default=10, type="int",
                      help="limit the number of directories on the graph to the x largest directories")
    
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments. Use svnstatscsv.py --help to see the details."
    else:        
        svndbpath = args[0]
        csvfilename = args[1]
        
        if( options.searchpath.endswith('%') == False):
            options.searchpath +='%'
            
        if( options.verbose == True):
            print "Exporting subversion repository data in CSV format"
            print "Subversion log database : %s" % svndbpath
            print "CSV file name : %s" % csvfilename
            print "Repository Name : %s" % options.reponame
            print "Search path inside repository : %s" % options.searchpath
            print "Maximum dir count: %d" % options.maxdircount            
                
        svnstats = SVNStats(svndbpath)
        
        svnstatscsv = SVNStatsCSV(svnstats)
        svnstatscsv.SetVerbose(options.verbose)
        svnstatscsv.SetRepoName(options.reponame)
        svnstatscsv.AllStats(csvfilename, options.searchpath, options.maxdircount)

if(__name__ == "__main__"):
    RunMain()

