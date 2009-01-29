function init() {
var json = jsondata;
var tmopts = {
    //main container id.
    rootId: 'treemap',
    //orientation
    orientation: "v",
	tips: true,
	 
     Color: {
        //Allow coloring
        allow: true,
        //Set min value and max value for
        //the second *dataset* object values.
        //Default's to -100 and 100.
        minValue: 0,
        maxValue: 1.0,
        //Set color range. Default's to reddish and
        //greenish. It takes an array of three
        //integers as R, G and B values.
        minColorValue: [0, 255, 50],
        maxColorValue: [255, 0, 50]
     },
	 onAfterCompute: function() {
      var that = this, parent;
      $$('#treemap .leaf', '#treemap .head').each(function(elem, i) {
        //get the JSON tree node element having the same id
        //as the dom element queried and makeTip.
        if(p = elem.getParent()) {
          var sTree = TreeUtil.getSubtree(tm.tree, p.id);
          if(sTree) that.makeTip(elem, sTree);
        }
      });
    },
	 //Tooltip content is setted by setting the *title* of the element to be *tooltiped*.
	//Read the mootools docs for further understanding.
    makeTip: function(elem, json) {
      var title = json.name;
      var html = this.makeHTMLFromData(json.data);
      elem.store('tip:title', title).store('tip:text', html);
    },
	//Take each dataset object key and value and make an HTML from it.
    makeHTMLFromData: function(data) {
      var html = '';
      for(var i=0; i<data.length; i++) {
        html += data[i].key + ': ' + data[i].value + '<br />';
      }
      return html;
    }
  };
  
  var tm = new TM.Squarified(tmopts);
  tm.loadFromJSON(json);
}