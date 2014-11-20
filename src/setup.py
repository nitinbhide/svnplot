'''
setup.py
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
Setup file for installing svnplot
'''

from distutils.core import setup

setup(name='SVNPlot', version ='0.8.4',
      description='python module to generate graphs and statistics from Subversion repository data',
      author='Nitin Bhide',
      author_email='nitinbhide@gmail.com',
      license = 'http://www.opensource.org/licenses/bsd-license.php',
      url='http://code.google.com/p/svnplot',
      requires = ['matplotlib', 'numpy', 'pysvn'],
      packages=['svnplot'],
      package_dir = {'svnplot': 'svnplot'},
      package_data= {'svnplot':['readme.txt', 'README', 'javascript/*.js', 'javascript/jqplot/*.*',
                     'javascript/jqplot/plugins/*.js', 'javascript/d3.v3/*.*']},
      scripts = ['svnlog2sqlite.py', 'svngraphs.py', 'svnplotjs.py'],
      
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Version Control"
        ],
      
     )

