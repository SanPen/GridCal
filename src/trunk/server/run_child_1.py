from GridCalServer.run import start_server

start_server(
    host="localhost",
    port=8001,
    master_host="https://localhost",
    master_port=8000,
    username="child1",
    password="123456",
    is_master=False,
    secure=False,
)
