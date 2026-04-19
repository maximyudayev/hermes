@echo on
call ..\.venv\Scripts\activate

python utils\zmq_net_profiler.py 10.220.25.103 5555 5556 300 100
