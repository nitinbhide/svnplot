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
import StringIO

import svnstats
import heatmapclr

MINFONTSIZE=-2
MAXFONTSIZE=8

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



class SVNPlotBase:
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
        outstr = StringIO.StringIO()
        outstr.write("<ol>\n")
        for filepath, temperatur in hotfiles:
            outstr.write("<li>%s</li>\n"%filepath)
        outstr.write("</ol>\n")
        return(outstr.getvalue())

    def ActiveAuthors(self):
        '''
        TODO - template for generating the hot files list. Currently format is hard coded as
        HTML ordered list
        '''
        self._printProgress("Calculating Active authors list")
        hotfiles = self.svnstats.getActiveAuthors(10)
        outstr = StringIO.StringIO()
        outstr.write("<ol>\n")
        for author, temperatur in hotfiles:
            outstr.write("<li>%s</li>\n"%author)
        outstr.write("</ol>\n")
        return(outstr.getvalue())
    
    def AuthorCloud(self, maxAuthCount=50):
        self._printProgress("Calculating Author Tag Cloud")
        authCloud = self.svnstats.getAuthorCloud()
        tagHtmlStr = ''
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
 
            #now calculate the maximum value from the sorted list.
            minFreq = min(authTagList, key=operator.itemgetter(1))[1]
            minFreqLog = math.log(minFreq)
            maxFreq = max(authTagList, key=operator.itemgetter(1))[1]
            #if there is only one author or minFreq and maxFreq is same, then it will give wrong
            #results later. So make sure there is some difference between min and max freq.
            maxFreq = max(minFreq*1.2, maxFreq)
            maxFreqLog = math.log(maxFreq)
                
            minActivity = min(authTagList, key=operator.itemgetter(2))[2]
            maxActivity = max(authTagList, key=operator.itemgetter(2))[2]
            maxActivity = max(minActivity*1.2, maxActivity)
            minActivityLog = math.log(minActivity)
            maxActivityLog = math.log(maxActivity)
                        
            normlizer = lambda actIdx : (math.log(actIdx)-minActivityLog)/(maxActivityLog-minActivityLog)

            #Now sort the authers by author names
            authTagList = sorted(authTagList, key=operator.itemgetter(0))
            #change the font size between "-2" to "+8" relative to current font size
            tagHtmlStr = ' '.join([('<font size="%+d" color="%s">%s</font>\n'%
                                    (getTagFontSize(freq, minFreqLog, maxFreqLog), getActivityClr(normlizer, actIdx), auth))
                                       for auth, freq, actIdx in authTagList])
        return(tagHtmlStr)             

    def TagCloud(self, numWords=50):
        self._printProgress("Calculating tag cloud for log messages")
        words = self.svnstats.getLogMsgWordFreq(5)
        tagHtmlStr = ''
        if( len(words) > 0):
            #first get sorted wordlist (reverse sorted by frequency)
            tagWordList = sorted(words.items(), key=operator.itemgetter(1),reverse=True)
            #now extract top 'numWords' from the list and then sort it with alphabetical order.
            tagWordList = sorted(tagWordList[0:numWords], key=operator.itemgetter(0))        
            #now calculate the maximum value from the sorted list.
            minFreq = min(tagWordList, key=operator.itemgetter(1))[1]
            minFreqLog = math.log(minFreq)
            maxFreq = max(tagWordList, key=operator.itemgetter(1))[1]
            maxFreqLog = math.log(maxFreq)
            #change the font size between "-2" to "+8" relative to current font size
            tagHtmlStr = ' '.join([('<font size="%+d">%s</font>\n'%(getTagFontSize(freq, minFreqLog, maxFreqLog), x))
                                       for x,freq in tagWordList])                
        return(tagHtmlStr)
