from GridCalServer.run import start_server

start_server(
    key_file_name="key.pem",
    cert_file_name="cert.pem",
    host="localhost",
    port=8002,
    master_host="localhost",
    master_port=8000,
    username="child2",
    password="123456",
    is_master=False
)
