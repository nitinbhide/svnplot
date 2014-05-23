#!/usr/bin/env python
'''
configoptparse.py
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------

ConfigOptParse is class which combines the functionality of ConfigParser and OptParse
modules
'''

from optparse import OptionParser
from ConfigParser import ConfigParser

class ConfigOptionParser(OptionParser):
    '''
    ConfigOptionParser combines the functionality of ConfigParser and OptParser modules.
    It allows to read the options from configuation file and then combine or override those
    parameters values with values defined on the command line
    config file name is specified by --config parameter
    It assumes that the parameters are to be read from the section    
    '''
    def __init__(self, *args, **kwargs):
        OptionParser.__init__(self, *args, **kwargs)
        #add the
        self.section = 'config'
        self.add_option("", "--config", dest="configfile", default=None, action="store", type="string",
                      help="full path of the configuration file to read the parameters from.")
                      
    def parse_args(self, args=None, values=None):
        '''
        parse the command line arguments and config file arguments
        '''
        #first parse the command line arguments to read the 'configfile name' (if specified)
        options, args = OptionParser.parse_args(self, args, values)
        if options.configfile:
            #config file is specified now. Read the config file and set the parameters
            #as defaults
            config = ConfigParser()
            config.read(options.configfile)
            options = config.items(self.section)
            self.set_defaults(**options)
            options, args = OptionParser.parse_args(self, args, values)
            
        return options, args
            
    

