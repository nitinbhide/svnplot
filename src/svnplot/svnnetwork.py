'''
svnnetwork.py

Generate the social network graphs using the NetworkX and libsna libraries.

Two types of graphs are generated.
1. Files and Authors both are considered as nodes. Whenever author commits a file, it generates an edge
between the author and the file. Files commited in one version are connected together.
2. Only Files are considered as nodes.Files commited in one version are connected together.

TODO :
1. Do not add connections/edges if only properties are modified.

'''

import logging
import sqlite3
import datetime
import os,string
import operator
from optparse import OptionParser
from math import log,exp

from numpy import array, average, std
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
from matplotlib.font_manager import FontProperties

import networkx as NX

COOLINGRATE = 0.005/24.0 #degree per hour
TEMPINCREMENT = 10.0 # degrees per commit

def dirpath(filename):
    dirname,fname = os.path.split(filename)
    return(dirname)

def getTemperatureAtTime(curTime, lastTime, lastTemp, coolingRate):
    '''
    calculate the new temparature at time 'tm'. given the
    lastTemp - last temperature measurement,
    coolingRate - rate of cool per hour
    '''    
    try:        
        tmdelta = curTime-lastTime
        hrsSinceLastTime = tmdelta.days*24.0+tmdelta.seconds/3600.0
        #since this is cooling rate computation, curTime cannot be smaller than 'lastTime'
        #(i.e. if hrsSinceLastTime is -ve ) then reset hrsSinceLastTime to 0
        if( hrsSinceLastTime < 0.0):
            hrsSinceLastTime = 0.0
        tempFactor = -(coolingRate*hrsSinceLastTime)
        temperature = lastTemp*exp(tempFactor)        
    except Exception, expinst:
        logging.debug("Error %s" % expinst)
        temperature = 0.0
        
    return(temperature)
    
class SVNNetworkNode:
    def __init__(self, name):
        self._name = name
        self.commitCount = 0
    def name(self):
        return(self._name)
    def data(self):
        return(self.name())
        
class SVNNetworkAuthorNode(SVNNetworkNode):
    def __init__(self, name):
        SVNNetworkNode.__init__(self, name)

class SVNNetworkFileNode(SVNNetworkNode):
    def __init__(self, name):
        SVNNetworkNode.__init__(self, name)

    def data(self):
        dname, fname = os.path.split(self._name)
        return(fname)
    
        
class SVNNetworkRevisionNode(SVNNetworkNode):
    def __init__(self, name):
        SVNNetworkNode.__init__(self, str(name))

    
class SVNNetworkBase(NX.Graph):    
    def __init__(self, repodbpath=None, searchPath='/', repoUrl=None):
        NX.Graph.__init__(self)
        self._repodbpath = repodbpath
        self._searchpath = searchPath
        self._authorNodes = dict()
        self._fileNodes = dict()
        self._revNodes =dict()
        self._edgedict = dict()
        self._repoUrl = repoUrl
        self._deletedFiles = set()
        #Minimum weight of edge should at least 2 (i.e. edges with weight 1 and 0 will be filtered out)
        self._minWt = 1.0
        #if there is a slash at the 'end' of repoUrl, remove it.
        if( self._repoUrl !=None and self._repoUrl.endswith('/')==True):
            self._repoUrl = self._repoUrl[0:-1]
        
        self.clrlist = ['b', 'g', 'r', 'c', 'm', 'y', 'k']

    def setMinWeight(self, wt):
        self._minWt = wt
        
    def UpdateGraph(self):
        logging.debug("From SVNNetworkBase.Updategraph")
        self.dbcon = sqlite3.connect(self._repodbpath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        try:
            self._getDeletedFilesList()
            self._addRevisionsSlow()
            print "Initial nodes in graph : %d" % self.number_of_nodes()
            print "Initial edges in graph : %d" % self.number_of_edges()
            self._postProcessGraph()
            
            print "Final nodes in graph : %d" % self.number_of_nodes()
            print "Final edges in graph : %d" % self.number_of_edges()
        except:
            raise            
        finally:
            self.dbcon.close()

    def _getDeletedFilesList(self):
        self._deletedFiles=set()
        cur = self.dbcon.cursor()
        sqlquery="select changedpath from SVNLogDetailVw where changedpath like '%s%%' and changetype=='D' \
                    group by changedpath" % self._searchpath
        cur.execute(sqlquery)

        for changedpath in cur:
            print "found deleted path %s" % changedpath
            self._deletedFiles.add(changedpath)
        cur.close()
            
    def _postProcessGraph(self):
        logging.debug("From SVNNetworkBase._postProcessGraph")
        self._filterGraph()

    def _updateEdgeWtDecay(self, node1, node2, curdate):
        if( node1 != None and node2 != None):
            lastdate = self._edgedict.get((node1, node2))
            wt = self[node1][node2].get('weight', 1)
            assert(curdate >= lastdate)
            newwt = getTemperatureAtTime(curdate, lastdate, wt, COOLINGRATE)
            if newwt < 0:
                import pdb
                pdb.set_trace()
                newwt = getTemperatureAtTime(curdate, lastdate, wt, COOLINGRATE)
            assert(newwt > 0.0)
            self[node1][node2]['weight'] = newwt
            self[node2][node1]['weight'] = newwt
            self._edgedict[(node1, node2)]=curdate
            self._edgedict[(node2, node1)]=curdate             

    def _inverseWeights(self):
        '''
        calculate inverse of weights. Since the weights are typically the 'distance' between nodes.
        We may need to 'inverse' the weights.
        '''
        for node1, node2, wt in self.edges_iter(None, True):
            wt = wt['weight']
            if wt == 1:
                wt = 1.0001
            invwt = 1.0/log(wt)
            assert(invwt >= 0.0)
            self[node1][node2]['weight'] = invwt
            self[node2][node1]['weight'] = invwt
            
    def _addEdgeWtDecay(self, node1, node2, curdate):
        assert(curdate != None)
        if( node1 != None and node2 != None):
            lastdate = self._edgedict.get((node1, node2))
            wt = TEMPINCREMENT
            if( lastdate != None):
                wt = self[node1][node2].get('weight', 1)
                wt = TEMPINCREMENT+getTemperatureAtTime(curdate, lastdate, wt, COOLINGRATE)
            self._edgedict[(node1, node2)]=curdate
            self._edgedict[(node2, node1)]=curdate
            assert(wt >= 0.0)
            self.add_edge(node1, node2, {'weight':wt})
            
            
    def _addEdge(self, node1, node2, wt=1):
        if( node1 != None and node2 != None):
            assert(wt >= 0);
            if( self.has_edge(node1, node2) != False):
                wt += self[node1][node2].get('weight', wt)
            self.add_edge(node1, node2, {'weight':wt})        

    def getRevisionNode(self, revno):
        revnode = self._revNodes.get(revno)
        if( revnode is None):
            revnode = SVNNetworkRevisionNode(revno)
            self._revNodes[revno] = revnode
            
        return(revnode)
    
    def getAuthorNode(self, authorname):        
        authorNode = self._authorNodes.get(authorname)        
        if( authorNode is None):
            authorNode = SVNNetworkAuthorNode(authorname)
            self._authorNodes[authorname] = authorNode
            
        return(authorNode)
    
    def getFileNode(self, filename):
        fileNode = None
        if( filename not in self._deletedFiles):
            fileNode = self._fileNodes.get(filename)
            if( fileNode is None): 
                fileNode = SVNNetworkFileNode(filename)
                self._fileNodes[filename] = fileNode
            
        return(fileNode)

    def _updateCentrality(self, date):
        #logging.debug("From SVNNetworkBase._updateCentrality")
        weigthed = True
        degcentrality = NX.degree_centrality(self)
        closecentrality = NX.closeness_centrality(self, v=None, distance=weigthed)
        
        for authnode in self.getNodes(SVNNetworkAuthorNode):                        
            if( self._degcen.has_key(authnode) == False):
                self._degcen[authnode] = []
            if( self._closeness.has_key(authnode) == False):
                self._closeness[authnode] = []
            self._degcen[authnode].append((date, degcentrality[authnode]))
            self._closeness[authnode].append((date, closecentrality[authnode]))
        
    def _addEdgeAuthorFile(self, prevrev, currev):
        revno, date, authorname, filename = currev
        
        authorNode = self.getAuthorNode(authorname)
        fileNode = self.getFileNode(filename)
        self._addEdge(authorNode, fileNode)
        
    def _addEdgeFileFile(self, prevrev, currev):
        prevrevno = prevrev[0]
        revno, date, authorname, filename2 = currev
        
        if( prevrevno == revno):
            assert(filename2 != None)
            filenode2 = self.getFileNode(filename2)
            for filename1 in self.revfilelist:
                filenode1 = self.getFileNode(filename1)
                self._addEdgeWtDecay(filenode1, filenode2,date)
                
    def _addEdgeRevFile(self, currev):
        revno, date, authorname, filename = currev
        revnode = self.getRevisionNode(revno)
        filenode = self.getFileNode(filename)
        #to ensure that these edges are not filtered by 'weight filters'
        #set its weight to minWt+1
        self.add_edge(revnode, filenode, self._minWt+1)
        
    def _updateGraphMetrics(self, prevrev, currev):
        pass

    def _addRevisions(self):
        logging.debug("From SVNNetworkBase._addRevisions")
        
        self._addAuthorFileEdges()
        self._addFileFileEdges()
        
    def _addAuthorFileEdges(self):
        #First add author and file connections.
        cur = self.dbcon.cursor()
        cur.execute("select SVNLog.author, SVNLogDetailVw.changedpath, count(*) as weight from SVNLog, SVNLogDetailVw \
            where SVNLog.revno = SVNLogDetail.revno and SVNLogDetailVw.changedpath like '%s%%' \
            group by SVNLog.author, SVNLogDetail.changedpath" % self._searchpath)
        for author, filename, weight in cur:
            filenode = self.getFileNode(filename)
            authornode = self.getAuthorNode(author)
            self._addEdge(authornode, filenode,weight)
        
        cur.close()
        
    def _addFileFileEdges(self):
        cur = self.dbcon.cursor()
        #first create a dummy temporary view
        cur.execute("DROP VIEW IF EXISTS detail_view1")
        cur.execute("DROP VIEW IF EXISTS detail_view2")
        cur.execute("CREATE TEMP VIEW detail_view1 AS select SVNLogDetailVw.* from SVNLogDetailVw \
                where SVNLogDetailVw.changedpath like '%s%%' \
                " % self._searchpath)
        cur.execute("CREATE TEMP VIEW detail_view2 AS select SVNLogDetailVw.* from SVNLogDetailVw \
                where SVNLogDetailVw.changedpath like '%s%%'" % self._searchpath)        
        #now using the temporary view directly create edges and weights
        cur.execute('select detail_view1.changedpath,detail_view2.changedpath, count(*) as weight\
                from detail_view1, detail_view2 where detail_view1.revno = detail_view2.revno \
                and detail_view1.changedpath <> detail_view2.changedpath \
                group by detail_view1.changedpath,detail_view2.changedpath')
        for filename1, filename2, weight in cur:
            filenode1 = self.getFileNode(filename1)
            filenode2 = self.getFileNode(filename2)
                            
            #Remember each connection will appear twice (filenameABC, filenameXYZ) and (filenameXYZ, filenameABC)
            self._addEdge(filenode1, filenode2, weight/2.0)

        cur.close()
        
    def _addRevisionsSlow(self):
        logging.debug("From SVNNetworkBase._addRevisionsSlow")
        cur = self.dbcon.cursor()
        cur.execute('select SVNLog.revno, date(SVNLog.commitdate) as "commitdate [date]", \
                    SVNLog.author, SVNLogDetailVw.changedpath from SVNLog, SVNLogDetailVw \
            where SVNLog.revno = SVNLogDetailVw.revno and SVNLogDetailVw.changedpath like "%s%%" \
            order by SVNLog.revno ASC' % self._searchpath)
        
        prevrev = (-1, None, None, None)
        self.revfilelist = []

        revcount = 0        
        for revno, commitdate, author, changedpath  in cur:
            currev = (revno, commitdate, author, changedpath)
            self._addEdgeAuthorFile(prevrev, currev)
            self._addEdgeFileFile(prevrev, currev)
            #self._addEdgeRevFile(currev)
            self._updateGraphMetrics(prevrev, currev)
            
            #if the current and previous revision number is same then add the
            #filename in the revision file list (revfilelist)
            if( revno != prevrev[0]):
                self.revfilelist = []
            self.revfilelist.append(changedpath)
                
            prevrev = currev
            revcount = revcount+1
            if( revcount % 500 == 0):
                print "Connections %d added" % revcount
##            if( revcount >= 500):
##                break
        del self.revfilelist
        
        cur.close()

    def _minWtEdgeFilter(self, node1, node2, wt):
        return( wt < self._minWt)
        
    def filterEdges(self, condition=None):
        '''
        condition : can be a lambda function similar to
                'condition=lambda node1, node2, wt:wt < 2'
        '''
        if( condition == None):
            #default : Remove edges with weight less than _minWt 
            condition = self._minWtEdgeFilter

        print "min weight = %f"%self._minWt            
        logging.debug("From SVNNetworkBase.filterEdges")
        edges = [(node1, node2) for node1,node2,wt in self.edges_iter(None, True) if condition(node1, node2, wt)==True]
        if( len(edges) > 0):
            self.remove_edges_from(edges)
        self.filterEmptyNodes()
        
    def filterEmptyNodes(self):
        logging.debug("From SVNNetworkBase.filterEmptyNodes")
        #remove nodes with no edges
        nodes = [ node for node in self.nodes_iter() if len(self.neighbors(node)) == 0]
        self.remove_nodes_from(nodes)

    def filterOnCores(self, mincorenum):
        kcores = NX.find_cores(self)
        core_items=kcores.items()
        nodes =[node for (node, corenum) in core_items if  corenum < mincorenum]
        self.remove_nodes_from(nodes)
        self.filterEmptyNodes()
        
    def _filterGraph(self):
        logging.debug("From SVNNetworkBase._filterGraph")
        '''Filter the graph based on number of connections and weights'''
        #remove unknown authors
        node = self.getAuthorNode('unknown')
        if( self.has_node(node) == True):
            self.remove_node(node)
        self.filterEmptyNodes()
        
    def getNodes(self, nodeType):
        nodes = [ node for node in self.nodes_iter() if isinstance(node, nodeType) == True]
        return(nodes)
    
    def _getLegendFont(self):
        legendfont = FontProperties(size='x-small')
        return(legendfont)
    
    def _getBetweenCentralityGraph(self):
        '''
        returns a graph made of same nodes and edges as 'self' but weights of edges
        are replaced by 'edge betweenness centrality'
        '''
        centralityGraph = self.__class__()
        edgeBetwness = NX.edge_betweenness(self)
        for edge, betwnness in edgeBetwness.items():
            u = edge[0]
            v = edge[1]
            centralityGraph.add_edge(u,v,betwnness)
            
        return(centralityGraph)

    def _getMSTGraph(self):
        centralityGraph = self._getBetweenCentralityGraph()
        mstEdgeList = NX.minimum_spanning_tree(centralityGraph)
        treemapNodeDict = dict()
        root = treemapdata.TreemapNode("Root")
        treemapNodeDict['Root'] = root
        
        mstGraph = self.__class__()
        for edge in mstEdgeList:
            u = edge[0]
            v = edge[1]
            mstGraph.add_edge(u,v, centralityGraph[u][v])
            uname = u.name()
            tnodeU = treemapNodeDict.get(uname)
            if(tnodeU == None):
                tnodeU = treemapdata.TreemapNode(uname)
                treemapNodeDict[uname] = tnodeU
                root.addChildNode(tnodeU)
            vname = v.name()
            tnodeV = treemapNodeDict.get(vname)
            if( tnodeV == None):
                tnodeV = treemapdata.TreemapNode(vname)
                treemapNodeDict[vname] = tnodeV
            tnodeU.addChildNode(tnodeV)

        weighted_edges=True
        cln_cent = NX.closeness_centrality(self, distance=weighted_edges)
        btwn_cent = NX.betweenness_centrality(self, distance=weighted_edges)
        
        for node in mstGraph.nodes_iter():
            tmnode = treemapNodeDict[node.name()]
            tmnode.setProp('closeness', cln_cent[node])
            tmnode.setProp('betweenness', btwn_cent[node])

        self.treemapNodeDict = treemapNodeDict       
        return(mstGraph)
            
class SVNAuthorNetwork(SVNNetworkBase):
    def __init__(self, repodbpath=None, searchPath='/%', repoUrl=None):
        SVNNetworkBase.__init__(self, repodbpath, searchPath, repoUrl)
        self._closeness = dict()
        self._degcen = dict()
        self.setMinWeight(1.1)
    
    def _postProcessGraph(self):
        logging.debug("From SVNAuthorNetwork._postProcessGraph")
        SVNNetworkBase._postProcessGraph(self)        
        self.filterEdges()
        authorNodes = self.getNodes(SVNNetworkAuthorNode)
##        nodes = [ node for node in authorNodes if NX.degree_centrality(self, node) < 0.1]
##        self.remove_nodes_from(nodes)
        self.filterEmptyNodes()
        self._inverseWeights()
        self._sortMetrics()
        
    def remove_nodes_from(self, nodes):
        SVNNetworkBase.remove_nodes_from(self, nodes)
        #removes nodes from centrality data dictionay as well.
        for node in nodes:
            if( self._closeness.has_key(node)):
                del self._closeness[node]
            if( self._degcen.has_key(node)):
                del self._degcen[node]

    def _sortMetrics(self):
        logging.debug("From SVNAuthorNetwork._sortMetrics")
        #sort the metrics data as per the dates. So that graphs are correct
        for node in self._closeness.keys():
            self._closeness[node].sort(key=operator.itemgetter(0))
        for node in self._degcen.keys():
            self._degcen[node].sort(key=operator.itemgetter(0))                                  

    def _addEdgeRevFile(self, currev):
        #do not add revision number ->filename edges
        pass
    def _addEdgeFileFile(self, prevrev, currev):
        #do not add file-file edges.
        pass
    
    def _addFileFileEdges(self):
        #do not add file-file edges.
        pass
    
    def _updateGraphMetrics(self, prevrev, currev):
        prevcommitdate = prevrev[1]
        commitdate = currev[1]
        if( prevcommitdate != commitdate):
            self._updateCentrality(commitdate)
                        
    def _getLabelsList(self):
        labels = [node.name() for node in self.nodes_iter() if isinstance(node, SVNNetworkAuthorNode) == True]
        return(labels)
    
    def _getLabels(self):
        labels = dict()
        for node in self.nodes_iter():
            if( isinstance(node, SVNNetworkAuthorNode) == True):
                labels[node] = node.name()
        return(labels)

    def _getClrList(self, nsize):
        clrcount = len(self.clrlist)        
        clrlist = self.clrlist*((nsize/clrcount)+1)
        assert(len(clrlist) >= nsize)
        clrlist = clrlist[0:nsize]
        assert(len(clrlist) == nsize)
        return(clrlist)
        
    def _drawAuthorNodes(self, pos):
        logging.debug("From SVNAuthorNetwork._drawAuthorNodes")
        
        authorNodes = self.getNodes(SVNNetworkAuthorNode)
        authCount = len(authorNodes)
        clrlist = self._getClrList(authCount)
        
        handles = []        
        for node,clr in zip(authorNodes, clrlist):
            authors = [node]
            handles.append(NX.draw_networkx_nodes(self, pos, authors, with_labels=False, node_color=clr))
        axs = plt.gca()
        assert(axs != None)
        assert(handles != None and len(handles) > 0)
        labels = self._getLabelsList()
        assert(labels != None and len(handles) == len(labels))
        legendfont = self._getLegendFont()
        axs.legend(handles, labels, prop=legendfont,scatterpoints=1, markerscale=0.1)

    def printAuthorCentrality(self, centralityType, centralityfunc):
        logging.debug("From SVNAuthorNetwork.printAuthorCentrality")
        print "----------- Author Centrality Data ------------------"
        centrality = centralityfunc(self)
        for node in self.getNodes(SVNNetworkAuthorNode):            
            print "%s Centrality (%s) : %f" % (centralityType, node.name(), centrality[node])

    def SaveCentralityGraphs(self):
        logging.debug("From SVNAuthorNetwork.SaveCentralityGraphs")
        self.SaveCentralityGraph("closeness.png", self._closeness)
        self.SaveCentralityGraph("degreecen.png", self._degcen)                                

    def SaveGraph(self, filename):
        logging.debug("From SVNAuthorNetwork.SaveGraph")
        print "saving auhtor network graph to %s" % filename
        plt.clf()
        #
        dt1 = datetime.datetime.now()
        pos = NX.pydot_layout(self) 
        #pos = NX.spring_layout(self, dim=2, iterations=10)
        dt2 = datetime.datetime.now()
        print "time of layout=%s" % (dt2-dt1)
        plt.figure(figsize=(8.0, 8.0))        
        nodeimgs = NX.draw_networkx_nodes(self, pos, with_labels=False,node_size=10)
        #set the urls for filenodes
        if (self._repoUrl != None):
            nodeUrls = []
            for node in self.nodes_iter():
                fileUrl = None
                if( isinstance(node, SVNNetworkFileNode) == True):
                    #File node add the URL
                    fileUrl = ''.join([self._repoUrl,node.name()])                    
                nodeUrls.append(fileUrl)
            nodeimgs.set_urls(nodeUrls)
        #Now draw edges                
        NX.draw_networkx_edges(self, pos, with_labels=False)
        #draw author nodes with different color        
        self._drawAuthorNodes(pos)
        plt.savefig(filename+'.svg', dpi=100, format="svg")
        plt.savefig(filename+'.png', dpi=100, format="png")
        print "Saved ..."

        
    def SaveCentralityGraph(self, filename, centrality):
        logging.debug("From SVNAuthorNetwork.SaveCentralityGraph")
        print "Saving centrality graph %s" %filename
        plt.clf()
        fig = plt.figure()            
        axs = fig.add_subplot(111)
        axs.set_color_cycle(self.clrlist)

        authNodes = self.getNodes(SVNNetworkAuthorNode)
        for node in authNodes:
            dates = [date for date, val in centrality[node]]
            values = [val for date, val in centrality[node]]
            axs.plot_date(dates, values, '-', xdate=True, ydate=False)

        # format the ticks
        axs.autoscale_view()
        
        axs.grid(True)
        axs.set_xlabel('Date')
        authors = [node.name() for node in authNodes]
        legendfont = self._getLegendFont()
        axs.legend(authors, loc="upper right", prop=legendfont)
        fig.autofmt_xdate()
        plt.savefig(filename, dpi=100, format='png')
        print "Saved ..."

class SVNFileNetwork(SVNNetworkBase):    
    def __init__(self, repodbpath=None, searchPath='/%', repoUrl=None):
        SVNNetworkBase.__init__(self, repodbpath, searchPath,repoUrl)

    def _postProcessGraph(self):
        logging.debug("From SVNFileNetwork._postProcessGraph")
        SVNNetworkBase._postProcessGraph(self)
        self.updateFileMetrics()
        self._updateEdgeWeights()
        self.filterEdges()
        self.filterOnCores(5)
        #self._inverseWeights()
    
    def _updateEdgeWeights(self):
        curdate = datetime.date.today()        
        for node1,node2 in self.edges_iter(None, False):
            self._updateEdgeWtDecay(node1,node2, curdate)
        
    def _addEdgeAuthorFile(self, prevrev, currev):
        pass
    
    def _addAuthorFileEdges(self):
        #do not add author-file edges.
        pass

    def getEdgeBetweennessList(self):
        edgelist = []
        edgeBetwness = NX.edge_betweenness(self)
        #sort the edges based on betweeness centrality in reverse order (highest first)
        edgelist = [(edge[0], edge[1], betwcen) for edge, betwcen in edgeBetwness.items()]        
        return(edgelist)

    def _filterEdgesBetwnness(self):
        logging.debug("filtering edges based on edge betweenness")
        print "filtering edges based on edge betweenness"
        print "current edgecount %d" % self.number_of_edges()
        #Fiter edges based on edge_betweenness centrality
        graphs = NX.connected_component_subgraphs(self)

        edgesToRemove = []
        for subgraph in graphs:
            if( subgraph.number_of_edges() > 3):
                edgelist = subgraph.getEdgeBetweennessList()
                betwnarr = array([betwn for node1, node2, betwn in edgelist])
                avgbetwn = average(betwnarr)
                stddevbetwn = std(betwnarr)                
                maxBetwn = avgbetwn+stddevbetwn
                print "maxbetweenness centrality %f" % maxBetwn
                edgesToRemove = edgesToRemove+ [ (node1, node2) for node1, node2, betwcen in edgelist if betwcen> maxBetwn]
        
        if( len(edgesToRemove) > 0):
            self.remove_edges_from(edgesToRemove)            
        
    def filterEdges(self):
        SVNNetworkBase.filterEdges(self)
        #self._filterEdgesBetwnness()
        
    def updateFileMetrics(self):
        '''
        update the commit count metrics of files
        '''
        logging.debug("From SVNFileNetwork.updateFileMetrics")
        
        cur = self.dbcon.cursor()
        cur.execute("select count(*),changedpath from SVNLogDetailVw where changedpath like '%s%%'\
            group by changedpath" % self._searchpath)
        for count, changedpath in cur:
            if( self._fileNodes.has_key(changedpath) ==True):
                self._fileNodes[changedpath].commitCount = count
            
        cur.close()
        
    def KeepLargestConnected(self):
        logging.debug("From SVNFileNetwork.KeepLargestConnected")
        print "keeping only larget connected subgraph"
        graphs = NX.connected_component_subgraphs(self)
        largestconnected = graphs[0]
        #remove the nodes not the largest connected graph. Essentially making
        # 'self' same as larget connected graph
        nodesForRemoval = [node for node in self.nodes_iter() if largestconnected.has_node(node) == False]
        self.remove_nodes_from(nodesForRemoval)
        print "Nodes removed : %d" % len(nodesForRemoval)
        print "finished larget connected subgraph"

    def SaveJsonTreemapData(self, filename, minNodeCount=10):
        '''Save the data as treemap. First level is made of 'connected subgraphs'. Second level
        nodes are made of filepath. The size and color is based on 'centrality' values.        
        '''
        logging.debug("From SVNFileNetwork.SaveJsonTreemapData")
        
        print "writing json treemap data to %s" % filename
        graphs = NX.connected_component_subgraphs(self)

        root = treemapdata.TreemapNode("Root")

        weigthed=True
        for idx in range(0, len(graphs)):
            subgraph  = graphs[idx]
            if( subgraph.number_of_nodes() > minNodeCount):
                print "subgraph %d Node count = %d" % (idx+1, subgraph.number_of_nodes())
                for node in subgraph.nodes_iter():
                    nodepath = node.name()
                    #replace the search path at the start of the filepath ONLY. Do not replace
                    #subsequent occurances.
                    nodepath = nodepath.replace(self._searchpath, '', 1)
                    nodeparentlist = nodepath.split('/')
                    nodeparentlist = ["subgraph %d" %(idx+1)]+nodeparentlist
                    tmnode = root.addChild(nodeparentlist)                
                    tmnode.setProp('commitcount', node.commitCount)
                    tmnode.setProp('centrality', NX.closeness_centrality(subgraph, node, weigthed))
                    
        outfile = open(filename, "w")
        root.writejson(outfile, 'commitcount', 'centrality')
        outfile.close()
        print "finished jsondata output"
        
    def SaveConnected(self, filename, minNodeCount=10, savefunc=lambda g,fname: g.SaveGraph(fname)):
        logging.debug("From SVNFileNetwork.SaveConnected")
        print "saving connected subgraphs"
        fname, ext = os.path.splitext(filename)
        graphs = NX.connected_component_subgraphs(self)
        
        for idx in range(0, len(graphs)):
            subgraph  = graphs[idx]
            if( subgraph.number_of_nodes() >= minNodeCount):
                savefunc(subgraph, "%s%d%s"%(fname,idx+1,ext))                                
        print "Saved ..."

    def PrintGraphStat(self):
        logging.debug("From SVNFileNetwork.PrintGraphStat")
        print "%s" % '-'*40
        print "Graph Radius : %f" % NX.radius(self)
        print "Graph Diameter : %f" % NX.diameter(self)
        for n1, n2, prop in self.edges_iter(data=True):
            print 'wt %d' % prop['weight']
            
        weighted = True
        closenessdict = NX.closeness_centrality(self, distance=weighted)
        print "%s" % '-'*40
        print "All nodes in graph"
        
        nodeinfolist = [(node, closeness) for node,closeness in closenessdict.items()]        
        #sort the node infolist by closeness number
        nodeinfolist = sorted(nodeinfolist, key=operator.itemgetter(1), reverse=True)
        for node, closeness in nodeinfolist:
            print "\t%s : %f" %(node.name(), closeness)
        print "%s" % '-'*40

    def SaveGraph(self, filename):
        logging.debug("From SVNFileNetwork.SaveGraph")
        
        print "saving the file network graph to %s" % filename
        plt.clf()
        #pos = NX.spring_layout(self, dim=2, iterations=20)
        logging.info("starting layout using pydot_layout")
        pos = NX.pydot_layout(self, prog='neato')
        print "finished layout"
        logging.info("finished layout using pydot_layout")
        plt.figure(figsize=(8.0, 8.0))
        NX.draw_networkx_nodes(self, pos, node_size=10)
        NX.draw_networkx_edges(self, pos)
        #display revision nodes in different colors
        revnodes = self.getNodes(SVNNetworkRevisionNode)
        NX.draw_networkx_nodes(self, pos, revnodes, node_color='g', node_size=30)
        #display center nodes with larger size
        NX.draw_networkx_nodes(self, pos, NX.center(self), node_color='b', node_size=50)

        ax = plt.gca()
        plt.setp(ax.get_yticklabels(), visible=False)
        plt.setp(ax.get_xticklabels(), visible=False)
                
        plt.savefig(filename, dpi=100, format="png")
        self.PrintGraphStat()
        print "Saved ..."
        
    def SaveMST(self, filename):
        logging.debug("From SVNFileNetwork.SaveMST")

        mstGraph = self._getMSTGraph()        
        
        print "saving MST of the file network graph to %s" % filename
        plt.clf()
        #pos = NX.spring_layout(self, dim=2, iterations=20)
        logging.info("starting layout using pydot_layout")
        pos = NX.pydot_layout(mstGraph, prog='neato')
        print "finished layout"
        logging.info("finished layout using pydot_layout")
        plt.figure(figsize=(8.0, 8.0))
        
        NX.draw_networkx_nodes(mstGraph, pos, node_size=10)
        NX.draw_networkx_edges(mstGraph, pos)
        #display center nodes with larger size
        NX.draw_networkx_nodes(mstGraph, pos, NX.center(mstGraph), node_color='b', node_size=50)
        #create node labels
        label=dict()
        for node in mstGraph.nodes_iter():
            dirname, fname = os.path.split(node.name())
            label[node]=fname
        NX.draw_networkx_labels(mstGraph,pos, label, font_size=8)

        #disable X and Y tick labels
        ax = plt.gca()
        plt.setp(ax.get_yticklabels(), visible=False)
        plt.setp(ax.get_xticklabels(), visible=False)
        
        plt.savefig(filename, dpi=100, format="png")
        print "Saved MST..."
        print "saving MST treemap"
        jsfilename,ext = os.path.splitext(filename)
        jsfilename = jsfilename+'.js'
        print "treemap filename %s" %jsfilename
        outfile = open(jsfilename, "w")
        self.treemapNodeDict['Root'].writejson(outfile, 'closeness', 'betweenness')
        outfile.close()        
        
                 
def GenerateAuthorNet(repodbpath, searchpath, repoUrl):
    print "Updating SVN Author Net"
    svnauthnet = SVNAuthorNetwork(repodbpath, searchpath, repoUrl=repoUrl)
    svnauthnet.UpdateGraph()
    svnauthnet.printAuthorCentrality("Degree", NX.degree_centrality)
    svnauthnet.printAuthorCentrality("Closeness", NX.closeness_centrality)
    svnauthnet.SaveCentralityGraphs()
    svnauthnet.SaveGraph("svnnet")
    print "Finished generating SVN Author Net"

def GenerateFileNet(repodbpath, searchpath ):
    print "Updating SVN Filenet"
    svnfilenet = SVNFileNetwork(repodbpath, searchpath )
    svnfilenet.UpdateGraph()        
    svnfilenet.SaveConnected("svnfilenet.png")
    #svnfilenet.SaveConnected("svnfilenetmst.png", savefunc=lambda g,fname:g.SaveMST(fname))
    svnfilenet.PrintGraphStat()
    print "Finished generating SVN file Net"
##    svnfilenet.SaveGraph("svnfilenet(large).png")
                                       
def RunMain():
    usage = "usage: %prog [options] <sqlitedbpath> <searchpath> <repourl>"
    
    logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s',
                    filename="svnnetwork.log",
                    filemode='w')
    
    try:
        parser = OptionParser(usage)
        parser.add_option("-a", "--author", action="store_true", dest="author_net", default=False,
                          help="Generate svn author net stats and graphs")
        parser.add_option("-f", "--file", action="store_true", dest="file_net", default=False,
                          help="Generate svn file net stats and graphs")
        parser.add_option("", "--all", action="store_true", dest="all_net", default=False,
                          help="Generate svn file and author net stats and graphs")
        
        (options, args) = parser.parse_args()
        
        if( len(args) < 3 ):
            print "Invalid number of arguments. Use svnnetwork.py --help to see the details."
            print "svnnetwork.py has large number of dependencies. You have to install following packages"
            print "\tmatplotlib"
            print "\tnetworkx"
            print "\tpydot"
            print "These can be installed using easy_install"
            print "However GraphViz (http://graphviz.org) toolkit has to be downloaded and installed seperately"
            
        if not options.author_net and not options.file_net:
            options.all_net=True
            
        print "NOTE : network graph analysis functions take time. Have patience !!!"
        if options.all_net:            
            #GenerateAuthorNet(args[0], args[1], args[2])
            GenerateFileNet(args[0], args[1])
            exit(0)
        
        if options.author_net:
            GenerateAuthorNet(args[0], args[1], args[2])
        
        if options.file_net:
            GenerateFileNet(args[0], args[1])
    except:
        logging.exception("Error in svn network graph computations")
        
if __name__ == "__main__":        
    RunMain()
    

    