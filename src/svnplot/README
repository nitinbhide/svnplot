
SVNPlot - Ver 0.7.1

============
Introduction
============
SVNPlot generates graphs similar to StatSVN. The difference is in how the graphs are generated. SVNPlot
generates these graphs in two steps. First it converts the Subversion logs into a 'sqlite3' database. Then
it uses sql queries to extract the data from the database and then uses excellent Matplotlib plotting
library to plot the graphs.

I believe using SQL queries to query the necessary data results in great flexibility in data extraction.
Also since the sqlite3 is quite fast, it is possible to generate these graphs on demand.

==========================
Installation prerequisites
==========================
You will need following additional libraries for using SVNPlot

   1. sqlite3 - is default installed with python
   2. http://pysvn.tigris.org/- Python SVN bindings.
   
   If you are going to use Javascript canvas based graphs (svnplot-js.py), 
   3. JqPlot (http://www.jqplot.com/) - Excellent Javascript canvas based plotting library. It is included 	
	  in the svnplot installation
   
   If you want to use Matplotlib based SVNPlot (svnplot.py) then you will need.
   3. http://numpy.scipy.org/- Matplotlib uses NumPy and SVNPlot uses Matplotlib for plotting.
   4. http://matplotlib.sourceforge.net/ - You need at least version 0.98.5.2 

	
============
Quick Start
============
1. First generate the sqlite database for your project.

    svnlog2sqlite.py <svnrepo url> <sqlitedbpath> 

    <svnrepo url> can be any repository format supported by Subverson. If you are using the local repositories on windows use the file:///d:/... format. <sqlitedbpath> is sqlite database file path. Its a path on your local machine 

	NOTE : For example, updating the SVN graphs for SVNPlot project use http://svnplot.googlecode.com/svn/. Using other urls like http://svnplot.googlecode.com/svn/trunk/ will result in error. (Upto version 0.5.4. This issue is fixed version 0.5.5, now svnrepo_url can be any url inside the repository)

    You can run this step multiple times. The new revisions added in the repository will get added to datatbase 
    
	Options : 
    * -l : Update the changed line count data also. By default line count data is NOT updated.     
    
    * -v : Verbose output
    * -g : enable logging of intermediate data and errors. Enable this option if you face any problems like line count not getting generated, no data in the generated sqlite database etc. 
	
2. Now generate the graphs.

    svnplot.py [options] <svnsqlitedbpath> <output directory> 
	OR
	svnplot-js.py [options] <svnsqlitedbpath> <output directory> 

    <graphdir> is local directory on your machine. All the graphs will placed in this directory. 

    Following addition options are useful 

    * -n '<reponame>' : This is name of repository (e.g. project name). It will use in generating the graph titles
    * -s '<searchpath>' :search path in the repository (e.g. /trunk) 
	* -p 'template file path' :  Default svnplot uses its own standard report format. However, you can change report format using -p option. 
	* -v : verbose output
	
	For svnplot-js.py,
	* -j or --copyjs : Copy the required excanvas,jquery and jqPlot javascript and css file to output directory
	
3. Generating Graph with your own report template
   You can use your own report template for the generated graphs. One example of report template is available in 'svnplot-long.tmpl'. This template directly embed the generated graphs images in the report and doesnot use thumbnails. It is useful to get a printed report.
   
   For example, 
   svnplot.py -v --dpi 70 -p svnplot-long.tmpl -n "MyRepo" <sqlitedb path> <output directory>
   or
   svnplot-js.py [options] <svnsqlitedbpath> <output directory> 
   
   TIP - Use 70 pixesl per inch resolution for better results with svnplot-long.tmpl template.

==============================================
Changes from 0.6.1 to 0.7.0
==============================================
1. Fixed XHTML template for svnplot-js.
2. LocChurn graph added for matplot lib based svnplot (svnplot.py)
3. Better start/end revision detection.
4. Command line parameters for specifying Username/password  for repository authentication.
5. Some basic support for exporting the stats in CSV format (svnstatscsv.py)
6. GSoC 2010/2009 changes by Oscar Castaneda merged into trunk. 
7. Two plots added for 'Activity by Time of day for last 3 months' and 'Activity by day of week for last 3 months'.
8. Bug fixes for correct display of javascript charts in IE 7 and IE8.
9. Improvements in the computation of author activity index. 
10. Improvements in the heat map colour computations for 'tag cloud'
11. Many small bug fixes.

==============================================
Changes from 0.5.x to 0.6.1
==============================================
1. Many bug fixes especially related to linecount and file count when folders are deleted or renamed.
2. Bug fixes related to binary files detection.
3. NEW FEATURE : Support to Javascript canvas based charts using JqPlot.
4. New chart type : Daily commits count

==============================================
IMPORTANT NOTE for migrating from 0.5.x to 0.6
==============================================
SVNPlot ver 0.6 sqlite database schema is different than 0.5.x schema. Hence for migrating from 0.5.x to 0.6 you will need to regenerate the sqlite database.

==============================================
Changes from 0.6.x to 0.7.x
==============================================
1. Many minor bug fixes for charts and activity index computations for Authors.
2. Added the facility to define username and password for the repository on command line.
3. Added svnstatscsv.py to export the basic statistics data to csv format.
4. Merged the changes to export the network data from svn to Gephi. (Contributed by Oscar Castaneda
   from GSoC 2010).
5. Fixes Issue 44. In cases svnlog2sqlite.py aborted with 'unknown node kind error'.
6. Fixes the duplicate filenames with extra '/' characters in filenames (e.g. trunk/xyz.txt and trunk//xyz.txt)
7. Fixes issue 47 : wrong line count.
8. Fixes issue 48 and 49.
9. improved root url detection
10. Bug fixes for linecount computation errors 
11. Bug fixes for unknown_node_kind error fixes.
12. Fixes a bug where rare case svnlog2sqlite.py got an 'Inconsistent line ending style' and stopped.
13. Fixes a bug in svnplot where svnplot crashed in end with error 'super' object has no attribute '__del__' 

============
License
============
SVNPlot is released under New BSD License http://www.opensource.org/licenses/bsd-license.php

