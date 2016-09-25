'''
svnsqlite2ora.py
Copyright (C) 2010 Oscar Castaneda (oscar.castaneda@gmail.com)

This module is part of SVNPlot (https://bitbucket.org/nitinbhide/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

python script to process a Subversion log collected by svnlog2sqlite.py, which is stored in a 
sqlite database. The idea is to use the SQLite database generated by SVNPlot to create the XML 
input file for CMU's Organizational Risk Analyzer (*ORA). Using *ORA several SNA graphs and 
analyses may be conducted.

Note: This is version was inspired by Apache Agora. It considers commits as part
of conversations (like email conversations in Apache Agora). Upon committing code, a committer
creates a revision in SVN which in turn creates a link to all committers who have co-authored 
the corresponding files from that revision. The idea is the same as in Agora, namely to create
links based on reply actions, but differs in that there is no one originator but instead links
are created to all co-authors who are active in the sqlite db contents.

This version of svnsqlite2ora.py has been tested with SVNPlot version 0.6.1 .
'''

import sqlite3
import datetime
from datetime import date
import calendar
import string
from datetime import datetime
from optparse import OptionParser

try:
    from numpy import *
    from numpy import matrix
    from numpy import linalg
except:
    print("numpy not found. Please install numpy")

try:
    import scipy
except:
    print("scipy not found. Please install scipy")


class SVNSqlite2Ora:

    def __init__(self, sqlitedbpath, outputfilepath):
        self.dbpath = sqlitedbpath
        self.dbcon = None
        self.outputfile = outputfilepath
        self.Process()

    def initdb(self):
        self.dbcon = sqlite3.connect(
            self.dbpath, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

    def closedb(self):
        self.dbcon.commit()
        self.dbcon.close()

    def Process(self):
        output = open(self.outputfile, 'w')
        self.initdb()
        print("Processing...")

        revisions = []
        revisions_count = 0
        r = {}

        committers = []
        committer_count = 0
        c = {}

        # Write XML prelude to CMU node specification
        output.write("<?xml version=\"1.0\" standalone=\"yes\"?>\n")
        output.write("<DynamicMetaNetwork id=\"Meta Network\">\n")

        # We create a cursor for SVNLog and do a SELECT on all records (*), so
        # cur = SVNLog
        cur = self.dbcon.cursor()

        # Write XML specification for MetaNetwork, then start writing <nodes>
        # section of the XML file consisting of Agents
        output.write(
            "<MetaNetwork id=\"Meta Network \" date=\"20000101T00:00:00\">\n")
        output.write("<nodes>\n")
        output.write("<nodeclass type=\"Agent\" id=\"Agent\">\n")

        # We go through all the committers and their revisions, then we create
        # lists of both.
        cur.execute('SELECT * FROM SVNLog')
        for row in cur:

            committer = row[2]
            revno = row[0]

            # If committer has not been counted then add him/her to the list, and increment committer_count
            # then write <node id> in XML file.
            if (committers.count(committer) == 0):
                committers.append(committer)
                committer_count = committer_count + 1
                c[committer] = committer_count
                output.write("<node id=\"" + "%s" % committer + "\"/>\n")

            # If a revision has not been counted then add it to the list, increment revision_count and
            # associate revision to committer.
            if (revisions.count(revno) == 0):
                revisions.append(revno)
                revisions_count = revisions_count + 1
                r[revno] = committer

        committer_count = committer_count + 1

        cur.close

        # Finish the <nodeclass> and <nodes> section, and start the <networks> section
        # of the XML file.
        output.write("</nodeclass>\n")
        output.write("</nodes>\n")
        output.write("<networks>\n")

        #######################################################################
        # Write sociomatrix from                                                   #
        # Agent x Resource(changedpathid) and Resource(changedpathid) x Agent      #
        #######################################################################
        cur = self.dbcon.cursor()
        cur.execute('SELECT * FROM SVNLog')

        # Create a matrix of committers with the dimensions we found out
        # previously.
        mat = array([[0] * committer_count] * committer_count)

        for row in cur:
            committer = row[2]
            revno = row[0]

            cur2 = self.dbcon.cursor()
            cur2.execute(
                'SELECT * FROM SVNLogDetail where revno=' + "%s" % revno)

            # Iterate over all files that were worked on in a single revision
            # (commit).
            for row2 in cur2:

                changedpathid = row2[1]

                # Iterate over the individual files (changedpathid's) to get the work contents
                # from them, namely lines-of-code (loc).

                # Note: We only take into account lines added (row3[6]) and not lines deleted
                # because we are interested in what committers 'do' and that is more evident from
                # the loc they add, and not so from the loc they delete. Furthermore, negative links
                # between developers are meaningless.
                cur3 = self.dbcon.cursor()
                cur3.execute(
                    'SELECT * FROM SVNLogDetail where changedpathid=' + "%s" % changedpathid)

                for row3 in cur3:

                    # As mentioned, we only consider the lines of code that
                    # have been added by a committer.
                    loc = row3[6]

                    # And create links to all previous committers who have revised this same
                    # file, ie. file co-authorship.
                    if (row3[0] <= row2[0]):

                        mat[c[committer]][c[r[row3[0]]]] = mat[
                            c[committer]][c[r[row3[0]]]] + loc

                    else:
                        continue

        cur.close
        cur2.close
        cur3.close

        # Then we prepare for writing the file co-authorship networks.
        output.write(
            "<network sourceType=\"Agent\" source=\"Agent\" targetType=\"Agent\" target=\"Agent\" id=\"AgentxAgent\">\n")

        # We iterate over the resulting matrix to write it out to the XML file.
        i = 0
        j = 0

        for i in c:
            for j in c:
                output.write("<link source=\"" + "%s" % i + "\" target=\"" + "%s" %
                             j + "\" value=\"" + "%i" % mat[c[i]][c[j]] + "\"/>\n")

        output.write("</network>\n")
        output.write("</networks>\n")
        output.write("</MetaNetwork>\n")
        output.write("</DynamicMetaNetwork>\n")

        self.closedb()


def RunMain():
    usage = "(File co-authorship version) usage: %prog <sqlitedbpath> <outputfile>"
    parser = OptionParser(usage)
    (options, args) = parser.parse_args()

    if(len(args) < 2):
        print("Invalid number of arguments. Use svnsqlite2ora_filecoauthorship.py --help to see the details.")
    else:
        sqlitedbpath = args[0]
        outputfilepath = args[1]

        try:
            print("Processing the sqlite subversion log")

            SVNSqlite2Ora(sqlitedbpath, outputfilepath)
        except:
            pass
            raise

if(__name__ == "__main__"):
    RunMain()
