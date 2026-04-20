@echo on
call ..\.venv\Scripts\activate

python utils\gen_plot_sync_dist.py .\data\ntp_sync
