@echo on
call ..\.venv\Scripts\activate

python utils\gen_plot_latency.py %1
