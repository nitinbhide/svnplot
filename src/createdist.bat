@echo off
REM Creating binrary and source distribution of SVNPlot
del /s /q build\*
del MANIFEST
python setup.py clean
echo "Creating SVNPlot source distribution in zip format"
python setup.py sdist --formats=zip
echo Creating Windows installer for SVNPlot
python setup.py bdist_wininst
echo Creating Python Wheel
python setup.py bdist_wheel
REM python setup.py bdist_egg
