#!/usr/bin/env python
'''
setup.py
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
Setup file for installing svnplot
'''
import sys
import distribute_setup

distribute_setup.use_setuptools()

from setuptools import setup, find_packages

setup(name='SVNPlot', version ='0.7.7',      
      description='python module to generate graphs and statistics from Subversion repository data',
      author='Nitin Bhide',
      author_email='nitinbhide@gmail.com',
      license = 'http://www.opensource.org/licenses/bsd-license.php',
      url='http://code.google.com/p/svnplot',
      install_requires=['pysvn','numpy', 'matplotlib'],
      dependency_links = [
        "http://pysvn.tigris.org/servlets/ProjectDocumentList?folderID=1768"
        ],
      #packages=find_packages('src'),
      package_dir = {'svnplot': 'svnplot'},
      package_data= {'svnplot':['readme.txt', 'README', 'javascript/*.js', 'javascript/jqplot/*.*',
                     'javascript/jqplot/plugins/*.js']},
      exclude_package_data= { '': ['.svn/*']},
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Version Control"
        ],
      zip_safe=False,
     )


