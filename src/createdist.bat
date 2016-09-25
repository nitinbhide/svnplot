@echo off
REM Creating binrary and source distribution of SVNPlot
set PYTHON_VER=%1
del /s /q build\*
del MANIFEST
REM Setup distributions for Python 2
echo Creating distributions for Python %PYTHON_VER%
py -%PYTHON_VER% setup.py clean
echo "Creating SVNPlot source distribution in zip format"
py -%PYTHON_VER% setup.py sdist --formats=zip
echo Creating Windows installer for SVNPlot
py -%PYTHON_VER% setup.py bdist_wininst --target-version %PYTHON_VER%
echo Creating Python Wheel
py -%PYTHON_VER% setup.py bdist_wheel
REM python setup.py bdist_egg
