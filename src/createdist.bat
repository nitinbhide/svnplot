@echo off
REM Creating binrary and source distribution of SVNPlot
echo "Creating SVNPlot source distribution in zip format"
setup.py sdist --formats=zip
echo "Creating Windows installer for SVNPlot"
setup.py bdist_wininst

