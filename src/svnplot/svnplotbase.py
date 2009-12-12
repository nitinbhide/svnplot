'''
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
SVNPlotBase implementation. Common base class various ploting functions. Stores common settings as well
'''

__revision__ = '$Revision:$'
__date__     = '$Date:$'

import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
from matplotlib.ticker import FixedLocator, FormatStrFormatter
from matplotlib.font_manager import FontProperties
import os.path, sys
import string
import operator
import logging
import svnstats
    
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
    
    def _getLegendFont(self):
        legendfont = FontProperties(size='x-small')
        return(legendfont)
    
    def _addFigureLegend(self, ax, labels, loc="lower center", ncol=4):
        fig = ax.figure
        legendfont = self._getLegendFont()
        assert(len(labels) > 0)
        lnhandles =ax.get_lines()
        assert(len(lnhandles) > 0)
        #Fix for a bug in matplotlib 0.98.5.2. If the len(labels) < ncol,
        # then i get an error "range() step argument must not be zero" on line 542 in legend.py
        if( len(labels) < ncol):
           ncol = len(labels)
        fig.legend(lnhandles, labels, loc=loc, ncol=ncol, prop=legendfont)
                    
    def _drawBarGraph(self, data, labels, barwid, **kwargs):
        #create dummy locations based on the number of items in data values
        xlocations = [x*2*barwid+barwid for x in range(len(data))]
        xtickloc = [x+barwid/2.0 for x in xlocations]
        xtickloc.append(xtickloc[-1]+barwid)
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.bar(xlocations, data, width=barwid, **kwargs)
        ax.set_xticks(xtickloc)
        ax.set_xticklabels(labels)
        
        return(ax)

    def _drawHBarGraph(self, datalist, labels, barwid):
        assert(len(datalist) > 0)
        numDataItems = len(datalist)
        #create dummy locations based on the number of items in data values
        ymin = 0.0        
        ylocations = [y*barwid*2+barwid/2 for y in range(numDataItems)]
        ymax = ylocations[-1]+2.0*barwid
        ytickloc = [y+barwid/2.0 for y in ylocations]
        ytickloc.append(ytickloc[-1]+barwid)
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.set_color_cycle(self.clrlist)
        ax.set_yticks(ytickloc)
        ax.set_yticklabels(labels)
        
        clridx = 0
        maxclridx = len(self.clrlist)
        ax.barh(ylocations, datalist, height=barwid, color=self.clrlist[clridx])
        ax.set_ybound(ymin, ymax)
        return(ax)
    
    def _drawStackedHBarGraph(self, dataList, labels, legendlist, barwid):
        assert(len(dataList) > 0)
        numDataItems = len(dataList[0])
        #create dummy locations based on the number of items in data values
        ymin = 0.0
        ylocations = [y*barwid*2+barwid/2 for y in range(numDataItems)]
        #leave some extra position at the top for placing the legend 
        ymax = ylocations[-1]+4.0*barwid
        ytickloc = [y+barwid/2.0 for y in ylocations]
        ytickloc.append(ytickloc[-1]+barwid)
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.set_color_cycle(self.clrlist)
        ax.set_yticks(ytickloc)
        ax.set_yticklabels(labels)
        
        clridx = 0
        maxclridx = len(self.clrlist)
        ax.barh(ylocations, dataList[0], height=barwid, color=self.clrlist[clridx], label=legendlist[0])
        leftlist = [0 for x in range(0, numDataItems)]
        
        for i in range(1, len(dataList)):
            clridx=clridx+1
            if( clridx >= maxclridx):
                clridx = 0
            leftlist = [x+y for x,y in zip(leftlist, dataList[i-1])]
            ax.barh(ylocations, dataList[i], left=leftlist, height=barwid,
                    color=self.clrlist[clridx], label=legendlist[i])
            
        ax.legend(loc='upper center',ncol=3,)     
        ax.set_ybound(ymin, ymax)
        
        return(ax)

    def _drawHistogram(self, values, numbins=10,logbins=False):
        bins=numbins
        
        if( logbins==True):
            #create list of bins on a log scale
            minbinval = min(values)
            logminbinval = math.log(max(minbinval, 0.0001))
            fnumbins = float(numbins)
            logbinstep = (math.log(5)-logminbinval)/fnumbins
            bins = [math.exp(logminbinval+val*logbinstep) for val in range(0, numbins)]
            
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.hist(values, bins=bins,histtype='bar',rwidth=0.8)
        ax.grid(True)
        return(ax)
    
    def _drawScatterPlot(self,dates, values, plotidx, plotcount, title, refaxs):
        if( refaxs == None):
            logging.debug("initializing scatter plot")
            fig = plt.figure()
            #1 inch height for each author graph. So recalculate with height. Else y-scale get mixed.
            figHt = float(self.commitGraphHtPerAuthor*plotcount)
            fig.set_figheight(figHt)
            #since figureheight is in inches, set around maximum of 0.75 inches margin on top.
            topmarginfrac = min(0.15, 0.85/figHt)
            logging.debug("top/bottom margin fraction is %f" % topmarginfrac)
            fig.subplots_adjust(bottom=topmarginfrac, top=1.0-topmarginfrac, left=0.05, right=0.95)
        else:
            fig = refaxs.figure
            
        axs = fig.add_subplot(plotcount, 1, plotidx,sharex=refaxs,sharey=refaxs)
        axs.grid(True)
        axs.plot_date(dates, values, marker='.', xdate=True, ydate=False)
        axs.autoscale_view()
        
        #Pass None as 'handles' since I want to display just the titles
        axs.set_title(title, fontsize='small',fontstyle='italic')
        
        self._setXAxisDateFormatter(axs)        
        plt.setp( axs.get_xmajorticklabels(), visible=False)
        plt.setp( axs.get_xminorticklabels(), visible=False)
                    
        return(axs)
    
    def _closeScatterPlot(self, refaxs, filename,title):
        #Do not autoscale. It will reset the limits on the x and y axis
        #refaxs.autoscale_view()

        fig = refaxs.figure
        #Update the font size for all subplots y-axis
        for axs in fig.get_axes():
            plt.setp( axs.get_yticklabels(), fontsize='x-small')
                
        fig.suptitle(title)        
        fig.savefig(filename, dpi=self.dpi, format=self.format)
        
    def _drawPieGraph(self, slicesizes, slicelabels):
        fig = plt.figure()
        axs = fig.add_subplot(111, aspect='equal')        
        (patches, labeltext, autotexts) = axs.pie(slicesizes, labels=slicelabels, autopct='%1.1f%%')
        #Turn off the labels displayed on the Piechart. 
        plt.setp(labeltext, visible=False)
        plt.setp(autotexts, visible=False)
        axs.autoscale_view()
        #Reposition the pie chart so that we can place a legend on the right
        bbox = axs.get_position()        
        (x,y, wid, ht) = bbox.bounds
        wid = wid*0.8
        bbox.bounds = (0, y, wid, ht)
        axs.set_position(bbox)
        #Now create a legend and place it on the right of the box.        
        legendtext=[]
        for slabel, ssize in zip(slicelabels, autotexts):
           legendtext.append("%s : %s" % (slabel, ssize.get_text()))

        fontprop = self._getLegendFont()
        legend = axs.legend(patches, legendtext, loc=(1, y), prop=fontprop)
        
        return(axs)

    def _setXAxisDateFormatter(self, ax):
##        years    = YearLocator()   # every year
##        months   = MonthLocator(interval=3)  # every 3 month
##        yearsFmt = DateFormatter('%Y')
##        monthsFmt = DateFormatter('%b')
        # format the ticks
##        ax.xaxis.set_major_locator(years)
##        ax.xaxis.set_major_formatter(yearsFmt)
##        ax.xaxis.set_minor_locator(months)
##        ax.xaxis.set_minor_formatter(monthsFmt)
        plt.setp( ax.get_xmajorticklabels(), fontsize='small')
        plt.setp( ax.get_xminorticklabels(), fontsize='x-small')
        
    def _closeDateLineGraph(self, ax, filename):
        assert(ax != None)
        ax.autoscale_view()
        self._setXAxisDateFormatter(ax)
        ax.grid(True)
        ax.set_xlabel('Date')
        fig = ax.figure
        fig.autofmt_xdate()
        fig.savefig(filename, dpi=self.dpi, format=self.format)        
        
    def _drawDateLineGraph(self, dates, values, axs= None):
        if( axs == None):
            fig = plt.figure()            
            axs = fig.add_subplot(111)
            axs.set_color_cycle(self.clrlist)
            
        axs.plot_date(dates, values, '-', xdate=True, ydate=False)
        
        return(axs)
    
