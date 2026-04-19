@echo on
call ..\.venv\Scripts\activate

python utils\zmq_net_echo.py 10.220.25.103 5555 5556
