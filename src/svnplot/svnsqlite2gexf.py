'''
svnsqlite2ora.py
Copyright (C) 2009 Oscar Castaneda (oscar.castaneda@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

python script to process the Subversion log collected by SVNPlot and stored on a sqlite database.
The idea is to use the generated SQLite database as input to CMU's Organizational Risk Analyzer (*ORA) for
creating various social network graphs and analyses based on SVN logs, like those related to the evolution 
of networks.
'''

import sqlite3
import datetime
from datetime import date
import calendar
import string
from datetime import datetime
from optparse import OptionParser
from numpy import *
from numpy import matrix
from numpy import linalg
import scipy

class SVNSqlite2Ora:
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

	# Write prelude to node specification

	#output.write("<?xml version=\"1.0\" standalone=\"yes\"?>\n")
	#output.write("<DynamicMetaNetwork id=\"Meta Network\">\n")
	
	
    output.write("<?xml version=”1.0” encoding=”UTF−8”?>")
    output.write("<gexf xmlns=”http://www.gexf.net/1.1draft”")
	output.write("xmlns:xsi=”http://www.w3.org/2001/XMLSchema−instance”")
	output.write("xsi:schemaLocation=”http://www.gexf.net/1.1draft")
	output.write("http://www.gexf.net/1.1draft/gexf.xsd”")
	output.write("version=”1.1”>")
	
	output.write("<graph defaultedgetype=”directed”>")
	
	# Get last commitdate from last row in DB

	cur = self.dbcon.cursor()
        cur.execute('select * from SVNLog order by commitdate desc limit 1;')
	for lastrow in cur:
	
		date_header = datetime.strptime("%s" % lastrow[1], "%Y-%m-%d %H:%M:%S")
	
	if (date_header.month > 9):
		if (date_header.day > 9):
			date_string = "%i" % date_header.year + "%i" %date_header.month + "01"
		else:
			date_string = "%i" % date_header.year + "%i" %date_header.month + "01"
	else:	
		date_string = "%i" % date_header.year + "0%i" %date_header.month + "01"

	#output.write("<MetaNetwork id=\"Meta Network_" + "%s" %date_string + "\" date=\"" + "%s" %date_string + "T00:00:00\">\n")

	output.write("<nodes>\n")
	
	#OC 3Mar2010: Uncommented below
	#output.write("<nodeclass type=\"Resource\" id=\"Resource\">\n")

	cur.execute('SELECT * FROM SVNLog;')
	
	files = []
	file_count = 0
	f = {}

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
                                                if (files.count(backlink) == 0):
                                                        files.append(backlink)
							f[backlink] = file_count + 1
                                                        f[msgID] = file_count + 1
							#OC 3Mar2010: Uncommented below.
                                                        #output.write("<node id=\"" + "%s" %backlink + "\"/>\n")
                                            		file_count = file_count + 1
						else:
                                                        f[msgID] = file_count + 1
			
	file_count = file_count + 1
	cur3.close
	cur2.close
	cur.close	

        #output.write("</nodeclass>\n")
        #output.write("<nodeclass type=\"Agent\" id=\"Agent\">\n")

	cur = self.dbcon.cursor()
        cur.execute('SELECT * FROM SVNLog;')

	users = []
	committers = []
	user_count = 0
	u = {}

	for row in cur:
                date = "%s" % datetime.strptime("%s" % row[1], "%Y-%m-%d %H:%M:%S").isoformat()

                address = row[2]
		
		if(committers.count(address) == 0):
			committers.append(address)
			output.write("<node id=\"" + "%i\"" %user_count + "label=\"" + "%s\"" %address "/>\n") 
	
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
						if (users.count(address) == 0):
                                                        users.append(address)
							# Users dictionary

							u[address] = user_count + 1 
							#print u
							#print u[address]
                                                        #OC 3Mar2010: Uncommented below
							#output.write("<node id=\"" + "%s" %address + "\"/>\n")
							user_count = user_count + 1
						else:
							if(users.count(address) == 0):
								u[address] = user_count + 1
	
	user_count = user_count + 1

	cur3.close
	cur2.close
	cur.close

	#output.write("</nodeclass>\n")
	
	output.write("</nodes>\n")
	output.write("<edges>\n")
	
	# OC 3Mar2010: Uncommented below
	#output.write("<network sourceType=\"Agent\" source=\"Agent\" targetType=\"Resource\" target=\"Resource\" id=\"f1\">\n")

	# Write the networks: Agent x Resource(link)
	
	cur = self.dbcon.cursor()
        cur.execute('SELECT * FROM SVNLog;')
	
	mat = array([[0]*file_count]*user_count)
	loc_global = 0

	
	for row in cur:
                date = "%s" % datetime.strptime("%s" % row[1], "%Y-%m-%d %H:%M:%S").isoformat()
                                        
                address = row[2]        
                cur2 = self.dbcon.cursor()      
                cur2.execute('SELECT * FROM SVNLogDetail where revno=' + "%s" %row[0] +';')
                for row2 in cur2:
                        msgID = "%s" %row2[1] + "@" + "%s" %row2[0]
			#OC 3Mar2010: Added for LoC count
			loc_global = loc_global + row2[3] - row2[4]
                        cur3 = self.dbcon.cursor()
                        cur3.execute('SELECT * FROM SVNLogDetail where changedpath="' + "%s" %row2[1] + '";')
                        for row3 in cur3:
                                if (row3[2] == "M"):
                                        if (row3[0] < row2[0]):
						backlink = "%s" %row3[1] + "@" + "%s" %row3[0]
                                                #print "Count: %s" %mat.count(address,backlink)
						
						mat[u[address]][f[msgID]] = mat[u[address]][f[msgID]] + row3[3]

					else:
                                                continue
	
	cur3.close
	cur2.close
	cur.close

	#pdb.set_trace()
	#OC 3Mar2010: Uncommented below
	#output.write("</network>")
	#output.write("<network sourceType=\"Resource\" source=\"Resource\" targetType=\"Agent\" target=\"Agent\" id=\"f2\">\n")

	# Write the networks: Resource(backlink) x Agent

	cur = self.dbcon.cursor()
        cur.execute('SELECT * FROM SVNLog;')

	mat2 = array([[0]*user_count]*file_count)

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

						mat2[f[backlink]][u[address]] = mat2[f[backlink]][u[address]] + row3[3]

					else:
                                        	continue
		print mat2
	
	cur3.close
	cur2.close
	cur.close

        #output.write("<network sourceType=\"Agent\" source=\"Agent\" targetType=\"Agent\" target=\"Agent\" id=\"AgentxAgent_" + "%s" %date_string + "\">\n")

        output.write("<edge id=\"" + )

	mat12 = dot(mat,mat2)
	i = 0
	j = 0
	loc = 0
	loc_total = 0

	for i in u:
                for j in u:
			if (i <> j):
				loc = sqrt(mat12[u[i]][u[j]]) 
				loc_total = loc_total + loc
				output.write("<link source=\""+ "%s" % i + "\" target=\"" + "%s" % j + "\" value=\"" + "%i" % loc + "\"/>\n")
	

	output.write("</network>\n")
	output.write("</networks>\n")
   	output.write("</MetaNetwork>\n")
	output.write("</DynamicMetaNetwork>\n")

	#output.write("<!-- LoC SoCNET: " + "%f" % loc_total + " LoC Total: " + "%f" % loc_global + "-->\n")

        output.write("<!-- LoC SoCNET: " + "%f" % loc_total + " LoC Total: " + "%f" % loc_global + " File Count: " + "%i" % file_count + " User Count: " + "%i" % user_count + " -->\n")



	self.closedb()

def RunMain():
    usage = "usage: %prog <sqlitedbpath> <outputfile>"
    parser = OptionParser(usage)
    (options, args) = parser.parse_args()
    
    if( len(args) < 2):
        print "Invalid number of arguments. Use svnsqlite2ora.py --help to see the details."
    else:
        sqlitedbpath = args[0]
	outputfilepath = args[1]

        try:
            print "Processing the sqlite subversion log"
            
            SVNSqlite2Ora(sqlitedbpath, outputfilepath)
        except:
            pass
            raise
        
if( __name__ == "__main__"):
    RunMain()
