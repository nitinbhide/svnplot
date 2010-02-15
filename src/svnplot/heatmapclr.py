'''
Copyright (C) 2009 Nitin Bhide (nitinbhide@gmail.com)

This module is part of SVNPlot (http://code.google.com/p/svnplot) and is released under
the New BSD License: http://www.opensource.org/licenses/bsd-license.php
--------------------------------------------------------------------------------------
heatmap color calculation implementation. 
'''


#The heat map color data is a copy of matplotlib JET colormap data
HEATMAP_CLRDATA =   {'red':   ((0., 0, 0), (0.35, 0, 0), (0.66, 1.0, 1.0), (0.89,1.0, 1.0),
                         (1.0, 0.5, 0.5)),
               'green': ((0., 0.0, 0.0), (0.125,0.0, 0.0), (0.375,1.0, 1.0), (0.64,1.0, 1.0),
                         (0.91,0.0,0.0), (1.0, 0.0, 0.0)),
               'blue':  ((0., 0.5, 0.5), (0.11, 1.0, 1.0), (0.34, 1.0, 1.0), (0.65,0.0, 0.0),
                         (1.0, 0.0, 0.0))}


def __getHeatColor(clrname, heatindex):
    assert(clrname in HEATMAP_CLRDATA)
    clrdata = HEATMAP_CLRDATA[clrname]
    clr = 1.0
    for idx in range(0, len(clrdata)-2):
        heat1 = clrdata[idx][0]
        heat2 = clrdata[idx+1][0]
        if( heatindex > heat1 and heatindex <= heat2):
            clr1 = clrdata[idx][2]
            clr2 = clrdata[idx+1][1]
            clr = clr1+((clr2-clr1)*((heatindex-heat1)/(heat2-heat1)))
            break
    assert(clr >= 0.0 and clr <= 1.0)
    clr = int(255*clr+0.5)
    return(clr)
    
def getHeatColor(heatindex):
    '''
    heat index has to be between 0 and 1
    '''
    assert(heatindex >= 0.0 and heatindex <= 1.0)
    heatindex = float(heatindex)
    r = __getHeatColor('red', heatindex)
    g = __getHeatColor('green', heatindex)
    b = __getHeatColor('blue', heatindex)
    print "heatindex %f colors = (%d, %d, %d)" % (heatindex, r, g, b)
    return((r,g,b))

def getHeatColorHex(heatindex):
    r,g,b = getHeatColor(heatindex)
    hexclr = "#%02X%02X%02X" % (r,g,b)
    return(hexclr)
