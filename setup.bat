:: Setup and switch to the virtual environment
CALL vars.bat
CALL %CondaPath%\Scripts\activate
CALL conda env create -f environment.yml -p %envpath% --force
CALL conda clean --all -y
PAUSE
