'''
svnsqlite2gexf.py
Copyright (C) 2010 Oscar Castaneda (oscar.castaneda@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

python script to process a Subversion log collected by svnlog2sqlite.py, which is stored in a 
sqlite database. The idea is to use the SQLite database generated by SVNPlot to create the XML 
input file for the open source Gephi, an interactive visualization and exploration platform for 
all kinds of networks and complex systems, dynamic and hierarchical graphs. Using Gephi several 
SNA graphs and analyses may be conducted and, since Gephi is open source, possibly extended.

Note: This is version of svnsqlite2gexf.py was inspired by Apache Agora. It considers commits 
as part of conversations (like email conversations in Apache Agora). Upon committing code, a 
committer creates a revision in SVN which in turn creates a link to all committers who have 
co-authored the corresponding files from that revision. The idea is the same as in Agora, namely 
to create links based on reply actions, but differs in that there is no one originator but instead 
links are created to all co-authors who are active in the sqlite db contents.

This version of svnsqlite2gexf.py has been tested with SVNPlot version 0.6.1 .
'''

import string
import sqlite3

from optparse import OptionParser
from numpy import *
from numpy import matrix


class SVNSqlite2Gephi:
	def __init__(self, sqlitedbpath, outputfilepath):
		self.dbpath = sqlitedbpath
		self.dbcon = None
		self.outputfile = outputfilepath
		self.Process()  

	def initdb(self):
		self.dbcon = sqlite3.connect(self.dbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
	
	def closedb(self):
		self.dbcon.close()

	def __processNodes(self, output):
		# We create a cursor for SVNLog and do a SELECT on all records (*), so cur = SVNLog
		cur = self.dbcon.cursor()
		# We go through all the committers and their revisions, then we create lists of both.
		cur.execute('SELECT * FROM SVNLog')
		
		# Write XML specification for Gephi network, then start writing <nodes> section of the XML file consisting of nodes
		output.write("\t\t<nodes>\n")
		
		for row in cur:     		
			committer = row[2]
			if( committer== '' or committer == None):
				committer = 'Unknown'
			revno = row[0]
	
			# If committer has not been counted then add him/her to the list, and increment committer_count
			# then write <node id> in XML file.
			if (committer not in self.committers):
				committer_id = len(self.committers)
				self.committers.add(committer)
				self.c[committer] = committer_id
				output.write('\t\t\t<node id="%d" label="%s"/>\n' %(committer_id,committer))
			
			# If a revision has not been counted then add it to the list, increment revision_count and 
			# associate revision to committer.
			if (revno not in self.revisions):
				self.revisions.add(revno) 
				self.r[revno] = committer
				
		# Finish the <nodes> section, and start the <edges> section
		# of the Gephi XML file.
		output.write("\t\t</nodes>\n")
						
		cur.close()
		
	def __processEdges(self, output):
		committer_count = len(self.committers)
				
		# Create a matrix of committers with the dimensions we found out previously.
		mat = array([[0]*committer_count]*committer_count)
	
		############################################################################
		# Write sociomatrix from                                                   #
		# Agent x Resource(changedpathid) and Resource(changedpathid) x Agent      #
		############################################################################
		cur = self.dbcon.cursor()
		cur.execute('SELECT * FROM SVNLog')
				
		for row in cur:         
			committer = row[2]
			if( committer == '' or committer == None):
				committer = 'Unknown'
			revno = row[0]
	
			cur2 = self.dbcon.cursor()
			cur2.execute('SELECT * FROM SVNLogDetail where revno=?',(revno,))
	
			committer_id = self.c[committer]
			# Iterate over all files that were worked on in a single revision (commit).
			for row2 in cur2:
				
				changedpathid = row2[1]         
				
				# Iterate over the individual files (changedpathid's) to get the work contents 
				# from them, namely lines-of-code (loc).
				
				# Note: We only take into account lines added (row3[6]) and not lines deleted
				# because we are interested in what committers 'do' and that is more evident from
				# the loc they add, and not so from the loc they delete. Furthermore, negative links
				# between developers are meaningless. 
				cur3 = self.dbcon.cursor()
				cur3.execute('SELECT * FROM SVNLogDetail where changedpathid=?',(changedpathid,))
				
				for row3 in cur3:
					
					# As mentioned, we only consider the lines of code that have been added by a committer.     
					loc = max(row3[6],1)
					assert(loc > 0)
					# And create links to all previous committers who have revised this same
					# file, ie. file co-authorship.
					if (row3[0] <= row2[0]):
						coauthor = self.r[row3[0]]
						coauthor_id = self.c[coauthor]
						mat[committer_id][coauthor_id] = mat[committer_id][coauthor_id] + loc
	
		cur.close
		cur2.close
		cur3.close
	
		output.write("\t\t<edges>\n")		
		# We iterate over the resulting matrix to write it out to the XML file.
		edge_id = 0
		for auth1, auth1_id in self.c.iteritems():
			for auth2, auth2_id in self.c.iteritems():
				wt = mat[auth1_id][auth2_id]
				if( wt > 0):
					output.write('\t\t\t<edge id="%d" source="%d" target="%d" weight="%d"/>\n'
								 % (edge_id, auth1_id, auth2_id,wt))
					edge_id = edge_id+1
					
					
		output.write("\t\t</edges>\n")
		
	def Process(self):
		with open(self.outputfile, 'w') as output:
			self.initdb()   
			print "Processing..."
			
			self.revisions = set()
			self.r = {}
			
			self.committers = set()
			self.c = {}
		
			# Write XML prelude to CMU node specification
				#output.write("<?xml version=\"1.0\" standalone=\"yes\"?>\n")
				#output.write("<DynamicMetaNetwork id=\"Meta Network\">\n")
		
			# Write XML prelude to Gephi node specification
			output.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
			output.write("  <gexf xmlns=\"http://www.gexf.net/1.1draft\"\n")
			output.write("  xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n")
			output.write("  xsi:schemaLocation=\"http://www.gexf.net/1.1draft http://www.gexf.net/1.1draft/gexf.xsd\"\n")
			output.write("  version=\"1.1\">\n")
			output.write("  <graph defaultedgetype=\"directed\">\n")
		
			self.__processNodes(output)
			self.__processEdges(output)
			
			output.write("\t</graph>\n")
			output.write("</gexf>\n")
		
			self.closedb()

def RunMain():
	usage = "(File co-authorship version) usage: %prog <sqlitedbpath> <outputfile>"
	parser = OptionParser(usage)
	(options, args) = parser.parse_args()
	
	if( len(args) < 2):
		print "Invalid number of arguments. Use svnsqlite2ora_filecoauthorship.py --help to see the details."
	else:
		sqlitedbpath = args[0]
		outputfilepath = args[1]

		try:
			print "Processing the sqlite subversion log"
			
			SVNSqlite2Gephi(sqlitedbpath, outputfilepath)
		except:
			pass
			raise
		
if( __name__ == "__main__"):
	RunMain()
