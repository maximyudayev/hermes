@echo on
call ..\..\.venv\Scripts\activate

python utils\gen_plot_tcn.py %1
