@echo on
call ..\.venv\Scripts\activate

python utils\zmq_net_profiler.py windows a 10.220.25.100 Desktop/KDD2026/hermes/test 10.220.25.103 300 100
