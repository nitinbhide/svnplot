
SVNPlot - Ver 0.6

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
   4. http://matplotlib.sourforge.net/ - You need at least version 0.98.5.2 

	
============
Quick Start
============
1. First generate the sqlite database for your project.

    svnlog2sqlite.py <svnrepo url> <sqlitedbpath> 

    <svnrepo url> can be any repository format supported by Subverson. If you are using the local repositories on windows use the file:///d:/... format. <sqlitedbpath> is sqlite database file path. Its a path on your local machine 

    You can run this step multiple times. The new revisions added in the repository will get added to datatbase 
    
	Options : 
    * -l : Update the changed line count data also. By default line count data is NOT updated.     
    NOTE : for version 0.5.5 -l option works only if svnrepo_url is 'repository root'. It doesn't work if the URL is inside the repository. This a bug. It will be fixed in the next version. 

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
	
3. Generating Graph with your own report template
   You can use your own report template for the generated graphs. One example of report template is available in 'svnplot-long.tmpl'. This template directly embed the generated graphs images in the report and doesnot use thumbnails. It is useful to get a printed report.
   
   For example, 
   svnplot.py -v --dpi 70 -p svnplot-long.tmpl -n "MyRepo" <sqlitedb path> <output directory>
   or
   svnplot-js.py [options] <svnsqlitedbpath> <output directory> 
   
   TIP - Use 70 pixesl per inch resolution for better results with svnplot-long.tmpl template.

==============================================
Changes from 0.5.x to 0.6
==============================================
1. Many bug fixes especially related to linecount and file count when folders are deleted or renamed.
2. Support to Javascript canvas based charts using JqPlot.
3. 

==============================================
IMPORTANT NOTE for migrating from 0.5.x to 0.6
==============================================
SVNPlot ver 0.6 sqlite database schema is different than 0.5.x schema. Hence for migrating from 0.5.x to 0.6 you will need to regenerate the sqlite database.

============
License
============
SVNPlot is released under New BSD License http://www.opensource.org/licenses/bsd-license.php

