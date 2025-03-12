from GridCalServer.run import start_server

start_server(
    key_file_name="key.pem",
    cert_file_name="cert.pem",
    domain="localhost",
    port=8000,
    # secure=False,
)
