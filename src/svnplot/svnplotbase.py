'''
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
SVNPlotBase implementation. Common base class various ploting functions. Stores common settings as well
'''

__revision__ = '$Revision:$'
__date__     = '$Date:$'

import os.path, sys
import math
import string
import operator
import logging
from StringIO import StringIO

import svnstats
import heatmapclr

MINFONTSIZE=10
MAXFONTSIZE=30

def getTagFontSize(freq, minFreqLog, maxFreqLog):
    #change the font size between "-2" to "+8" relative to current font size
    #change minFreqLog in such a way smallest log(freq)-minFreqLog is greater than 0
    fontsizevariation = (MAXFONTSIZE-MINFONTSIZE)
    minFreqLog = minFreqLog-(maxFreqLog-minFreqLog)/fontsizevariation
    #now calculate the scaling factor for scaling the freq to fontsize.
    if maxFreqLog == minFreqLog:
        scalingFactor = 1
    else:
        scalingFactor = fontsizevariation/(maxFreqLog-minFreqLog)

    fontsize = int(MINFONTSIZE+((math.log(freq)-minFreqLog)*scalingFactor)+0.5)
    #now round off to ensure that font size remains in MINFONTSIZE and MAXFONTSIZE
    assert(fontsize >= MINFONTSIZE and fontsize <= MAXFONTSIZE)
    return(fontsize)


def getActivityClr(normlizer, actIdx):
    heatindex = normlizer(actIdx)
    clrstr = heatmapclr.getHeatColorHex(heatindex)
    return(clrstr)


def normalize_activityidx(actIdx, minActivity, maxActivity):
    assert(maxActivity > minActivity)
    normactidx = 0.0
    if( actIdx-minActivity > 1.0):
        #log of actIdx-minactivity has to be +ve for subsequent computations to work.
        normactidx=math.log(actIdx-minActivity)/math.log(maxActivity-minActivity)
    assert(normactidx >=0.0)
    return(normactidx)
    
class SVNPlotBase(object):
    def __init__(self, svnstats, dpi=100,format='png'):
        self.svnstats = svnstats
        self.reponame = ""        
        self.dpi = dpi
        self.format = format
        self.verbose = False
        self.clrlist = ['b', 'g', 'r', 'c', 'm', 'y', 'k']
            
    def SetVerbose(self, verbose):       
        self.verbose = verbose
        self.svnstats.SetVerbose(verbose)

    def SetRepoName(self, reponame):
        self.reponame = reponame
        
    def _printProgress(self, msg):
        if( self.verbose == True):
            print msg

    def _getAuthorLabel(self, author):
        '''
        sometimes are author names are email ids. Hence labels have higher width. So split the
        author names on '@' symbol        
        '''
        auth = author.replace('@', '@\n')
        return(auth)
    
    def BasicStats(self, basicStatsTmpl):
        '''
        get the html string for basic repository statistics (like last revision, etc)
        '''
        self._printProgress("Calculating Basic stats")
        basestats = self.svnstats.getBasicStats()
        #replace dates with proper formated date strings
        basestats['FirstRevDate']= basestats['FirstRevDate'].strftime('%b %d, %Y %I:%M %p')
        basestats['LastRevDate']= basestats['LastRevDate'].strftime('%b %d, %Y %I:%M %p')
        statsTmpl = string.Template(basicStatsTmpl)
        statsStr = statsTmpl.safe_substitute(basestats)
        
        return(statsStr)

    def ActiveFiles(self):
        '''
        TODO - template for generating the hot files list. Currently format is hard coded as
        HTML ordered list
        '''
        self._printProgress("Calculating Active (hot) files list")
        hotfiles = self.svnstats.getHotFiles(10)
        outstr = StringIO()
        outstr.write("<ol>\n")
        for filepath, temperatur, revcount in hotfiles:
            outstr.write("<li>%s (rev count: %d)</li>\n"% (self.svnstats.getSearchPathRelName(filepath),revcount))
        outstr.write("</ol>\n")
        return(outstr.getvalue())

    def ActiveAuthors(self):
        '''
        TODO - template for generating the hot files list. Currently format is hard coded as
        HTML ordered list
        '''
        self._printProgress("Calculating Active authors list")
        hotauthors = self.svnstats.getActiveAuthors(10)
        outstr = StringIO()
        outstr.write("<ol>\n")
        for author, temperatur in hotauthors:
            outstr.write("<li>%s</li>\n"%author)
        outstr.write("</ol>\n")
        return(outstr.getvalue())
    
    def AuthorCloud(self, maxAuthCount=50):
        self._printProgress("Calculating Author Tag Cloud")
        authCloud = self.svnstats.getAuthorCloud()
        tagData = []
        if( len(authCloud) > 0):
            #sort and extract maximum of the "maxAuthCount" number of author based on the
            #activity index
            authTagList = sorted(authCloud, key=operator.itemgetter(2),reverse=True)
            authTagList = authTagList[0:maxAuthCount]
            #remove elements being zeror or less
            for x in authTagList[:]:
                #if less than or equal zero remove, otherwise clrNorm fails 
                if (x[2] <= 0):
                    authTagList.remove(x)
             
            #Now sort the authers by author names
            authTagList = sorted(authTagList, key=operator.itemgetter(0))
            
            #Create a list of list for javascript input
            tagsData = [{'text':str(auth), 'count':freq, 'color': actIdx} for auth, freq, actIdx in authTagList]
            
        return(tagsData)             

    def TagCloud(self, numWords=50):
        self._printProgress("Calculating tag cloud for log messages")
        words = self.svnstats.getLogMsgWordFreq(5)
        tagData = []
        if( len(words) > 0):
            #first get sorted wordlist (reverse sorted by frequency)
            tagWordList = sorted(words.items(), key=operator.itemgetter(1),reverse=True)
            #now extract top 'numWords' from the list and then sort it with alphabetical order.
            tagWordList = sorted(tagWordList[0:numWords], key=operator.itemgetter(0))        
            
            #Create a list of list for javascript input
            tagData = [{ 'text':str(x), 'count':freq} for x, freq in tagWordList]
             
        return(tagData)
