'''
svnlog2sqlite.py
Copyright (C) 2009 Oscar Castaneda (oscar.castaneda@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

python script to process the Subversion log collected by SVNPlot and stored on a sqlite database.
The idea is to use the generated SQLite database as input to Apache Agora for
creating various graphs and analyses based on SVN logs.
'''

import sqlite3
import datetime
import calendar
from datetime import datetime
from optparse import OptionParser


class SVNSqlite2Agora:
    def __init__(self, sqlitedbpath, outputfilepath):
        self.dbpath = sqlitedbpath
        self.dbcon = None
	self.outputfile = outputfilepath
	self.Process()	

    def initdb(self):
        self.dbcon = sqlite3.connect(self.dbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
	
    def closedb(self):
        self.dbcon.commit()
        self.dbcon.close()

    def Process(self):
	output = open(self.outputfile, 'w')
	self.initdb()	
	print "Processing..."

	cur = self.dbcon.cursor()
	cur.execute('SELECT * FROM SVNLog;')	

	for row in cur:
		date = "%s" % datetime.strptime("%s" % row[1], "%Y-%m-%d %H:%M:%S").isoformat()

		address = row[2]
		cur2 = self.dbcon.cursor()
		cur2.execute('SELECT * FROM SVNLogDetail where revno=' + "%s" %row[0] +';')
		for row2 in cur2:
			msgID = "%s" %row2[1] + "@" + "%s" %row2[0]
			cur3 = self.dbcon.cursor()
			cur3.execute('SELECT * FROM SVNLogDetail where changedpath="' + "%s" %row2[1] + '";')
			for row3 in cur3:
				if (row3[2] == "M"):
					if (row3[0] < row2[0]):
						backlink = "%s" %row3[1] + "@" + "%s" %row3[0] 
						print "Backlink: %s" %backlink
						output.write("%s" %msgID + "," + "%s" %date + "," + "%s" %address + "," + "%s" %backlink + "\n")
				
			cur3.close			
		cur2.close()
	cur.close()		
	self.closedb()

def RunMain():
    usage = "usage: %prog <sqlitedbpath> <outputfile>"
    parser = OptionParser(usage)
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments. Use svnsqlite2agora.py --help to see the details."
    else:
        sqlitedbpath = args[0]
	outputfilepath = args[1]

        try:
            print "Processing the sqlite subversion log"
            
            SVNSqlite2Agora(sqlitedbpath, outputfilepath)
        except:
            pass
            raise
        
if( __name__ == "__main__"):
    RunMain()

