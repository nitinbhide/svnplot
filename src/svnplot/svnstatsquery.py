#!/usr/bin/env python
'''
svnstatsquery.py
Copyright (C) 2013 Nitin Bhide nitinbhide@gmail.com

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

Run some ad-hoc queries on svnplot database. Read the query from the commandline
and dump the data in csv format in the output file.
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
    
class SVNStatsQuery:
    '''
    class to export the svn repository statistics in csv format for processing
    '''
    def __init__(self,svnstats):
        self.svnstats = svnstats
        self.reponame = ""                
        self.verbose = False
        
    def SetVerbose(self, verbose):       
        self.svnstats.SetVerbose(verbose)

    def SetRepoName(self, reponame):
        self.reponame = reponame
        
    def runQuery(self, csvfilename, query):
        '''
        run the ad-hoc query and dump the output in the csv file.
        '''
        print "Runnng query %s" % query
        with open(csvfilename, "wb") as csvfile:        
            csvwriter = csv.writer(csvfile)
            for row in self.svnstats.runQuery(query):                
                csvwriter.writerow(row)                    
    
def RunMain():
    usage = "usage: %prog [options] <svnsqlitedbpath> <csvfile>"
    parser = OptionParser(usage)

    parser.add_option("-n", "--name", dest="reponame",
                      help="repository name")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="display verbose progress")
    parser.add_option("-q", "--query", dest="query", help="query to be executed")
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments. Use svnstatsquery.py --help to see the details."
    else:        
        svndbpath = args[0]
        csvfilename = args[1]
                
        if( options.verbose == True):
            print "Exporting subversion repository data in CSV format"
            print "Subversion log database : %s" % svndbpath
            print "CSV file name : %s" % csvfilename
            print "Repository Name : %s" % options.reponame
                
        svnstats = SVNStats(svndbpath)
        
        svnstatsquery = SVNStatsQuery(svnstats)
        svnstatsquery.SetVerbose(options.verbose)
        svnstatsquery.SetRepoName(options.reponame)
        svnstatsquery.runQuery(csvfilename, options.query)

if(__name__ == "__main__"):
    RunMain()

